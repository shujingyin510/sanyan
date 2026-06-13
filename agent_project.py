"""Agent 项目引擎 — 任务分解 → 执行 → 验证 → 重试 → 完成

用法:
    from agent_project import ProjectRunner
    runner = ProjectRunner(rt)  # rt = AgentRuntime
    result = runner.run(\"写一个水仙花数计算器\")

流程:
    1. 接收项目规格
    2. 拆成子任务 (TaskDecomposer)
    3. 按依赖顺序执行 (ProjectExecutor)
    4. 每步验证 + 失败重试 (Validator + RetryLoop)
    5. 输出完成报告
"""

import os
import time
import subprocess
from dataclasses import dataclass, field
from enum import Enum


class TaskStatus(Enum):
    PENDING = 'pending'
    RUNNING = 'running'
    DONE = 'done'
    FAILED = 'failed'
    RETRY = 'retry'
    SKIPPED = 'skipped'


@dataclass
class ProjectTask:
    name: str
    description: str
    tools: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    validation: str = ''  # python -m pytest tests/xxx.py
    status: TaskStatus = TaskStatus.PENDING
    result: str = ''
    retries: int = 0
    max_retries: int = 3


@dataclass
class ProjectResult:
    success: bool
    tasks: list[ProjectTask]
    summary: str


class ProjectOrchestrator:
    """项目编排引擎 — 分解、执行、验证、重试的完整循环"""

    def __init__(self, rt=None, tools: dict = None):
        """rt: AgentRuntime (V5引擎), tools: 可用工具字典"""
        self.rt = rt
        self.tools = tools or {}
        self.memory = {}  # 跨任务记忆
        self.errors = []  # 错误日志

    def _llm_decompose(self, spec: str) -> list[ProjectTask]:
        """任务分解：用 LLM 拆项目为子任务"""
        # 如果 AgentRuntime 可用，用它的分解引擎
        if self.rt and self.rt.decomposition_engine:
            try:
                result = self.rt.decomposition_engine.decompose(spec)
                if result:
                    tasks = []
                    for item in result if isinstance(result, list) else [result]:
                        tasks.append(
                            ProjectTask(
                                name=item.get('name', 'task'),
                                description=item.get('desc', spec),
                                tools=item.get('tools', []),
                                depends_on=item.get('depends', []),
                                validation=item.get('test', ''),
                            )
                        )
                    return tasks
            except Exception as e:
                self.errors.append(f'LLM decompose failed: {e}')

        # 回退：基于模式的分词法分解
        return self._rule_decompose(spec)

    def _rule_decompose(self, spec: str) -> list[ProjectTask]:
        """规则分解：按关键词拆解任务"""
        tasks = []
        keywords = {
            '写': ('实现代码', ['write_file', 'read_file']),
            '定义': ('定义函数', ['write_file']),
            '编译': ('编译验证', ['run_test']),
            '测试': ('运行测试', ['run_test']),
            '检查': ('代码检查', ['analyze', 'search']),
            '优化': ('性能优化', ['write_file', 'run_test']),
            '文档': ('写文档', ['write_file']),
        }
        for kw, (desc, tools) in keywords.items():
            if kw in spec:
                tasks.append(
                    ProjectTask(
                        name=desc,
                        description=f'{spec}',
                        tools=tools,
                        depends_on=[t.name for t in tasks[-1:]] if tasks else [],
                    )
                )
        if not tasks:
            tasks.append(ProjectTask(name='实现', description=spec, tools=['write_file', 'run_test']))
        return tasks

    def _execute_task(self, task: ProjectTask, workspace: str = '.') -> bool:
        """执行单个任务"""
        task.status = TaskStatus.RUNNING
        print(f'  [{task.name}] 执行中...')

        # 1. 根据工具类型执行
        for tool in task.tools:
            if tool in self.tools:
                try:
                    result = self.tools[tool](task.description)
                    task.result += str(result)[:500]
                except Exception as e:
                    self.errors.append(f'{task.name}: {tool} failed: {e}')
                    task.status = TaskStatus.FAILED
                    return False

        # 2. 验证
        if task.validation:
            if not self._validate(task):
                task.status = TaskStatus.FAILED
                return False

        task.status = TaskStatus.DONE
        return True

    def _validate(self, task: ProjectTask) -> bool:
        """验证任务结果"""
        cmd = task.validation
        try:
            r = subprocess.run(
                cmd.split() if isinstance(cmd, str) else cmd,
                capture_output=True,
                text=True,
                timeout=30,
                cwd='.',
            )
            if r.returncode != 0:
                task.result = f'验证失败: {r.stderr[:300]}'
                return False
            return True
        except Exception as e:
            task.result = f'验证异常: {e}'
            return False

    def _retry_loop(self, task: ProjectTask) -> bool:
        """重试循环：失败后最多重试 max_retries 次"""
        while task.retries < task.max_retries:
            if self._execute_task(task):
                return True
            task.retries += 1
            task.status = TaskStatus.RETRY
            print(f'  [{task.name}] 重试 {task.retries}/{task.max_retries}')
            time.sleep(1)

        task.status = TaskStatus.FAILED
        return False

    def _topological_order(self, tasks: list[ProjectTask]) -> list[ProjectTask]:
        """拓扑排序：按依赖关系排序"""
        name_to_task = {t.name: t for t in tasks}
        visited = set()
        order = []

        def dfs(name):
            if name in visited:
                return
            visited.add(name)
            task = name_to_task.get(name)
            if task:
                for dep in task.depends_on:
                    if dep in name_to_task:
                        dfs(dep)
                order.append(task)

        for t in tasks:
            dfs(t.name)
        return order

    def run(self, spec: str, workspace: str = '.') -> ProjectResult:
        """运行完整项目"""
        print(f'\n{"=" * 50}')
        print(f'  项目: {spec[:60]}')
        print(f'{"=" * 50}\n')

        # Step 1: 分解
        print('[1/4] 任务分解...')
        tasks = self._llm_decompose(spec)
        ordered = self._topological_order(tasks)
        print(f'      拆为 {len(ordered)} 个子任务\n')

        # Step 2: 执行
        print('[2/4] 执行任务...')
        failed_count = 0
        for task in ordered:
            ok = self._retry_loop(task)
            status = 'OK' if ok else 'FAIL'
            print(f'  {status} {task.name} ({task.status.value})')
            if not ok:
                failed_count += 1
                if failed_count >= 3:
                    print(f'\n  ⚠ 连续 {failed_count} 个任务失败，暂停')
                    break

        # Step 3: 验证
        print('\n[3/4] 验证...')
        all_pass = all(t.status == TaskStatus.DONE for t in tasks)
        skipped = [t for t in tasks if t.status in (TaskStatus.FAILED, TaskStatus.SKIPPED)]

        # Step 4: 报告
        print('[4/4] 生成报告...')
        summary_lines = [
            f'项目: {spec}',
            f'任务: {len(tasks)} 个 ({len([t for t in tasks if t.status == TaskStatus.DONE])} 完成, {len(skipped)} 跳过/失败)',
            f'重试: {sum(t.retries for t in tasks)} 次',
        ]
        if self.errors:
            summary_lines.append(f'错误: {len(self.errors)} 个')
            for e in self.errors[:3]:
                summary_lines.append(f'  - {e[:200]}')

        summary = '\n'.join(summary_lines)
        print(f'\n{summary}\n')

        return ProjectResult(success=all_pass, tasks=tasks, summary=summary)


# ═══════════════════════════════════════════════
# 便捷入口
# ═══════════════════════════════════════════════


def run_project(spec: str) -> ProjectResult:
    """一行命令运行项目"""
    orch = ProjectOrchestrator(
        tools={
            'run_test': lambda _: subprocess.run(
                ['python', '-X', 'utf8', '-m', 'pytest', 'tests/', '-q'],
                capture_output=True,
                text=True,
                timeout=60,
            ).stdout[:500],
            'write_file': lambda desc: f'任务描述: {desc} (需 LLM 生成代码)',
            'read_file': lambda path: open(path).read()[:2000] if os.path.exists(path) else '',
        }
    )
    return orch.run(spec)
