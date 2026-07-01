"""操作注册表：统一的内置命令分派系统
所有 ops/*.py 模块在加载时向此表注册各自的操作。
evaluator.py 通过 get_op() 查询此表，不再维护自有的 _OP_DISPATCH。
"""

from __future__ import annotations
from typing import Callable, Any
from core.values import SanyanKeyError

_OP_DISPATCH: dict[str, tuple[Callable, Any]] = {}


def register(name: str, func: Callable, extra: Any = False) -> None:
    """注册一个操作名到其实现函数。

    Args:
        name: 操作名（内部标识，如 'if', 'add'）
        func: 实现函数 (evaluator, args) -> result
        extra: 额外参数，如算术操作的类型标识。若为 truthy，
               调用时传 func(evaluator, extra, args)
    """
    _OP_DISPATCH[name] = (func, extra)


def register_alias(alias: str, target: str) -> None:
    """为已注册的操作创建一个别名。"""
    if target not in _OP_DISPATCH:
        raise SanyanKeyError(f"别名目标 '{target}' 尚未注册")
    _OP_DISPATCH[alias] = _OP_DISPATCH[target]


def get_op(name: str) -> tuple[Callable, Any] | None:
    return _OP_DISPATCH.get(name)


def has_op(name: str) -> bool:
    return name in _OP_DISPATCH


def all_ops() -> list[str]:
    return list(_OP_DISPATCH.keys())


def clear() -> None:
    """清空注册表，主要用于测试隔离。"""
    _OP_DISPATCH.clear()
