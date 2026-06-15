"""任务分解引擎 + 有界上下文
Phase 0 核心：大任务自动递归分解，每层只携带摘要
"""

import time
import re
from typing import Any, Callable, List, Optional, Optional


class ComplexityClassifier:
    """任务复杂度分类器"""

    SIMPLE_PATTERNS = ['读取', '告诉我', '列出来', '查看', '是什么', '读', '列出']
    COMPLEX_PATTERNS = ['重构', '多个文件', '全部替换', '生成测试', '新建模块', '批量', '全局']
    MEDIUM_PATTERNS = ['修改', '替换', '修复', '增加', '删除', '改', '更新']

    def classify(self, task: str) -> str:
        if any(p in task for p in self.COMPLEX_PATTERNS):
            return 'complex'
        if any(p in task for p in self.SIMPLE_PATTERNS):
            return 'simple'
        if any(p in task for p in self.MEDIUM_PATTERNS):
            return 'medium'
        return 'medium'

    def should_decompose(self, task: str) -> bool:
        return self.classify(task) in ('medium', 'complex')


class TaskNode:
    """任务树节点"""

    def __init__(
        self,
        task_id: str,
        description: str,
        parent: Optional['TaskNode'] = None,
        context_budget: int = 2000,
    ):
        self.task_id = task_id
        self.description = description
        self.parent = parent
        self.children: List['TaskNode'] = []
        self.result_summary: str = ''
        self.context_budget = context_budget
        self.status: str = 'pending'
        self.created_at = time.time()

    def add_child(self, child: 'TaskNode'):
        child.parent = self
        self.children.append(child)

    def is_leaf(self) -> bool:
        return len(self.children) == 0

    def to_dict(self) -> dict:
        return {
            'id': self.task_id,
            'description': self.description,
            'status': self.status,
            'result': self.result_summary[:200],
            'children': [c.to_dict() for c in self.children],
        }


class BoundedContext:
    """有界上下文：硬限制 token 消耗"""

    def __init__(self, budget: int = 4000):
        self.budget = budget
        self.task: str = ''
        self.tool_results: List[str] = []
        self.extras: List[str] = []

    def set_task(self, task: str):
        self.task = task

    def add_tool_result(self, result: str):
        self.tool_results.append(str(result)[:500])

    def add_extra(self, text: str):
        self.extras.append(text)

    def build(self) -> str:
        """构建上下文，硬限制 token 数"""
        parts = [f'任务: {self.task}']
        if self.extras:
            parts.extend(self.extras)
        if self.tool_results:
            # 保留最近的结果
            recent = self.tool_results[-5:]
            parts.append('工具结果:')
            parts.extend(recent)
        full = '\n'.join(parts)
        # 硬限制：按字符截断（粗略估算 1 token ≈ 2 字符）
        max_chars = self.budget * 2
        if len(full) > max_chars:
            full = full[:max_chars] + f'\n...(截断，共{len(full)}字符)'
        return full

    def token_count(self) -> int:
        """估算当前 token 数"""
        full = self.build()
        return len(full) // 2


class DecompositionEngine:
    """任务分解引擎：递归分解 + 执行 + 合并"""

    MAX_DEPTH = 3
    LEAF_THRESHOLD = 200  # 小于200字符的任务不分

    def __init__(self, llm_fn: Callable, agent: Any):
        self.llm = llm_fn
        self.agent = agent
        self.classifier = ComplexityClassifier()

    def run(self, task: str) -> str:
        """主入口：分解任务并执行"""
        root = TaskNode(task_id='root', description=task)
        self._process(root, depth=0)
        return root.result_summary

    def _process(self, node: TaskNode, depth: int):
        """递归处理任务节点"""
        # 终止条件：达到最大深度 / 任务足够小 / 不需要分解
        if depth >= self.MAX_DEPTH:
            self._execute_leaf(node)
            return
        if len(node.description) < self.LEAF_THRESHOLD:
            self._execute_leaf(node)
            return
        if not self.classifier.should_decompose(node.description):
            self._execute_leaf(node)
            return

        # 分解
        subtasks = self._decompose(node)
        if not subtasks:
            self._execute_leaf(node)
            return

        for i, subtask in enumerate(subtasks):
            child = TaskNode(
                task_id=f'{node.task_id}.{i}',
                description=subtask,
                context_budget=node.context_budget // len(subtasks),
            )
            node.add_child(child)
            self._process(child, depth + 1)

        # 合并子节点结果
        self._merge_children(node)

    def _decompose(self, node: TaskNode) -> List[str]:
        """用 LLM 分解任务为子任务"""
        prompt = f'将以下任务分解为2-4个子任务，每个子任务一行，不要编号：\n任务: {node.description}\n子任务:'
        try:
            raw = self.llm(prompt)
            lines = [line.strip() for line in raw.strip().split('\n') if line.strip()]
            # 清理编号
            cleaned = []
            for line in lines:
                line = re.sub(r'^[\d]+[\.\)、]\s*', '', line)
                if line and len(line) > 3:
                    cleaned.append(line)
            return cleaned[:4]
        except Exception:
            return []

    def _execute_leaf(self, node: TaskNode):
        """执行叶节点任务"""
        node.status = 'executing'
        ctx = BoundedContext(budget=node.context_budget)
        ctx.set_task(node.description)
        try:
            result = self.agent._run_single_task(node.description, ctx)
            node.result_summary = str(result)[:500]
            node.status = 'done'
        except Exception as e:
            node.result_summary = f'执行失败: {e}'
            node.status = 'failed'

    def _merge_children(self, node: TaskNode):
        """合并子节点结果摘要"""
        if not node.children:
            return
        summaries = []
        for c in node.children:
            if c.result_summary:
                summaries.append(f'[{c.task_id}] {c.result_summary[:200]}')
        node.result_summary = '\n'.join(summaries)
        node.status = 'done'
