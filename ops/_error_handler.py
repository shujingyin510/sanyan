"""统一错误处理装饰器：为 ops 模块提供标准化的错误处理"""

from functools import wraps
from typing import Callable, Any
from values import (
    SanyanError,
    SanyanTypeError,
    SanyanSyntaxError,
    SanyanValueError,
    SanyanRuntimeError,
)


def check_args_count(args: list, expected: int, op_name: str) -> None:
    """检查参数数量"""
    if len(args) != expected:
        raise SanyanSyntaxError(f"'{op_name}' 需要 {expected} 个参数，但提供了 {len(args)} 个")


def check_args_range(args: list, min_count: int, max_count: int, op_name: str) -> None:
    """检查参数数量范围"""
    if len(args) < min_count or len(args) > max_count:
        raise SanyanSyntaxError(
            f"'{op_name}' 需要 {min_count}-{max_count} 个参数，但提供了 {len(args)} 个"
        )


def check_min_args(args: list, min_count: int, op_name: str) -> None:
    """检查最小参数数量"""
    if len(args) < min_count:
        raise SanyanSyntaxError(
            f"'{op_name}' 至少需要 {min_count} 个参数，但提供了 {len(args)} 个"
        )


def type_check(value: Any, expected_type: type, param_name: str, op_name: str) -> None:
    """类型检查辅助函数"""
    if not isinstance(value, expected_type):
        actual_type = type(value).__name__
        raise SanyanTypeError(f"'{op_name}' 的参数 '{param_name}' 期望 {expected_type.__name__}，但得到 {actual_type}")


def handle_op_errors(op_name: str) -> Callable:
    """操作错误处理装饰器

    用法:
        @handle_op_errors('加')
        def add(evaluator, args):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(evaluator, args: list) -> Any:
            try:
                return func(evaluator, args)
            except SanyanError:
                raise
            except Exception as e:
                raise SanyanRuntimeError(f"'{op_name}' 执行错误: {e}") from e
        return wrapper
    return decorator


def validate_numeric(value: Any, param_name: str, op_name: str) -> None:
    """验证值是否为数值类型"""
    from ternary_core import TritValue
    if not isinstance(value, (int, float, TritValue)):
        raise SanyanTypeError(f"'{op_name}' 的参数 '{param_name}' 期望数值类型，但得到 {type(value).__name__}")


def validate_string(value: Any, param_name: str, op_name: str) -> None:
    """验证值是否为字符串类型"""
    if not isinstance(value, str):
        raise SanyanTypeError(f"'{op_name}' 的参数 '{param_name}' 期望字符串类型，但得到 {type(value).__name__}")


def validate_list(value: Any, param_name: str, op_name: str) -> None:
    """验证值是否为列表类型"""
    if not isinstance(value, list):
        raise SanyanTypeError(f"'{op_name}' 的参数 '{param_name}' 期望列表类型，但得到 {type(value).__name__}")


def validate_dict(value: Any, param_name: str, op_name: str) -> None:
    """验证值是否为字典类型"""
    if not isinstance(value, dict):
        raise SanyanTypeError(f"'{op_name}' 的参数 '{param_name}' 期望字典类型，但得到 {type(value).__name__}")
