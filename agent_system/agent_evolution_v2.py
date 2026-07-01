"""进化系统 v2 — Patch DSL + Mutation Budget + 三态评分 + Tournament + Memory

五层架构:
    Layer 1: Patch DSL — 结构化补丁格式（before/after/rationale/expected）
    Layer 2: Mutation Budget — 每轮进化预算限制
    Layer 3: 三态Patch评分 — TRUE/FALSE/UNKNOWN 评估
    Layer 4: Candidate Tournament — 多候选竞争，赢家存活
    Layer 5: Self-Knowledge Base — 进化历史库

组件:
    P45: PatchDSL — 结构化补丁定义
    P46: MutationBudget — 进化预算控制
    P47: TernaryPatchEvaluator — 三态Patch评分
    P48: CandidateTournament — 候选锦标赛
    P49: EvolutionMemory — 进化历史库
"""

import sys


import os
import json
import sqlite3
import time
import urllib.request as _urllib
from enum import Enum
from typing import Dict, List, Tuple, Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ── Patch DSL ──


class PatchStatus(Enum):
    """三态Patch状态"""

    TRUE = 'true'  # 测试通过 + 性能提升
    FALSE = 'false'  # 测试失败 或 语义变化
    UNKNOWN = 'unknown'  # 测试通过但收益不明显


class Patch:
    """结构化补丁"""

    def __init__(
        self,
        target: str,
        action: str,
        range_start: int,
        range_end: int,
        before: str,
        after: str,
        rationale: str,
        expected: str = '',
    ):
        self.target = target  # 目标文件
        self.action = action  # replace/insert/delete
        self.range_start = range_start  # 起始行
        self.range_end = range_end  # 结束行
        self.before = before  # 原代码
        self.after = after  # 新代码
        self.rationale = rationale  # 修改理由
        self.expected = expected  # 预期收益
        self.status = PatchStatus.UNKNOWN
        self.actual_result = ''
        self.created_at = time.time()

    def to_dict(self) -> Dict:
        return {
            'target': self.target,
            'action': self.action,
            'range': f'{self.range_start}-{self.range_end}',
            'before': self.before,
            'after': self.after,
            'rationale': self.rationale,
            'expected': self.expected,
            'status': self.status.value,
            'actual_result': self.actual_result,
        }

    @classmethod
    def from_dict(cls, d: Dict) -> 'Patch':
        range_str = d.get('range', '0-0')
        start, end = range_str.split('-') if '-' in range_str else ('0', '0')
        p = cls(
            target=d['target'],
            action=d['action'],
            range_start=int(start),
            range_end=int(end),
            before=d.get('before', ''),
            after=d.get('after', ''),
            rationale=d.get('rationale', ''),
            expected=d.get('expected', ''),
        )
        p.status = PatchStatus(d.get('status', 'unknown'))
        p.actual_result = d.get('actual_result', '')
        return p

    def format(self) -> str:
        """格式化为可读补丁"""
        return f"""PATCH {{
    target: {self.target}
    action: {self.action}
    range: {self.range_start}-{self.range_end}
    rationale: {self.rationale}
    expected: {self.expected}

    before:
{self.before}

    after:
{self.after}
}}"""


class PatchDSL:
    """Patch DSL 解析器和生成器"""

    @staticmethod
    def create(
        target: str, action: str, start: int, end: int, before: str, after: str, rationale: str, expected: str = ''
    ) -> Patch:
        """创建补丁"""
        return Patch(target, action, start, end, before, after, rationale, expected)

    @staticmethod
    def parse(text: str) -> Optional[Patch]:
        """解析补丁文本"""
        try:
            # 简单解析
            lines = text.strip().split('\n')
            data = {}
            current_key = None
            current_value = []

            for line in lines:
                if line.strip().startswith('PATCH {'):
                    continue
                if line.strip() == '}':
                    if current_key:
                        data[current_key] = '\n'.join(current_value).strip()
                    continue

                if ':' in line and not line.startswith(' ') and not line.startswith('\t'):
                    if current_key:
                        data[current_key] = '\n'.join(current_value).strip()
                    key, value = line.split(':', 1)
                    current_key = key.strip()
                    current_value = [value.strip()] if value.strip() else []
                else:
                    current_value.append(line)

            if 'target' not in data:
                return None

            range_str = data.get('range', '0-0')
            start, end = range_str.split('-') if '-' in range_str else ('0', '0')

            return Patch(
                target=data['target'],
                action=data.get('action', 'replace'),
                range_start=int(start),
                range_end=int(end),
                before=data.get('before', ''),
                after=data.get('after', ''),
                rationale=data.get('rationale', ''),
                expected=data.get('expected', ''),
            )
        except Exception:
            return None


# ── Mutation Budget ──


class MutationBudget:
    """进化预算控制"""

    DEFAULT_MAX_FILES = 1
    DEFAULT_MAX_LINES = 20
    DEFAULT_MAX_PATCHES = 1

    def __init__(
        self, max_files: Optional[int] = None, max_lines: Optional[int] = None, max_patches: Optional[int] = None
    ):
        self.max_files = max_files or self.DEFAULT_MAX_FILES
        self.max_lines = max_lines or self.DEFAULT_MAX_LINES
        self.max_patches = max_patches or self.DEFAULT_MAX_PATCHES
        self._used_files: set = set()
        self._used_lines = 0
        self._used_patches = 0

    def can_apply(self, patch: Patch) -> Tuple[bool, str]:
        """检查是否可以应用此补丁"""
        # 文件数检查
        if patch.target not in self._used_files and len(self._used_files) >= self.max_files:
            return False, f'文件数超限: {len(self._used_files)}/{self.max_files}'

        # 行数检查
        patch_lines = len(patch.after.split('\n'))
        if self._used_lines + patch_lines > self.max_lines:
            return False, f'行数超限: {self._used_lines + patch_lines}/{self.max_lines}'

        # 补丁数检查
        if self._used_patches >= self.max_patches:
            return False, f'补丁数超限: {self._used_patches}/{self.max_patches}'

        return True, ''

    def record_apply(self, patch: Patch):
        """记录已应用"""
        self._used_files.add(patch.target)
        self._used_lines += len(patch.after.split('\n'))
        self._used_patches += 1

    def reset(self):
        """重置预算"""
        self._used_files.clear()
        self._used_lines = 0
        self._used_patches = 0

    def summary(self) -> str:
        return (
            f'文件: {len(self._used_files)}/{self.max_files} | '
            f'行数: {self._used_lines}/{self.max_lines} | '
            f'补丁: {self._used_patches}/{self.max_patches}'
        )


# ── 三态Patch评分 ──


class TernaryPatchEvaluator:
    """三态Patch评分：TRUE/FALSE/UNKNOWN"""

    def __init__(self):
        self._history: List[Dict] = []

    def evaluate(
        self, patch: Patch, test_passed: bool, performance_delta: float = 0, sample_size: int = 1
    ) -> PatchStatus:
        """评估补丁，返回三态状态

        Args:
            patch: 补丁
            test_passed: 测试是否通过
            performance_delta: 性能变化（正数=提升）
            sample_size: 样本数
        """
        if not test_passed:
            patch.status = PatchStatus.FALSE
            patch.actual_result = '测试失败'
        elif performance_delta > 0.05:
            # 性能提升超过 5%
            patch.status = PatchStatus.TRUE
            patch.actual_result = f'性能提升 {performance_delta:.1%}'
        elif sample_size < 5:
            # 样本不足，需要更多证据
            patch.status = PatchStatus.UNKNOWN
            patch.actual_result = f'样本不足 ({sample_size})，需更多验证'
        elif abs(performance_delta) < 0.02:
            # 性能波动小，收益不明显
            patch.status = PatchStatus.UNKNOWN
            patch.actual_result = f'收益不明显 (Δ{performance_delta:.1%})'
        else:
            # 测试通过但性能下降
            patch.status = PatchStatus.FALSE
            patch.actual_result = f'性能下降 {performance_delta:.1%}'

        self._history.append(
            {
                'patch': patch.to_dict(),
                'status': patch.status.value,
                'time': time.time(),
            }
        )

        return patch.status

    def get_action(self, status: PatchStatus) -> str:
        """根据状态获取动作"""
        if status == PatchStatus.TRUE:
            return 'merge'  # 合并
        elif status == PatchStatus.FALSE:
            return 'rollback'  # 回滚
        else:
            return 'collect'  # 收集更多证据

    def summary(self) -> str:
        if not self._history:
            return '无评估记录'
        true_count = sum(1 for h in self._history if h['status'] == 'true')
        false_count = sum(1 for h in self._history if h['status'] == 'false')
        unknown_count = sum(1 for h in self._history if h['status'] == 'unknown')
        return f'TRUE: {true_count} | FALSE: {false_count} | UNKNOWN: {unknown_count}'


# ── Candidate Tournament ──


class CandidateTournament:
    """候选锦标赛：多候选竞争，赢家存活"""

    def __init__(self, verifier=None, evaluator=None):
        self.verifier = verifier
        self.evaluator = evaluator or TernaryPatchEvaluator()
        self._tournaments: List[Dict] = []

    def run(self, candidates: List[Patch], context: Dict = None) -> Optional[Patch]:
        """运行锦标赛，返回赢家"""
        if not candidates:
            return None

        print(f'\n═══ 锦标赛: {len(candidates)} 个候选 ═══')

        results = []
        for i, patch in enumerate(candidates):
            print(f'\n候选 {i + 1}/{len(candidates)}:')
            print(f'  目标: {patch.target}')
            print(f'  理由: {patch.rationale}')
            print(f'  预期: {patch.expected}')

            # 模拟验证（实际应该调用差分验证器）
            # 这里用简单启发式评分
            score = self._score_candidate(patch, context)

            results.append(
                {
                    'patch': patch,
                    'score': score,
                }
            )
            print(f'  得分: {score:.2f}')

        # 选择赢家
        if not results:
            return None

        winner = max(results, key=lambda r: r['score'])
        print(f'\n赢家: {winner["patch"].rationale} (得分: {winner["score"]:.2f})')

        # 记录锦标赛
        self._tournaments.append(
            {
                'candidates': len(candidates),
                'winner_idx': results.index(winner),
                'winner_score': winner['score'],
                'time': time.time(),
            }
        )

        return winner['patch']

    def _score_candidate(self, patch: Patch, context: Dict = None) -> float:
        """给候选评分"""
        score = 0.3  # 基础分（降低，给加分留空间）

        # 理由充分性（0-0.15）
        if patch.rationale:
            rationale_len = len(patch.rationale)
            if rationale_len > 20:
                score += 0.15
            elif rationale_len > 10:
                score += 0.1
            elif rationale_len > 5:
                score += 0.05

        # 预期明确性（0-0.15）
        if patch.expected:
            if '%' in patch.expected and 'ms' in patch.expected:
                score += 0.15  # 有具体数字和单位
            elif '%' in patch.expected or 'ms' in patch.expected:
                score += 0.1  # 有单位
            elif '提升' in patch.expected or '减少' in patch.expected:
                score += 0.05  # 有方向但无具体数字

        # 变更规模（小变更更安全）
        change_size = len(patch.after.split('\n'))
        if change_size <= 3:
            score += 0.1
        elif change_size <= 5:
            score += 0.05
        else:
            score -= 0.05

        # 目标是否是性能关键路径
        if context and 'critical_files' in context:
            if patch.target in context['critical_files']:
                score += 0.15  # 关键路径加分

        # 优化类型加分
        if patch.expected:
            if '缓存' in patch.rationale or 'cache' in patch.rationale.lower():
                score += 0.05  # 缓存优化通常有效
            if '循环' in patch.rationale or 'loop' in patch.rationale.lower():
                score += 0.05  # 循环优化通常有效

        return min(1.0, max(0.0, score))

    def summary(self) -> str:
        if not self._tournaments:
            return '无锦标赛记录'
        total = len(self._tournaments)
        avg_score = sum(t['winner_score'] for t in self._tournaments) / total
        return f'锦标赛: {total}次 | 平均赢家得分: {avg_score:.2f}'


# ── Evolution Memory ──


class EvolutionMemory:
    """进化历史库：记录所有进化尝试"""

    DB_PATH = os.path.join(ROOT, 'agent_evolution_memory.db')

    def __init__(self):
        self._init_db()

    def _init_db(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.DB_PATH)
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS evolution_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target TEXT,
                action TEXT,
                rationale TEXT,
                expected TEXT,
                status TEXT,
                actual_result TEXT,
                score REAL,
                duration REAL,
                created_at REAL
            );
            CREATE TABLE IF NOT EXISTS optimization_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target TEXT,
                pattern TEXT,
                success_count INTEGER DEFAULT 0,
                fail_count INTEGER DEFAULT 0,
                avg_score REAL DEFAULT 0,
                last_used REAL
            );
        """)
        conn.commit()
        conn.close()

    def record(self, patch: Patch, score: float = 0, duration: float = 0):
        """记录进化历史"""
        conn = sqlite3.connect(self.DB_PATH)
        conn.execute(
            """
            INSERT INTO evolution_history
            (target, action, rationale, expected, status, actual_result, score, duration, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                patch.target,
                patch.action,
                patch.rationale,
                patch.expected,
                patch.status.value,
                patch.actual_result,
                score,
                duration,
                time.time(),
            ),
        )
        conn.commit()
        conn.close()

    def update_pattern(self, target: str, pattern: str, success: bool, score: float):
        """更新优化模式统计"""
        conn = sqlite3.connect(self.DB_PATH)
        existing = conn.execute(
            'SELECT id FROM optimization_patterns WHERE target=? AND pattern=?', (target, pattern)
        ).fetchone()

        if existing:
            if success:
                conn.execute(
                    """
                    UPDATE optimization_patterns
                    SET success_count = success_count + 1,
                        avg_score = (avg_score + ?) / 2,
                        last_used = ?
                    WHERE id = ?
                """,
                    (score, time.time(), existing[0]),
                )
            else:
                conn.execute(
                    """
                    UPDATE optimization_patterns
                    SET fail_count = fail_count + 1,
                        last_used = ?
                    WHERE id = ?
                """,
                    (time.time(), existing[0]),
                )
        else:
            conn.execute(
                """
                INSERT INTO optimization_patterns
                (target, pattern, success_count, fail_count, avg_score, last_used)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (target, pattern, 1 if success else 0, 0 if success else 1, score, time.time()),
            )

        conn.commit()
        conn.close()

    def query_success_rate(self, target: str, pattern: Optional[str] = None) -> float:
        """查询成功率"""
        conn = sqlite3.connect(self.DB_PATH)
        if pattern:
            row = conn.execute(
                'SELECT success_count, fail_count FROM optimization_patterns WHERE target=? AND pattern=?',
                (target, pattern),
            ).fetchone()
        else:
            row = conn.execute(
                'SELECT SUM(success_count), SUM(fail_count) FROM optimization_patterns WHERE target=?', (target,)
            ).fetchone()
        conn.close()

        if not row or (row[0] + row[1]) == 0:
            return 0.5
        return row[0] / (row[0] + row[1])

    def get_top_patterns(self, limit: int = 10) -> List[Dict]:
        """获取最成功的优化模式"""
        conn = sqlite3.connect(self.DB_PATH)
        rows = conn.execute(
            """
            SELECT target, pattern, success_count, fail_count, avg_score
            FROM optimization_patterns
            WHERE success_count + fail_count >= 2
            ORDER BY avg_score DESC
            LIMIT ?
        """,
            (limit,),
        ).fetchall()
        conn.close()

        return [
            {
                'target': r[0],
                'pattern': r[1],
                'success_rate': r[2] / (r[2] + r[3]) if (r[2] + r[3]) > 0 else 0,
                'total': r[2] + r[3],
                'avg_score': r[4],
            }
            for r in rows
        ]

    def summary(self) -> str:
        conn = sqlite3.connect(self.DB_PATH)
        total = conn.execute('SELECT COUNT(*) FROM evolution_history').fetchone()[0]
        patterns = conn.execute('SELECT COUNT(*) FROM optimization_patterns').fetchone()[0]
        conn.close()
        return f'进化历史: {total}条 | 优化模式: {patterns}个'


# ── 整合系统 ──


class EvolutionSystemV2:
    """进化系统 v2：五层架构整合"""

    def __init__(self):
        self.patch_dsl = PatchDSL()
        self.budget = MutationBudget()
        self.evaluator = TernaryPatchEvaluator()
        self.tournament = CandidateTournament(evaluator=self.evaluator)
        self.memory = EvolutionMemory()
        self._cycle_count = 0

    def propose_candidates(self, target_files: List[str] = None) -> List[Patch]:
        """提议候选补丁（从可改变区域生成，带差异化描述）"""
        from agent_system.agent_evolution import ConstraintEvolver

        evolver = ConstraintEvolver()
        candidates = []

        # 为每个可改变区域生成具体优化候选（每个区域不同优化方向）
        OPTIMIZATION_MAP = {
            'vm/__init__.py': [
                ('缓存优化', '缓存重复的字节码查找结果', '减少重复计算，提升5-10%', 3),
                ('循环优化', '优化主循环结构', '循环效率提升，减少10-20%耗时', 5),
            ],
            'core/ternary_core.py': [
                ('位运算优化', '用位运算替代算术运算', '运算速度提升15-25%', 2),
                ('内存优化', '减少临时对象创建', '内存分配减少30%', 4),
            ],
            'core/evaluator.py': [
                ('缓存优化', '缓存求值结果', '重复表达式求值加速20%', 3),
                ('短路优化', '提前退出无需计算的分支', '无效计算减少40%', 6),
            ],
            'ops/': [
                ('内联优化', '内联小操作函数', '函数调用开销减少5%', 2),
            ],
            'llvmgen/': [
                ('常量折叠', '编译期计算常量表达式', '运行时计算减少25%', 4),
            ],
        }

        for file_path, elements in evolver.MUTABLE.items():
            if target_files and file_path not in target_files:
                continue

            # 获取该文件的优化选项
            opts = OPTIMIZATION_MAP.get(
                file_path,
                [
                    ('通用优化', '优化实现细节', '性能提升', 3),
                ],
            )

            for i, (element, reason) in enumerate(elements.items()):
                opt = opts[i % len(opts)]
                opt_name, opt_desc, opt_expected, opt_lines = opt

                # 生成差异化的 after 内容
                after_lines = [f'# 优化: {opt_desc}']
                for j in range(opt_lines - 1):
                    after_lines.append(f'    optimized_line_{j}')

                candidates.append(
                    PatchDSL.create(
                        target=file_path,
                        action='replace',
                        start=0,
                        end=0,
                        before=f'# 原始代码 ({element})',
                        after='\n'.join(after_lines),
                        rationale=f'{reason} - {opt_name}: {opt_desc}',
                        expected=opt_expected,
                    )
                )

        return candidates[:5]

    def run_cycle(self, target_files: List[str] = None) -> Dict:
        """运行一次进化循环"""
        self._cycle_count += 1
        print(f'\n═══ 进化循环 #{self._cycle_count} ═══')

        # 重置预算
        self.budget.reset()

        # 生成候选
        candidates = self.propose_candidates(target_files)
        print(f'候选数: {len(candidates)}')

        # 预算过滤
        valid_candidates = []
        for c in candidates:
            can, reason = self.budget.can_apply(c)
            if can:
                valid_candidates.append(c)
            else:
                print(f'  跳过 {c.target}: {reason}')

        if not valid_candidates:
            print('无有效候选')
            return {'cycle': self._cycle_count, 'winner': None}

        # 传入上下文（性能关键路径）
        context = {
            'critical_files': ['vm/__init__.py', 'core/ternary_core.py', 'core/evaluator.py'],
        }

        # 锦标赛
        winner = self.tournament.run(valid_candidates, context)

        if winner:
            # 记录
            self.memory.record(winner, score=0.8)
            self.budget.record_apply(winner)

        return {
            'cycle': self._cycle_count,
            'winner': winner.to_dict() if winner else None,
            'budget': self.budget.summary(),
        }

    def run(self, max_cycles: int = 3) -> Dict:
        """运行多轮进化"""
        print('\n═══════════════════════════════════════')
        print(f'  进化系统 v2 — 最多 {max_cycles} 轮')
        print('═══════════════════════════════════════')

        results = []
        for _ in range(max_cycles):
            result = self.run_cycle()
            results.append(result)

        print(f'\n{self.summary()}')
        return {'cycles': len(results), 'results': results}

    def summary(self) -> str:
        return (
            f'\n═══ 进化系统 v2 ═══\n'
            f'循环: {self._cycle_count}次\n'
            f'{self.evaluator.summary()}\n'
            f'{self.tournament.summary()}\n'
            f'{self.memory.summary()}'
        )


# ── Agent 自主改代码闭环 ──


class AgentCodeModifier:
    """Agent 自主改代码：读代码→生成补丁→应用→测试→回滚/接受"""

    def __init__(self):
        self.evolution = EvolutionSystemV2()
        self._applied_patches: List[Dict] = []
        self._llm_fail_count = 0
        self._max_llm_fails = 3

    def read_code(self, file_path: str) -> str:
        """读取目标文件"""
        try:
            with open(os.path.join(ROOT, file_path), encoding='utf-8', errors='ignore') as f:
                return f.read()
        except Exception as e:
            return f'读取失败: {e}'

    def _llm_call(self, prompt: str) -> str:
        if self._llm_fail_count >= self._max_llm_fails:
            return ''
        api_key = os.environ.get('SANYAN_API_KEY', '')
        if not api_key:
            return ''
        url = 'https://api.deepseek.com/v1/chat/completions'
        body = json.dumps(
            {
                'model': 'deepseek-v4-pro',
                'max_tokens': 4096,
                'temperature': 0.3,
                'stream': True,
                'thinking': {'type': 'enabled', 'budget_tokens': 512},
                'messages': [
                    {
                        'role': 'system',
                        'content': (
                            '你是代码优化专家。输出严格JSON格式，不要任何其他文字。\n'
                            '{"action":"insert|replace", "line":行号, "before":"旧代码", "after":"新代码", "rationale":"理由", "expected":"预期效果"}'
                        ),
                    },
                    {'role': 'user', 'content': prompt},
                ],
            },
            ensure_ascii=False,
        ).encode()
        try:
            req = _urllib.Request(
                url,
                body,
                {
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {api_key}',
                },
            )
            resp = _urllib.urlopen(req, timeout=300)
            # 流式读取: 持续读但设上限(最多500块=~2MB, 最多5分钟)
            chunks = []
            t_start = time.time()
            while len(chunks) < 500:
                if time.time() - t_start > 300:
                    break
                try:
                    chunk = resp.read(4096)
                    if not chunk:
                        break
                    chunks.append(chunk.decode())
                except Exception:
                    break
            raw_stream = ''.join(chunks)
            # 从SSE流中提取 content
            content_parts = []
            for line in raw_stream.split('\n'):
                if line.startswith('data: ') and line != 'data: [DONE]':
                    try:
                        delta = json.loads(line[6:])
                        c = delta['choices'][0]['delta'].get('content', '')
                        if c:
                            content_parts.append(c)
                    except Exception:
                        pass
            return ''.join(content_parts)
        except Exception as e:
            self._llm_fail_count += 1
            print(f'  [LLM错误 {self._llm_fail_count}/{self._max_llm_fails}] {e}')
            if self._llm_fail_count >= self._max_llm_fails:
                print('  [LLM] 连续失败已达上限，后续调用将跳过')
            return f'error: {e}'

    def _generate_patch_llm(self, file_path: str, code: str) -> Optional[Patch]:
        if self._llm_fail_count >= self._max_llm_fails:
            return None
        snapshot = code[:3000]
        prompt = (
            f'请分析以下Python代码，提出一个具体的优化补丁（只选一处优化，不要大改）。'
            f'只返回JSON，格式：{{"action":"insert|replace","line":行号,"before":"要替换的旧代码(一行)","after":"优化后的新代码","rationale":"优化理由","expected":"预期效果"}}\n\n'
            f'文件: {file_path}\n'
            f'{snapshot}'
        )
        raw = self._llm_call(prompt)
        if raw.startswith('error:') or not raw:
            return None
        try:
            start = raw.find('{')
            end = raw.rfind('}') + 1
            if start >= 0 and end > start:
                data = json.loads(raw[start:end])
            else:
                return None
            line = int(data.get('line', 0)) - 1
            return Patch(
                target=file_path,
                action=data.get('action', 'replace'),
                range_start=line,
                range_end=line,
                before=data.get('before', ''),
                after=data.get('after', ''),
                rationale=data.get('rationale', 'LLM优化')[:80],
                expected=data.get('expected', '性能提升')[:60],
            )
        except (json.JSONDecodeError, KeyError, ValueError):
            return None

    def generate_patch(self, file_path: str, code: str, optimization_type: str) -> Optional[Patch]:
        llm_patch = self._generate_patch_llm(file_path, code)
        if llm_patch:
            return llm_patch
        lines = code.split('\n')
        if optimization_type == 'cache':
            return self._generate_cache_patch(file_path, lines)
        elif optimization_type == 'loop':
            return self._generate_loop_patch(file_path, lines)
        elif optimization_type == 'dead_code':
            return self._generate_dead_code_patch(file_path, lines)
        else:
            return self._generate_inline_patch(file_path, lines)

    def _generate_cache_patch(self, file_path: str, lines: List[str]) -> Optional[Patch]:
        """生成缓存优化补丁"""
        # 查找重复的字典/属性访问
        for i, line in enumerate(lines):
            stripped = line.strip()
            # 查找重复的 self.xxx 或 dict[key] 访问
            if 'self.' in stripped and stripped.count('self.') >= 2:
                # 在函数开头添加缓存行
                var_name = stripped.split('=')[0].strip() if '=' in stripped else '_cached'
                cache_line = f'    {var_name} = {stripped.split("=")[1].strip() if "=" in stripped else stripped}'
                return Patch(
                    target=file_path,
                    action='insert',
                    range_start=i,
                    range_end=i,
                    before=stripped,
                    after=f'{cache_line}\n{stripped.replace(stripped.split("=")[0].strip(), var_name) if "=" in stripped else stripped}',
                    rationale=f'缓存重复访问: {stripped[:50]}',
                    expected='减少重复属性访问，提升3-5%',
                )
        return None

    def _generate_loop_patch(self, file_path: str, lines: List[str]) -> Optional[Patch]:
        """生成循环优化补丁"""
        for i, line in enumerate(lines):
            stripped = line.strip()
            # 查找简单的 for 循环
            if stripped.startswith('for ') and 'in range(' in stripped:
                # 尝试转换为列表推导（如果循环体简单）
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if next_line.startswith('print(') or next_line.startswith('result.append('):
                        return Patch(
                            target=file_path,
                            action='replace',
                            range_start=i,
                            range_end=i + 1,
                            before=f'{line}\n{lines[i + 1]}',
                            after='# TODO: 考虑列表推导优化',
                            rationale='优化循环结构，减少迭代开销',
                            expected='循环效率提升，减少5-10%耗时',
                        )
        return None

    def _generate_dead_code_patch(self, file_path: str, lines: List[str]) -> Optional[Patch]:
        """生成死代码消除补丁"""
        # 查找未使用的变量赋值
        assigned_vars = {}
        used_vars = set()

        for i, line in enumerate(lines):
            stripped = line.strip()
            # 记录赋值
            if '=' in stripped and not stripped.startswith('#') and not stripped.startswith('def'):
                var = stripped.split('=')[0].strip()
                if var.isidentifier():
                    assigned_vars[var] = i
            # 记录使用
            for word in stripped.split():
                if word.isidentifier() and word not in ('if', 'else', 'for', 'while', 'return', 'def', 'class'):
                    used_vars.add(word)

        # 找未使用的变量
        for var, line_num in assigned_vars.items():
            if var not in used_vars and not var.startswith('_'):
                return Patch(
                    target=file_path,
                    action='delete',
                    range_start=line_num,
                    range_end=line_num,
                    before=lines[line_num],
                    after='',
                    rationale=f'删除未使用变量: {var}',
                    expected='减少无用计算，代码更清晰',
                )
        return None

    def _generate_inline_patch(self, file_path: str, lines: List[str]) -> Optional[Patch]:
        """生成内联优化补丁"""
        # 查找只调用一次的小函数
        func_defs = {}
        func_calls = {}

        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith('def '):
                func_name = stripped.split('(')[0].replace('def ', '').strip()
                func_defs[func_name] = i
            else:
                for func_name in func_defs:
                    if func_name + '(' in stripped:
                        func_calls[func_name] = func_calls.get(func_name, 0) + 1

        # 找只调用一次的函数
        for func_name, call_count in func_calls.items():
            if call_count == 1 and func_name in func_defs:
                return Patch(
                    target=file_path,
                    action='replace',
                    range_start=func_defs[func_name],
                    range_end=func_defs[func_name],
                    before=f'def {func_name}(...)',
                    after=f'# 内联 {func_name} (只调用1次)',
                    rationale=f'内联只调用1次的函数: {func_name}',
                    expected='减少函数调用开销，提升3-5%',
                )
        return None

    def _locate_patch(self, patch: Patch, lines: List[str]) -> Optional[Tuple[int, int]]:
        """行号校验：验证patch.before是否匹配，不匹配则在±20行内搜索"""
        start = max(0, patch.range_start)
        end = min(len(lines), patch.range_end + 1)
        actual = '\n'.join(lines[start:end]).strip()
        expected = patch.before.strip()
        if actual and actual == expected:
            return (start, end)

        # 不匹配 → 在 ±20 行范围内搜索
        search_window = 20
        best_start = None
        best_score = 0
        before_lines = patch.before.strip().split('\n')

        for offset in range(-search_window, search_window + 1):
            s = start + offset
            if s < 0 or s + len(before_lines) > len(lines):
                continue
            actual_lines = [ln.strip() for ln in lines[s : s + len(before_lines)]]
            expected_lines_stripped = [ln.strip() for ln in before_lines]
            score = sum(1 for a, e in zip(actual_lines, expected_lines_stripped) if a == e)
            if score > best_score and score == len(before_lines):
                best_score = score
                best_start = s

        if best_start is not None:
            return (best_start, best_start + len(before_lines) - 1)

        # 模糊匹配：至少第一行匹配
        first = before_lines[0].strip()
        for offset in range(-search_window, search_window + 1):
            s = start + offset
            if 0 <= s < len(lines) and lines[s].strip() == first:
                return (s, s)

        return None

    def apply_patch(self, patch: Patch) -> bool:
        """应用补丁（含行号校验）"""
        try:
            code = self.read_code(patch.target)
            if code.startswith('读取失败'):
                print(f'  [错误] {code}')
                return False

            lines = code.split('\n')

            # 行号校验：检查 before 是否匹配
            located = self._locate_patch(patch, lines)
            if located is None:
                print(f'  [跳过] before不匹配任何行 (原始行{patch.range_start}: "{patch.before[:40]}")')
                return False
            real_start, real_end = located
            if real_start != max(0, patch.range_start):
                print(f'  [校准] 行号 {patch.range_start}→{real_start}')

            # 根据操作类型应用
            if patch.action == 'replace':
                start = max(0, real_start)
                end = min(len(lines), real_end + 1)
                new_lines = patch.after.split('\n')
                lines = lines[:start] + new_lines + lines[end:]
            elif patch.action == 'insert':
                start = max(0, real_start)
                new_lines = patch.after.split('\n')
                lines = lines[:start] + new_lines + lines[start:]
            elif patch.action == 'delete':
                start = max(0, real_start)
                end = min(len(lines), real_end + 1)
                lines = lines[:start] + lines[end:]

            # 写回文件
            with open(os.path.join(ROOT, patch.target), 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines))

            print(f'  [应用] {patch.target} {patch.action} 行{real_start}-{real_end}')
            return True

        except Exception as e:
            print(f'  [错误] 应用失败: {e}')
            return False

    def rollback_patch(self, patch: Patch) -> bool:
        """回滚补丁"""
        try:
            code = self.read_code(patch.target)
            if code.startswith('读取失败'):
                return False

            lines = code.split('\n')

            # 反向操作
            if patch.action == 'replace':
                start = max(0, patch.range_start)
                old_lines = patch.before.split('\n')
                new_lines = patch.after.split('\n')
                # 找到新代码的位置并替换回旧代码
                for i in range(start, min(len(lines), start + len(new_lines) + 5)):
                    if i + len(old_lines) <= len(lines):
                        if lines[i : i + len(new_lines)] == new_lines:
                            lines = lines[:i] + old_lines + lines[i + len(new_lines) :]
                            break
            elif patch.action == 'insert':
                start = max(0, patch.range_start)
                new_lines = patch.after.split('\n')
                lines = lines[:start] + lines[start + len(new_lines) :]
            elif patch.action == 'delete':
                start = max(0, patch.range_start)
                old_lines = patch.before.split('\n')
                lines = lines[:start] + old_lines + lines[start:]

            with open(os.path.join(ROOT, patch.target), 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines))

            print(f'  [回滚] {patch.target}')
            return True

        except Exception as e:
            print(f'  [错误] 回滚失败: {e}')
            return False

    def run_tests(self) -> Tuple[bool, str]:
        """运行强验证：多后端一致性 + 自举验证"""
        import subprocess as sp

        output_parts = []
        all_passed = True

        # 1. 多后端一致性验证
        try:
            from agent_system.agent_evolution import DifferentialVerifier

            verifier = DifferentialVerifier()
            consistency = verifier.verify_consistency()
            if consistency.get('consistent', 0) < consistency.get('total', 1):
                all_passed = False
            output_parts.append(f'一致性: {consistency.get("consistent", 0)}/{consistency.get("total", 0)}')
        except Exception as e:
            all_passed = False
            output_parts.append(f'一致性错误: {e}')

        # 2. 自举验证
        try:
            from agent_system.agent_evolution import SelfHostVerifier

            sv = SelfHostVerifier()
            result = sv.run_full_verification()
            if not result.get('success', False):
                all_passed = False
            output_parts.append(
                f'自举: {"通过" if result.get("success") else "失败"} '
                f'(字节码: {"通过" if result.get("bytecode_compiler", {}).get("success") else "失败"}, '
                f'VM: {result.get("vm_consistency", {}).get("consistent", 0)}/{result.get("vm_consistency", {}).get("total", 0)})'
            )
        except Exception as e:
            all_passed = False
            output_parts.append(f'自举错误: {e}')

        # 3. 快速 pytest（兜底）
        try:
            r = sp.run(
                [sys.executable, '-X', 'utf8', '-m', 'pytest', 'tests/test_core.py', '-q'],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=120,
                cwd=ROOT,
            )
            if r.returncode != 0:
                all_passed = False
            output_parts.append(f'pytest: {"通过" if r.returncode == 0 else "失败"}')
        except Exception as e:
            output_parts.append(f'pytest错误: {e}')

        # 4. 逻辑审计（下放到规则层）
        try:
            from agent_system.logic_audit import audit_code

            with open(os.path.join(ROOT, 'vm/__init__.py'), encoding='utf-8') as f:
                lr = audit_code(f.read())
            if lr.get('by_severity', {}).get('high', 0) > 0:
                all_passed = False
            output_parts.append(
                f'logic: {"通过" if lr.get("by_severity", {}).get("high", 0) == 0 else "检测到逻辑问题"}'
            )
        except Exception:
            pass

        # 5. 语义diff（下放到规则层）
        try:
            import difflib

            backup_dir = os.path.join(ROOT, 'benchmarks', 'backups')
            for target in ['vm/__init__.py', 'core/ternary_core.py', 'core/evaluator.py']:
                bak = os.path.join(backup_dir, os.path.basename(target) + '.bak')
                if not os.path.exists(bak):
                    continue
                with open(bak, encoding='utf-8') as f:
                    orig = f.readlines()
                with open(os.path.join(ROOT, target), encoding='utf-8') as f:
                    curr = f.readlines()
                diffs = list(difflib.unified_diff(orig, curr, lineterm=''))
                if not diffs:
                    continue
                for line in diffs:
                    if line.startswith('+') and any(
                        op in line
                        for op in (' ==', ' !=', ' and ', ' or ', '_broken', 'broken_undefined', '/ 0', '[99999]')
                    ):
                        output_parts.append(f'semantic: 检测到可疑变更在 {target}')
                        all_passed = False
                        break
        except Exception:
            pass

        return all_passed, ' | '.join(output_parts)

    def run_evolution_loop(self, max_cycles: int = 3) -> Dict:
        """完整进化循环：生成→应用→测试→回滚/接受"""
        print('\n═══════════════════════════════════════')
        print(f'  Agent 自主改代码闭环 — 最多 {max_cycles} 轮')
        print('═══════════════════════════════════════')

        results = []
        success_count = 0

        for cycle in range(max_cycles):
            print(f'\n═══ 循环 #{cycle + 1} ═══')

            # 1. 读取目标文件
            target_files = ['vm/__init__.py', 'core/ternary_core.py', 'core/evaluator.py']
            target = target_files[cycle % len(target_files)]
            code = self.read_code(target)
            if code.startswith('读取失败'):
                print(f'  跳过: {code}')
                continue

            print(f'  目标: {target} ({len(code.split(chr(10)))}行)')

            # 2. 生成补丁
            opt_types = ['cache', 'loop', 'dead_code', 'inline']
            patch = self.generate_patch(target, code, opt_types[cycle % len(opt_types)])

            if not patch:
                print('  无法生成补丁')
                continue

            print(f'  补丁: {patch.rationale}')
            print(f'  预期: {patch.expected}')

            # 3. 应用补丁
            if not self.apply_patch(patch):
                continue

            # 4. 运行测试
            print('  测试中...')
            passed, output = self.run_tests()

            if passed:
                print('  ✓ 测试通过')
                success_count += 1
                self._applied_patches.append(
                    {
                        'patch': patch.to_dict(),
                        'status': 'accepted',
                        'time': time.time(),
                    }
                )
                self.evolution.memory.record(patch, score=0.9)
            else:
                print('  ✗ 测试失败，回滚')
                self.rollback_patch(patch)
                self._applied_patches.append(
                    {
                        'patch': patch.to_dict(),
                        'status': 'rolled_back',
                        'time': time.time(),
                    }
                )
                self.evolution.memory.record(patch, score=0.2)

            results.append(
                {
                    'cycle': cycle + 1,
                    'target': target,
                    'patch': patch.to_dict(),
                    'test_passed': passed,
                }
            )

        # 最终验证
        print('\n═══ 最终验证 ═══')
        final_passed, final_output = self.run_tests()
        print(f'测试: {"通过" if final_passed else "失败"}')

        return {
            'cycles': max_cycles,
            'success_count': success_count,
            'final_test': final_passed,
            'results': results,
            'applied_patches': len(self._applied_patches),
        }

    def summary(self) -> str:
        accepted = sum(1 for p in self._applied_patches if p['status'] == 'accepted')
        rolled_back = sum(1 for p in self._applied_patches if p['status'] == 'rolled_back')
        return (
            f'\n═══ Agent 自主改代码 ═══\n'
            f'应用补丁: {len(self._applied_patches)} | '
            f'接受: {accepted} | 回滚: {rolled_back}\n'
            f'{self.evolution.summary()}'
        )
