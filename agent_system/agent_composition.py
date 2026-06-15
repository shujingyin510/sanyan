"""高阶工具组合 — 工具链嵌套 + 管道 + 条件执行
P31: ToolPipeline — 工具管道（Unix风格管道）
P32: ToolComposer — 高阶工具组合（工具使用工具）
P33: ConditionalChain — 条件工具链
"""

from typing import Any, Callable, Dict, List, Tuple


class ToolPipeline:
    """工具管道：前一个工具的输出作为下一个的输入"""

    def __init__(self, tools: Dict[str, Callable]):
        self.tools = tools
        self._pipelines: Dict[str, List[str]] = {}

    def define(self, name: str, steps: List[str]):
        """定义管道: name = [tool1, tool2, tool3]"""
        self._pipelines[name] = steps

    def execute(self, pipeline_name: str, initial_input: str, dry_run: bool = False) -> Tuple[str, List[Dict]]:
        """执行管道，返回 (最终结果, 执行记录)"""
        if pipeline_name not in self._pipelines:
            return f'未知管道: {pipeline_name}', []

        steps = self._pipelines[pipeline_name]
        current_input = initial_input
        history = []

        for i, tool_name in enumerate(steps):
            if tool_name not in self.tools:
                history.append(
                    {
                        'step': i,
                        'tool': tool_name,
                        'input': current_input[:200],
                        'result': f'未知工具: {tool_name}',
                        'success': False,
                    }
                )
                continue

            try:
                result = self.tools[tool_name](current_input, dry_run)
                history.append(
                    {
                        'step': i,
                        'tool': tool_name,
                        'input': current_input[:200],
                        'result': str(result)[:200],
                        'success': True,
                    }
                )
                current_input = str(result)
            except Exception as e:
                history.append(
                    {
                        'step': i,
                        'tool': tool_name,
                        'input': current_input[:200],
                        'result': str(e)[:200],
                        'success': False,
                    }
                )
                break

        return current_input, history

    def execute_parallel(self, pipeline_name: str, initial_input: str, dry_run: bool = False) -> str:
        """并行执行管道（无依赖的步骤）"""
        if pipeline_name not in self._pipelines:
            return f'未知管道: {pipeline_name}'

        from concurrent.futures import ThreadPoolExecutor, as_completed

        steps = self._pipelines[pipeline_name]
        results = {}

        with ThreadPoolExecutor(max_workers=min(4, len(steps))) as pool:
            futures = {}
            for i, tool_name in enumerate(steps):
                if tool_name in self.tools:
                    future = pool.submit(self.tools[tool_name], initial_input, dry_run)
                    futures[future] = i

            for future in as_completed(futures):
                i = futures[future]
                try:
                    results[i] = future.result(timeout=30)
                except Exception as e:
                    results[i] = f'错误: {e}'

        # 合并结果
        merged = '\n'.join(f'[{steps[i]}] {results[i]}' for i in sorted(results.keys()))
        return merged

    def list_pipelines(self) -> List[str]:
        """列出所有管道"""
        return list(self._pipelines.keys())


class ToolComposer:
    """高阶工具组合：定义复合工具"""

    def __init__(self, tools: Dict[str, Callable]):
        self.tools = tools
        self._composites: Dict[str, Dict] = {}

    def define_composite(
        self, name: str, description: str, steps: List[Dict[str, Any]], parallel_groups: List[List[int]] = None
    ):
        """定义复合工具

        Args:
            name: 工具名
            description: 描述
            steps: 步骤列表，每步 {'tool': str, 'params_template': str, 'condition': str}
            parallel_groups: 可并行的步骤组 [[0,1], [2]] 表示0和1可并行
        """
        self._composites[name] = {
            'description': description,
            'steps': steps,
            'parallel_groups': parallel_groups or [],
        }

    def execute(self, name: str, context: Dict[str, str] = None, dry_run: bool = False) -> str:
        """执行复合工具"""
        if name not in self._composites:
            return f'未知复合工具: {name}'

        composite = self._composites[name]
        steps = composite['steps']
        context = context or {}
        results = []

        for i, step in enumerate(steps):
            tool_name = step['tool']
            params_template = step.get('params_template', '')

            # 模板替换: {input} -> 上一步结果, {var_x} -> context变量
            params = params_template
            if '{input}' in params and results:
                params = params.replace('{input}', str(results[-1])[:500])
            for key, val in context.items():
                params = params.replace('{' + key + '}', str(val))

            # 条件检查
            condition = step.get('condition', '')
            if condition:
                if not self._check_condition(condition, context, results):
                    results.append(f'[跳过] {tool_name} 条件不满足')
                    continue

            # 执行
            if tool_name in self.tools:
                try:
                    result = self.tools[tool_name](params, dry_run)
                    results.append(str(result)[:500])
                except Exception as e:
                    results.append(f'错误: {e}')
            else:
                results.append(f'未知工具: {tool_name}')

        return results[-1] if results else '无结果'

    def _check_condition(self, condition: str, context: Dict, results: List) -> bool:
        """检查条件"""
        # 简单条件: "last_contains:X" "context_equals:key:value"
        if condition.startswith('last_contains:'):
            keyword = condition[14:]
            return bool(results and keyword in str(results[-1]))
        elif condition.startswith('context_equals:'):
            parts = condition[15:].split(':')
            if len(parts) == 2:
                return context.get(parts[0]) == parts[1]
        return True

    def list_composites(self) -> List[Dict[str, str]]:
        """列出所有复合工具"""
        return [
            {'name': name, 'description': info['description'], 'steps': len(info['steps'])}
            for name, info in self._composites.items()
        ]


class ConditionalChain:
    """条件工具链：根据条件选择不同的工具路径"""

    def __init__(self, tools: Dict[str, Callable]):
        self.tools = tools
        self._branches: Dict[str, Dict] = {}

    def define_branch(self, name: str, condition_tool: str, true_branch: List[str], false_branch: List[str]):
        """定义条件分支"""
        self._branches[name] = {
            'condition_tool': condition_tool,
            'true_branch': true_branch,
            'false_branch': false_branch,
        }

    def execute(self, name: str, input_data: str, dry_run: bool = False) -> Tuple[str, str]:
        """执行条件链，返回 (结果, 走的分支)"""
        if name not in self._branches:
            return f'未知分支: {name}', ''

        branch = self._branches[name]
        cond_tool = branch['condition_tool']

        # 执行条件工具
        if cond_tool in self.tools:
            try:
                cond_result = self.tools[cond_tool](input_data, dry_run)
                is_true = self._evaluate_condition(cond_result)
            except Exception as e:
                return f'条件执行失败: {e}', ''
        else:
            return f'未知条件工具: {cond_tool}', ''

        # 选择分支
        steps = branch['true_branch'] if is_true else branch['false_branch']
        chosen = 'true' if is_true else 'false'

        # 执行分支
        current = input_data
        for tool_name in steps:
            if tool_name in self.tools:
                try:
                    current = str(self.tools[tool_name](current, dry_run))
                except Exception as e:
                    return f'执行失败: {e}', chosen

        return current, chosen

    def _evaluate_condition(self, result: Any) -> bool:
        """评估条件结果"""
        result_str = str(result).lower()
        # 真值判断
        if result_str in ('true', '1', 'yes', '是', '真', '通过'):
            return True
        if result_str in ('false', '0', 'no', '否', '假', '失败'):
            return False
        # 包含判断
        return 'true' in result_str or 'pass' in result_str or '通过' in result_str
