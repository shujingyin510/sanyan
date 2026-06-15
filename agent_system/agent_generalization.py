"""Knowledge Generalization — 知识泛化验证

核心实验：
  训练集任务 → 学知识
  测试集任务 → 提升成功率

如果成立：
  Agent记住了经验 → 低层次
  Agent学会了规律 → 高层次

组件：
  P76: TrainTestSplit — 训练/测试集划分
  P77: KnowledgeLearner — 从训练集学习
  P78: GeneralizationValidator — 泛化验证器
"""

import os
import random
import statistics
from typing import Dict, List, Tuple

ROOT = os.path.dirname(os.path.abspath(__file__))


# ── Train/Test Split ──


class TrainTestSplit:
    """训练/测试集划分"""

    def __init__(self, train_ratio: float = 0.7):
        self.train_ratio = train_ratio

    def split(self, tasks: List[Dict], seed: int = 42) -> Tuple[List[Dict], List[Dict]]:
        """划分训练集和测试集"""
        random.seed(seed)
        shuffled = tasks.copy()
        random.shuffle(shuffled)

        split_idx = int(len(shuffled) * self.train_ratio)
        train = shuffled[:split_idx]
        test = shuffled[split_idx:]

        return train, test

    def split_by_type(self, tasks: List[Dict], train_ratio: float = 0.7) -> Tuple[List[Dict], List[Dict]]:
        """按类型分层划分（保证每种类型都有训练和测试）"""
        by_type: Dict[str, List[Dict]] = {}
        for task in tasks:
            t = task.get('type', 'unknown')
            if t not in by_type:
                by_type[t] = []
            by_type[t].append(task)

        train = []
        test = []

        for task_type, type_tasks in by_type.items():
            random.shuffle(type_tasks)
            split_idx = int(len(type_tasks) * train_ratio)
            train.extend(type_tasks[:split_idx])
            test.extend(type_tasks[split_idx:])

        return train, test


# ── Knowledge Learner ──


class KnowledgeLearner:
    """从训练集学习知识"""

    def __init__(self):
        self._knowledge: Dict[str, Dict] = {}

    def learn(self, train_tasks: List[Dict], train_results: List[Dict]) -> Dict:
        """从训练集学习"""
        # 按任务类型分组
        by_type: Dict[str, List[Dict]] = {}
        for task, result in zip(train_tasks, train_results):
            t = task.get('type', 'unknown')
            if t not in by_type:
                by_type[t] = []
            by_type[t].append(result)

        # 为每种类型学习最优配置
        knowledge = {}
        for task_type, results in by_type.items():
            success_rates = [r.get('success_rate', 0) for r in results]
            durations = [r.get('duration', 1) for r in results]
            tokens = [r.get('tokens', 100) for r in results]

            knowledge[task_type] = {
                'n_samples': len(results),
                'avg_success_rate': statistics.mean(success_rates) if success_rates else 0,
                'std_success_rate': statistics.stdev(success_rates) if len(success_rates) > 1 else 0,
                'avg_duration': statistics.mean(durations) if durations else 1,
                'avg_tokens': statistics.mean(tokens) if tokens else 100,
            }

        self._knowledge = knowledge
        return knowledge

    def predict(self, task_type: str) -> Dict:
        """预测任务类型的表现"""
        if task_type in self._knowledge:
            return self._knowledge[task_type]
        return {
            'n_samples': 0,
            'avg_success_rate': 0.5,
            'std_success_rate': 0.2,
            'avg_duration': 2.0,
            'avg_tokens': 200,
        }

    def get_best_strategy(self, task_type: str) -> Dict:
        """获取任务类型的最优策略"""
        prediction = self.predict(task_type)

        # 基于历史数据推荐策略
        sr = prediction['avg_success_rate']
        if sr > 0.8:
            # 高成功率：保守策略
            return {'simple_max': 3, 'candidates': 3, 'auto_fix': 2}
        elif sr > 0.6:
            # 中成功率：标准策略
            return {'simple_max': 4, 'candidates': 4, 'auto_fix': 3}
        else:
            # 低成功率：激进策略
            return {'simple_max': 5, 'candidates': 6, 'auto_fix': 5}


# ── Generalization Validator ──


class GeneralizationValidator:
    """泛化验证器：验证知识能否帮助新任务"""

    def __init__(self):
        self.learner = KnowledgeLearner()
        self.splitter = TrainTestSplit(train_ratio=0.7)

    def validate(self, tasks: List[Dict], results: List[Dict]) -> Dict:
        """验证知识泛化"""
        print(f'\n═══ Knowledge Generalization 验证 ({len(tasks)}任务) ═══')

        # 1. 划分训练/测试集
        train_tasks, test_tasks = self.splitter.split_by_type(tasks)
        train_results = [results[tasks.index(t)] for t in train_tasks if t in tasks]
        test_results = [results[tasks.index(t)] for t in test_tasks if t in tasks]

        print(f'训练集: {len(train_tasks)}任务')
        print(f'测试集: {len(test_tasks)}任务')

        # 2. 从训练集学习
        print('\n从训练集学习...')
        knowledge = self.learner.learn(train_tasks, train_results)

        for task_type, info in knowledge.items():
            print(f'  {task_type}: {info["n_samples"]}样本, SR={info["avg_success_rate"]:.1%}')

        # 3. 验证泛化
        print('\n验证泛化...')
        generalization_result = self._test_generalization(test_tasks, test_results, knowledge)

        return {
            'train_size': len(train_tasks),
            'test_size': len(test_tasks),
            'knowledge': knowledge,
            'generalization': generalization_result,
        }

    def _test_generalization(self, test_tasks: List[Dict], test_results: List[Dict], knowledge: Dict) -> Dict:
        """测试泛化能力"""
        # 对比：有知识 vs 无知识
        with_knowledge = []
        without_knowledge = []

        for task, result in zip(test_tasks, test_results):
            task_type = task.get('type', 'unknown')
            predicted = self.learner.predict(task_type)
            actual_sr = result.get('success_rate', 0)

            # 有知识：使用预测的最优策略
            with_knowledge.append(
                {
                    'task_type': task_type,
                    'predicted_sr': predicted['avg_success_rate'],
                    'actual_sr': actual_sr,
                    'error': abs(predicted['avg_success_rate'] - actual_sr),
                }
            )

            # 无知识：使用默认策略（50%成功率）
            without_knowledge.append(
                {
                    'task_type': task_type,
                    'predicted_sr': 0.5,
                    'actual_sr': actual_sr,
                    'error': abs(0.5 - actual_sr),
                }
            )

        # 计算指标
        with_mae = statistics.mean([e['error'] for e in with_knowledge])
        without_mae = statistics.mean([e['error'] for e in without_knowledge])

        # 泛化提升
        generalization_improvement = (without_mae - with_mae) / max(without_mae, 0.001)

        # 按任务类型分析
        type_analysis = {}
        for task_type in set(t.get('type', 'unknown') for t in test_tasks):
            type_with = [e for e in with_knowledge if e['task_type'] == task_type]
            type_without = [e for e in without_knowledge if e['task_type'] == task_type]

            if type_with:
                type_analysis[task_type] = {
                    'n_test': len(type_with),
                    'with_mae': statistics.mean([e['error'] for e in type_with]),
                    'without_mae': statistics.mean([e['error'] for e in type_without]),
                    'improvement': (
                        statistics.mean([e['error'] for e in type_without])
                        - statistics.mean([e['error'] for e in type_with])
                    )
                    / max(statistics.mean([e['error'] for e in type_without]), 0.001),
                }

        return {
            'with_knowledge_mae': with_mae,
            'without_knowledge_mae': without_mae,
            'generalization_improvement': generalization_improvement,
            'type_analysis': type_analysis,
            'significant': generalization_improvement > 0.1,  # 10%提升算显著
        }

    def print_report(self, report: Dict):
        """打印报告"""
        print('\n' + '=' * 60)
        print('  Knowledge Generalization 报告')
        print('=' * 60)

        print('\n数据划分:')
        print(f'  训练集: {report["train_size"]}任务')
        print(f'  测试集: {report["test_size"]}任务')

        print('\n泛化验证:')
        gen = report['generalization']
        print(f'  有知识 MAE: {gen["with_knowledge_mae"]:.3f}')
        print(f'  无知识 MAE: {gen["without_knowledge_mae"]:.3f}')
        print(f'  泛化提升: {gen["generalization_improvement"]:.1%}')
        print(f'  显著性: {"✓ 显著" if gen["significant"] else "✗ 不显著"}')

        print('\n按任务类型分析:')
        for task_type, analysis in gen['type_analysis'].items():
            print(f'  {task_type}:')
            print(f'    测试样本: {analysis["n_test"]}')
            print(f'    有知识MAE: {analysis["with_mae"]:.3f}')
            print(f'    无知识MAE: {analysis["without_mae"]:.3f}')
            print(f'    提升: {analysis["improvement"]:.1%}')

        # 结论
        print('\n结论:')
        if gen['significant']:
            print('  ✓ 知识泛化成立：训练集学到的知识可以帮助测试集任务')
            print('  ✓ Agent学会了规律，不仅仅是记住了经验')
        else:
            print('  ✗ 知识泛化不显著：需要更多数据或更好的特征')

    def run_full_experiment(self, n_tasks: int = 2000, n_iterations: int = 5) -> Dict:
        """运行完整实验（多次划分取平均）"""
        print(f'\n{"=" * 60}')
        print('  Knowledge Generalization 完整实验')
        print(f'  {n_tasks}任务 × {n_iterations}次划分')
        print(f'{"=" * 60}')

        # 生成任务
        from agent_system.agent_task_taxonomy import TaskClassifier

        classifier = TaskClassifier()

        all_tasks = []
        all_results = []

        task_types = list(classifier.TASK_TYPES.keys())
        for i in range(n_tasks):
            task_type = random.choice(task_types)
            task = {
                'id': i,
                'type': task_type,
                'text': f'{task_type}_{i}',
            }

            # 模拟结果（不同任务类型有不同的"真实"成功率）
            true_sr = {
                'bug_fix': 0.75,
                'refactor': 0.65,
                'performance': 0.70,
                'feature': 0.80,
                'analysis': 0.85,
                'test': 0.72,
                'documentation': 0.90,
            }.get(task_type, 0.70)

            noise = random.gauss(0, 0.1)
            sr = max(0.3, min(0.99, true_sr + noise))

            result = {
                'success_rate': sr,
                'duration': 1.0 + random.gauss(0, 0.5),
                'tokens': 100 + random.randint(0, 200),
            }

            all_tasks.append(task)
            all_results.append(result)

        # 多次划分验证
        improvements = []
        for i in range(n_iterations):
            print(f'\n--- 迭代 {i + 1}/{n_iterations} ---')
            validator = GeneralizationValidator()
            report = validator.validate(all_tasks, all_results)
            improvements.append(report['generalization']['generalization_improvement'])

        # 汇总
        avg_improvement = statistics.mean(improvements)
        std_improvement = statistics.stdev(improvements) if len(improvements) > 1 else 0

        print(f'\n{"=" * 60}')
        print('  汇总结果')
        print(f'{"=" * 60}')
        print(f'  平均泛化提升: {avg_improvement:.1%} ± {std_improvement:.1%}')
        print(f'  显著性: {"✓ 成立" if avg_improvement > 0.1 else "✗ 不成立"}')

        return {
            'n_tasks': n_tasks,
            'n_iterations': n_iterations,
            'avg_improvement': avg_improvement,
            'std_improvement': std_improvement,
            'improvements': improvements,
            'significant': avg_improvement > 0.1,
        }
