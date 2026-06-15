"""可观测性增强 — 可视化 + 性能分析 + 决策链追踪
P25: DecisionTracer — 完整决策链记录与可视化
P26: PerformanceProfiler — 每步耗时 + Token用量分析
P27: AgentDashboard — 实时仪表盘摘要
"""

import time
from collections import defaultdict
from typing import Any, Dict, List, Optional


class DecisionTracer:
    """决策链追踪器：记录完整决策路径"""

    def __init__(self):
        self._traces: List[Dict[str, Any]] = []
        self._current_trace: Optional[Dict] = None

    def start_trace(self, task: str) -> str:
        """开始一次追踪"""
        trace_id = f'trace_{int(time.time() * 1000)}'
        self._current_trace = {
            'trace_id': trace_id,
            'task': task,
            'steps': [],
            'start_time': time.time(),
            'end_time': None,
            'status': 'running',
        }
        return trace_id

    def add_step(self, step: int, tool: str, params: str, result: str, decision: str = '', confidence: float = 0.5):
        """记录一步决策"""
        if not self._current_trace:
            return

        self._current_trace['steps'].append(
            {
                'step': step,
                'tool': tool,
                'params': str(params)[:200],
                'result': str(result)[:300],
                'decision': decision,
                'confidence': confidence,
                'timestamp': time.time(),
            }
        )

    def end_trace(self, status: str = 'completed', answer: str = ''):
        """结束追踪"""
        if not self._current_trace:
            return

        self._current_trace['end_time'] = time.time()
        self._current_trace['status'] = status
        self._current_trace['answer'] = answer
        self._traces.append(self._current_trace)
        self._current_trace = None

    def get_trace(self, trace_id: str = None) -> Optional[Dict]:
        """获取追踪记录"""
        if trace_id:
            for t in self._traces:
                if t['trace_id'] == trace_id:
                    return t
            return None
        return self._current_trace

    def visualize(self, trace_id: str = None) -> str:
        """可视化决策链"""
        trace = self.get_trace(trace_id)
        if not trace:
            return '(无追踪记录)'

        lines = [
            f'═══ 决策追踪: {trace["trace_id"]} ═══',
            f'任务: {trace["task"][:80]}',
            f'状态: {trace["status"]}',
            '',
        ]

        for step in trace['steps']:
            tool = step['tool']
            confidence = step['confidence']
            decision = step['decision']

            # 置信度指示器
            if confidence > 0.8:
                conf_bar = '█' * 5
            elif confidence > 0.6:
                conf_bar = '█' * 3 + '░' * 2
            elif confidence > 0.4:
                conf_bar = '█' * 2 + '░' * 3
            else:
                conf_bar = '░' * 5

            result_preview = step['result'][:60].replace('\n', ' ')
            lines.append(f'  Step {step["step"]}: [{tool}] conf={conf_bar} {confidence:.2f}')
            if decision:
                lines.append(f'    └─ {decision}')
            lines.append(f'    └─ {result_preview}')

        duration = (trace['end_time'] or time.time()) - trace['start_time']
        lines.append(f'\n总耗时: {duration:.1f}s, 步骤数: {len(trace["steps"])}')

        return '\n'.join(lines)

    def get_summary(self) -> str:
        """获取追踪摘要"""
        if not self._traces:
            return '(无历史追踪)'

        recent = self._traces[-5:]
        parts = [f'最近 {len(recent)} 次执行:']
        for t in recent:
            duration = (t['end_time'] or time.time()) - t['start_time']
            steps = len(t['steps'])
            parts.append(f'  [{t["status"]}] {t["task"][:40]}... ({steps}步, {duration:.1f}s)')
        return '\n'.join(parts)


class PerformanceProfiler:
    """性能分析器：每步耗时 + Token用量"""

    def __init__(self):
        self._records: List[Dict[str, Any]] = []
        self._current: Optional[Dict] = None

    def start(self, task: str):
        """开始性能分析"""
        self._current = {
            'task': task,
            'start_time': time.time(),
            'tool_times': defaultdict(float),
            'tool_counts': defaultdict(int),
            'total_tokens': 0,
            'llm_calls': 0,
            'llm_times': [],
            'steps': [],
        }

    def record_step(self, step: int, tool: str, duration: float, tokens: int = 0):
        """记录一步的性能"""
        if not self._current:
            return

        self._current['tool_times'][tool] += duration
        self._current['tool_counts'][tool] += 1
        self._current['total_tokens'] += tokens
        self._current['steps'].append(
            {
                'step': step,
                'tool': tool,
                'duration': duration,
                'tokens': tokens,
            }
        )

    def record_llm_call(self, duration: float, tokens: int = 0):
        """记录LLM调用"""
        if not self._current:
            return

        self._current['llm_calls'] += 1
        self._current['llm_times'].append(duration)
        self._current['total_tokens'] += tokens

    def end(self) -> Dict[str, Any]:
        """结束分析，返回报告"""
        if not self._current:
            return {}

        self._current['end_time'] = time.time()
        self._current['total_duration'] = self._current['end_time'] - self._current['start_time']
        self._records.append(self._current)
        report = self._generate_report(self._current)
        self._current = None
        return report

    def _generate_report(self, record: Dict) -> Dict[str, Any]:
        """生成性能报告"""
        tool_times = dict(record['tool_times'])
        tool_counts = dict(record['tool_counts'])
        llm_times = record['llm_times']

        return {
            'total_duration': record['total_duration'],
            'total_tokens': record['total_tokens'],
            'llm_calls': record['llm_calls'],
            'avg_llm_time': sum(llm_times) / len(llm_times) if llm_times else 0,
            'tool_breakdown': {
                tool: {
                    'total_time': tool_times[tool],
                    'count': tool_counts[tool],
                    'avg_time': tool_times[tool] / tool_counts[tool],
                }
                for tool in tool_times
            },
            'slowest_tools': sorted(tool_times.items(), key=lambda x: -x[1])[:5] if tool_times else [],
        }

    def format_report(self, report: Dict) -> str:
        """格式化报告为可读文本"""
        if not report:
            return '(无性能数据)'

        lines = [
            '═══ 性能报告 ═══',
            f'总耗时: {report.get("total_duration", 0):.2f}s',
            f'Token用量: {report.get("total_tokens", 0)}',
            f'LLM调用: {report.get("llm_calls", 0)}次 (平均{report.get("avg_llm_time", 0):.2f}s)',
            '',
            '工具耗时:',
        ]

        for tool, info in report.get('tool_breakdown', {}).items():
            lines.append(f'  {tool}: {info["total_time"]:.2f}s ({info["count"]}次, 平均{info["avg_time"]:.2f}s)')

        if report.get('slowest_tools'):
            lines.append('\n最慢工具:')
            for tool, time_val in report['slowest_tools']:
                lines.append(f'  {tool}: {time_val:.2f}s')

        return '\n'.join(lines)

    def get_history(self, limit: int = 10) -> List[Dict]:
        """获取历史性能记录"""
        return self._records[-limit:]


class AgentDashboard:
    """Agent 实时仪表盘"""

    def __init__(self):
        self.tracer = DecisionTracer()
        self.profiler = PerformanceProfiler()
        self._alerts: List[str] = []

    def alert(self, message: str):
        """添加告警"""
        self._alerts.append(f'[{time.strftime("%H:%M:%S")}] {message}')

    def get_status(self, runtime=None) -> str:
        """获取实时状态"""
        lines = ['═══ Agent 仪表盘 ═══', '']

        # 决策追踪
        trace_summary = self.tracer.get_summary()
        if trace_summary:
            lines.append(trace_summary)

        # 性能数据
        if self.profiler._current:
            elapsed = time.time() - self.profiler._current['start_time']
            lines.append(f'\n当前运行: {elapsed:.1f}s')
            lines.append(f'Token已用: {self.profiler._current["total_tokens"]}')

        # 告警
        if self._alerts:
            lines.append(f'\n最近告警 ({len(self._alerts)}):')
            for alert in self._alerts[-3:]:
                lines.append(f'  {alert}')

        return '\n'.join(lines)

    def clear_alerts(self):
        """清除告警"""
        self._alerts.clear()
