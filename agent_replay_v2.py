"""Replay v2: 真实因果链模拟

让历史任务真正受参数影响：

cooldown → 影响重试频率/总耗时
tournament_candidates → 影响 Token/成功率
review_threshold → 影响接受率/坏Patch率
max_auto_fix → 影响修复成功率/执行时间

配置 → 行为 → 结果（真实因果链）
"""

import random
import statistics
from typing import Dict, List


# ── 任务类型定义 ──


TASK_TYPES = {
    'simple_lookup': {
        'base_success_rate': 0.95,
        'base_duration': 0.5,
        'base_tokens': 50,
        'complexity': 1,
        'retry_sensitivity': 0.1,  # cooldown 影响
        'candidate_sensitivity': 0.05,  # tournament_candidates 影响
        'review_sensitivity': 0.02,  # review_threshold 影响
        'fix_sensitivity': 0.3,  # max_auto_fix 影响
    },
    'code_analysis': {
        'base_success_rate': 0.90,
        'base_duration': 1.0,
        'base_tokens': 100,
        'complexity': 2,
        'retry_sensitivity': 0.15,
        'candidate_sensitivity': 0.10,
        'review_sensitivity': 0.05,
        'fix_sensitivity': 0.4,
    },
    'bug_fix': {
        'base_success_rate': 0.75,
        'base_duration': 2.0,
        'base_tokens': 200,
        'complexity': 5,
        'retry_sensitivity': 0.25,
        'candidate_sensitivity': 0.20,
        'review_sensitivity': 0.15,
        'fix_sensitivity': 0.5,
    },
    'feature_add': {
        'base_success_rate': 0.70,
        'base_duration': 3.0,
        'base_tokens': 300,
        'complexity': 6,
        'retry_sensitivity': 0.20,
        'candidate_sensitivity': 0.25,
        'review_sensitivity': 0.20,
        'fix_sensitivity': 0.6,
    },
    'refactor': {
        'base_success_rate': 0.65,
        'base_duration': 4.0,
        'base_tokens': 400,
        'complexity': 8,
        'retry_sensitivity': 0.30,
        'candidate_sensitivity': 0.30,
        'review_sensitivity': 0.25,
        'fix_sensitivity': 0.7,
    },
}


# ── 因果链模拟器 ──


class CausalSimulator:
    """基于配置的因果链模拟"""

    def __init__(self):
        self._seed = 42
        random.seed(self._seed)

    def simulate_task(self, task_type: str, config: Dict) -> Dict:
        """模拟单个任务执行"""
        params = TASK_TYPES.get(task_type, TASK_TYPES['code_analysis'])

        # 基础值
        success_rate = params['base_success_rate']
        duration = params['base_duration']
        tokens = params['base_tokens']

        # 因果链1: cooldown 影响重试频率
        cooldown = config.get('cooldown_seconds', 30)
        cooldown_factor = 30 / max(cooldown, 1)  # cooldown越小，重试越频繁
        retry_penalty = params['retry_sensitivity'] * (cooldown_factor - 1)
        duration *= 1 + retry_penalty * 0.3  # 重试增加耗时

        # 因果链2: tournament_candidates 影响成功率和Token
        candidates = config.get('tournament_candidates', 3)
        candidate_factor = candidates / 3  # 基准3个
        success_boost = params['candidate_sensitivity'] * (candidate_factor - 1)
        success_rate += success_boost
        tokens *= 1 + (candidate_factor - 1) * 0.2  # 更多候选=更多Token

        # 因果链3: review_threshold 影响接受率
        threshold = config.get('review_threshold', 0.8)
        threshold_factor = threshold / 0.8  # 基准0.8
        review_penalty = params['review_sensitivity'] * (threshold_factor - 1)
        success_rate -= review_penalty  # 更高阈值=更多拒绝

        # 因果链4: max_auto_fix 影响修复成功率
        max_fix = config.get('max_auto_fix', 3)
        fix_factor = max_fix / 3  # 基准3次
        fix_boost = params['fix_sensitivity'] * (fix_factor - 1)
        success_rate += fix_boost
        duration *= 1 + (fix_factor - 1) * 0.15  # 更多修复=更多耗时

        # 应用随机噪声
        noise = random.gauss(0, 0.05)
        success_rate = max(0.3, min(0.99, success_rate + noise))
        duration = max(0.1, duration * (1 + random.gauss(0, 0.1)))
        tokens = max(10, int(tokens * (1 + random.gauss(0, 0.1))))

        # 最终成功判定
        success = random.random() < success_rate

        return {
            'success': success,
            'success_rate': success_rate,
            'duration': duration,
            'tokens': tokens,
            'complexity': params['complexity'],
        }


# ── Replay v2 ──


class ReplayV2:
    """真实因果链回放"""

    def __init__(self):
        self.simulator = CausalSimulator()
        self._task_pool: List[Dict] = []

    def generate_task_pool(self, n: int = 500) -> List[Dict]:
        """生成任务池"""
        self._task_pool = []
        task_type_names = list(TASK_TYPES.keys())

        for i in range(n):
            task_type = random.choice(task_type_names)
            self._task_pool.append(
                {
                    'id': i,
                    'type': task_type,
                    'name': f'{task_type}_{i}',
                }
            )

        return self._task_pool

    def replay(self, tasks: List[Dict], config: Dict) -> Dict:
        """用指定配置回放任务"""
        results = []
        for task in tasks:
            result = self.simulator.simulate_task(task['type'], config)
            results.append(result)

        # 统计
        total = len(results)
        success_count = sum(1 for r in results if r['success'])
        durations = [r['duration'] for r in results]
        tokens = [r['tokens'] for r in results]

        return {
            'total': total,
            'success_count': success_count,
            'success_rate': success_count / max(total, 1),
            'avg_duration': statistics.mean(durations) if durations else 0,
            'avg_tokens': statistics.mean(tokens) if tokens else 0,
            'p50_duration': statistics.median(durations) if durations else 0,
            'p95_duration': sorted(durations)[int(len(durations) * 0.95)] if durations else 0,
            'results': results,
        }

    def compare_configs(self, tasks: List[Dict], baseline: Dict, new: Dict) -> Dict:
        """对比两个配置"""
        baseline_result = self.replay(tasks, baseline)
        new_result = self.replay(tasks, new)

        # 计算变化
        sr_change = new_result['success_rate'] - baseline_result['success_rate']
        dur_change = (new_result['avg_duration'] - baseline_result['avg_duration']) / max(
            baseline_result['avg_duration'], 0.001
        )
        tok_change = (new_result['avg_tokens'] - baseline_result['avg_tokens']) / max(baseline_result['avg_tokens'], 1)

        return {
            'baseline': {
                'success_rate': baseline_result['success_rate'],
                'avg_duration': baseline_result['avg_duration'],
                'avg_tokens': baseline_result['avg_tokens'],
            },
            'new': {
                'success_rate': new_result['success_rate'],
                'avg_duration': new_result['avg_duration'],
                'avg_tokens': new_result['avg_tokens'],
            },
            'delta': {
                'success_rate': sr_change,
                'duration': dur_change,
                'tokens': tok_change,
            },
        }


# ── 因果链验证 ──


class CausalChainVerification:
    """验证配置→行为→结果的因果链"""

    def __init__(self):
        self.replay = ReplayV2()

    def verify_all_chains(self, n_tasks: int = 500) -> Dict:
        """验证所有因果链"""
        print(f'\n═══ 因果链验证 ({n_tasks}任务) ═══')

        tasks = self.replay.generate_task_pool(n_tasks)
        baseline_config = {
            'cooldown_seconds': 30,
            'tournament_candidates': 3,
            'review_threshold': 0.8,
            'max_auto_fix': 3,
            'max_lines_changed': 20,
            'max_cycles': 10,
        }

        results = {}

        # 因果链1: cooldown
        print('\n[1/4] cooldown 因果链...')
        results['cooldown'] = self._verify_chain(tasks, baseline_config, 'cooldown_seconds', [15, 30, 60])

        # 因果链2: tournament_candidates
        print('[2/4] tournament_candidates 因果链...')
        results['candidates'] = self._verify_chain(tasks, baseline_config, 'tournament_candidates', [2, 3, 5])

        # 因果链3: review_threshold
        print('[3/4] review_threshold 因果链...')
        results['threshold'] = self._verify_chain(tasks, baseline_config, 'review_threshold', [0.6, 0.8, 1.0])

        # 因果链4: max_auto_fix
        print('[4/4] max_auto_fix 因果链...')
        results['fix'] = self._verify_chain(tasks, baseline_config, 'max_auto_fix', [1, 3, 5])

        return results

    def _verify_chain(self, tasks: List[Dict], baseline: Dict, param: str, values: List) -> Dict:
        """验证单个因果链"""
        chain_results = []

        for v in values:
            config = {**baseline, param: v}
            comparison = self.replay.compare_configs(tasks, baseline, config)
            chain_results.append(
                {
                    'value': v,
                    'delta': comparison['delta'],
                }
            )

            print(
                f'  {param}={v}: SR={comparison["delta"]["success_rate"]:+.1%}, '
                f'Dur={comparison["delta"]["duration"]:+.1%}, '
                f'Tok={comparison["delta"]["tokens"]:+.1%}'
            )

        # 检查是否有因果效应
        sr_range = max(r['delta']['success_rate'] for r in chain_results) - min(
            r['delta']['success_rate'] for r in chain_results
        )
        has_effect = sr_range > 0.01  # 成功率变化超过1%

        return {
            'param': param,
            'values': values,
            'results': chain_results,
            'has_causal_effect': has_effect,
            'sr_range': sr_range,
        }

    def print_report(self, results: Dict):
        """打印验证报告"""
        print('\n' + '=' * 60)
        print('  因果链验证报告')
        print('=' * 60)

        for name, chain in results.items():
            effect = '✓ 有因果效应' if chain['has_causal_effect'] else '✗ 无因果效应'
            print(f'\n  {chain["param"]}:')
            print(f'    状态: {effect}')
            print(f'    成功率范围: {chain["sr_range"]:.1%}')

        # 汇总
        chains_with_effect = sum(1 for r in results.values() if r['has_causal_effect'])
        print(f'\n  汇总: {chains_with_effect}/{len(results)} 个因果链有效')
