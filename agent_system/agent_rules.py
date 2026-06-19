"""Agent Rules Engine — 按规则执行，不调 LLM 选工具

流程：
  1. 读取 agent_rules.md
  2. 匹配任务到规则
  3. 按规则工具链执行（不调 LLM）
  4. 无匹配规则时，LLM 生成新规则 → 用户审批 → 执行

优势：
  - 减少 LLM 调用（从每步调 LLM 变成 0 次）
  - 工具链正确（规则是人工/LLM 审核过的）
  - 可追溯（规则文件可查看）
"""

import os
import re
from typing import Callable, Dict, List, Optional


RULES_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'agent_rules.md')


class AgentRule:
    """单条规则"""

    def __init__(self, name: str, pattern: str, steps: List[Dict], validation: str):
        self.name = name
        self.pattern = pattern
        self.steps = steps  # [{'tool': 'write_file', 'desc': '创建文件'}, ...]
        self.validation = validation

    def match(self, task: str) -> bool:
        """检查任务是否匹配此规则"""
        try:
            return bool(re.search(self.pattern, task, re.IGNORECASE))
        except re.error:
            return self.pattern.lower() in task.lower()

    def to_markdown(self) -> str:
        """转为 markdown 格式"""
        steps = '\n'.join(f'{i + 1}. {s["tool"]}({s["args_desc"]}) — {s["desc"]}' for i, s in enumerate(self.steps))
        return f"""## 规则：{self.name}
匹配：{self.pattern}
工具链：
{steps}
验证：{self.validation}"""


class RuleEngine:
    """规则引擎：读取规则 → 匹配 → 执行"""

    def __init__(self, rules_file: Optional[str] = None, llm_fn: Optional[Callable] = None):
        self.rules_file = rules_file or RULES_FILE
        self.rules: List[AgentRule] = []
        self.llm_fn = llm_fn
        self._pending_rule: Optional[AgentRule] = None
        self._load_rules()

    def _load_rules(self):
        """从 agent_rules.md 加载规则"""
        if not os.path.exists(self.rules_file):
            return

        with open(self.rules_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # 解析规则块
        blocks = re.split(r'^## 规则：', content, flags=re.MULTILINE)
        for block in blocks[1:]:  # 跳过第一个（标题）
            rule = self._parse_rule_block(block)
            if rule:
                self.rules.append(rule)

    def _parse_rule_block(self, block: str) -> Optional[AgentRule]:
        """解析单个规则块"""
        lines = block.strip().split('\n')
        if not lines:
            return None

        name = lines[0].strip()
        pattern = ''
        steps = []
        validation = ''

        for line in lines[1:]:
            line = line.strip()
            if line.startswith('匹配：') or line.startswith('匹配:'):
                pattern = line.split('：', 1)[-1].split(':', 1)[-1].strip()
            elif line.startswith('验证：') or line.startswith('验证:'):
                validation = line.split('：', 1)[-1].split(':', 1)[-1].strip()
            elif re.match(r'^\d+\.', line):
                # 工具步骤：1. write_file({filename}|{code}) — 创建文件
                match = re.match(r'^\d+\.\s+(\w+)\((.*?)\)\s*[—\-]\s*(.*)', line)
                if match:
                    tool = match.group(1)
                    args_desc = match.group(2)
                    desc = match.group(3)
                    steps.append({'tool': tool, 'args_desc': args_desc, 'desc': desc})

        if name and pattern and steps:
            return AgentRule(name, pattern, steps, validation)
        return None

    def match_rule(self, task: str) -> Optional[AgentRule]:
        """匹配任务到规则（语义匹配）"""
        # 1. 先用关键词快速筛选候选规则
        candidates, primary_intent = self._find_candidates(task)

        # 2. 如果只有一条候选，直接返回
        if len(candidates) == 1:
            return candidates[0]

        # 3. 如果有多条候选，用 LLM 选最匹配的
        if len(candidates) > 1 and self.llm_fn:
            return self._llm_select_rule(task, candidates)

        # 4. 如果有多条候选但没有 LLM，返回第一条
        if len(candidates) > 1:
            return candidates[0]

        # 5. 如果没有候选但有代码意图，用 LLM 生成规则（仅限简单任务）
        if not candidates and primary_intent and self.llm_fn:
            # 只在有明显代码意图且任务较短时生成规则
            if len(task) < 80:
                rule = self.generate_rule(task)
                if rule:
                    return rule

        # 6. 完全没有匹配，返回 None
        return None

    def _find_candidates(self, task: str) -> List[AgentRule]:
        """用关键词快速筛选候选规则（考虑主要意图）"""
        candidates = []
        task_lower = task.lower()

        # 提取主要意图关键词（优先级：创建 > 修复 > 重构 > 测试）
        intent_keywords = {
            '创建': ['创建', '新增', '写一个', '实现', '添加模块'],
            '修复': ['修复', 'fix', 'bug', '错误', '报错'],
            '重构': ['重构', 'refactor', '优化', '整理'],
            '测试': ['测试', 'test', '验证'],
        }

        # 确定主要意图
        primary_intent = None
        for intent, keywords in intent_keywords.items():
            if any(kw in task for kw in keywords):
                primary_intent = intent
                break

        for rule in self.rules:
            # 跳过约束规则
            if rule.pattern == '.*':
                continue

            # 检查关键词匹配
            try:
                if re.search(rule.pattern, task, re.IGNORECASE):
                    # 如果有主要意图，优先匹配同类型的规则
                    if primary_intent:
                        rule_name_lower = rule.name.lower()
                        if primary_intent in rule_name_lower:
                            candidates.insert(0, rule)  # 插入到前面
                        else:
                            candidates.append(rule)
                    else:
                        candidates.append(rule)
            except re.error:
                if rule.pattern.lower() in task_lower:
                    candidates.append(rule)

        return candidates, primary_intent

    def _llm_select_rule(self, task: str, candidates: List[AgentRule]) -> Optional[AgentRule]:
        """用 LLM 从候选规则中选最匹配的"""
        if not self.llm_fn:
            return candidates[0] if candidates else None

        # 构建候选列表
        rule_list = []
        for i, rule in enumerate(candidates):
            steps_desc = ', '.join(s['desc'] for s in rule.steps[:3])
            rule_list.append(f'{i + 1}. {rule.name} — {steps_desc}')

        prompt = f"""任务: {task[:200]}

候选规则:
{chr(10).join(rule_list)}

选择最匹配任务的规则编号。只输出数字，不要其他文字。"""

        try:
            raw = self.llm_fn(prompt)
            # 提取数字
            match = re.search(r'\d+', raw)
            if match:
                idx = int(match.group()) - 1
                if 0 <= idx < len(candidates):
                    return candidates[idx]
        except Exception:
            pass

        # 兜底：返回第一条
        return candidates[0] if candidates else None

    def generate_rule(self, task: str, context: str = '') -> Optional[AgentRule]:
        """用 LLM 生成新规则"""
        if not self.llm_fn:
            return None

        # 构建提示
        prompt = f"""为以下任务生成一个 Agent 工具链规则。

任务: {task[:300]}
上下文: {context[:200]}

可用工具:
- analyze(path) — 分析文件结构
- read_file(path,start,count) — 读文件
- search_code(keyword) — 搜索代码
- replace_in_file(path,old,new) — 单次替换
- write_file(path,content) — 写入文件
- list_files(pattern) — 列出文件
- run_test(test_file) — 运行测试
- run_shell(cmd) — 执行shell命令
- done(answer) — 任务完成

请用 JSON 格式回答:
{{
  "name": "规则名称",
  "pattern": "匹配正则表达式",
  "steps": [
    {{"tool": "工具名", "args_desc": "参数描述", "desc": "步骤描述"}}
  ],
  "validation": "验证命令"
}}

要求:
1. pattern 必须是有效的正则表达式
2. steps 按执行顺序排列
3. validation 必须是可在终端执行的命令
4. 只输出 JSON，不要其他文字"""

        try:
            raw = self.llm_fn(prompt)
            # 提取 JSON
            match = re.search(r'\{.*\}', raw, re.DOTALL)
            if match:
                import json

                data = json.loads(match.group())

                # 构建规则
                name = data.get('name', '未命名规则')
                pattern = data.get('pattern', '')
                steps = data.get('steps', [])
                validation = data.get('validation', 'echo done')

                # 验证格式
                if not pattern or not steps:
                    return None

                # 尝试编译正则
                try:
                    re.compile(pattern)
                except re.error:
                    return None

                rule = AgentRule(name, pattern, steps, validation)
                self._pending_rule = rule
                return rule
        except Exception:
            pass

        return None

    def approve_rule(self) -> bool:
        """审批通过，保存规则到文件"""
        if not self._pending_rule:
            return False

        rule = self._pending_rule

        # 读取现有内容
        with open(self.rules_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # 追加新规则
        rule_md = rule.to_markdown()
        content = content.rstrip() + '\n\n' + rule_md + '\n'

        # 写入文件
        with open(self.rules_file, 'w', encoding='utf-8') as f:
            f.write(content)

        # 添加到内存
        self.rules.append(rule)
        self._pending_rule = None

        return True

    def reject_rule(self) -> bool:
        """拒绝规则"""
        if not self._pending_rule:
            return False

        self._pending_rule = None
        return True

    def get_pending_rule(self) -> Optional[AgentRule]:
        """获取待审批的规则"""
        return self._pending_rule

    def get_rules_summary(self) -> str:
        """获取规则摘要"""
        if not self.rules:
            return '（无规则）'
        lines = [f'共 {len(self.rules)} 条规则：']
        for rule in self.rules:
            lines.append(f'  - {rule.name}: {rule.pattern}')
        return '\n'.join(lines)

    def format_rule_for_prompt(self, rule: AgentRule) -> str:
        """格式化规则，注入 LLM 上下文"""
        steps = '\n'.join(f'  {i + 1}. {s["tool"]}({s["args_desc"]}) — {s["desc"]}' for i, s in enumerate(rule.steps))
        return f'[规则] {rule.name}\n工具链:\n{steps}\n验证: {rule.validation}'

    def extract_filename(self, task: str, rule: Optional[AgentRule] = None) -> Optional[str]:
        """从任务中提取文件名（含路径前缀）"""
        path_prefix = self.extract_path(task)
        lang = self.detect_language(task)
        ext = self.LANG_EXTENSIONS.get(lang, '.py')
        ext_pattern = ext.replace('.', r'\.')

        # 匹配完整路径+文件名: csrc/foo.ext
        match = re.search(rf'([a-zA-Z0-9_/\\-]+/[a-zA-Z0-9_]+{ext_pattern})', task)
        if match:
            return match.group(1).replace('\\', '/')
        # 匹配纯文件名: foo.ext
        match = re.search(rf'[a-zA-Z0-9_]+{ext_pattern}', task)
        if match:
            fname = match.group(0)
            if path_prefix:
                return f'{path_prefix}/{fname}'
            return fname
        return None

    # 语言扩展名映射
    LANG_EXTENSIONS = {
        'python': '.py',
        'py': '.py',
        'java': '.java',
        'go': '.go',
        'golang': '.go',
        'javascript': '.js',
        'js': '.js',
        'node': '.js',
        'typescript': '.ts',
        'ts': '.ts',
        'rust': '.rs',
        'rs': '.rs',
        'c': '.c',
        'cpp': '.cpp',
        'c++': '.cpp',
        'ruby': '.rb',
        'rb': '.rb',
        'php': '.php',
        'swift': '.swift',
        'kotlin': '.kt',
        'kt': '.kt',
        'scala': '.scala',
        'r': '.r',
        'sql': '.sql',
        'html': '.html',
        'css': '.css',
        'shell': '.sh',
        'bash': '.sh',
        'yaml': '.yml',
        'yml': '.yml',
        'toml': '.toml',
        'markdown': '.md',
        'md': '.md',
        'text': '.txt',
        'txt': '.txt',
    }

    def detect_language(self, task: str) -> str:
        """从任务描述中检测编程语言"""
        task_lower = task.lower()
        lang_keywords = {
            'python': ['python', '.py', 'pytest', 'pip', 'django', 'flask', 'fastapi', 'numpy', 'pandas'],
            'java': ['java', '.java', 'maven', 'gradle', 'spring', 'jvm', 'jar', 'class '],
            'go': ['go', 'golang', '.go', 'goroutine', 'go mod'],
            'javascript': ['javascript', '.js', 'node', 'npm', 'react', 'vue', 'angular'],
            'typescript': ['typescript', '.ts', 'tsx', 'ts-node'],
            'rust': ['rust', '.rs', 'cargo', 'crate'],
            'c': ['c语言', ' c ', '.c ', 'gcc', 'makefile'],
            'cpp': ['c++', 'cpp', '.cpp', 'cmake', 'qt'],
            'ruby': ['ruby', '.rb', 'rails', 'gem'],
            'php': ['php', '.php', 'laravel', 'composer'],
            'kotlin': ['kotlin', '.kt', 'gradle.kts'],
            'swift': ['swift', '.swift', 'xcode', 'ios'],
            'shell': ['shell', 'bash', '.sh', 'script'],
        }
        for lang, keywords in lang_keywords.items():
            for kw in keywords:
                if kw in task_lower:
                    return lang
        return 'python'

    def extract_path(self, task: str) -> Optional[str]:
        """从任务描述中提取目标目录路径
        支持: '在X下新建', '在X目录下创建', '在X中新建', 'X目录下', 'X下'
        """
        patterns = [
            r'在([\w_/\\-]+(?:目录)?)(?:下|中)(?:新建|创建|添加)',
            r'([\w_/\\-]+)(?:目录)?下(?:新建|创建|添加)',
            r'在([\w_/\\-]+)(?:下|中)(?:写|放|存)',
            r'(?:解释|分析|看懂|说明)(?:.*?)([\w_]+\.py)',
        ]
        for pat in patterns:
            m = re.search(pat, task)
            if m:
                p = m.group(1).rstrip('目录').replace('\\', '/')
                if p.endswith('.py'):
                    return None
                if 1 <= len(p) <= 30 and not p.startswith('.') and '/' not in p.lstrip('/'):
                    return p
        return None
        """从任务描述中提取目标目录路径
        支持: '在X下新建', '在X目录下创建', '在X中新建', 'X目录下', 'X下'
        """
        patterns = [
            r'在([\w_/\\-]+(?:目录)?)(?:下|中)(?:新建|创建|添加)',
            r'([\w_/\\-]+)(?:目录)?下(?:新建|创建|添加)',
            r'在([\w_/\\-]+)(?:下|中)(?:写|放|存)',
            r'(?:解释|分析|看懂|说明)(?:.*?)([\w_]+\.py)',  # 解释代码 → 提取文件名
        ]
        for pat in patterns:
            m = re.search(pat, task)
            if m:
                p = m.group(1).rstrip('目录').replace('\\', '/')
                # 如果是文件名（.py 结尾），不作为目录路径
                if p.endswith('.py'):
                    return None
                # 验证路径合理性
                if 1 <= len(p) <= 30 and not p.startswith('.') and '/' not in p.lstrip('/'):
                    return p
        return None

    def extract_module_name(self, task: str, filename: Optional[str] = None) -> Optional[str]:
        """提取模块名（用于测试文件名）"""
        if filename:
            base = filename.replace('\\', '/').split('/')[-1]
            return base.rsplit('.', 1)[0] if '.' in base else base
        lang = self.detect_language(task)
        ext = self.LANG_EXTENSIONS.get(lang, '.py')
        ext_pattern = ext.replace('.', r'\.')
        match = re.search(rf'([a-zA-Z0-9_]+){ext_pattern}', task)
        if match:
            return match.group(1)
        return None
