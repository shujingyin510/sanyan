"""Meta-Knowledge Transfer — 元知识迁移

核心洞察：
  配置不可迁移，但任务规律可能可迁移

实验设计：
  实验A：迁移任务规律（Task Pattern → Strategy Pattern）
  实验B：迁移置信度模型（Confidence Formula）

Level 1（已证伪）：Project Config 不可迁移
Level 2（待验证）：Task Pattern → Strategy Pattern 可能可迁移
Level 3（待验证）：Uncertainty Pattern → Exploration Policy 可能跨项目迁移
"""

import os
import random
import statistics
from typing import Dict, List

ROOT = os.path.dirname(os.path.abspath(__file__))


# ── 项目模拟器 ──


class ProjectSimulator:
    """模拟不同项目"""

    PROJECT_PROFILES = {
        'sanyan': {
            'name': '三言语言项目',
            'task_characteristics': {
                'bug_fix': {'base_sr': 0.75, 'complexity': 0.6, 'optimal_strategy': 'multi_fix'},
                'refactor': {'base_sr': 0.65, 'complexity': 0.7, 'optimal_strategy': 'careful'},
                'performance': {'base_sr': 0.70, 'complexity': 0.8, 'optimal_strategy': 'multi_candidate'},
                'feature': {'base_sr': 0.80, 'complexity': 0.5, 'optimal_strategy': 'standard'},
                'analysis': {'base_sr': 0.85, 'complexity': 0.4, 'optimal_strategy': 'direct'},
                'test': {'base_sr': 0.72, 'complexity': 0.5, 'optimal_strategy': 'thorough'},
                'documentation': {'base_sr': 0.90, 'complexity': 0.3, 'optimal_strategy': 'direct'},
            },
        },
        'iot_system': {
            'name': 'IoT控制系统',
            'task_characteristics': {
                'bug_fix': {'base_sr': 0.70, 'complexity': 0.7, 'optimal_strategy': 'quick_fix'},
                'refactor': {'base_sr': 0.60, 'complexity': 0.8, 'optimal_strategy': 'incremental'},
                'performance': {'base_sr': 0.75, 'complexity': 0.6, 'optimal_strategy': 'profile_first'},
                'feature': {'base_sr': 0.72, 'complexity': 0.6, 'optimal_strategy': 'standard'},
                'analysis': {'base_sr': 0.80, 'complexity': 0.5, 'optimal_strategy': 'direct'},
                'test': {'base_sr': 0.68, 'complexity': 0.6, 'optimal_strategy': 'hardware_test'},
                'documentation': {'base_sr': 0.85, 'complexity': 0.4, 'optimal_strategy': 'direct'},
            },
        },
        'web_app': {
            'name': 'Web应用项目',
            'task_characteristics': {
                'bug_fix': {'base_sr': 0.72, 'complexity': 0.5, 'optimal_strategy': 'test_driven'},
                'refactor': {'base_sr': 0.68, 'complexity': 0.6, 'optimal_strategy': 'incremental'},
                'performance': {'base_sr': 0.65, 'complexity': 0.7, 'optimal_strategy': 'cache_first'},
                'feature': {'base_sr': 0.78, 'complexity': 0.5, 'optimal_strategy': 'standard'},
                'analysis': {'base_sr': 0.82, 'complexity': 0.4, 'optimal_strategy': 'direct'},
                'test': {'base_sr': 0.75, 'complexity': 0.5, 'optimal_strategy': 'integration'},
                'documentation': {'base_sr': 0.88, 'complexity': 0.3, 'optimal_strategy': 'direct'},
            },
        },
    }

    # 策略类型定义（可迁移的元知识）
    STRATEGY_TYPES = {
        'multi_fix': {'description': '多轮修复尝试', 'candidates': 8, 'auto_fix': 5, 'review': 0.6},
        'careful': {'description': '谨慎重构', 'candidates': 2, 'auto_fix': 1, 'review': 0.95},
        'multi_candidate': {'description': '多候选比较', 'candidates': 10, 'auto_fix': 2, 'review': 0.85},
        'standard': {'description': '标准流程', 'candidates': 4, 'auto_fix': 3, 'review': 0.7},
        'direct': {'description': '直接执行', 'candidates': 1, 'auto_fix': 1, 'review': 0.3},
        'thorough': {'description': '全面测试', 'candidates': 5, 'auto_fix': 3, 'review': 0.75},
        'quick_fix': {'description': '快速修复', 'candidates': 3, 'auto_fix': 2, 'review': 0.5},
        'incremental': {'description': '增量改进', 'candidates': 3, 'auto_fix': 2, 'review': 0.8},
        'profile_first': {'description': '先分析后优化', 'candidates': 6, 'auto_fix': 2, 'review': 0.85},
        'test_driven': {'description': '测试驱动', 'candidates': 4, 'auto_fix': 3, 'review': 0.8},
        'hardware_test': {'description': '硬件测试', 'candidates': 3, 'auto_fix': 2, 'review': 0.7},
        'cache_first': {'description': '缓存优先', 'candidates': 5, 'auto_fix': 2, 'review': 0.75},
    }

    def __init__(self):
        random.seed(42)

    def generate_tasks(self, project: str, n: int = 200) -> List[Dict]:
        """为项目生成任务"""
        profile = self.PROJECT_PROFILES.get(project, self.PROJECT_PROFILES['sanyan'])
        tasks = []

        for i in range(n):
            task_type = random.choice(list(profile['task_characteristics'].keys()))
            char = profile['task_characteristics'][task_type]

            tasks.append(
                {
                    'id': f'{project}_{i}',
                    'type': task_type,
                    'text': f'{project}_{task_type}_{i}',
                    'project': project,
                    'complexity': random.randint(1, 10),
                    'base_sr': char['base_sr'],
                    'optimal_strategy': char['optimal_strategy'],
                }
            )

        return tasks

    def simulate_task(self, task: Dict, strategy_config: Dict) -> Dict:
        """模拟任务执行"""
        base_sr = task.get('base_sr', 0.7)
        difficulty = task.get('complexity', 5) / 10.0

        # 策略匹配度
        match_score = self._calculate_match(task['type'], strategy_config)

        # 成功率
        base_success_rate = base_sr * match_score * (1 - difficulty * 0.2)
        noise = random.gauss(0, 0.08)
        success_rate = max(0.2, min(0.99, base_success_rate + noise))
        success = random.random() < success_rate

        return {
            'success': success,
            'success_rate': success_rate,
            'match_score': match_score,
        }

    def _calculate_match(self, task_type: str, strategy_config: Dict) -> float:
        """计算策略配置匹配度"""
        # 找到该任务类型的最佳配置
        best_configs = {
            'bug_fix': {'candidates': 8, 'auto_fix': 8, 'review': 0.5},
            'refactor': {'candidates': 2, 'auto_fix': 1, 'review': 0.95},
            'performance': {'candidates': 10, 'auto_fix': 2, 'review': 0.9},
            'feature': {'candidates': 5, 'auto_fix': 4, 'review': 0.7},
            'analysis': {'candidates': 1, 'auto_fix': 1, 'review': 0.3},
            'test': {'candidates': 4, 'auto_fix': 3, 'review': 0.6},
            'documentation': {'candidates': 1, 'auto_fix': 1, 'review': 0.2},
        }

        best = best_configs.get(task_type, best_configs['feature'])
        scores = []
        for key in best:
            if key in strategy_config:
                diff = abs(strategy_config[key] - best[key])
                score = max(0, 1 - diff / max(best[key], 1))
                scores.append(score)

        return statistics.mean(scores) if scores else 0.5


# ── 实验A：迁移任务规律 ──


class TaskPatternTransfer:
    """迁移任务规律（不迁移参数）"""

    def __init__(self):
        self.simulator = ProjectSimulator()

    def learn_patterns(self, project: str, tasks: List[Dict], results: List[Dict]) -> Dict:
        """从项目学习任务规律"""
        patterns = {}

        for task, result in zip(tasks, results):
            task_type = task['type']
            optimal_strategy = task.get('optimal_strategy', 'standard')

            if task_type not in patterns:
                patterns[task_type] = {
                    'strategy_counts': {},
                    'total': 0,
                    'success_by_strategy': {},
                }

            patterns[task_type]['strategy_counts'][optimal_strategy] = (
                patterns[task_type]['strategy_counts'].get(optimal_strategy, 0) + 1
            )
            patterns[task_type]['total'] += 1

            if result['success']:
                if optimal_strategy not in patterns[task_type]['success_by_strategy']:
                    patterns[task_type]['success_by_strategy'][optimal_strategy] = 0
                patterns[task_type]['success_by_strategy'][optimal_strategy] += 1

        # 计算每种任务类型的最佳策略类型
        learned_patterns = {}
        for task_type, data in patterns.items():
            best_strategy = None
            best_score = -1
            for strategy, count in data['strategy_counts'].items():
                successes = data['success_by_strategy'].get(strategy, 0)
                score = successes / max(count, 1)
                if score > best_score:
                    best_score = score
                    best_strategy = strategy

            learned_patterns[task_type] = {
                'best_strategy_type': best_strategy,
                'confidence': best_score,
                'n_samples': data['total'],
            }

        return learned_patterns

    def apply_patterns(self, target_tasks: List[Dict], patterns: Dict) -> List[Dict]:
        """应用学到的规律到目标任务"""
        results = []

        for task in target_tasks:
            task_type = task['type']

            if task_type in patterns:
                # 有规律：使用学到的策略类型
                strategy_type = patterns[task_type]['best_strategy_type']
                confidence = patterns[task_type]['confidence']

                # 将策略类型转换为具体配置
                strategy_config = self._strategy_type_to_config(strategy_type)
                transferred = True
            else:
                # 无规律：使用默认策略
                strategy_config = {'candidates': 4, 'auto_fix': 3, 'review': 0.7}
                confidence = 0.0
                transferred = False

            # 执行任务
            result = self.simulator.simulate_task(task, strategy_config)
            result['transferred'] = transferred
            result['confidence'] = confidence
            result['strategy_type'] = strategy_type if transferred else 'default'
            results.append(result)

        return results

    def _strategy_type_to_config(self, strategy_type: str) -> Dict:
        """将策略类型转换为具体配置"""
        configs = {
            'multi_fix': {'candidates': 8, 'auto_fix': 5, 'review': 0.6},
            'careful': {'candidates': 2, 'auto_fix': 1, 'review': 0.95},
            'multi_candidate': {'candidates': 10, 'auto_fix': 2, 'review': 0.85},
            'standard': {'candidates': 4, 'auto_fix': 3, 'review': 0.7},
            'direct': {'candidates': 1, 'auto_fix': 1, 'review': 0.3},
            'thorough': {'candidates': 5, 'auto_fix': 3, 'review': 0.75},
            'quick_fix': {'candidates': 3, 'auto_fix': 2, 'review': 0.5},
            'incremental': {'candidates': 3, 'auto_fix': 2, 'review': 0.8},
            'profile_first': {'candidates': 6, 'auto_fix': 2, 'review': 0.85},
            'test_driven': {'candidates': 4, 'auto_fix': 3, 'review': 0.8},
            'hardware_test': {'candidates': 3, 'auto_fix': 2, 'review': 0.7},
            'cache_first': {'candidates': 5, 'auto_fix': 2, 'review': 0.75},
        }
        return configs.get(strategy_type, configs['standard'])

    def baseline(self, tasks: List[Dict]) -> List[Dict]:
        """Baseline：统一策略"""
        strategy = {'candidates': 4, 'auto_fix': 3, 'review': 0.7}
        results = []
        for task in tasks:
            result = self.simulator.simulate_task(task, strategy)
            result['transferred'] = False
            result['confidence'] = 0.0
            result['strategy_type'] = 'default'
            results.append(result)
        return results


# ── 实验B：迁移置信度模型 ──


class ConfidenceModelTransfer:
    """迁移置信度模型"""

    def __init__(self):
        self.simulator = ProjectSimulator()

    def learn_confidence_model(self, project: str, tasks: List[Dict], results: List[Dict]) -> Dict:
        """学习置信度模型"""
        # 统计每种任务类型的样本数与成功率关系
        by_type: Dict[str, List[Dict]] = {}
        for task, result in zip(tasks, results):
            t = task['type']
            if t not in by_type:
                by_type[t] = []
            by_type[t].append(result)

        model = {}
        for task_type, type_results in by_type.items():
            n_samples = len(type_results)
            success_rates = [r['success_rate'] for r in type_results]

            # 学习：多少样本后置信度达到0.8
            confidence_threshold = self._learn_confidence_threshold(n_samples, success_rates)

            model[task_type] = {
                'n_samples': n_samples,
                'avg_sr': statistics.mean(success_rates) if success_rates else 0.5,
                'confidence_threshold': confidence_threshold,
            }

        return model

    def _learn_confidence_threshold(self, n_samples: int, success_rates: List[float]) -> float:
        """学习置信度阈值：多少样本后预测稳定"""
        if n_samples < 10:
            return 100  # 需要很多样本
        elif n_samples < 30:
            return 50
        elif n_samples < 100:
            return 20
        else:
            return 10

    def apply_confidence(self, target_tasks: List[Dict], model: Dict) -> List[Dict]:
        """应用置信度模型"""
        results = []

        for task in target_tasks:
            task_type = task['type']

            if task_type in model:
                # 有模型：使用学到的置信度阈值
                threshold = model[task_type]['confidence_threshold']
                # 模拟：高置信度时更保守
                if threshold < 20:
                    strategy = {'candidates': 6, 'auto_fix': 2, 'review': 0.9}
                else:
                    strategy = {'candidates': 4, 'auto_fix': 3, 'review': 0.7}
                confidence = 0.8
            else:
                # 无模型：使用默认策略
                strategy = {'candidates': 4, 'auto_fix': 3, 'review': 0.7}
                confidence = 0.0

            result = self.simulator.simulate_task(task, strategy)
            result['confidence_applied'] = task_type in model
            result['confidence'] = confidence
            results.append(result)

        return results

    def baseline(self, tasks: List[Dict]) -> List[Dict]:
        """Baseline：统一策略"""
        strategy = {'candidates': 4, 'auto_fix': 3, 'review': 0.7}
        results = []
        for task in tasks:
            result = self.simulator.simulate_task(task, strategy)
            result['confidence_applied'] = False
            result['confidence'] = 0.0
            results.append(result)
        return results


# ── 整合实验 ──


class MetaKnowledgeTransferExperiment:
    """Meta-Knowledge Transfer 实验"""

    def __init__(self):
        self.simulator = ProjectSimulator()
        self.pattern_transfer = TaskPatternTransfer()
        self.confidence_transfer = ConfidenceModelTransfer()

    def run_experiment(self, n_tasks: int = 500) -> Dict:
        """运行完整实验"""
        print(f'\n{"=" * 60}')
        print('  Meta-Knowledge Transfer 实验')
        print(f'{"=" * 60}')

        # 1. 在项目A上学习
        print('\n--- 阶段1: 在项目A上学习 ---')
        project_a = 'sanyan'
        tasks_a = self.simulator.generate_tasks(project_a, n_tasks)

        # 模拟执行
        results_a = []
        for task in tasks_a:
            strategy = ProjectSimulator.STRATEGY_TYPES.get(
                task['optimal_strategy'], {'candidates': 4, 'auto_fix': 3, 'review': 0.7}
            )
            strategy_config = {
                'candidates': strategy.get('candidates', 4),
                'auto_fix': strategy.get('auto_fix', 3),
                'review': strategy.get('review', 0.7),
            }
            result = self.simulator.simulate_task(task, strategy_config)
            results_a.append(result)

        # 学习规律
        patterns = self.pattern_transfer.learn_patterns(project_a, tasks_a, results_a)
        confidence_model = self.confidence_transfer.learn_confidence_model(project_a, tasks_a, results_a)

        print(f'  学习到 {len(patterns)} 种任务规律:')
        for t, p in patterns.items():
            print(f'    {t}: → {p["best_strategy_type"]} (置信度: {p["confidence"]:.2f})')

        # 2. 测试迁移
        print('\n--- 阶段2: 测试迁移效果 ---')
        projects_to_test = ['iot_system', 'web_app']

        all_results = {}
        for project in projects_to_test:
            print(f'\n  目标项目: {project}')
            tasks_b = self.simulator.generate_tasks(project, n_tasks)

            # Baseline
            baseline = self.pattern_transfer.baseline(tasks_b)
            baseline_sr = sum(1 for r in baseline if r['success']) / len(baseline)

            # 实验A：迁移任务规律
            transfer_a = self.pattern_transfer.apply_patterns(tasks_b, patterns)
            transfer_a_sr = sum(1 for r in transfer_a if r['success']) / len(transfer_a)

            # 实验B：迁移置信度模型
            transfer_b = self.confidence_transfer.apply_confidence(tasks_b, confidence_model)
            transfer_b_sr = sum(1 for r in transfer_b if r['success']) / len(transfer_b)

            # 分析
            improvement_a = transfer_a_sr - baseline_sr
            improvement_b = transfer_b_sr - baseline_sr

            all_results[project] = {
                'baseline_sr': baseline_sr,
                'pattern_transfer_sr': transfer_a_sr,
                'confidence_transfer_sr': transfer_b_sr,
                'pattern_improvement': improvement_a,
                'confidence_improvement': improvement_b,
            }

            print(f'    Baseline: {baseline_sr:.1%}')
            print(f'    Pattern Transfer: {transfer_a_sr:.1%} ({improvement_a:+.1%})')
            print(f'    Confidence Transfer: {transfer_b_sr:.1%} ({improvement_b:+.1%})')

        return {
            'source_project': project_a,
            'target_projects': projects_to_test,
            'patterns': patterns,
            'results': all_results,
        }

    def print_report(self, report: Dict):
        """打印报告"""
        print(f'\n{"=" * 60}')
        print('  Meta-Knowledge Transfer 报告')
        print(f'{"=" * 60}')

        print(f'\n源项目: {report["source_project"]}')

        print('\n学到的任务规律:')
        for t, p in report['patterns'].items():
            print(f'  {t}: → {p["best_strategy_type"]} (置信度: {p["confidence"]:.2f})')

        print('\n┌─ 迁移结果 ──────────────────────────────────────┐')
        print('│  目标项目      Baseline  Pattern   Confidence │')
        print('├──────────────────────────────────────────────────┤')
        for project, data in report['results'].items():
            print(
                f'│  {project:15s} {data["baseline_sr"]:.1%}    {data["pattern_transfer_sr"]:.1%}({data["pattern_improvement"]:+.1%})  {data["confidence_transfer_sr"]:.1%}({data["confidence_improvement"]:+.1%}) │'
            )
        print('└──────────────────────────────────────────────────┘')

        # 结论
        pattern_improvements = [d['pattern_improvement'] for d in report['results'].values()]
        confidence_improvements = [d['confidence_improvement'] for d in report['results'].values()]

        avg_pattern = statistics.mean(pattern_improvements) if pattern_improvements else 0
        avg_confidence = statistics.mean(confidence_improvements) if confidence_improvements else 0

        print('\n结论:')
        print(f'  Pattern Transfer 平均改进: {avg_pattern:+.1%}')
        print(f'  Confidence Transfer 平均改进: {avg_confidence:+.1%}')

        if avg_pattern > 0:
            print('  ✓ 任务规律可迁移：迁移的是策略类型，不是具体配置')
        else:
            print('  ✗ 任务规律迁移不显著')

        if avg_confidence > 0:
            print('  ✓ 置信度模型可迁移：如何判断知识可信可以跨项目')
        else:
            print('  ✗ 置信度模型迁移不显著')
