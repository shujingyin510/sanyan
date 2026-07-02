"""Reviewer Agent — 独立代码审查

P50: ReviewerAgent — 独立代码审查（11条规则，含4条对抗补丁检测）

其他组件已拆分到独立文件：
  - agent_benchmark.py: RealBenchmark
  - agent_dashboard.py: EvolutionDashboard
  - agent_test_gen.py: TestGenerator
  - agent_history.py: PatchHistory
  - agent_loop_review.py: ReviewedEvolutionLoop
"""

import json
import os
import sqlite3
import statistics
import time
from typing import Dict, List, Optional

from agent_system.paths import db_path

ROOT = os.path.dirname(os.path.abspath(__file__))


# ── Reviewer Agent ──


class ReviewerAgent:
    """独立代码审查Agent：Coder的Patch必须通过审查才能接受"""

    DB_PATH = db_path('agent_review_history.db')

    # 审查规则
    RULES = {
        'no_critical_changes': {
            'check': lambda p: not any(k in p.get('target', '') for k in ['agent.san', 'decision.san']),
            'reason': '禁止修改Agent核心决策文件',
            'severity': 'block',
        },
        'no_magic_numbers': {
            'check': lambda p: not any(c.isdigit() and len(c) > 3 for c in p.get('after', '').split()),
            'reason': '避免硬编码魔法数字',
            'severity': 'warn',
        },
        'no_empty_rationale': {
            'check': lambda p: bool(p.get('rationale', '').strip()),
            'reason': '补丁必须有修改理由',
            'severity': 'block',
        },
        'max_lines_changed': {
            'check': lambda p: len(p.get('after', '').split('\n')) <= 20,
            'reason': '单次变更不超过20行',
            'severity': 'block',
        },
        'has_expected': {
            'check': lambda p: bool(p.get('expected', '').strip()),
            'reason': '补丁必须有预期收益',
            'severity': 'warn',
        },
        'no_delete_all': {
            'check': lambda p: not (p.get('action') == 'delete' and len(p.get('before', '').split('\n')) > 10),
            'reason': '禁止删除超过10行的代码块',
            'severity': 'block',
        },
        # 对抗补丁检测
        'no_redundant_cache': {
            'check': lambda p: (
                not (
                    '缓存' in p.get('rationale', '')
                    and (
                        p.get('after', '').count('cache') > p.get('before', '').count('cache') + 2
                        or p.get('after', '').count('_cache') > p.get('before', '').count('_cache') + 1
                    )
                )
            ),
            'reason': '禁止无意义缓存（缓存变量异常增加）',
            'severity': 'block',
        },
        'no_redundant_computation': {
            'check': lambda p: (
                not (
                    p.get('after', '').count('(') > p.get('before', '').count('(') * 1.5
                    and '优化' in p.get('rationale', '')
                )
            ),
            'reason': '禁止重复计算（函数调用数量异常增加）',
            'severity': 'block',
        },
        'no_wrong_inline': {
            'check': lambda p: (
                not ('内联' in p.get('rationale', '') and len(p.get('after', '')) > len(p.get('before', '')) * 2)
            ),
            'reason': '禁止错误内联（代码膨胀超过2倍）',
            'severity': 'block',
        },
        'no_wrong_loop_unroll': {
            'check': lambda p: (
                not (
                    '循环' in p.get('rationale', '')
                    and p.get('after', '').count('for') > p.get('before', '').count('for') + 3
                )
            ),
            'reason': '禁止错误循环展开（for循环数量异常增加）',
            'severity': 'block',
        },
        'no_code_bloat': {
            'check': lambda p: (
                len(p.get('after', '')) <= len(p.get('before', '')) * 1.5 or len(p.get('after', '')) < 500
            ),
            'reason': '禁止代码膨胀（超过1.5倍或500字符）',
            'severity': 'warn',
        },
    }

    def __init__(self):
        self._init_db()

    def _init_db(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.DB_PATH)
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS review_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patch_target TEXT,
                patch_action TEXT,
                patch_rationale TEXT,
                verdict TEXT,
                reasons TEXT,
                reviewer_score REAL,
                created_at REAL
            );
        """)
        conn.commit()
        conn.close()

    def review(self, patch_dict: Dict) -> Dict:
        """审查补丁"""
        issues = []
        block = False

        for rule_name, rule in self.RULES.items():
            try:
                passed = rule['check'](patch_dict)
                if not passed:
                    issues.append(
                        {
                            'rule': rule_name,
                            'reason': rule['reason'],
                            'severity': rule['severity'],
                        }
                    )
                    if rule['severity'] == 'block':
                        block = True
            except Exception:
                pass

        # 计算审查分数
        total_rules = len(self.RULES)
        passed_rules = total_rules - len(issues)
        score = passed_rules / total_rules if total_rules > 0 else 0

        # 最终裁决
        if block:
            verdict = 'reject'
        elif len(issues) > 2:
            verdict = 'revise'
        else:
            verdict = 'approve'

        result = {
            'verdict': verdict,
            'score': score,
            'issues': issues,
            'total_rules': total_rules,
            'passed_rules': passed_rules,
        }

        # 记录审查历史
        self._record_review(patch_dict, result)

        return result

    def _record_review(self, patch_dict: Dict, result: Dict):
        """记录审查历史"""
        conn = sqlite3.connect(self.DB_PATH)
        conn.execute(
            """
            INSERT INTO review_history
            (patch_target, patch_action, patch_rationale, verdict, reasons, reviewer_score, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
                patch_dict.get('target', ''),
                patch_dict.get('action', ''),
                patch_dict.get('rationale', ''),
                result['verdict'],
                json.dumps(result['issues'], ensure_ascii=False),
                result['score'],
                time.time(),
            ),
        )
        conn.commit()
        conn.close()

    def get_stats(self) -> Dict:
        """获取审查统计"""
        conn = sqlite3.connect(self.DB_PATH)
        rows = conn.execute('SELECT verdict, COUNT(*) FROM review_history GROUP BY verdict').fetchall()
        total = conn.execute('SELECT COUNT(*) FROM review_history').fetchone()[0]
        conn.close()

        stats = {'total': total}
        for verdict, count in rows:
            stats[verdict] = count
        return stats

    def summary(self) -> str:
        stats = self.get_stats()
        approve_rate = stats.get('approve', 0) / max(stats['total'], 1)
        return (
            f'审查: {stats["total"]}次 | '
            f'通过: {stats.get("approve", 0)} ({approve_rate:.0%}) | '
            f'拒绝: {stats.get("reject", 0)} | '
            f'修改: {stats.get("revise", 0)}'
        )


# ── Patch历史数据库 ──


class PatchHistory:
    """Patch历史数据库：收益/风险/回滚率（升级版）"""

    DB_PATH = db_path('agent_patch_history.db')

    def __init__(self):
        self._init_db()

    def _init_db(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.DB_PATH)
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS patch_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target TEXT,
                action TEXT,
                rationale TEXT,
                expected TEXT,
                before_lines INTEGER,
                after_lines INTEGER,
                test_passed INTEGER,
                reviewer_verdict TEXT,
                reviewer_score REAL,
                rolled_back INTEGER DEFAULT 0,
                rollback_reason TEXT,
                score REAL,
                duration REAL,
                created_at REAL,
                real_speedup REAL,
                real_memory_delta REAL,
                test_count INTEGER DEFAULT 0,
                new_tests_generated INTEGER DEFAULT 0,
                review_reason TEXT
            );
            CREATE TABLE IF NOT EXISTS patch_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target TEXT,
                optimization_type TEXT,
                success_count INTEGER DEFAULT 0,
                fail_count INTEGER DEFAULT 0,
                rollback_count INTEGER DEFAULT 0,
                avg_score REAL DEFAULT 0,
                avg_speedup REAL DEFAULT 0,
                avg_memory_delta REAL DEFAULT 0,
                total_tests INTEGER DEFAULT 0,
                last_used REAL
            );
        """)
        conn.commit()
        conn.close()

    def record_patch(
        self,
        patch_dict: Dict,
        test_passed: bool,
        reviewer_verdict: str = '',
        reviewer_score: float = 0,
        rolled_back: bool = False,
        rollback_reason: str = '',
        score: float = 0,
        duration: float = 0,
        real_speedup: float = 0,
        real_memory_delta: float = 0,
        test_count: int = 0,
        new_tests_generated: int = 0,
        review_reason: str = '',
    ):
        """记录补丁历史（升级版）"""
        before_lines = len(patch_dict.get('before', '').split('\n'))
        after_lines = len(patch_dict.get('after', '').split('\n'))

        conn = sqlite3.connect(self.DB_PATH)
        conn.execute(
            """
            INSERT INTO patch_history
            (target, action, rationale, expected, before_lines, after_lines,
             test_passed, reviewer_verdict, reviewer_score, rolled_back,
             rollback_reason, score, duration, created_at,
             real_speedup, real_memory_delta, test_count, new_tests_generated,
             review_reason)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                patch_dict.get('target', ''),
                patch_dict.get('action', ''),
                patch_dict.get('rationale', ''),
                patch_dict.get('expected', ''),
                before_lines,
                after_lines,
                1 if test_passed else 0,
                reviewer_verdict,
                reviewer_score,
                1 if rolled_back else 0,
                rollback_reason,
                score,
                duration,
                time.time(),
                real_speedup,
                real_memory_delta,
                test_count,
                new_tests_generated,
                review_reason,
            ),
        )

        # 更新模式统计
        opt_type = self._extract_opt_type(patch_dict.get('rationale', ''))
        target = patch_dict.get('target', '')
        self._update_pattern(
            conn, target, opt_type, test_passed, rolled_back, score, real_speedup, real_memory_delta, test_count
        )

        conn.commit()
        conn.close()

    def _extract_opt_type(self, rationale: str) -> str:
        """从理由中提取优化类型"""
        if '缓存' in rationale or 'cache' in rationale.lower():
            return 'cache'
        elif '循环' in rationale or 'loop' in rationale.lower():
            return 'loop'
        elif '内联' in rationale or 'inline' in rationale.lower():
            return 'inline'
        elif '内存' in rationale or 'memory' in rationale.lower():
            return 'memory'
        elif '位运算' in rationale or 'bit' in rationale.lower():
            return 'bitwise'
        else:
            return 'other'

    def _update_pattern(
        self,
        conn,
        target: str,
        opt_type: str,
        success: bool,
        rolled_back: bool,
        score: float,
        speedup: float = 0,
        memory_delta: float = 0,
        test_count: int = 0,
    ):
        """更新优化模式统计"""
        existing = conn.execute(
            'SELECT id FROM patch_patterns WHERE target=? AND optimization_type=?', (target, opt_type)
        ).fetchone()

        if existing:
            if success and not rolled_back:
                conn.execute(
                    """
                    UPDATE patch_patterns
                    SET success_count = success_count + 1,
                        avg_score = (avg_score + ?) / 2,
                        avg_speedup = (avg_speedup + ?) / 2,
                        avg_memory_delta = (avg_memory_delta + ?) / 2,
                        total_tests = total_tests + ?,
                        last_used = ?
                    WHERE id = ?
                """,
                    (score, speedup, memory_delta, test_count, time.time(), existing[0]),
                )
            else:
                conn.execute(
                    """
                    UPDATE patch_patterns
                    SET fail_count = fail_count + ?,
                        rollback_count = rollback_count + ?,
                        last_used = ?
                    WHERE id = ?
                """,
                    (1, 1 if rolled_back else 0, time.time(), existing[0]),
                )
        else:
            conn.execute(
                """
                INSERT INTO patch_patterns
                (target, optimization_type, success_count, fail_count, rollback_count,
                 avg_score, avg_speedup, avg_memory_delta, total_tests, last_used)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    target,
                    opt_type,
                    1 if success and not rolled_back else 0,
                    0 if success else 1,
                    1 if rolled_back else 0,
                    score,
                    speedup,
                    memory_delta,
                    test_count,
                    time.time(),
                ),
            )

    def query_success_rate(self, target: str, opt_type: Optional[str] = None) -> float:
        """查询成功率"""
        conn = sqlite3.connect(self.DB_PATH)
        if opt_type:
            row = conn.execute(
                'SELECT success_count, fail_count FROM patch_patterns WHERE target=? AND optimization_type=?',
                (target, opt_type),
            ).fetchone()
        else:
            row = conn.execute(
                'SELECT SUM(success_count), SUM(fail_count) FROM patch_patterns WHERE target=?', (target,)
            ).fetchone()
        conn.close()

        if not row or (row[0] + row[1]) == 0:
            return 0.5
        return row[0] / (row[0] + row[1])

    def query_rollback_rate(self, target: str, opt_type: Optional[str] = None) -> float:
        """查询回滚率"""
        conn = sqlite3.connect(self.DB_PATH)
        if opt_type:
            row = conn.execute(
                'SELECT rollback_count, success_count + fail_count FROM patch_patterns WHERE target=? AND optimization_type=?',
                (target, opt_type),
            ).fetchone()
        else:
            row = conn.execute(
                'SELECT SUM(rollback_count), SUM(success_count + fail_count) FROM patch_patterns WHERE target=?',
                (target,),
            ).fetchone()
        conn.close()

        if not row or row[1] == 0:
            return 0
        return row[0] / row[1]

    def get_risky_patterns(self, threshold: float = 0.3) -> List[Dict]:
        """获取高风险模式（回滚率>threshold）"""
        conn = sqlite3.connect(self.DB_PATH)
        rows = conn.execute(
            """
            SELECT target, optimization_type, rollback_count, success_count + fail_count as total
            FROM patch_patterns
            WHERE total >= 3 AND CAST(rollback_count AS REAL) / total > ?
            ORDER BY rollback_count DESC
        """,
            (threshold,),
        ).fetchall()
        conn.close()

        return [
            {
                'target': r[0],
                'opt_type': r[1],
                'rollback_rate': r[2] / r[3] if r[3] > 0 else 0,
                'total': r[3],
            }
            for r in rows
        ]

    def get_safe_patterns(self, min_trials: int = 5) -> List[Dict]:
        """获取安全模式（成功率>80%，回滚率<10%）"""
        conn = sqlite3.connect(self.DB_PATH)
        rows = conn.execute(
            """
            SELECT target, optimization_type, success_count, fail_count, rollback_count
            FROM patch_patterns
            WHERE success_count + fail_count >= ? AND
                  CAST(success_count AS REAL) / (success_count + fail_count) > 0.8 AND
                  CAST(rollback_count AS REAL) / (success_count + fail_count) < 0.1
            ORDER BY success_count DESC
        """,
            (min_trials,),
        ).fetchall()
        conn.close()

        return [
            {
                'target': r[0],
                'opt_type': r[1],
                'success_rate': r[2] / (r[2] + r[3]) if (r[2] + r[3]) > 0 else 0,
                'rollback_rate': r[4] / (r[2] + r[3]) if (r[2] + r[3]) > 0 else 0,
                'total': r[2] + r[3],
            }
            for r in rows
        ]

    # ── Analytics ──

    def get_analytics(self) -> Dict:
        """获取完整分析数据"""
        conn = sqlite3.connect(self.DB_PATH)

        # 基础统计
        total = conn.execute('SELECT COUNT(*) FROM patch_history').fetchone()[0]
        passed = conn.execute('SELECT COUNT(*) FROM patch_history WHERE test_passed=1').fetchone()[0]
        rolled_back = conn.execute('SELECT COUNT(*) FROM patch_history WHERE rolled_back=1').fetchone()[0]

        # 性能统计（带可信度权重）
        rows = conn.execute("""
            SELECT real_speedup, reviewer_score, test_count, real_memory_delta
            FROM patch_history WHERE real_speedup > 0
        """).fetchall()

        if rows:
            weighted_speedups = []
            for speedup, review_score, test_count, memory_delta in rows:
                # 可信度权重
                review_factor = review_score if review_score else 0.5
                test_factor = min(1.0, test_count / 1000)  # 1000测试为满分
                confidence = review_factor * 0.4 + test_factor * 0.6

                weighted_speedups.append(speedup * confidence)

            avg_speedup = statistics.mean(weighted_speedups) if weighted_speedups else 0
            raw_avg_speedup = statistics.mean([r[0] for r in rows])
        else:
            avg_speedup = 0
            raw_avg_speedup = 0

        # 内存统计
        avg_memory = (
            conn.execute('SELECT AVG(real_memory_delta) FROM patch_history WHERE real_memory_delta != 0').fetchone()[0]
            or 0
        )

        # 测试统计
        total_tests = conn.execute('SELECT SUM(test_count) FROM patch_history').fetchone()[0] or 0
        total_new_tests = conn.execute('SELECT SUM(new_tests_generated) FROM patch_history').fetchone()[0] or 0

        # 模式统计
        patterns = conn.execute("""
            SELECT target, optimization_type, success_count, fail_count, rollback_count,
                   avg_speedup, avg_memory_delta
            FROM patch_patterns
            WHERE success_count + fail_count >= 3
            ORDER BY CAST(success_count AS REAL) / (success_count + fail_count) DESC
        """).fetchall()

        # 最近7天
        week_ago = time.time() - 7 * 86400
        week_count = conn.execute('SELECT COUNT(*) FROM patch_history WHERE created_at > ?', (week_ago,)).fetchone()[0]

        conn.close()

        return {
            'total_patches': total,
            'success_count': passed,
            'rollback_count': rolled_back,
            'success_rate': passed / max(total, 1),
            'rollback_rate': rolled_back / max(total, 1),
            'avg_speedup': avg_speedup,
            'raw_avg_speedup': raw_avg_speedup,
            'avg_memory_delta': avg_memory,
            'total_tests_run': total_tests,
            'total_new_tests': total_new_tests,
            'week_patches': week_count,
            'patterns': [
                {
                    'target': r[0],
                    'opt_type': r[1],
                    'success_rate': r[2] / (r[2] + r[3]) if (r[2] + r[3]) > 0 else 0,
                    'rollback_rate': r[4] / (r[2] + r[3]) if (r[2] + r[3]) > 0 else 0,
                    'avg_speedup': r[5],
                    'avg_memory_delta': r[6],
                }
                for r in patterns
            ],
        }

    def get_top_patterns(self, metric: str = 'success_rate', limit: int = 10) -> List[Dict]:
        """获取Top模式"""
        analytics = self.get_analytics()
        patterns = analytics['patterns']

        if metric == 'success_rate':
            patterns.sort(key=lambda x: -x.get('success_rate', 0))
        elif metric == 'speedup':
            patterns.sort(key=lambda x: -x.get('avg_speedup', 0))
        elif metric == 'rollback':
            patterns.sort(key=lambda x: -x.get('rollback_rate', 0))

        return patterns[:limit]

    def summary(self) -> str:
        conn = sqlite3.connect(self.DB_PATH)
        total = conn.execute('SELECT COUNT(*) FROM patch_history').fetchone()[0]
        passed = conn.execute('SELECT COUNT(*) FROM patch_history WHERE test_passed=1').fetchone()[0]
        rolled_back = conn.execute('SELECT COUNT(*) FROM patch_history WHERE rolled_back=1').fetchone()[0]
        patterns = conn.execute('SELECT COUNT(*) FROM patch_patterns').fetchone()[0]
        conn.close()

        success_rate = passed / max(total, 1)
        rollback_rate = rolled_back / max(total, 1)

        return f'Patch历史: {total}条 | 成功率: {success_rate:.0%} | 回滚率: {rollback_rate:.0%} | 模式: {patterns}个'


# ── 真实 Benchmark ──


class RealBenchmark:
    """真实基准测试：before/after 耗时对比"""

    def __init__(self):
        self._results: List[Dict] = []

    def measure(self, func, iterations: int = 5) -> Dict:
        """测量函数执行时间"""
        import statistics

        times = []
        for _ in range(iterations):
            start = time.time()
            try:
                func()
            except Exception:
                pass
            times.append(time.time() - start)

        if not times:
            return {'avg_ms': 0, 'min_ms': 0, 'max_ms': 0, 'stdev': 0}

        avg = statistics.mean(times)
        return {
            'avg_ms': avg * 1000,
            'min_ms': min(times) * 1000,
            'max_ms': max(times) * 1000,
            'stdev': statistics.stdev(times) * 1000 if len(times) > 1 else 0,
            'iterations': len(times),
        }

    def compare(self, before_func, after_func, iterations: int = 5) -> Dict:
        """对比 before/after 性能"""
        before = self.measure(before_func, iterations)
        after = self.measure(after_func, iterations)

        # 计算提升
        if before['avg_ms'] > 0:
            speedup = (before['avg_ms'] - after['avg_ms']) / before['avg_ms']
        else:
            speedup = 0

        result = {
            'before': before,
            'after': after,
            'speedup': speedup,
            'speedup_pct': f'{speedup * 100:.1f}%',
            'improved': speedup > 0,
        }

        self._results.append(result)
        return result

    def benchmark_file(self, file_path: str, func_name: str, iterations: int = 3) -> Dict:
        """对文件中的函数进行基准测试"""
        try:
            import importlib.util

            spec = importlib.util.spec_from_file_location('module', file_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            func = getattr(module, func_name, None)
            if func is None:
                return {'error': f'函数 {func_name} 未找到'}

            return self.measure(func, iterations)
        except Exception as e:
            return {'error': str(e)}

    def summary(self) -> str:
        if not self._results:
            return '无基准测试数据'
        improved = sum(1 for r in self._results if r['improved'])
        avg_speedup = sum(r['speedup'] for r in self._results) / len(self._results)
        return (
            f'基准测试: {len(self._results)}次 | '
            f'提升: {improved}/{len(self._results)} | '
            f'平均提升: {avg_speedup * 100:.1f}%'
        )


# ── Evolution Dashboard ──


class EvolutionDashboard:
    """进化仪表盘：可视化进化状态"""

    def __init__(
        self,
        patch_history: Optional[PatchHistory] = None,
        benchmark: Optional[RealBenchmark] = None,
        reviewer: Optional[ReviewerAgent] = None,
    ):
        self.patch_history = patch_history or PatchHistory()
        self.benchmark = benchmark or RealBenchmark()
        self.reviewer = reviewer or ReviewerAgent()

    def render(self) -> str:
        """渲染仪表盘"""
        analytics = self.patch_history.get_analytics()
        review_stats = self.reviewer.get_stats()

        lines = [
            '╔══════════════════════════════════════════════════════╗',
            '║          Evolution Dashboard                        ║',
            '╠══════════════════════════════════════════════════════╣',
            f'║  总补丁数:     {analytics["total_patches"]:40d}║',
            f'║  成功:         {analytics["success_count"]:40d}║',
            f'║  回滚:         {analytics["rollback_count"]:40d}║',
            f'║  成功率:       {analytics["success_rate"]:.1%}{" " * 37}║',
            f'║  回滚率:       {analytics["rollback_rate"]:.1%}{" " * 37}║',
            '╠══════════════════════════════════════════════════════╣',
            f'║  加权提升:     {analytics["avg_speedup"]:.1f}% (含可信度权重){" " * 18}║',
            f'║  原始提升:     {analytics.get("raw_avg_speedup", 0):.1f}% (未加权){" " * 22}║',
            f'║  平均内存变化: {analytics["avg_memory_delta"]:.1f}KB{" " * 34}║',
            f'║  总测试数:     {analytics["total_tests_run"]:40d}║',
            f'║  新生成测试:   {analytics["total_new_tests"]:40d}║',
            f'║  本周补丁:     {analytics["week_patches"]:40d}║',
            '╠══════════════════════════════════════════════════════╣',
            '║  审查统计                                          ║',
            f'║  总审查:       {review_stats["total"]:40d}║',
            f'║  通过:         {review_stats.get("approve", 0):40d}║',
            f'║  拒绝:         {review_stats.get("reject", 0):40d}║',
            '╠══════════════════════════════════════════════════════╣',
            '║  Top 模式 (按成功率)                               ║',
        ]

        top_patterns = self.patch_history.get_top_patterns('success_rate', 5)
        for p in top_patterns:
            name = f'{p["target"]}:{p["opt_type"]}'
            rate = f'{p["success_rate"]:.0%}'
            speedup = f'+{p["avg_speedup"]:.1f}%' if p['avg_speedup'] > 0 else '0%'
            lines.append(f'║    {name:25s} {rate:6s} {speedup:10s}        ║')

        lines.extend(
            [
                '╚══════════════════════════════════════════════════════╝',
            ]
        )

        return '\n'.join(lines)


class TestGenerator:
    """测试用例生成器：根据代码变更生成新测试"""

    # 测试模板
    TEMPLATES = {
        'function': {
            'pattern': r'def\s+(\w+)\s*\(([^)]*)\)',
            'template': '''
def test_{func_name}():
    """测试 {func_name}"""
    # TODO: 实现测试
    result = {func_name}({args})
    assert result is not None
''',
        },
        'class': {
            'pattern': r'class\s+(\w+)',
            'template': '''
def test_{class_name}_init():
    """测试 {class_name} 初始化"""
    obj = {class_name}()
    assert obj is not None
''',
        },
        'edge_case': {
            'pattern': None,
            'template': '''
def test_{func_name}_edge_cases():
    """测试 {func_name} 边界情况"""
    # 空输入
    # None输入
    # 负数输入
    # 超大输入
    pass
''',
        },
    }

    def __init__(self):
        self._generated_tests: List[Dict] = []

    def generate_from_code(self, code: str, file_path: str) -> List[str]:
        """从代码生成测试"""
        import re

        tests = []
        lines = code.split('\n')

        # 提取函数定义
        func_pattern = re.compile(r'def\s+(\w+)\s*\(([^)]*)\)')
        for i, line in enumerate(lines):
            match = func_pattern.search(line)
            if match:
                func_name = match.group(1)
                match.group(2)

                # 跳过私有函数和测试函数
                if func_name.startswith('_') or func_name.startswith('test_'):
                    continue

                # 生成基础测试
                test_code = f'''
def test_{func_name}():
    """测试 {func_name}"""
    # 来源: {file_path}:{i + 1}
    # TODO: 实现具体测试逻辑
    pass
'''
                tests.append(test_code)

        return tests

    def generate_from_patch(self, patch_dict: Dict) -> List[str]:
        """从补丁生成测试"""
        target = patch_dict.get('target', '')
        rationale = patch_dict.get('rationale', '')

        # 根据补丁类型生成针对性测试
        tests = []

        if '缓存' in rationale or 'cache' in rationale:
            tests.append(f'''
def test_{target.replace('.', '_').replace('/', '_')}_cache():
    """测试缓存优化是否正确"""
    # 验证缓存命中
    # 验证缓存失效
    # 验证缓存一致性
    pass
''')

        if '循环' in rationale or 'loop' in rationale:
            tests.append(f'''
def test_{target.replace('.', '_').replace('/', '_')}_loop():
    """测试循环优化是否正确"""
    # 验证循环次数
    # 验证循环边界
    # 验证循环结果
    pass
''')

        return tests

    def generate_edge_cases(self, func_name: str, params: List[str]) -> str:
        """生成边界测试"""
        param_list = ', '.join('None' if i == 0 else '0' for i in range(len(params)))

        return f'''
def test_{func_name}_edge_cases():
    """测试 {func_name} 边界情况"""
    # None输入
    try:
        {func_name}({param_list})
    except (TypeError, ValueError):
        pass

    # 空输入
    try:
        {func_name}({', '.join('""' if 'str' in p.lower() else '[]' for p in params)})
    except (TypeError, ValueError):
        pass
'''

    def save_tests(self, tests: List[str], output_path: str):
        """保存生成的测试"""
        with open(os.path.join(ROOT, output_path), 'w', encoding='utf-8') as f:
            f.write('"""自动生成的测试用例"""\n\n')
            for test in tests:
                f.write(test)
                f.write('\n\n')

        self._generated_tests.append(
            {
                'path': output_path,
                'count': len(tests),
                'time': time.time(),
            }
        )

    def summary(self) -> str:
        total = sum(t['count'] for t in self._generated_tests)
        return f'生成测试: {len(self._generated_tests)}文件, {total}个用例'


# ── 整合：带审查的进化循环 ──


class ReviewedEvolutionLoop:
    """带审查的进化循环：Coder→Reviewer→Test→Accept/Rollback"""

    def __init__(self):
        self.reviewer = ReviewerAgent()
        self.patch_history = PatchHistory()
        self.test_generator = TestGenerator()
        self._cycle_count = 0

    def run_cycle(self, patch_dict: Dict, test_func=None) -> Dict:
        """运行一次带审查的进化循环"""
        self._cycle_count += 1
        cycle_start = time.time()
        print(f'\n═══ 审查循环 #{self._cycle_count} ═══')

        # 1. Coder 生成补丁
        print(f'[Coder] 生成补丁: {patch_dict.get("target", "?")}')
        print(f'  理由: {patch_dict.get("rationale", "?")}')

        # 2. Reviewer 审查
        print('[Reviewer] 审查中...')
        review_result = self.reviewer.review(patch_dict)
        print(f'  裁决: {review_result["verdict"]} (分数: {review_result["score"]:.2f})')

        if review_result['issues']:
            for issue in review_result['issues']:
                print(f'  - [{issue["severity"]}] {issue["reason"]}')

        # 3. 根据审查结果决定
        if review_result['verdict'] == 'reject':
            print('[结果] 审查拒绝，跳过')
            self.patch_history.record_patch(
                patch_dict,
                False,
                reviewer_verdict='reject',
                reviewer_score=review_result['score'],
                rolled_back=True,
                rollback_reason='reviewer_reject',
            )
            return {
                'cycle': self._cycle_count,
                'verdict': 'reject',
                'review': review_result,
            }

        # 4. 运行测试
        print('[Test] 运行测试...')
        if test_func:
            test_passed, test_output = test_func(patch_dict)
        else:
            test_passed, _test_output = True, '无测试函数'

        print(f'  结果: {"通过" if test_passed else "失败"}')

        # 5. 根据测试结果决定
        if test_passed:
            print('[结果] 接受补丁')
            self.patch_history.record_patch(
                patch_dict,
                True,
                reviewer_verdict=review_result['verdict'],
                reviewer_score=review_result['score'],
                score=0.9,
                duration=time.time() - cycle_start,
            )
            return {
                'cycle': self._cycle_count,
                'verdict': 'accept',
                'review': review_result,
                'test_passed': True,
            }
        else:
            print('[结果] 测试失败，回滚')
            self.patch_history.record_patch(
                patch_dict,
                False,
                reviewer_verdict=review_result['verdict'],
                reviewer_score=review_result['score'],
                rolled_back=True,
                rollback_reason='test_failed',
                duration=time.time() - cycle_start,
            )
            return {
                'cycle': self._cycle_count,
                'verdict': 'rollback',
                'review': review_result,
                'test_passed': False,
            }

    def run(self, patches: List[Dict], test_func=None) -> Dict:
        """运行多轮"""
        results = []
        for patch in patches:
            result = self.run_cycle(patch, test_func)
            results.append(result)

        accept_count = sum(1 for r in results if r['verdict'] == 'accept')
        reject_count = sum(1 for r in results if r['verdict'] == 'reject')
        rollback_count = sum(1 for r in results if r['verdict'] == 'rollback')

        return {
            'cycles': len(results),
            'accepted': accept_count,
            'rejected': reject_count,
            'rolled_back': rollback_count,
            'results': results,
        }

    def summary(self) -> str:
        return (
            f'\n═══ 带审查的进化循环 ═══\n'
            f'{self.reviewer.summary()}\n'
            f'{self.patch_history.summary()}\n'
            f'{self.test_generator.summary()}'
        )
