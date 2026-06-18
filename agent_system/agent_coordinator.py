"""多 Agent 协作 — 子 Agent 并行执行

功能：
  1. 主 Agent 分解任务为子任务
  2. 子 Agent 并行执行子任务
  3. 主 Agent 汇总结果

用法：
  coordinator = AgentCoordinator()
  results = coordinator.run_parallel([
      {'name': '分析代码', 'task': '分析 evaluator.py 的结构'},
      {'name': '编写测试', 'task': '为 evaluator.py 编写单元测试'},
      {'name': '更新文档', 'task': '更新 README 中的 evaluator 部分'},
  ])
"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Dict, List, Optional


class SubAgent:
    """子 Agent"""

    def __init__(self, name: str, llm_fn: Callable, tools: Dict[str, Callable]):
        self.name = name
        self.llm_fn = llm_fn
        self.tools = tools
        self.history: List[Dict] = []

    def run(self, task: str, max_rounds: int = 5) -> Dict:
        """执行任务"""
        start_time = time.time()
        result = {
            'name': self.name,
            'task': task,
            'success': False,
            'answer': '',
            'tools_used': [],
            'duration': 0,
        }

        try:
            # 构建上下文
            context = (
                f'你是子Agent "{self.name}"，负责执行以下任务:\n{task}\n\n可用工具: {", ".join(self.tools.keys())}'
            )

            for round_num in range(max_rounds):
                # 调用 LLM
                prompt = f'{context}\n\n请完成任务。输出格式: {{"tool":"工具名","args":{{"参数":"值"}}}}'
                raw = self.llm_fn(prompt)

                # 解析工具调用
                tool_name, params = self._parse_tool(raw)

                if tool_name == 'done':
                    result['success'] = True
                    # 提取 answer
                    if isinstance(params, dict):
                        result['answer'] = params.get('answer', '完成')
                    else:
                        result['answer'] = str(params) if params else '完成'
                    break

                if tool_name and tool_name in self.tools:
                    try:
                        tool_result = self.tools[tool_name](params, False)
                        result['tools_used'].append(tool_name)
                        self.history.append(
                            {
                                'tool': tool_name,
                                'params': str(params)[:100],
                                'result': str(tool_result)[:200],
                            }
                        )
                        context += f'\n\n[{tool_name}] 结果: {str(tool_result)[:500]}'
                    except Exception as e:
                        context += f'\n\n[{tool_name}] 错误: {e}'

        except Exception as e:
            result['answer'] = f'执行失败: {e}'

        result['duration'] = time.time() - start_time
        return result

    def _parse_tool(self, raw: str) -> tuple:
        """解析工具调用"""
        import json
        import re

        raw = raw.strip()
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group())
                return data.get('tool', ''), data.get('args', {})
            except json.JSONDecodeError:
                pass

        # 尝试 pipe 格式
        if '|' in raw:
            parts = raw.split('|', 1)
            return parts[0].strip(), parts[1].strip()

        return '', ''


class AgentCoordinator:
    """Agent 协调器"""

    def __init__(self, llm_fn: Optional[Callable] = None, tools: Optional[Dict[str, Callable]] = None):
        self.llm_fn = llm_fn
        self.tools = tools or {}
        self.sub_agents: Dict[str, SubAgent] = {}
        self.results: List[Dict] = []

    def create_sub_agent(
        self, name: str, llm_fn: Optional[Callable] = None, tools: Optional[Dict[str, Callable]] = None
    ) -> SubAgent:
        """创建子 Agent"""
        agent = SubAgent(
            name=name,
            llm_fn=llm_fn or self.llm_fn,
            tools=tools or self.tools,
        )
        self.sub_agents[name] = agent
        return agent

    def run_parallel(self, tasks: List[Dict], max_workers: int = 3) -> List[Dict]:
        """并行执行多个任务

        Args:
            tasks: [{'name': '任务名', 'task': '任务描述'}, ...]
            max_workers: 最大并行数

        Returns:
            [{'name': '任务名', 'success': True/False, 'answer': '结果', ...}, ...]
        """
        results = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {}
            for task_info in tasks:
                name = task_info.get('name', f'task_{len(futures)}')
                task = task_info.get('task', '')

                # 创建子 Agent
                agent = self.create_sub_agent(name)

                # 提交任务
                future = executor.submit(agent.run, task)
                futures[future] = name

            # 收集结果
            for future in as_completed(futures):
                name = futures[future]
                try:
                    result = future.result(timeout=120)
                    results.append(result)
                    status = '✓' if result['success'] else '✗'
                    print(f'  [{status}] {name}: {result["answer"][:50]}')
                except Exception as e:
                    results.append(
                        {
                            'name': name,
                            'success': False,
                            'answer': f'执行失败: {e}',
                            'duration': 0,
                        }
                    )

        self.results = results
        return results

    def run_sequential(self, tasks: List[Dict]) -> List[Dict]:
        """顺序执行多个任务（前一个的结果传给后一个）"""
        results = []
        context = ''

        for task_info in tasks:
            name = task_info.get('name', f'task_{len(results)}')
            task = task_info.get('task', '')

            # 创建子 Agent
            agent = self.create_sub_agent(name)

            # 执行任务（带上之前的上下文）
            full_task = f'{task}\n\n之前的上下文:\n{context}' if context else task
            result = agent.run(full_task)
            results.append(result)

            # 更新上下文
            context += f'\n[{name}] {result["answer"][:200]}'

            status = '✓' if result['success'] else '✗'
            print(f'  [{status}] {name}: {result["answer"][:50]}')

        self.results = results
        return results

    def get_summary(self) -> str:
        """获取执行摘要"""
        if not self.results:
            return '（无结果）'

        total = len(self.results)
        success = sum(1 for r in self.results if r['success'])
        failed = total - success
        total_time = sum(r.get('duration', 0) for r in self.results)

        lines = [
            'Agent 协作摘要:',
            f'  总任务: {total}',
            f'  成功: {success}',
            f'  失败: {failed}',
            f'  总耗时: {total_time:.1f}s',
            '',
            '详细结果:',
        ]

        for r in self.results:
            status = '✓' if r['success'] else '✗'
            answer = str(r.get('answer', ''))[:60]
            lines.append(f'  [{status}] {r["name"]}: {answer}')

        return '\n'.join(lines)

    def decompose_task(self, task: str) -> List[Dict]:
        """用 LLM 分解任务为子任务"""
        if not self.llm_fn:
            # 无 LLM 时返回单个任务
            return [{'name': '主任务', 'task': task}]

        prompt = f"""将以下任务分解为可并行执行的子任务。

任务: {task[:300]}

请用 JSON 格式回答:
[
  {{"name": "子任务1名称", "task": "子任务1描述"}},
  {{"name": "子任务2名称", "task": "子任务2描述"}}
]

要求:
1. 子任务可以独立执行
2. 子任务数量 2-5 个
3. 只输出 JSON，不要其他文字"""

        try:
            raw = self.llm_fn(prompt)
            import json
            import re

            match = re.search(r'\[.*\]', raw, re.DOTALL)
            if match:
                tasks = json.loads(match.group())
                return tasks
        except Exception:
            pass

        # 降级：返回单个任务
        return [{'name': '主任务', 'task': task}]


def run_parallel_tasks(tasks: List[Dict], llm_fn: Callable, tools: Dict[str, Callable]) -> List[Dict]:
    """并行执行任务的便捷函数"""
    coordinator = AgentCoordinator(llm_fn=llm_fn, tools=tools)
    return coordinator.run_parallel(tasks)
