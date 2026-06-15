"""Cost-Aware Evolution — 收益/成本感知

核心指标：
  Expected Improvement / Evaluation Cost

组件：
  P61: CostTracker — 追踪每次验证的成本
  P62: CostAwareRanker — 基于成本效益的参数排名
  P63: ExplorationBudget — 探索预算管理
  P64: UCBExploration — UCB探索策略
"""

import math
import os
import sqlite3
import time
from typing import Dict, List, Optional

ROOT = os.path.dirname(os.path.abspath(__file__))


# ── Cost Tracker ──


class CostTracker:
    """追踪每次验证的成本"""

    DB_PATH = os.path.join(ROOT, 'agent_cost_tracking.db')

    def __init__(self):
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.DB_PATH)
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS verification_costs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parameter TEXT,
                improvement REAL,
                verification_time REAL,
                tasks_replayed INTEGER,
                tokens_used INTEGER,
                cost_efficiency REAL,
                created_at REAL
            );
        """)
        conn.commit()
        conn.close()

    def record_verification(
        self, parameter: str, improvement: float, verification_time: float, tasks_replayed: int, tokens_used: int = 0
    ):
        """记录验证成本"""
        # 成本 = 时间（秒）+ Token/1000
        cost = verification_time + tokens_used / 1000

        # 效率 = 改进 / 成本（改进越大，成本越低，效率越高）
        efficiency = improvement / max(cost, 0.001)

        conn = sqlite3.connect(self.DB_PATH)
        conn.execute(
            """
            INSERT INTO verification_costs
            (parameter, improvement, verification_time, tasks_replayed, tokens_used, cost_efficiency, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (parameter, improvement, verification_time, tasks_replayed, tokens_used, efficiency, time.time()),
        )
        conn.commit()
        conn.close()

        return efficiency

    def get_parameter_costs(self, parameter: str) -> List[Dict]:
        """获取参数的验证成本历史"""
        conn = sqlite3.connect(self.DB_PATH)
        rows = conn.execute(
            'SELECT improvement, verification_time, tasks_replayed, cost_efficiency, created_at FROM verification_costs WHERE parameter=? ORDER BY created_at DESC',
            (parameter,),
        ).fetchall()
        conn.close()

        return [
            {
                'improvement': r[0],
                'time': r[1],
                'tasks': r[2],
                'efficiency': r[3],
                'created_at': r[4],
            }
            for r in rows
        ]

    def get_average_cost(self, parameter: str) -> Dict:
        """获取参数的平均验证成本"""
        conn = sqlite3.connect(self.DB_PATH)
        row = conn.execute(
            'SELECT AVG(verification_time), AVG(cost_efficiency), COUNT(*) FROM verification_costs WHERE parameter=?',
            (parameter,),
        ).fetchone()
        conn.close()

        if not row or row[2] == 0:
            return {'avg_time': 0, 'avg_efficiency': 0, 'count': 0}

        return {
            'avg_time': row[0] or 0,
            'avg_efficiency': row[1] or 0,
            'count': row[2],
        }


# ── Cost-Aware Ranker ──


class CostAwareRanker:
    """基于成本效益的参数排名"""

    def __init__(self):
        self.cost_tracker = CostTracker()

    def rank_parameters(self, parameters: List[Dict], improvements: Dict[str, float]) -> List[Dict]:
        """基于成本效益排名参数

        Args:
            parameters: 参数列表 [{name, impact, tier, ...}]
            improvements: 参数改进 {param_name: improvement_pct}
        """
        ranked = []

        for param in parameters:
            name = param['name']
            improvement = improvements.get(name, 0)
            cost_info = self.cost_tracker.get_average_cost(name)

            # 计算成本效益
            if cost_info['count'] > 0:
                # 有历史数据：用历史平均成本
                efficiency = improvement / max(cost_info['avg_time'], 0.001)
            else:
                # 无历史数据：假设标准成本（100任务≈1秒）
                efficiency = improvement / 1.0

            ranked.append(
                {
                    'name': name,
                    'improvement': improvement,
                    'avg_cost_time': cost_info['avg_time'],
                    'efficiency': efficiency,
                    'tier': param.get('tier', 'Tier 4'),
                    'verification_count': cost_info['count'],
                }
            )

        # 按效率排序
        ranked.sort(key=lambda x: -x['efficiency'])
        return ranked

    def get_best_to_explore(
        self, parameters: List[Dict], improvements: Dict[str, float], budget_remaining: float = 60
    ) -> Optional[str]:
        """获取当前最值得探索的参数"""
        ranked = self.rank_parameters(parameters, improvements)

        for param in ranked:
            # 估算验证时间
            if param['avg_cost_time'] > 0:
                estimated_time = param['avg_cost_time']
            else:
                estimated_time = 10.0  # 默认10秒

            # 检查预算
            if estimated_time <= budget_remaining:
                return param['name']

        return None


# ── Exploration Budget ──


class ExplorationBudget:
    """探索预算管理"""

    def __init__(self, total_budget: float = 300):  # 默认5分钟
        self.total_budget = total_budget
        self.remaining = total_budget
        self._spent: List[Dict] = []

    def spend(self, parameter: str, amount: float, improvement: float = 0):
        """花费预算"""
        self.remaining = max(0, self.remaining - amount)
        self._spent.append(
            {
                'parameter': parameter,
                'amount': amount,
                'improvement': improvement,
                'time': time.time(),
            }
        )

    def can_afford(self, estimated_cost: float) -> bool:
        """是否能负担"""
        return self.remaining >= estimated_cost

    def get_status(self) -> Dict:
        """获取预算状态"""
        return {
            'total': self.total_budget,
            'remaining': self.remaining,
            'spent': self.total_budget - self.remaining,
            'utilization': (self.total_budget - self.remaining) / max(self.total_budget, 1),
        }

    def summary(self) -> str:
        status = self.get_status()
        return f'探索预算: {status["remaining"]:.1f}s / {status["total"]:.1f}s (已用 {status["utilization"]:.0%})'


# ── UCB Exploration ──


class UCBExploration:
    """UCB探索策略：平衡探索与利用"""

    def __init__(self, exploration_constant: float = 1.41):
        self.c = exploration_constant
        self._counts: Dict[str, int] = {}
        self._values: Dict[str, float] = {}

    def select(self, parameters: List[str]) -> str:
        """UCB1选择参数"""
        # 未探索过的参数优先
        for p in parameters:
            if p not in self._counts or self._counts[p] == 0:
                return p

        # UCB1公式
        total_plays = sum(self._counts.values())
        best_score = -1
        best_param = parameters[0]

        for p in parameters:
            if p not in self._counts:
                continue

            avg_value = self._values.get(p, 0) / max(self._counts[p], 1)
            exploration = self.c * math.sqrt(math.log(total_plays + 1) / self._counts[p])
            ucb_score = avg_value + exploration

            if ucb_score > best_score:
                best_score = ucb_score
                best_param = p

        return best_param

    def update(self, parameter: str, value: float):
        """更新参数价值"""
        self._counts[parameter] = self._counts.get(parameter, 0) + 1
        self._values[parameter] = self._values.get(parameter, 0) + value

    def get_stats(self) -> Dict:
        """获取统计"""
        stats = {}
        for p in self._counts:
            count = self._counts[p]
            avg = self._values.get(p, 0) / max(count, 1)
            stats[p] = {'count': count, 'avg_value': avg}
        return stats

    def summary(self) -> str:
        stats = self.get_stats()
        lines = ['UCB Exploration Stats:']
        for p, s in sorted(stats.items(), key=lambda x: -x[1]['avg_value']):
            lines.append(f'  {p}: {s["count"]}次, 平均价值={s["avg_value"]:.3f}')
        return '\n'.join(lines)


# ── 整合 Cost-Aware Evolution ──


class CostAwareEvolution:
    """Cost-Aware Evolution 系统"""

    def __init__(self, total_budget: float = 300):
        self.cost_tracker = CostTracker()
        self.ranker = CostAwareRanker()
        self.budget = ExplorationBudget(total_budget)
        self.ucb = UCBExploration()
        self._history: List[Dict] = []

    def evaluate_parameter(
        self, parameter: str, improvement: float, verification_time: float, tasks_replayed: int
    ) -> Dict:
        """评估参数（记录成本+更新UCB）"""
        # 记录成本
        efficiency = self.cost_tracker.record_verification(parameter, improvement, verification_time, tasks_replayed)

        # 花费预算
        self.budget.spend(parameter, verification_time, improvement)

        # 更新UCB
        self.ucb.update(parameter, improvement)

        # 记录历史
        self._history.append(
            {
                'parameter': parameter,
                'improvement': improvement,
                'time': verification_time,
                'efficiency': efficiency,
                'budget_remaining': self.budget.remaining,
            }
        )

        return {
            'parameter': parameter,
            'improvement': improvement,
            'time': verification_time,
            'efficiency': efficiency,
            'budget': self.budget.get_status(),
        }

    def select_next_parameter(self, parameters: List[Dict], improvements: Dict[str, float]) -> Optional[str]:
        """选择下一个最值得探索的参数"""
        # 检查预算
        if self.budget.remaining <= 10:
            return None

        # UCB选择
        param_names = [p['name'] for p in parameters]
        selected = self.ucb.select(param_names)

        return selected

    def get_efficiency_report(self, parameters: List[Dict], improvements: Dict[str, float]) -> str:
        """生成效率报告"""
        ranked = self.ranker.rank_parameters(parameters, improvements)

        lines = [
            '╔══════════════════════════════════════════════════════╗',
            '║     Cost-Aware Parameter Ranking                    ║',
            '╠══════════════════════════════════════════════════════╣',
            '║  参数              改进      成本     效率   Tier  ║',
            '╠══════════════════════════════════════════════════════╣',
        ]

        for r in ranked[:10]:
            name = r['name'][:20].ljust(20)
            imp = f'{r["improvement"]:.1f}%'.rjust(6)
            cost = f'{r["avg_cost_time"]:.1f}s'.rjust(6) if r['avg_cost_time'] > 0 else '  N/A'
            eff = f'{r["efficiency"]:.2f}'.rjust(6)
            tier = r['tier'][-1]  # 只取数字
            lines.append(f'║  {name} {imp}  {cost}  {eff}   T{tier}   ║')

        lines.extend(
            [
                '╠══════════════════════════════════════════════════════╣',
                f'║  {self.budget.summary():50s}║',
                '╚══════════════════════════════════════════════════════╝',
            ]
        )

        return '\n'.join(lines)

    def summary(self) -> str:
        return (
            f'Cost-Aware Evolution:\n  {self.budget.summary()}\n  验证次数: {len(self._history)}\n{self.ucb.summary()}'
        )
