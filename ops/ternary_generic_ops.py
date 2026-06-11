"""三态泛型容器：三态集、三态图、三态队列、三态栈
本文件为向后兼容包装器，实际实现在以下模块：
- ternary_set_ops.py   — 三态集
- ternary_graph_ops.py — 三态图
- ternary_queue_ops.py — 三态队列 + 三态栈
"""

from ops.ternary_set_ops import TernarySet
from ops.ternary_graph_ops import TernaryGraph
from ops.ternary_queue_ops import TernaryQueue, TernaryStack

__all__ = ['TernarySet', 'TernaryGraph', 'TernaryQueue', 'TernaryStack']
