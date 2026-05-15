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
            raise SanyanSyntaxError("等待 需要一个参数（秒数）")
        sec = evaluator.eval(args[0]).to_int()
        try:
            time.sleep(sec)
        except KeyboardInterrupt:
            raise SanyanRuntimeError("等待被用户中断（Ctrl+C）")
        return TritValue(0)

    @staticmethod
    def is_number(evaluator, args):
        if len(args) != 1:
            raise SanyanSyntaxError("是数字 需要一个参数")
        val = evaluator.eval(args[0])
        if isinstance(val, TritValue):
            return TritValue(1)
        return TritValue(-1)

    @staticmethod
    def is_string(evaluator, args):
        if len(args) != 1:
            raise SanyanSyntaxError("是字符串 需要一个参数")
        val = evaluator.eval(args[0])
        if isinstance(val, str):
            return TritValue(1)
        return TritValue(-1)

    @staticmethod
    def str_equals(evaluator, args):
        if len(args) != 2:
            raise SanyanSyntaxError("字符串相等 需要两个参数")
        a = evaluator.eval(args[0])
        b = evaluator.eval(args[1])
        if isinstance(a, str) and isinstance(b, str):
            return TritValue(1 if a == b else -1)
        return TritValue(-1)

# 注册类型操作
register('time', TypeOps.time_now)
register('sleep', TypeOps.sleep_op)
register('is_number', TypeOps.is_number)
register('is_string', TypeOps.is_string)
register('str_equals', TypeOps.str_equals)
