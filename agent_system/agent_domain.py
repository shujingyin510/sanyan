"""领域知识层 — LLM 动态生成，不硬编码

流程：
  1. 规则快速分类（毫秒级，不调 LLM）
  2. 缓存命中？直接返回
  3. 缓存未命中？问 LLM 生成领域知识
  4. 缓存结果，下次直接用

位置：DecompositionEngine → DomainKnowledgeLayer → HypothesisGenerator
"""

import json
import os
import re
import sqlite3
import time
from typing import Callable, Dict, List, Optional, Tuple

from agent_system import paths, store


# ── 最小化分类规则（只做分类，不定义知识）──

DOMAIN_PATTERNS = {
    'web_app': ['前端', '后端', 'API', '页面', '接口', 'web', '网站', '应用', 'app', '服务', '网页'],
    'cli_tool': ['命令行', 'CLI', '工具', '脚本', '命令', '终端', 'argparse', 'click'],
    'library': ['库', '模块', 'package', 'library', 'SDK', '工具包', 'pip'],
    'bug_fix': ['修复', 'fix', 'bug', '错误', '报错', '崩溃', '异常', '问题', '不工作'],
    'refactor': ['重构', 'refactor', '整理', '优化结构', '重写', 'clean'],
    'test': ['测试', 'test', '验证', '检查', '断言', 'pytest', 'unittest'],
    'feature': ['新增', '添加', '实现', '功能', 'feature', '支持', '开发'],
    'docs': ['文档', 'docs', 'README', '说明', '注释', 'CHANGELOG', '手册'],
    'data': ['数据', 'data', '数据库', 'SQL', 'CSV', '分析', '可视化', '图表'],
    'devops': ['部署', 'deploy', 'CI', 'CD', 'Docker', '容器', '自动化', 'pipeline'],
    'ai_ml': ['模型', '训练', '推理', '机器学习', '深度学习', 'LLM', 'GPT', '神经网络'],
    'research': ['研究', '实验', '论文', '报告', '分析', '验证', 'benchmark', '评测'],
}

# 通用终止条件模板（所有领域共享）
DEFAULT_ANTI_LOOP = '连续3轮无代码变化则停止，达到15轮自动终止'
DEFAULT_COMPLETION = '任务目标达成 + 验证通过'


class DomainKnowledgeLayer:
    """领域知识层：LLM 动态生成，不硬编码

    核心流程：
      1. 规则分类 → 领域名
      2. 查缓存 → 命中直接返回
      3. 未命中 → 调 LLM 生成 → 缓存 → 返回

    LLM 生成的内容包括：
      - 组件列表（这个任务需要哪些部分）
      - 验证命令（怎么检查完成质量）
      - 完成标准（什么算做完了）
      - 终止条件（什么时候该停）
    """

    def __init__(self, llm_fn: Optional[Callable] = None, db_path: Optional[str] = None):
        self.llm_fn = llm_fn
        # 阶段 2：默认并入单一 agent.db（旧 domain_knowledge.db 缓存首次自动搬入、旧库保留可回滚）
        self.db_path = db_path or paths.db_path(store.AGENT_DB)
        self._init_db()
        self._confidence_cache: Dict[str, float] = {}  # 会话级置信度缓存

    def _init_db(self):
        """初始化缓存数据库（若并入 agent.db，则从旧独立库非破坏迁移历史缓存）"""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS domain_cache (
                domain TEXT PRIMARY KEY,
                knowledge TEXT,
                created_at REAL,
                hit_count INTEGER DEFAULT 0
            )
        """)
        conn.commit()
        if os.path.basename(self.db_path) == store.AGENT_DB:
            store.adopt_legacy(conn, 'domain_knowledge.db', ('domain_cache',))
            store.set_version(conn, 'domain', 1)
        conn.close()

    # ── 分类（规则，毫秒级）──

    def classify(self, task: str) -> Tuple[str, float]:
        """规则分类，返回 (domain, confidence)"""
        task_lower = task.lower()
        scores = {}

        for domain, patterns in DOMAIN_PATTERNS.items():
            hit = sum(1 for p in patterns if p.lower() in task_lower)
            if hit > 0:
                scores[domain] = hit / len(patterns)

        if not scores:
            return 'general', 0.2

        # 优先规则：如果任务涉及创建新文件，优先归为 feature
        create_keywords = ['新增', '创建', '写一个', '新建', '实现', '添加']
        has_create = any(kw in task for kw in create_keywords)
        if has_create and 'feature' in scores:
            scores['feature'] += 0.3  # 提升 feature 权重

        best = max(scores, key=scores.get)
        return best, min(0.95, scores[best] + 0.3)

    def update_confidence(self, domain: str, new_conf: float):
        """会话级动态更新置信度（同一领域后续任务生效）"""
        self._confidence_cache[domain] = max(0.05, min(0.95, new_conf))

    # ── 缓存（SQLite）──

    def _cache_get(self, domain: str) -> Optional[Dict]:
        """从缓存读取"""
        conn = sqlite3.connect(self.db_path)
        row = conn.execute('SELECT knowledge, hit_count FROM domain_cache WHERE domain=?', (domain,)).fetchone()
        if row:
            conn.execute('UPDATE domain_cache SET hit_count=hit_count+1 WHERE domain=?', (domain,))
            conn.commit()
            conn.close()
            return json.loads(row[0])
        conn.close()
        return None

    def _cache_set(self, domain: str, knowledge: Dict):
        """写入缓存"""
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """INSERT OR REPLACE INTO domain_cache (domain, knowledge, created_at, hit_count)
               VALUES (?, ?, ?, 0)""",
            (domain, json.dumps(knowledge, ensure_ascii=False), time.time()),
        )
        conn.commit()
        conn.close()

    # ── LLM 生成 ──

    def _ask_llm(self, task: str, domain: str) -> Dict:
        """问 LLM 生成领域知识"""
        if not self.llm_fn:
            return self._fallback(domain)

        prompt = f"""分析以下任务，生成执行计划。

任务: {task[:300]}

请用 JSON 格式回答：
{{
  "domain_name": "领域中文名（如：编程开发、数据分析、文档编写等）",
  "components": ["步骤1", "步骤2", ...],
  "validation": "验证命令",
  "completion": "完成标准",
  "anti_loop": "终止条件"
}}

要求：
1. components 必须是具体可执行的步骤，不要泛泛的"分析需求"
   - 如果是写代码：["创建文件xxx", "实现函数yyy", "编写测试", "运行测试"]
   - 如果是修bug：["定位错误", "修复代码", "运行测试验证"]
   - 如果是写文档：["编写内容", "检查格式"]
2. validation 必须是实际可执行的命令：
   - Python项目: "python -X utf8 -m pytest tests/ -x -q"
   - 通用: "echo done"
3. 只输出 JSON，不要其他文字"""

        try:
            raw = self.llm_fn(prompt)
            match = re.search(r'\{.*\}', raw, re.DOTALL)
            if match:
                result = json.loads(match.group())
                return {
                    'domain_name': result.get('domain_name', domain),
                    'components': result.get('components', ['执行任务']),
                    'validation': result.get('validation', 'echo done'),
                    'completion': result.get('completion', DEFAULT_COMPLETION),
                    'anti_loop': result.get('anti_loop', DEFAULT_ANTI_LOOP),
                }
        except Exception:
            pass

        return self._fallback(domain)

    def _fallback(self, domain: str) -> Dict:
        """LLM 失败时的兜底（按领域给更具体的默认值）"""
        fallbacks = {
            'bug_fix': {
                'domain_name': 'Bug修复',
                'components': ['定位错误文件和行号', '分析错误原因', '修复代码', '运行测试验证'],
                'validation': 'python -X utf8 -m pytest tests/ -x -q',
            },
            'feature': {
                'domain_name': '功能开发',
                'components': ['创建或修改文件', '实现核心逻辑', '编写测试', '运行测试'],
                'validation': 'python -X utf8 -m pytest tests/ -x -q',
            },
            'test': {
                'domain_name': '测试编写',
                'components': ['分析被测代码', '编写测试用例', '运行测试'],
                'validation': 'python -X utf8 -m pytest tests/ -x -q',
            },
            'refactor': {
                'domain_name': '代码重构',
                'components': ['分析现有代码', '执行重构', '运行测试确认功能不变'],
                'validation': 'python -X utf8 -m pytest tests/ -x -q',
            },
            'docs': {
                'domain_name': '文档编写',
                'components': ['编写文档内容', '检查格式'],
                'validation': 'echo done',
            },
        }
        fb = fallbacks.get(
            domain,
            {
                'domain_name': domain,
                'components': ['分析任务', '执行任务', '验证结果'],
                'validation': 'echo done',
            },
        )
        return {
            **fb,
            'completion': DEFAULT_COMPLETION,
            'anti_loop': DEFAULT_ANTI_LOOP,
        }

    # ── 主接口 ──

    def analyze(self, task: str) -> Dict:
        """分析任务，返回领域知识（优先缓存，其次 LLM）"""
        # 1. 分类
        domain, confidence = self.classify(task)
        # 会话级动态置信度覆盖
        if domain in self._confidence_cache:
            confidence = self._confidence_cache[domain]

        # 2. 查缓存
        cached = self._cache_get(domain)
        if cached:
            plan = self._generate_plan(cached.get('components', []))
            return {**cached, 'domain': domain, 'confidence': confidence, 'plan': plan, 'source': 'cache'}

        # 3. 问 LLM
        knowledge = self._ask_llm(task, domain)

        # 4. 缓存
        self._cache_set(domain, knowledge)

        # 5. 生成执行计划
        plan = self._generate_plan(knowledge['components'])

        return {
            **knowledge,
            'domain': domain,
            'confidence': confidence,
            'plan': plan,
            'source': 'llm',
        }

    def _generate_plan(self, components: List[str]) -> List[Dict]:
        """从组件列表生成执行计划（优化：合并简单步骤）"""
        plan = []
        validation_keywords = ['测试', '验证', '检查', 'test', 'verify', 'check', '集成']

        # 合并连续的非验证步骤
        merged_actions = []
        for comp in components:
            is_validation = any(kw in comp.lower() for kw in validation_keywords)
            if is_validation:
                merged_actions.append(comp)
            else:
                # 合并非验证步骤
                if merged_actions and not any(kw in merged_actions[-1].lower() for kw in validation_keywords):
                    merged_actions[-1] += f'、{comp}'
                else:
                    merged_actions.append(comp)

        for i, action in enumerate(merged_actions, 1):
            is_validation = any(kw in action.lower() for kw in validation_keywords)
            plan.append({'step': i, 'action': action, 'validate': is_validation})

        # 确保最后一步是验证
        if not plan or not plan[-1]['validate']:
            plan.append({'step': len(plan) + 1, 'action': '最终验证', 'validate': True})

        return plan

    def format_for_prompt(self, task: str) -> str:
        """格式化领域知识，注入 LLM 上下文"""
        info = self.analyze(task)
        source = '缓存' if info.get('source') == 'cache' else 'LLM'

        lines = [
            f'[领域知识] {info["domain_name"]} (置信度: {info["confidence"]:.0%}, 来源: {source})',
            f'  组件: {" → ".join(info["components"])}',
            f'  完成: {info["completion"]}',
            f'  终止: {info["anti_loop"]}',
            f'  验证: {info["validation"]}',
            '  计划:',
        ]
        for step in info.get('plan', []):
            marker = '★' if step['validate'] else '○'
            lines.append(f'    {marker} {step["step"]}. {step["action"]}')

        return '\n'.join(lines)

    def get_validation_command(self, task: str) -> str:
        """获取验证命令"""
        info = self.analyze(task)
        return info.get('validation', 'echo done')

    def should_stop(self, task: str, history: List[Dict], same_file_count: int) -> Tuple[bool, str]:
        """判断是否应该停止"""
        info = self.analyze(task)

        if same_file_count >= 3:
            return True, f'连续 {same_file_count} 轮无变化，{info["anti_loop"]}'

        if len(history) >= 15:
            return True, '达到最大轮次（15轮）'

        # 检查验证是否通过
        for h in reversed(history[-3:]):
            if h.get('tool') == 'run_test' and h.get('success'):
                return True, '验证通过，任务完成'

        return False, ''

    def list_cached_domains(self) -> List[Dict]:
        """列出已缓存的领域"""
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute('SELECT domain, knowledge, hit_count FROM domain_cache').fetchall()
        conn.close()
        result = []
        for domain, knowledge_json, hit_count in rows:
            knowledge = json.loads(knowledge_json)
            result.append(
                {
                    'domain': domain,
                    'name': knowledge.get('domain_name', domain),
                    'components': knowledge.get('components', []),
                    'hit_count': hit_count,
                }
            )
        return result
