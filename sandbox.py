"""沙箱机制：限制运行时可用的操作

注意：沙箱状态是模块级全局变量，所有 evaluator 实例共享。
在多实例场景（LSP/DAP）中，一个实例调用 restrict() 会影响其他实例。
如需实例级隔离，需重构为实例化 Sandbox 类。"""

from typing import FrozenSet
from values import SanyanRuntimeError


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
