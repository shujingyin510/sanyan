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


def entry_names(name: str) -> list[str]:
    """返回与 name 共享同一分派实现的所有注册名（含自身）。

    沙箱按能力连坐封锁用：只封 'http读' 拦不住别名 'http_get'（同一实现，
    不同名字）——按 (func, extra) 值相等聚合，同时覆盖 register_alias（共享
    tuple）与重复 register（如 匹配3/ternary_match 各自 register 到同一函数、
    tuple 内容相等但非同一对象）两种同族逃逸。extra 参与比较，故 eq/gt
    （共享 _compare 但 extra 不同）不会被误并。"""
    entry = _OP_DISPATCH.get(name)
    if entry is None:
        return [name]
    return [k for k, v in _OP_DISPATCH.items() if v == entry]


def clear() -> None:
    """清空注册表，主要用于测试隔离。"""
    _OP_DISPATCH.clear()
