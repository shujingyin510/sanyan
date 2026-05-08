"""字符串相关操作"""
from ternary_core import TritValue

class StringOps:
    @staticmethod
    def string_concat(evaluator, args):
        if len(args) < 2:
            raise SyntaxError("连接 需要至少两个参数")
        parts = []
        for a in args:
            val = evaluator.eval(a)
            if isinstance(val, str):
                parts.append(val)
            elif isinstance(val, TritValue):
                parts.append(str(val.to_int()))
            else:
                parts.append(str(val))
        return ''.join(parts)

    @staticmethod
    def string_length(evaluator, args):
        if len(args) != 1:
            raise SyntaxError("取长 需要一个参数")
        val = evaluator.eval(args[0])
        if isinstance(val, str):
            return TritValue(len(val))
        if isinstance(val, TritValue):
            return TritValue(len(str(val.to_int())))
        return TritValue(len(str(val)))

    @staticmethod
    def str_to_list(evaluator, args):
        if len(args) != 1:
            raise SyntaxError("字列 需要一个字符串参数")
        val = evaluator.eval(args[0])
        if isinstance(val, str):
            return list(val)
        raise TypeError("字列 需要字符串")