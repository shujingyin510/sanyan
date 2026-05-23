"""类型判断、时间、等待操作"""

import time
from ternary_core import TritValue
from values import SanyanSyntaxError, SanyanRuntimeError
from ops.registry import register


class TypeOps:
    @staticmethod
    def time_now(evaluator, args):
        return TritValue(int(time.time()))

    @staticmethod
    def sleep_op(evaluator, args):
        if len(args) != 1:
            raise SanyanSyntaxError('等待 需要一个参数（秒数）')
        sec = evaluator.eval(args[0]).to_int()
        try:
            time.sleep(sec)
        except KeyboardInterrupt:
            raise SanyanRuntimeError('等待被用户中断（Ctrl+C）')
        return TritValue(0)

    @staticmethod
    def is_number(evaluator, args):
        if len(args) != 1:
            raise SanyanSyntaxError('是数字 需要一个参数')
        val = evaluator.eval(args[0])
        if isinstance(val, TritValue):
            return TritValue(1)
        return TritValue(-1)

    @staticmethod
    def is_string(evaluator, args):
        if len(args) != 1:
            raise SanyanSyntaxError('是字符串 需要一个参数')
        val = evaluator.eval(args[0])
        if isinstance(val, str):
            return TritValue(1)
        return TritValue(-1)

    @staticmethod
    def is_list(evaluator, args):
        if len(args) != 1:
            raise SanyanSyntaxError('是列表 需要一个参数')
        val = evaluator.eval(args[0])
        if isinstance(val, list):
            return TritValue(1)
        return TritValue(-1)

    @staticmethod
    def is_dict(evaluator, args):
        if len(args) != 1:
            raise SanyanSyntaxError('是字典 需要一个参数')
        val = evaluator.eval(args[0])
        if isinstance(val, dict):
            return TritValue(1)
        return TritValue(-1)

    @staticmethod
    def str_equals(evaluator, args):
        if len(args) != 2:
            raise SanyanSyntaxError('字符串相等 需要两个参数')
        a = evaluator.eval(args[0])
        b = evaluator.eval(args[1])
        if isinstance(a, str) and isinstance(b, str):
            return TritValue(1 if a == b else -1)
        return TritValue(-1)

    @staticmethod
    def to_number(evaluator, args):
        if len(args) != 1:
            raise SanyanSyntaxError('to_number 需要一个参数')
        val = evaluator.eval(args[0])
        if isinstance(val, TritValue):
            return val
        if isinstance(val, (int, float)):
            return TritValue(val)
        if isinstance(val, str):
            try:
                return (
                    TritValue(int(val))
                    if val.isdigit() or (val.startswith('-') and val[1:].isdigit())
                    else TritValue(float(val))
                )
            except (ValueError, TypeError):
                raise SanyanTypeError(f"无法将 '{val}' 转换为数字")
        raise SanyanTypeError(f'无法将 {type(val).__name__} 转换为数字')

    @staticmethod
    def to_string(evaluator, args):
        if len(args) != 1:
            raise SanyanSyntaxError('字符串 需要一个参数')
        val = evaluator.eval(args[0])
        if isinstance(val, str):
            return val
        if isinstance(val, TritValue):
            return str(val.to_int())
        if isinstance(val, list):
            return '[' + ', '.join(str(v) for v in val) + ']'
        if isinstance(val, dict):
            return '{' + ', '.join(f'{k}: {v}' for k, v in val.items()) + '}'
        return str(val)


# 注册类型操作
register('time', TypeOps.time_now)
register('sleep', TypeOps.sleep_op)
register('is_number', TypeOps.is_number)
register('is_string', TypeOps.is_string)
register('is_list', TypeOps.is_list)
register('is_dict', TypeOps.is_dict)
register('str_equals', TypeOps.str_equals)
register('to_string', TypeOps.to_string)
register('to_number', TypeOps.to_number)
