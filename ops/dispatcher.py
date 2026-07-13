"""操作分派器：统一的操作名解析、注册表查询、点号/变量分派。

负责将用户操作名映射到内部实现，按优先级尝试内置操作、点号访问、变量调用。
所有函数接受 evaluator 实例作为第一个参数，操作注册表等共享状态。
"""

from typing import Any
from ops.registry import get_op
from core.values import (
    FunctionValue,
    ModuleValue,
    SanyanNameError,
    SanyanKeyError,
    SanyanSyntaxError,
    SanyanTypeError,
    SanyanAttributeError,
)
from core.ternary_core import TritValue, ArrayValue
from core.sandbox import check_op as _check_op, check_func as _check_func
from ops.capability import check_dispatch as _check_cap

# 哨兵：dispatch_op 用此值区分"未找到 op"和"op 返回了 None"
_DISPATCH_NOT_FOUND = object()


def resolve_op_name(evaluator: Any, op: str) -> str:
    """解析操作名为内部标识符（皮肤映射 + 缓存）。"""
    cached = evaluator._name_cache.get(op)
    if isinstance(cached, str):
        return cached
    internal = op
    skin = evaluator.skin_manager
    if skin:
        kw = skin.get_internal_keyword(op) or skin.get_internal_op(op)
        if kw:
            internal = kw
    if len(evaluator._name_cache) >= evaluator._name_cache_max:
        evaluator._name_cache.pop(next(iter(evaluator._name_cache)))
    evaluator._name_cache[op] = internal
    return internal


def dispatch_op(evaluator: Any, internal: str, args: list) -> Any:
    """从注册表查询并执行内置操作。

    支持缓存加速，未找到时返回 _DISPATCH_NOT_FOUND 哨兵。
    """
    _check_op(internal)
    _check_cap(evaluator, internal)  # 能力约束层（块内默认拒绝；块外零成本早退）
    if internal in evaluator._op_cache:
        method, extra = evaluator._op_cache[internal]
    else:
        entry = get_op(internal)
        if entry is not None:
            method, extra = entry
            evaluator._op_cache[internal] = entry
        else:
            return _DISPATCH_NOT_FOUND
    if extra:
        return method(evaluator, extra, args)
    return method(evaluator, args)


def handle_dot_access(evaluator: Any, op: str, args: list) -> Any:
    """处理点号访问: module.func, dict.key, list[idx]"""
    if not isinstance(op, str) or '.' not in op:
        return None
    module_name, func_name = op.split('.', 1)
    if not evaluator.has_var(module_name):
        return None
    module_val = evaluator.get_var(module_name)
    if isinstance(module_val, ModuleValue):
        if not module_val.is_exported(func_name):
            raise SanyanNameError(f"模块 '{module_name}' 未导出 '{func_name}'")
        evaluated_args = [evaluator.eval(a) for a in args]
        return module_val.call(evaluator, [func_name] + evaluated_args)
    if isinstance(module_val, dict):
        if args:
            raise SanyanTypeError(f"字典 '{module_name}' 不支持方法调用")
        if func_name in module_val:
            return module_val[func_name]
        raise SanyanKeyError(f"字典 '{module_name}' 中没有键 '{func_name}'")
    if isinstance(module_val, (list, ArrayValue)):
        if func_name in ('length', '长度'):
            return TritValue(len(module_val) if isinstance(module_val, list) else module_val.length)
        try:
            return module_val[int(func_name)]
        except (ValueError, IndexError):
            raise SanyanAttributeError(f"列表 '{module_name}' 没有属性 '{func_name}'")
    return None


def handle_variable_call(evaluator: Any, op: str, args: list) -> Any:
    """处理变量调用：自定义函数、模块调用、容器索引、变量值。

    根据变量类型分派不同调用方式。
    """
    if not evaluator.has_var(op):
        return None
    val = evaluator.get_var(op)
    if isinstance(val, FunctionValue):
        _check_func(op)
        evaluated_args = [evaluator.eval(a) for a in args]
        return val.call(evaluator, evaluated_args)
    if isinstance(val, ModuleValue):
        evaluated_args = [evaluator.eval(a) for a in args]
        return val.call(evaluator, evaluated_args)
    if isinstance(val, (list, ArrayValue, dict)):
        if len(args) != 1:
            raise SanyanSyntaxError(f'容器索引需要一个参数，但提供了 {len(args)} 个')
        idx = evaluator.eval(args[0])
        if isinstance(val, dict):
            key = idx.to_int() if isinstance(idx, TritValue) else idx
            return val[key]
        index_int = idx.to_int() if isinstance(idx, TritValue) else idx
        return val[index_int]
    if len(args) == 0:
        return val
    raise SanyanTypeError(f"变量 '{op}' 的值不可调用或索引")


def apply(evaluator: Any, op: str, args: list) -> Any:
    """主分派入口：依次尝试注册表 → 点号访问 → 变量调用 → 自定义命令。

    按优先级查找并执行操作，返回执行结果。
    dispatch_op 返回 _DISPATCH_NOT_FOUND 时才回退后续路径，
    避免操作体返回 None 时误判为分派失败。
    """
    from core.commands import Commands

    internal = resolve_op_name(evaluator, op)

    result = dispatch_op(evaluator, internal, args)
    if result is not _DISPATCH_NOT_FOUND:
        return result

    result = handle_dot_access(evaluator, op, args)
    if result is not None:
        return result

    result = handle_variable_call(evaluator, op, args)
    if result is not None:
        return result

    _check_func(op)
    return Commands.call(evaluator, op, args)
