"""并行执行引擎 — 工具链并行 + 假设并行验证 + 结果融合
P14: ParallelExecutor — 独立工具并行执行
P15: HypothesisParaller — 多假设并行验证
"""

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Dict, List, Tuple

from agent_system.agent_tool_graph import ToolMetadata, DEFAULT_TOOL_META


class ParallelExecutor:
    """并行执行引擎：分析工具依赖，独立工具并行执行"""

    def __init__(self, tools: Dict[str, Callable], meta: ToolMetadata = None):
        self.tools = tools
        self.meta = meta or DEFAULT_TOOL_META
        self.max_workers = 4
        self._results: Dict[str, Any] = {}
        self._lock = threading.Lock()

    def execute_chain(
        self, tool_chain: List[str], params_chain: List[str], dry_run: bool = False
    ) -> List[Tuple[str, Any]]:
        """执行工具链，自动并行化独立步骤"""
        if not tool_chain:
            return []

        groups = self.meta.get_parallel_group(tool_chain)
        all_results: List[Tuple[str, Any]] = []

        for group in groups:
            if len(group) == 1:
                # 单工具，直接执行
                tool = group[0]
                idx = tool_chain.index(tool)
                params = params_chain[idx] if idx < len(params_chain) else ''
                result = self._execute_one(tool, params, dry_run)
                all_results.append((tool, result))
            else:
                # 多工具并行
                futures = {}
                with ThreadPoolExecutor(max_workers=min(self.max_workers, len(group))) as executor:
                    for tool in group:
                        idx = tool_chain.index(tool)
                        params = params_chain[idx] if idx < len(params_chain) else ''
                        future = executor.submit(self._execute_one, tool, params, dry_run)
                        futures[future] = tool

                for future in as_completed(futures):
                    tool = futures[future]
                    try:
                        result = future.result(timeout=30)
                    except Exception as e:
                        result = f'并行执行超时: {e}'
                    all_results.append((tool, result))

        return all_results

    def execute_parallel_tasks(self, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """并行执行多个独立任务
        每个任务: {'tool': name, 'params': str, 'id': str}
        """
        if not tasks:
            return []

        results = []
        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(tasks))) as executor:
            future_map = {}
            for task in tasks:
                future = executor.submit(
                    self._execute_one,
                    task['tool'],
                    task.get('params', ''),
                    task.get('dry_run', False),
                )
                future_map[future] = task.get('id', task['tool'])

            for future in as_completed(future_map):
                task_id = future_map[future]
                try:
                    result = future.result(timeout=30)
                    results.append({'id': task_id, 'result': result, 'success': True})
                except Exception as e:
                    results.append({'id': task_id, 'result': str(e), 'success': False})

        return results

    def _execute_one(self, tool: str, params: str, dry_run: bool) -> Any:
        """执行单个工具"""
        if tool not in self.tools:
            return f'未知工具: {tool}'
        try:
            return self.tools[tool](params, dry_run)
        except Exception as e:
            return f'工具执行异常: {e}'

    def analyze_parallelism(self, tool_chain: List[str]) -> Dict[str, Any]:
        """分析工具链的并行度"""
        groups = self.meta.get_parallel_group(tool_chain)
        total_steps = len(groups)
        parallel_steps = sum(1 for g in groups if len(g) > 1)
        max_parallel = max((len(g) for g in groups), default=1)

        return {
            'total_tools': len(tool_chain),
            'sequential_steps': total_steps,
            'parallel_steps': parallel_steps,
            'max_parallelism': max_parallel,
            'estimated_speedup': len(tool_chain) / max(total_steps, 1),
            'groups': [[t for t in g] for g in groups],
        }


class HypothesisParaller:
    """多假设并行验证：同时执行多个假设的前N步，提前淘汰低质量假设"""

    def __init__(self, tools: Dict[str, Callable], max_workers: int = 3):
        self.tools = tools
        self.max_workers = max_workers
        self.executor = ParallelExecutor(tools)

    def parallel_validate(self, hypotheses: list, context: Any, steps: int = 2) -> List[Tuple[Any, float]]:
        """并行验证多个假设的前N步，返回 (假设, 最终置信度)"""
        if not hypotheses:
            return []
        if len(hypotheses) == 1:
            h = hypotheses[0]
            return [(h, h.confidence)]

        results = []
        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(hypotheses))) as pool:
            future_map = {}
            for h in hypotheses:
                future = pool.submit(self._validate_one, h, context, steps)
                future_map[future] = h

            for future in as_completed(future_map):
                h = future_map[future]
                try:
                    final_conf = future.result(timeout=30)
                    results.append((h, final_conf))
                except Exception:
                    results.append((h, 0.0))

        return results

    def _validate_one(self, hypothesis, context, steps: int) -> float:
        """验证单个假设的前N步"""
        ctx_str = context.build() if hasattr(context, 'build') else str(context)
        for _ in range(steps):
            if hypothesis.confidence < 0.2:
                break
            if not hypothesis.tools_used:
                break
            tool_name = hypothesis.tools_used[0] if hypothesis.tools_used else None
            if not tool_name or tool_name not in self.tools:
                hypothesis.confidence *= 0.5
                continue
            try:
                result = self.tools[tool_name](ctx_str, False)
                if 'error' in str(result).lower() or '失败' in str(result):
                    hypothesis.confidence *= 0.7
                else:
                    hypothesis.confidence = min(0.99, hypothesis.confidence * 1.1)
            except Exception:
                hypothesis.confidence *= 0.5
        return hypothesis.confidence
