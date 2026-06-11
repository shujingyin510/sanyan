"""经验学习：工具成功率统计 + 遗忘函数 + 模块风险评估
Agent 从历史中学习，动态调整置信度
"""

import math
import time
from typing import Dict


class ExperienceStore:
    """经验存储：工具成功率 + 模块错误率 + 遗忘衰减"""

    def __init__(self, lambda_decay: float = 0.1):
        # 工具统计：{tool: {success: N, fail: N, last_used: time}}
        self.tool_stats: Dict[str, Dict[str, float]] = {}
        # 模块统计：{module: {error_count: N, total_count: N}}
        self.module_stats: Dict[str, Dict[str, float]] = {}
        # 遗忘系数（每小时衰减比例）
        self.lambda_decay = lambda_decay

    def record(self, tool: str, success: bool, module: str = ''):
        """记录一次工具调用结果"""
        now = time.time()
        if tool not in self.tool_stats:
            self.tool_stats[tool] = {'success': 0, 'fail': 0, 'last_used': now}
        stats = self.tool_stats[tool]
        if success:
            stats['success'] += 1
        else:
            stats['fail'] += 1
        stats['last_used'] = now

        if module:
            if module not in self.module_stats:
                self.module_stats[module] = {'error_count': 0, 'total_count': 0}
            mstats = self.module_stats[module]
            mstats['total_count'] += 1
            if not success:
                mstats['error_count'] += 1

    def tool_reliability(self, tool: str) -> float:
        """工具可靠性：0.0 ~ 1.0，带遗忘衰减"""
        if tool not in self.tool_stats:
            return 0.7
        stats = self.tool_stats[tool]
        total = stats['success'] + stats['fail']
        if total == 0:
            return 0.7
        # 基础可靠性
        base = stats['success'] / total
        # 时间衰减：最近使用的权重更高
        age_hours = (time.time() - stats['last_used']) / 3600
        decay = self.decay(age_hours)
        # 混合：基础 × 衰减 + 未衰减基准
        return base * decay + 0.5 * (1 - decay)

    def module_risk(self, module: str) -> float:
        """模块风险：0.0（安全） ~ 1.0（高风险）"""
        if module not in self.module_stats:
            return 0.0
        stats = self.module_stats[module]
        if stats['total_count'] == 0:
            return 0.0
        return stats['error_count'] / stats['total_count']

    def decay(self, age_hours: float) -> float:
        """遗忘衰减因子：e^{-λ × age}"""
        return math.exp(-self.lambda_decay * age_hours)

    def get_experience_context(self, tool: str = '', module: str = '') -> str:
        """获取经验上下文（注入到 Agent prompt）"""
        parts = []
        if tool and tool in self.tool_stats:
            rel = self.tool_reliability(tool)
            parts.append(f'[{tool} 可靠性={rel:.2f}]')
        if module and module in self.module_stats:
            risk = self.module_risk(module)
            if risk > 0.3:
                parts.append(f'[{module} 风险={risk:.2f}]')
        # Top 3 最不可靠工具
        unreliable = []
        for t, stats in self.tool_stats.items():
            total = stats['success'] + stats['fail']
            if total >= 3:
                rel = self.tool_reliability(t)
                if rel < 0.6:
                    unreliable.append((t, rel))
        unreliable.sort(key=lambda x: x[1])
        if unreliable:
            worst = ', '.join(f'{t}({r:.2f})' for t, r in unreliable[:3])
            parts.append(f'[低可靠性工具: {worst}]')
        return ' '.join(parts) if parts else ''

    def summary(self) -> str:
        """经验摘要"""
        lines = []
        for tool, stats in sorted(self.tool_stats.items()):
            total = stats['success'] + stats['fail']
            if total >= 3:
                rel = self.tool_reliability(tool)
                lines.append(f'  {tool}: {stats["success"]}/{total} ({rel:.2f})')
        return '\n'.join(lines) if lines else '  (无足够经验)'

    def to_dict(self) -> dict:
        return {
            'tool_stats': self.tool_stats,
            'module_stats': self.module_stats,
            'lambda': self.lambda_decay,
        }
