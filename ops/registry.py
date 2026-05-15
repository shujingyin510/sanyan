"""操作注册表：装饰器驱动的内置命令分派系统"""
from __future__ import annotations

_OP_DISPATCH: dict[str, tuple] = {}
_op_cache: dict[str, tuple] = {}


def register_op(name: str, extra=None):
    """装饰器：将方法注册为三言内置操作。"""
    def decorator(func):
        _OP_DISPATCH[name] = (func, extra)
        return func
    return decorator


def register(name: str, func, extra=None):
    """直接注册操作（非装饰器形式）。"""
    _OP_DISPATCH[name] = (func, extra)


def get_op(name: str):
    if name in _op_cache:
        return _op_cache[name]
    entry = _OP_DISPATCH.get(name)
    if entry is None:
        return None
    _op_cache[name] = entry
    return entry


def has_op(name: str) -> bool:
    return name in _OP_DISPATCH


def all_ops() -> list[str]:
    return list(_OP_DISPATCH.keys())
