"""扩展数学操作：统计"""
from ternary_core import TritValue, ArrayValue
from values import SanyanSyntaxError
from ops.registry import register, register_alias


def _to_float_list(val):
    """将 TritValue / ArrayValue / list 转为 float 列表"""
    if isinstance(val, ArrayValue):
        return [float(v) if isinstance(v, TritValue) else float(v) for v in val.data]
    if isinstance(val, list):
        return [float(v.to_int()) if isinstance(v, TritValue) else float(v) for v in val]
    if isinstance(val, TritValue):
        return [float(val.to_int())]
    return [float(val)]


def math_mean(evaluator, args):
    """均值(列表) — 计算算术平均数"""
    if not args:
        raise SanyanSyntaxError('均值 需要一个列表参数')
    data = _to_float_list(evaluator.eval(args[0]))
    if not data:
        return TritValue(0)
    return TritValue(sum(data) / len(data))


def math_median(evaluator, args):
    """中位数(列表) — 计算中位数"""
    if not args:
        raise SanyanSyntaxError('中位数 需要一个列表参数')
    data = sorted(_to_float_list(evaluator.eval(args[0])))
    if not data:
        return TritValue(0)
    n = len(data)
    if n % 2 == 1:
        return TritValue(data[n // 2])
    return TritValue((data[n // 2 - 1] + data[n // 2]) / 2)


def math_variance(evaluator, args):
    """方差(列表) — 计算总体方差"""
    if not args:
        raise SanyanSyntaxError('方差 需要一个列表参数')
    data = _to_float_list(evaluator.eval(args[0]))
    if not data:
        return TritValue(0)
    mean = sum(data) / len(data)
    return TritValue(sum((x - mean) ** 2 for x in data) / len(data))


def math_stdev(evaluator, args):
    """标准差(列表) — 计算总体标准差"""
    if not args:
        raise SanyanSyntaxError('标准差 需要一个列表参数')
    data = _to_float_list(evaluator.eval(args[0]))
    if not data:
        return TritValue(0)
    mean = sum(data) / len(data)
    var = sum((x - mean) ** 2 for x in data) / len(data)
    from math import sqrt
    return TritValue(sqrt(var))


register('均值', math_mean)
register('中位数', math_median)
register('方差', math_variance)
register('标准差', math_stdev)

register_alias('mean', '均值')
register_alias('median', '中位数')
register_alias('variance', '方差')
register_alias('stdev', '标准差')
