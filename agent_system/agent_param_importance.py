"""Parameter Importance Ranking + Phase 2B StrategySchema

P58: ParameterRanker — 自动计算参数影响力
P59: StrategySchema — 策略参数化（simple_max/single_max/tournament_min）
P60: StrategyReplay — 策略回放验证
"""

import os
import sqlite3
import statistics
import time
from typing import Any, Dict, List

from agent_system.paths import db_path

ROOT = os.path.dirname(os.path.abspath(__file__))


# ── Parameter Importance Ranking ──


class ParameterRanker:
    """自动计算参数影响力，形成进化优先级"""

    DB_PATH = db_path('agent_param_ranking.db')

    def __init__(self):
        self._init_db()

    def _init_db(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.DB_PATH)
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS param_impact (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parameter TEXT,
                delta_success_rate REAL,
                delta_latency REAL,
                delta_tokens REAL,
                total_impact REAL,
                tier TEXT,
                measured_at REAL
            );
        """)
        conn.commit()
        conn.close()

    def measure_impact(self, parameter: str, baseline: Dict, variants: List[Dict]) -> Dict:
        """测量单个参数的影响力"""
        impacts = []

        for variant in variants:
            # 计算变化
            sr_delta = abs(variant['success_rate'] - baseline['success_rate'])
            dur_delta = abs(variant['avg_duration'] - baseline['avg_duration']) / max(baseline['avg_duration'], 0.001)
            tok_delta = abs(variant['avg_tokens'] - baseline['avg_tokens']) / max(baseline['avg_tokens'], 1)

            # 综合影响力（百分比）
            total_impact = sr_delta * 100 + dur_delta * 50 + tok_delta * 50

            impacts.append(
                {
                    'value': variant.get('value'),
                    'sr_delta': sr_delta,
                    'dur_delta': dur_delta,
                    'tok_delta': tok_delta,
                    'total_impact': total_impact,
                }
            )

        # 取最大影响力
        max_impact = max(impacts, key=lambda x: x['total_impact']) if impacts else None

        # 分级
        if max_impact:
            impact = max_impact['total_impact']
            if impact > 20:
                tier = 'Tier 1'
            elif impact > 10:
                tier = 'Tier 2'
            elif impact > 5:
                tier = 'Tier 3'
            else:
                tier = 'Tier 4'
        else:
            tier = 'Tier 4'
            impact = 0

        # 记录
        self._record_impact(parameter, max_impact or {}, tier)

        return {
            'parameter': parameter,
            'impact': impact,
            'tier': tier,
            'details': impacts,
        }

    def _record_impact(self, parameter: str, impact_data: Dict, tier: str):
        """记录影响力"""
        conn = sqlite3.connect(self.DB_PATH)
        conn.execute(
            """
            INSERT INTO param_impact
            (parameter, delta_success_rate, delta_latency, delta_tokens, total_impact, tier, measured_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
                parameter,
                impact_data.get('sr_delta', 0),
                impact_data.get('dur_delta', 0),
                impact_data.get('tok_delta', 0),
                impact_data.get('total_impact', 0),
                tier,
                time.time(),
            ),
        )
        conn.commit()
        conn.close()

    def get_ranking(self) -> List[Dict]:
        """获取参数排名"""
        conn = sqlite3.connect(self.DB_PATH)
        rows = conn.execute("""
            SELECT parameter, total_impact, tier
            FROM param_impact
            WHERE id IN (SELECT MAX(id) FROM param_impact GROUP BY parameter)
            ORDER BY total_impact DESC
        """).fetchall()
        conn.close()

        return [{'parameter': r[0], 'impact': r[1], 'tier': r[2]} for r in rows]

    def get_priority_list(self) -> List[str]:
        """获取进化优先级列表"""
        ranking = self.get_ranking()
        return [r['parameter'] for r in ranking]

    def summary(self) -> str:
        ranking = self.get_ranking()
        lines = ['Parameter Importance Ranking:']
        for i, r in enumerate(ranking, 1):
            lines.append(f'  {i}. {r["parameter"]}: {r["impact"]:.1f}% ({r["tier"]})')
        return '\n'.join(lines)


# ── Strategy Schema ──


class StrategySchema:
    """策略参数化：Phase 2B"""

    DEFAULT_CONFIG = {
        'simple_max_complexity': {
            'value': 3,
            'type': 'int',
            'min': 1,
            'max': 10,
            'description': '简单任务复杂度上限',
            'category': 'strategy',
        },
        'single_max_complexity': {
            'value': 7,
            'type': 'int',
            'min': 3,
            'max': 15,
            'description': '单假设任务复杂度上限',
            'category': 'strategy',
        },
        'tournament_min_complexity': {
            'value': 8,
            'type': 'int',
            'min': 5,
            'max': 20,
            'description': '锦标赛任务复杂度下限',
            'category': 'strategy',
        },
        'tournament_default_candidates': {
            'value': 3,
            'type': 'int',
            'min': 2,
            'max': 10,
            'description': '锦标赛默认候选数',
            'category': 'strategy',
        },
        'hypothesis_confidence_threshold': {
            'value': 0.5,
            'type': 'float',
            'min': 0.1,
            'max': 0.9,
            'description': '假设置信度阈值',
            'category': 'strategy',
        },
        'early_death_threshold': {
            'value': 0.2,
            'type': 'float',
            'min': 0.05,
            'max': 0.5,
            'description': '假设早停阈值',
            'category': 'strategy',
        },
    }

    DB_PATH = db_path('agent_strategy_config.db')

    def __init__(self):
        self._config = {k: v['value'] for k, v in self.DEFAULT_CONFIG.items()}
        self._init_db()

    def _init_db(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.DB_PATH)
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS strategy_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parameter TEXT,
                old_value TEXT,
                new_value TEXT,
                reason TEXT,
                verdict TEXT,
                actual_impact REAL,
                created_at REAL
            );
        """)
        conn.commit()
        conn.close()

    def get(self, key: str) -> Any:
        return self._config.get(key)

    def set(self, key: str, value: Any):
        if key in self.DEFAULT_CONFIG:
            schema = self.DEFAULT_CONFIG[key]
            if schema['type'] == 'int':
                value = int(value)
            elif schema['type'] == 'float':
                value = float(value)
            value = max(schema['min'], min(schema['max'], value))
            self._config[key] = value

    def get_all(self) -> Dict[str, Any]:
        return dict(self._config)

    def get_all_parameters(self) -> List[Dict]:
        return [
            {
                'name': k,
                'current': v['value'],
                'type': v['type'],
                'min': v['min'],
                'max': v['max'],
                'description': v['description'],
            }
            for k, v in self.DEFAULT_CONFIG.items()
        ]


# ── Strategy Replay ──


class StrategyReplay:
    """策略回放验证：验证策略选择质量"""

    # 任务复杂度分布
    TASK_COMPLEXITY_DISTRIBUTION = [
        (1, 0.15),  # 15% 简单任务
        (2, 0.20),  # 20%
        (3, 0.15),  # 15%
        (4, 0.10),  # 10%
        (5, 0.10),  # 10%
        (6, 0.08),  # 8%
        (7, 0.07),  # 7%
        (8, 0.05),  # 5%
        (9, 0.03),  # 3%
        (10, 0.02),  # 2%
    ]

    def __init__(self):
        import random

        self.random = random

    def generate_tasks(self, n: int = 500) -> List[Dict]:
        """生成任务（带复杂度分布）"""
        tasks = []
        for i in range(n):
            # 按分布选择复杂度
            r = self.random.random()
            cumulative = 0
            complexity = 5  # 默认
            for c, p in self.TASK_COMPLEXITY_DISTRIBUTION:
                cumulative += p
                if r <= cumulative:
                    complexity = c
                    break

            tasks.append(
                {
                    'id': i,
                    'complexity': complexity,
                    'type': f'task_c{complexity}',
                }
            )
        return tasks

    def select_strategy(self, complexity: int, config: Dict) -> str:
        """根据配置选择策略"""
        if complexity < config.get('simple_max_complexity', 3):
            return 'direct'
        elif complexity < config.get('single_max_complexity', 7):
            return 'single'
        else:
            return 'tournament'

    def simulate_execution(self, strategy: str, complexity: int) -> Dict:
        """模拟执行结果"""
        # 策略基础成功率
        strategy_base = {
            'direct': 0.95,
            'single': 0.85,
            'tournament': 0.80,
        }

        # 复杂度惩罚
        complexity_penalty = (complexity - 5) * 0.03

        # 策略基础耗时
        strategy_time = {
            'direct': 0.5,
            'single': 1.5,
            'tournament': 3.0,
        }

        # 策略基础Token
        strategy_tokens = {
            'direct': 0,
            'single': 150,
            'tournament': 300,
        }

        base_sr = strategy_base[strategy]
        sr = max(0.3, min(0.99, base_sr - complexity_penalty + self.random.gauss(0, 0.05)))
        duration = strategy_time[strategy] * (1 + complexity * 0.1) * (1 + self.random.gauss(0, 0.1))
        tokens = strategy_tokens[strategy] + complexity * 20 + int(self.random.gauss(0, 20))

        success = self.random.random() < sr

        return {
            'success': success,
            'success_rate': sr,
            'duration': duration,
            'tokens': max(0, tokens),
        }

    def replay(self, tasks: List[Dict], config: Dict) -> Dict:
        """用指定配置回放"""
        results = []
        strategy_counts = {'direct': 0, 'single': 0, 'tournament': 0}

        for task in tasks:
            strategy = self.select_strategy(task['complexity'], config)
            strategy_counts[strategy] += 1
            result = self.simulate_execution(strategy, task['complexity'])
            results.append(result)

        total = len(results)
        success_count = sum(1 for r in results if r['success'])
        durations = [r['duration'] for r in results]
        tokens = [r['tokens'] for r in results]

        return {
            'total': total,
            'success_rate': success_count / max(total, 1),
            'avg_duration': statistics.mean(durations) if durations else 0,
            'avg_tokens': statistics.mean(tokens) if tokens else 0,
            'strategy_distribution': strategy_counts,
            'results': results,
        }


# ── 整合 ──


class StrategyEvolutionSystem:
    """Phase 2B: 策略参数进化系统"""

    def __init__(self):
        self.schema = StrategySchema()
        self.replay = StrategyReplay()
        self.ranker = ParameterRanker()
        self._history: List[Dict] = []

    def measure_all_impacts(self, n_tasks: int = 500) -> Dict:
        """测量所有参数的影响力"""
        print(f'\n═══ Parameter Importance Ranking ({n_tasks}任务) ═══')

        tasks = self.replay.generate_tasks(n_tasks)
        baseline_config = self.schema.get_all()
        baseline_result = self.replay.replay(tasks, baseline_config)

        impacts = {}
        for param_name, param_schema in self.schema.DEFAULT_CONFIG.items():
            variants = []
            # 测试最小值和最大值
            for v in [param_schema['min'], param_schema['max']]:
                config = {**baseline_config, param_name: v}
                result = self.replay.replay(tasks, config)
                variants.append(
                    {
                        'value': v,
                        'success_rate': result['success_rate'],
                        'avg_duration': result['avg_duration'],
                        'avg_tokens': result['avg_tokens'],
                    }
                )

            impact = self.ranker.measure_impact(
                param_name,
                {
                    'success_rate': baseline_result['success_rate'],
                    'avg_duration': baseline_result['avg_duration'],
                    'avg_tokens': baseline_result['avg_tokens'],
                },
                variants,
            )
            impacts[param_name] = impact
            print(f'  {param_name}: {impact["impact"]:.1f}% ({impact["tier"]})')

        return impacts

    def run_strategy_cycle(self, parameter: str, new_value: Any, reason: str) -> Dict:
        """运行一次策略进化循环"""
        print('\n═══ Strategy 进化循环 ═══')

        # 1. 提议变更
        old_value = self.schema.get(parameter)
        self.schema.set(parameter, new_value)
        new_config = self.schema.get_all()

        print(f'提议: {parameter} {old_value}→{new_value}')
        print(f'理由: {reason}')

        # 2. 回放验证
        tasks = self.replay.generate_tasks(500)
        baseline_config = {**new_config, parameter: old_value}
        baseline_result = self.replay.replay(tasks, baseline_config)
        new_result = self.replay.replay(tasks, new_config)

        # 3. 三态裁决
        sr_change = new_result['success_rate'] - baseline_result['success_rate']
        dur_change = (new_result['avg_duration'] - baseline_result['avg_duration']) / max(
            baseline_result['avg_duration'], 0.001
        )
        tok_change = (new_result['avg_tokens'] - baseline_result['avg_tokens']) / max(baseline_result['avg_tokens'], 1)

        if sr_change > 0.05 and (dur_change < 0.1 or tok_change < 0.1):
            verdict = 'TRUE'
        elif sr_change < -0.05:
            verdict = 'FALSE'
        else:
            verdict = 'UNKNOWN'

        print(f'裁决: {verdict}')
        print(f'  成功率变化: {sr_change:+.1%}')
        print(f'  耗时变化: {dur_change:+.1%}')
        print(f'  Token变化: {tok_change:+.1%}')

        # 4. 应用（仅TRUE）
        if verdict != 'TRUE':
            self.schema.set(parameter, old_value)  # 回滚
            print(f'回滚: {parameter} → {old_value}')
        else:
            print(f'接受: {parameter} = {new_value}')

        # 记录
        self._history.append(
            {
                'parameter': parameter,
                'old': old_value,
                'new': new_value,
                'verdict': verdict,
                'sr_change': sr_change,
            }
        )

        return {
            'parameter': parameter,
            'old': old_value,
            'new': new_value,
            'verdict': verdict,
            'baseline_sr': baseline_result['success_rate'],
            'new_sr': new_result['success_rate'],
        }

    def summary(self) -> str:
        ranking = self.ranker.get_ranking()
        accepted = sum(1 for h in self._history if h['verdict'] == 'TRUE')
        rejected = sum(1 for h in self._history if h['verdict'] == 'FALSE')

        lines = [
            'Phase 2B: Strategy Evolution',
            f'  参数数: {len(self.schema.get_all_parameters())}',
            f'  变更历史: {len(self._history)}次',
            f'  接受: {accepted} | 拒绝: {rejected}',
            '',
            'Parameter Ranking:',
        ]
        for r in ranking:
            lines.append(f'  {r["parameter"]}: {r["impact"]:.1f}% ({r["tier"]})')

        return '\n'.join(lines)
