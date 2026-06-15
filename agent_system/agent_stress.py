"""进化压力测试 — Phase 1.75

实验A: 1000轮连续进化 — 观察长期稳定性
实验B: Reviewer退化测试 — 禁用规则观察系统退化
实验C: 历史污染测试 — 插入坏Patch观察MetaConfig误导

Frozen Core（不可修改）:
  - Reviewer
  - TernaryEngine
  - PatchHistory
"""

import os
import random
import statistics
from typing import Dict, List

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ── 实验A: 1000轮连续进化 ──


class LongTermStabilityTest:
    """1000轮连续进化：观察长期稳定性"""

    def __init__(self):
        self.history: List[Dict] = []

    def run(self, n: int = 1000) -> Dict:
        """运行n轮连续进化"""
        print(f'\n═══ 实验A: {n}轮连续进化 ═══')

        self.history = []
        accept_count = 0
        rollback_count = 0
        speedups = []

        for i in range(n):
            # 模拟进化
            speedup = self._simulate_evolution(i, n)
            accepted = speedup > 0

            if accepted:
                accept_count += 1
                speedups.append(speedup)
            else:
                rollback_count += 1

            self.history.append(
                {
                    'round': i + 1,
                    'speedup': speedup,
                    'accepted': accepted,
                    'cumulative_avg': statistics.mean(speedups) if speedups else 0,
                }
            )

            if (i + 1) % 200 == 0:
                avg = statistics.mean(speedups) if speedups else 0
                print(f'  轮次 {i + 1}: 平均提升 {avg:.2f}% (接受 {accept_count}, 回滚 {rollback_count})')

        return self._analyze(n, accept_count, rollback_count, speedups)

    def _simulate_evolution(self, round_num: int, total: int) -> float:
        """模拟进化收益（递减+噪声）"""
        # 基础收益递减
        base = 8.0 * (0.98 ** (round_num / 50))

        # 随机噪声
        noise = random.gauss(0, 1.5)

        # 偶尔大收益（探索新区域）
        if random.random() < 0.05:
            base += random.uniform(3, 8)

        return max(0, base + noise)

    def _analyze(self, n: int, accepts: int, rollbacks: int, speedups: List[float]) -> Dict:
        """分析结果"""
        # 分段分析
        segments = []
        segment_size = n // 5
        for i in range(5):
            start = i * segment_size
            end = (i + 1) * segment_size
            segment_speedups = [self.history[j]['speedup'] for j in range(start, end) if self.history[j]['accepted']]
            segments.append(
                {
                    'round': f'{start + 1}-{end}',
                    'avg_speedup': statistics.mean(segment_speedups) if segment_speedups else 0,
                    'count': len(segment_speedups),
                }
            )

        # 收敛检查
        recent = self.history[-50:]
        recent_speedups = [h['speedup'] for h in recent if h['accepted']]
        converged = False
        if recent_speedups:
            stdev = statistics.stdev(recent_speedups) if len(recent_speedups) > 1 else 0
            converged = stdev < 1.0

        return {
            'total_rounds': n,
            'accepts': accepts,
            'rollbacks': rollbacks,
            'accept_rate': accepts / n,
            'avg_speedup': statistics.mean(speedups) if speedups else 0,
            'median_speedup': statistics.median(speedups) if speedups else 0,
            'stdev_speedup': statistics.stdev(speedups) if len(speedups) > 1 else 0,
            'segments': segments,
            'converged': converged,
            'final_50_avg': statistics.mean(recent_speedups) if recent_speedups else 0,
        }


# ── 实验B: Reviewer退化测试 ──


class ReviewerDegradationTest:
    """Reviewer退化测试：禁用规则观察系统退化"""

    def __init__(self):
        self.results: List[Dict] = []

    def run(self, n: int = 200) -> Dict:
        """运行退化测试"""
        print(f'\n═══ 实验B: Reviewer退化测试 ({n}轮) ═══')

        # 基线：完整Reviewer
        baseline = self._run_with_reviewer(n, disabled_rules=[])
        print(f'  基线 (完整Reviewer): 接受率 {baseline["accept_rate"]:.1%}')

        # 退化1：禁用1条规则
        deg1 = self._run_with_reviewer(n, disabled_rules=['no_redundant_cache'])
        print(f'  退化1 (禁用no_redundant_cache): 接受率 {deg1["accept_rate"]:.1%}')

        # 退化2：禁用2条规则
        deg2 = self._run_with_reviewer(n, disabled_rules=['no_redundant_cache', 'no_code_bloat'])
        print(f'  退化2 (禁用2条): 接受率 {deg2["accept_rate"]:.1%}')

        # 退化3：禁用所有对抗规则
        deg3 = self._run_with_reviewer(
            n,
            disabled_rules=[
                'no_redundant_cache',
                'no_redundant_computation',
                'no_wrong_inline',
                'no_wrong_loop_unroll',
                'no_code_bloat',
            ],
        )
        print(f'  退化3 (禁用所有对抗规则): 接受率 {deg3["accept_rate"]:.1%}')

        return {
            'baseline': baseline,
            'degradation_1': deg1,
            'degradation_2': deg2,
            'degradation_3': deg3,
        }

    def _run_with_reviewer(self, n: int, disabled_rules: List[str]) -> Dict:
        """使用指定规则运行"""
        accept_count = 0
        bad_accepted = 0

        for _ in range(n):
            # 生成随机Patch（70%好，30%坏）
            is_good = random.random() < 0.7
            if is_good:
                patch = {
                    'target': f'file_{random.randint(0, 4)}.py',
                    'action': 'replace',
                    'before': 'old code',
                    'after': 'new code',
                    'rationale': '优化：减少重复计算',
                    'expected': '提升5%',
                }
            else:
                # 坏Patch
                bad_type = random.choice(['cache', 'inline', 'loop'])
                if bad_type == 'cache':
                    patch = {
                        'target': 'vm.py',
                        'action': 'replace',
                        'before': '    x = compute(a, b)',
                        'after': '    _cache_x = compute(a, b)\n    x = _cache_x',
                        'rationale': '缓存优化',
                        'expected': '提升5%',
                    }
                elif bad_type == 'inline':
                    patch = {
                        'target': 'ternary_core.py',
                        'action': 'replace',
                        'before': 'def add(a, b): return a + b',
                        'after': 'def add(a, b):\n    result = 0\n    result = result + a\n    result = result + b\n    return result',
                        'rationale': '内联优化',
                        'expected': '提升3%',
                    }
                else:
                    patch = {
                        'target': 'vm.py',
                        'action': 'replace',
                        'before': 'for i in range(10): process(i)',
                        'after': 'for i in range(10): process(i)\n' * 4,
                        'rationale': '循环优化',
                        'expected': '提升20%',
                    }

            # 审查
            from agent_system.agent_review import ReviewerAgent

            reviewer = ReviewerAgent()
            original_rules = reviewer.RULES.copy()

            # 禁用指定规则
            for rule in disabled_rules:
                reviewer.RULES.pop(rule, None)

            result = reviewer.review(patch)
            reviewer.RULES = original_rules

            if result['verdict'] == 'approve':
                accept_count += 1
                if not is_good:
                    bad_accepted += 1

        return {
            'total': n,
            'accepts': accept_count,
            'accept_rate': accept_count / n,
            'bad_accepted': bad_accepted,
            'bad_rate': bad_accepted / n,
        }


# ── 实验C: 历史污染测试 ──


class HistoryPollutionTest:
    """历史污染测试：插入坏Patch观察MetaConfig误导"""

    def __init__(self):
        self.results: List[Dict] = []

    def run(self, n_good: int = 50, n_bad: int = 10) -> Dict:
        """运行污染测试"""
        print(f'\n═══ 实验C: 历史污染测试 (好{n_good} + 坏{n_bad}) ═══')

        # 生成正常历史
        good_history = []
        for i in range(n_good):
            good_history.append(
                {
                    'target': f'file_{i % 5}.py',
                    'opt_type': random.choice(['cache', 'loop', 'inline']),
                    'success': True,
                    'speedup': random.uniform(3, 10),
                }
            )

        # 生成污染历史
        bad_history = []
        for i in range(n_bad):
            bad_history.append(
                {
                    'target': f'file_{i % 5}.py',
                    'opt_type': random.choice(['cache', 'loop', 'inline']),
                    'success': True,  # 假装成功
                    'speedup': random.uniform(15, 25),  # 虚假高收益
                }
            )

        # 合并
        all_history = good_history + bad_history
        random.shuffle(all_history)

        # 计算污染前的平均收益
        pre_pollution_avg = statistics.mean([h['speedup'] for h in good_history])

        # 计算污染后的平均收益
        post_pollution_avg = statistics.mean([h['speedup'] for h in all_history])

        # 按类型分析
        type_analysis = {}
        for h in all_history:
            t = h['opt_type']
            if t not in type_analysis:
                type_analysis[t] = {'count': 0, 'total_speedup': 0}
            type_analysis[t]['count'] += 1
            type_analysis[t]['total_speedup'] += h['speedup']

        for t, stats in type_analysis.items():
            stats['avg_speedup'] = stats['total_speedup'] / stats['count']

        # 检测污染
        suspected_pollution = []
        for t, stats in type_analysis.items():
            if stats['avg_speedup'] > pre_pollution_avg * 1.5:
                suspected_pollution.append(t)

        return {
            'good_count': n_good,
            'bad_count': n_bad,
            'pre_pollution_avg': pre_pollution_avg,
            'post_pollution_avg': post_pollution_avg,
            'pollution_impact': post_pollution_avg - pre_pollution_avg,
            'type_analysis': type_analysis,
            'suspected_pollution': suspected_pollution,
            'can_detect': len(suspected_pollution) > 0,
        }


# ── 整合压力测试 ──


class EvolutionStressTest:
    """进化压力测试：整合所有实验"""

    def __init__(self):
        self.stability = LongTermStabilityTest()
        self.degradation = ReviewerDegradationTest()
        self.pollution = HistoryPollutionTest()

    def run_all(
        self, n_stability: int = 500, n_degradation: int = 200, n_pollution_good: int = 50, n_pollution_bad: int = 10
    ) -> Dict:
        """运行所有压力测试"""
        print('\n' + '=' * 60)
        print('  进化压力测试 — Phase 1.75')
        print('=' * 60)

        # 实验A
        stability_result = self.stability.run(n_stability)

        # 实验B
        degradation_result = self.degradation.run(n_degradation)

        # 实验C
        pollution_result = self.pollution.run(n_pollution_good, n_pollution_bad)

        return {
            'stability': stability_result,
            'degradation': degradation_result,
            'pollution': pollution_result,
        }

    def print_report(self, report: Dict):
        """打印压力测试报告"""
        print('\n' + '=' * 60)
        print('  压力测试报告')
        print('=' * 60)

        # 实验A
        s = report['stability']
        print(f'\n┌─ 实验A: 长期稳定性 ({s["total_rounds"]}轮) ────────────────┐')
        print(f'│  接受:       {s["accepts"]:4d} ({s["accept_rate"]:.1%})           │')
        print(f'│  回滚:       {s["rollbacks"]:4d}                          │')
        print(f'│  平均提升:   {s["avg_speedup"]:.2f}%                        │')
        print(f'│  中位数:     {s["median_speedup"]:.2f}%                        │')
        print(f'│  标准差:     {s["stdev_speedup"]:.2f}%                        │')
        print(f'│  已收敛:     {"是" if s["converged"] else "否"}                              │')
        print(f'│  最后50轮:   {s["final_50_avg"]:.2f}%                        │')
        print('│                                              │')
        print('│  分段趋势:                                     │')
        for seg in s['segments']:
            print(f'│    {seg["round"]:>7s}: {seg["avg_speedup"]:.2f}% ({seg["count"]:3d}轮)    │')
        print('└──────────────────────────────────────────────────────┘')

        # 实验B
        d = report['degradation']
        print('\n┌─ 实验B: Reviewer退化测试 ──────────────────────────┐')
        print(f'│  基线 (完整):    接受率 {d["baseline"]["accept_rate"]:.1%}             │')
        print(f'│  退化1 (禁1条):  接受率 {d["degradation_1"]["accept_rate"]:.1%}             │')
        print(f'│  退化2 (禁2条):  接受率 {d["degradation_2"]["accept_rate"]:.1%}             │')
        print(f'│  退化3 (禁所有): 接受率 {d["degradation_3"]["accept_rate"]:.1%}             │')
        print('│                                              │')
        print('│  坏Patch放过率:                               │')
        print(f'│    基线:     {d["baseline"]["bad_rate"]:.1%}                          │')
        print(f'│    退化1:    {d["degradation_1"]["bad_rate"]:.1%}                          │')
        print(f'│    退化2:    {d["degradation_2"]["bad_rate"]:.1%}                          │')
        print(f'│    退化3:    {d["degradation_3"]["bad_rate"]:.1%}                          │')
        print('└──────────────────────────────────────────────────────┘')

        # 实验C
        p = report['pollution']
        print('\n┌─ 实验C: 历史污染测试 ────────────────────────────┐')
        print(f'│  正常历史:     {p["good_count"]:3d}条                             │')
        print(f'│  污染历史:     {p["bad_count"]:3d}条                             │')
        print(f'│  污染前均值:   {p["pre_pollution_avg"]:.2f}%                        │')
        print(f'│  污染后均值:   {p["post_pollution_avg"]:.2f}%                        │')
        print(f'│  污染影响:     {p["pollution_impact"]:+.2f}%                       │')
        print(f'│  可检测污染:   {"是" if p["can_detect"] else "否"}                              │')
        if p['suspected_pollution']:
            print(f'│  疑似污染类型: {", ".join(p["suspected_pollution"]):30s}│')
        print('└──────────────────────────────────────────────────────┘')

        # 汇总
        print('\n┌─ 汇总 ─────────────────────────────────────────────┐')
        print(f'│  长期稳定性:   {"✓ 通过" if s["converged"] else "✗ 未收敛"}                          │')
        print(
            f'│  Reviewer退化: {"✓ 可检测" if d["degradation_3"]["bad_rate"] > d["baseline"]["bad_rate"] * 2 else "✗ 不可检测"}                          │'
        )
        print(f'│  历史污染:     {"✓ 可检测" if p["can_detect"] else "✗ 不可检测"}                          │')
        print('└──────────────────────────────────────────────────────┘')
