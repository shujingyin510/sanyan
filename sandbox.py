"""沙箱机制：限制运行时可用的操作

⚠ 已知限制：沙箱状态是模块级全局变量（_BLOCKED_OPS / _FUNC_BLOCKED），
所有 SanyanEvaluator 实例共享同一个沙箱状态。
- LSP/DAP 服务器中一个会话的 restrict() 会影响其他会话
- 多线程/并发场景不安全
- 预期修复：将 _BLOCKED_OPS / _FUNC_BLOCKED 移到 SanyanEvaluator 实例属性"""

from typing import FrozenSet
from values import SanyanRuntimeError


# ⚠ 模块级全局变量（共享状态），多实例不安全
_BLOCKED_OPS: FrozenSet[str] = frozenset()
_FUNC_BLOCKED: FrozenSet[str] = frozenset()


def restrict(ops: list[str] | None = None, funcs: list[str] | None = None) -> None:
    """设置沙箱限制：禁止调用指定操作或函数。

    Args:
        ops: 禁止的内置操作名列表
        funcs: 禁止的自定义函数名列表
    """
    global _BLOCKED_OPS, _FUNC_BLOCKED
    _BLOCKED_OPS = frozenset(ops or [])
    _FUNC_BLOCKED = frozenset(funcs or [])


def unblock() -> None:
    """清除沙箱限制。"""
    global _BLOCKED_OPS, _FUNC_BLOCKED
    _BLOCKED_OPS = frozenset()
    _FUNC_BLOCKED = frozenset()


def check_op(name: str) -> None:
    """检查操作是否被沙箱禁止，禁止则抛异常。"""
    if name in _BLOCKED_OPS:
        raise SanyanRuntimeError(f'沙箱禁止操作: {name}')


def check_func(name: str) -> None:
    """检查自定义函数是否被沙箱禁止。"""
    if name in _FUNC_BLOCKED:
        raise SanyanRuntimeError(f'沙箱禁止函数: {name}')


def is_active() -> bool:
    return bool(_BLOCKED_OPS) or bool(_FUNC_BLOCKED)
