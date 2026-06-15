"""Knowledge Transfer — 跨项目知识迁移

核心问题：
  项目A学到的知识，能否帮助项目B？

实验设计：
  训练：项目A的任务
  测试：项目B的任务（从未见过）

  如果成立：经验脱离具体项目，变成可迁移知识
"""

import math
import os
import random
import statistics
from typing import Dict, List

ROOT = os.path.dirname(os.path.abspath(__file__))


# ── 项目模拟器 ──


class ProjectSimulator:
    """模拟不同项目"""

    # 不同项目的特征（影响任务成功率的因素）
    PROJECT_PROFILES = {
        'sanyan': {
            'name': '三言语言项目',
            'task_characteristics': {
                'bug_fix': {'base_sr': 0.75, 'complexity': 0.6},
                'refactor': {'base_sr': 0.65, 'complexity': 0.7},
                'performance': {'base_sr': 0.70, 'complexity': 0.8},
                'feature': {'base_sr': 0.80, 'complexity': 0.5},
                'analysis': {'base_sr': 0.85, 'complexity': 0.4},
                'test': {'base_sr': 0.72, 'complexity': 0.5},
                'documentation': {'base_sr': 0.90, 'complexity': 0.3},
            },
        },
        'iot_system': {
            'name': 'IoT控制系统',
            'task_characteristics': {
                'bug_fix': {'base_sr': 0.70, 'complexity': 0.7},
                'refactor': {'base_sr': 0.60, 'complexity': 0.8},
                'performance': {'base_sr': 0.75, 'complexity': 0.6},
                'feature': {'base_sr': 0.72, 'complexity': 0.6},
                'analysis': {'base_sr': 0.80, 'complexity': 0.5},
                'test': {'base_sr': 0.68, 'complexity': 0.6},
                'documentation': {'base_sr': 0.85, 'complexity': 0.4},
            },
        },
        'web_app': {
            'name': 'Web应用项目',
            'task_characteristics': {
                'bug_fix': {'base_sr': 0.72, 'complexity': 0.5},
                'refactor': {'base_sr': 0.68, 'complexity': 0.6},
                'performance': {'base_sr': 0.65, 'complexity': 0.7},
                'feature': {'base_sr': 0.78, 'complexity': 0.5},
                'analysis': {'base_sr': 0.82, 'complexity': 0.4},
                'test': {'base_sr': 0.75, 'complexity': 0.5},
                'documentation': {'base_sr': 0.88, 'complexity': 0.3},
            },
        },
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
                }
            )

        return tasks

    def simulate_task(self, task: Dict, strategy: Dict) -> Dict:
        """模拟任务执行"""
        base_sr = task.get('base_sr', 0.7)
        difficulty = task.get('complexity', 5) / 10.0

        # 策略匹配度
        match_score = self._calculate_match(task['type'], strategy)

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

    def _calculate_match(self, task_type: str, strategy: Dict) -> float:
        """计算策略匹配度"""
        best_params = {
            'bug_fix': {'simple_max': 2, 'candidates': 8, 'auto_fix': 8},
            'refactor': {'simple_max': 6, 'candidates': 2, 'auto_fix': 1},
            'performance': {'simple_max': 3, 'candidates': 10, 'auto_fix': 2},
            'feature': {'simple_max': 4, 'candidates': 5, 'auto_fix': 4},
            'analysis': {'simple_max': 8, 'candidates': 1, 'auto_fix': 1},
            'test': {'simple_max': 5, 'candidates': 4, 'auto_fix': 3},
            'documentation': {'simple_max': 9, 'candidates': 1, 'auto_fix': 1},
        }

        best = best_params.get(task_type, best_params['feature'])
        scores = []
        for key in best:
            if key in strategy:
                diff = abs(strategy[key] - best[key])
                score = max(0, 1 - diff / max(best[key], 1))
                scores.append(score)

        return statistics.mean(scores) if scores else 0.5


# ── 知识迁移器 ──


class KnowledgeTransfer:
    """跨项目知识迁移"""

    def __init__(self):
        self.simulator = ProjectSimulator()
        self._learned_knowledge: Dict[str, Dict] = {}

    def learn_from_project(self, project: str, tasks: List[Dict], results: List[Dict]) -> Dict:
        """从项目学习知识"""
        by_type: Dict[str, List[Dict]] = {}
        for task, result in zip(tasks, results):
            t = task['type']
            if t not in by_type:
                by_type[t] = []
            by_type[t].append(result)

        knowledge = {}
        for task_type, type_results in by_type.items():
            success_rates = [r['success_rate'] for r in type_results]
            knowledge[task_type] = {
                'n_samples': len(type_results),
                'avg_success_rate': statistics.mean(success_rates),
                'std_success_rate': statistics.stdev(success_rates) if len(success_rates) > 1 else 0,
                'source_project': project,
            }

        self._learned_knowledge[project] = knowledge
        return knowledge

    def transfer_knowledge(self, source_project: str, target_tasks: List[Dict]) -> List[Dict]:
        """将知识迁移到目标任务"""
        source_knowledge = self._learned_knowledge.get(source_project, {})

        results = []
        for task in target_tasks:
            task_type = task['type']

            # 查找源项目的知识
            if task_type in source_knowledge:
                # 有知识：使用学到的策略
                strategy = self._knowledge_to_strategy(source_knowledge[task_type])
                confidence = min(1.0, math.log(source_knowledge[task_type]['n_samples'] + 1) / math.log(100))
            else:
                # 无知识：使用默认策略
                strategy = {'simple_max': 5, 'candidates': 3, 'auto_fix': 3}
                confidence = 0.0

            # 执行任务
            result = self.simulator.simulate_task(task, strategy)
            result['transferred'] = task_type in source_knowledge
            result['confidence'] = confidence
            results.append(result)

        return results

    def _knowledge_to_strategy(self, knowledge: Dict) -> Dict:
        """将知识转换为策略"""
        sr = knowledge['avg_success_rate']
        if sr > 0.8:
            return {'simple_max': 3, 'candidates': 3, 'auto_fix': 2}
        elif sr > 0.6:
            return {'simple_max': 4, 'candidates': 4, 'auto_fix': 3}
        else:
            return {'simple_max': 5, 'candidates': 6, 'auto_fix': 5}

    def baseline_strategy(self, tasks: List[Dict]) -> List[Dict]:
        """Baseline：统一策略"""
        strategy = {'simple_max': 5, 'candidates': 3, 'auto_fix': 3}
        results = []
        for task in tasks:
            result = self.simulator.simulate_task(task, strategy)
            result['transferred'] = False
            result['confidence'] = 0.0
            results.append(result)
        return results


# ── 知识迁移实验 ──


class KnowledgeTransferExperiment:
    """知识迁移实验"""

    def __init__(self):
        self.simulator = ProjectSimulator()
        self.transfer = KnowledgeTransfer()

    def run_experiment(self, n_tasks: int = 200) -> Dict:
        """运行知识迁移实验"""
        print(f'\n{"=" * 60}')
        print('  Knowledge Transfer 实验')
        print(f'{"=" * 60}')

        # 1. 在项目A上学习
        print('\n--- 阶段1: 在项目A上学习 ---')
        project_a = 'sanyan'
        tasks_a = self.simulator.generate_tasks(project_a, n_tasks)
        results_a = []
        for task in tasks_a:
            strategy = {'simple_max': 4, 'candidates': 5, 'auto_fix': 4}
            result = self.simulator.simulate_task(task, strategy)
            results_a.append(result)

        knowledge_a = self.transfer.learn_from_project(project_a, tasks_a, results_a)
        print(f'  项目A ({project_a}): 学习了 {len(knowledge_a)} 种任务类型')
        for t, k in knowledge_a.items():
            print(f'    {t}: {k["n_samples"]}样本, SR={k["avg_success_rate"]:.1%}')

        # 2. 测试迁移效果
        print('\n--- 阶段2: 测试迁移效果 ---')
        projects_to_test = ['iot_system', 'web_app']

        all_results = {}
        for project in projects_to_test:
            print(f'\n  目标项目: {project}')
            tasks_b = self.simulator.generate_tasks(project, n_tasks)

            # Baseline
            baseline = self.transfer.baseline_strategy(tasks_b)
            baseline_sr = sum(1 for r in baseline if r['success']) / len(baseline)

            # Knowledge Transfer
            transferred = self.transfer.transfer_knowledge(project_a, tasks_b)
            transfer_sr = sum(1 for r in transferred if r['success']) / len(transferred)

            # 分析
            improvement = transfer_sr - baseline_sr
            transferred_count = sum(1 for r in transferred if r['transferred'])
            avg_confidence = (
                statistics.mean([r['confidence'] for r in transferred if r['transferred']]) if transferred else 0
            )

            all_results[project] = {
                'baseline_sr': baseline_sr,
                'transfer_sr': transfer_sr,
                'improvement': improvement,
                'transferred_count': transferred_count,
                'total_count': len(tasks_b),
                'avg_confidence': avg_confidence,
            }

            print(f'    Baseline SR: {baseline_sr:.1%}')
            print(f'    Transfer SR: {transfer_sr:.1%}')
            print(f'    改进: {improvement:+.1%}')
            print(f'    迁移任务: {transferred_count}/{len(tasks_b)}')
            print(f'    平均置信度: {avg_confidence:.2f}')

        return {
            'source_project': project_a,
            'target_projects': projects_to_test,
            'results': all_results,
        }

    def print_report(self, report: Dict):
        """打印报告"""
        print(f'\n{"=" * 60}')
        print('  Knowledge Transfer 报告')
        print(f'{"=" * 60}')

        print(f'\n源项目: {report["source_project"]}')

        print('\n┌─ 迁移结果 ──────────────────────────────────────┐')
        print('│  目标项目      Baseline  Transfer  改进       │')
        print('├──────────────────────────────────────────────────┤')
        for project, data in report['results'].items():
            print(
                f'│  {project:15s} {data["baseline_sr"]:.1%}    {data["transfer_sr"]:.1%}    {data["improvement"]:+.1%}       │'
            )
        print('└──────────────────────────────────────────────────┘')

        # 结论
        improvements = [d['improvement'] for d in report['results'].values()]
        avg_improvement = statistics.mean(improvements) if improvements else 0

        print('\n结论:')
        if avg_improvement > 0:
            print(f'  ✓ 知识迁移成立：平均改进 {avg_improvement:+.1%}')
            print('  ✓ 经验脱离具体项目，变成可迁移知识')
        else:
            print('  ✗ 知识迁移不显著')
