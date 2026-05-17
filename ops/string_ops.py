"""字符串相关操作"""

from ternary_core import TritValue
from values import SanyanSyntaxError, SanyanTypeError
from ops.registry import register


class StringOps:
    """字符串操作：查找、截取、拼接、替换等"""

    @staticmethod
    def string_concat(evaluator, args):
        if len(args) < 2:
            raise SanyanSyntaxError('连接 需要至少两个参数')
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
            raise SanyanSyntaxError('取长 需要一个参数')
        val = evaluator.eval(args[0])
        if isinstance(val, str):
            return TritValue(len(val))
        if isinstance(val, TritValue):
            return TritValue(len(str(val.to_int())))
        return TritValue(len(str(val)))

    @staticmethod
    def str_to_list(evaluator, args):
        if len(args) != 1:
            raise SanyanSyntaxError('字列 需要一个字符串参数')
        val = evaluator.eval(args[0])
        if isinstance(val, str):
            return list(val)
        raise SanyanTypeError('字列 需要字符串')

    @staticmethod
    def string_substring(evaluator, args):
        """子串(str, start, length) - 提取子字符串"""
        if len(args) < 2 or len(args) > 3:
            raise SanyanSyntaxError('子串 需要 2-3 个参数: (子串 字符串 起始 [长度])')
        val = evaluator.eval(args[0])
        if not isinstance(val, str):
            raise SanyanTypeError('子串 的第一个参数必须是字符串')
        start = evaluator.eval(args[1]).to_int()
        if len(args) == 3:
            length = evaluator.eval(args[2]).to_int()
            return val[start : start + length]
        return val[start:]

    @staticmethod
    def string_replace(evaluator, args):
        """替换(str, old, new) - 替换子字符串"""
        if len(args) != 3:
            raise SanyanSyntaxError('替换 需要 3 个参数: (替换 字符串 旧串 新串)')
        val = evaluator.eval(args[0])
        if not isinstance(val, str):
            raise SanyanTypeError('替换 的第一个参数必须是字符串')
        old = evaluator.eval(args[1])
        new = evaluator.eval(args[2])
        if not isinstance(old, str):
            old = str(old)
        if not isinstance(new, str):
            new = str(new)
        return val.replace(old, new)

    @staticmethod
    def string_split(evaluator, args):
        """分割(str, delimiter) - 按分隔符分割字符串"""
        if len(args) != 2:
            raise SanyanSyntaxError('分割 需要 2 个参数: (分割 字符串 分隔符)')
        val = evaluator.eval(args[0])
        if not isinstance(val, str):
            raise SanyanTypeError('分割 的第一个参数必须是字符串')
        delim = evaluator.eval(args[1])
        if not isinstance(delim, str):
            delim = str(delim)
        return val.split(delim)

    @staticmethod
    def string_find(evaluator, args):
        """查找(str, sub) - 查找子字符串位置，未找到返回 -1"""
        if len(args) != 2:
            raise SanyanSyntaxError('查找 需要 2 个参数: (查找 字符串 子串)')
        val = evaluator.eval(args[0])
        if not isinstance(val, str):
            raise SanyanTypeError('查找 的第一个参数必须是字符串')
        sub = evaluator.eval(args[1])
        if not isinstance(sub, str):
            sub = str(sub)
        return TritValue(val.find(sub))

    @staticmethod
    def string_trim(evaluator, args):
        """去空白(str) - 去除首尾空白"""
        if len(args) != 1:
            raise SanyanSyntaxError('去空白 需要 1 个参数')
        val = evaluator.eval(args[0])
        if isinstance(val, str):
            return val.strip()
        raise SanyanTypeError('去空白 需要字符串')

    @staticmethod
    def string_upper(evaluator, args):
        """大写(str) - 转换为大写"""
        if len(args) != 1:
            raise SanyanSyntaxError('大写 需要 1 个参数')
        val = evaluator.eval(args[0])
        if isinstance(val, str):
            return val.upper()
        raise SanyanTypeError('大写 需要字符串')

    @staticmethod
    def string_lower(evaluator, args):
        """小写(str) - 转换为小写"""
        if len(args) != 1:
            raise SanyanSyntaxError('小写 需要 1 个参数')
        val = evaluator.eval(args[0])
        if isinstance(val, str):
            return val.lower()
        raise SanyanTypeError('小写 需要字符串')

    @staticmethod
    def string_startswith(evaluator, args):
        """前缀(str, prefix) - 检查是否以指定前缀开头"""
        if len(args) != 2:
            raise SanyanSyntaxError('前缀 需要 2 个参数')
        val = evaluator.eval(args[0])
        if not isinstance(val, str):
            raise SanyanTypeError('前缀 的第一个参数必须是字符串')
        prefix = evaluator.eval(args[1])
        if not isinstance(prefix, str):
            prefix = str(prefix)
        return TritValue(1 if val.startswith(prefix) else -1)

    @staticmethod
    def string_endswith(evaluator, args):
        """后缀(str, suffix) - 检查是否以指定后缀结尾"""
        if len(args) != 2:
            raise SanyanSyntaxError('后缀 需要 2 个参数')
        val = evaluator.eval(args[0])
        if not isinstance(val, str):
            raise SanyanTypeError('后缀 的第一个参数必须是字符串')
        suffix = evaluator.eval(args[1])
        if not isinstance(suffix, str):
            suffix = str(suffix)
        return TritValue(1 if val.endswith(suffix) else -1)


# 注册字符串操作
register('concat', StringOps.string_concat)
register('length', StringOps.string_length)
register('str_to_list', StringOps.str_to_list)
register('substring', StringOps.string_substring)
register('replace', StringOps.string_replace)
register('split', StringOps.string_split)
register('find', StringOps.string_find)
register('trim', StringOps.string_trim)
register('upper', StringOps.string_upper)
register('lower', StringOps.string_lower)
register('startswith', StringOps.string_startswith)
register('endswith', StringOps.string_endswith)
