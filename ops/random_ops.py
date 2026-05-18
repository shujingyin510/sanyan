"""随机操作"""

import random as _random
from ternary_core import TritValue, ArrayValue
from values import SanyanSyntaxError
from ops.registry import register, register_alias


def op_random(evaluator, args):
    """随机() — 返回 0~1 之间的随机浮点数"""
    return TritValue(_random.random())


def op_randint(evaluator, args):
    """随机整数(最小值, 最大值) — 返回闭区间内的随机整数"""
    if len(args) < 2:
        raise SanyanSyntaxError('随机整数 需要 最小值 和 最大值')
    a = evaluator.eval(args[0]).to_int()
    b = evaluator.eval(args[1]).to_int()
    return TritValue(_random.randint(a, b))


def op_choice(evaluator, args):
    """选取(列表) — 从列表中随机选一个元素"""
    if not args:
        raise SanyanSyntaxError('选取 需要一个列表参数')
    lst = evaluator.eval(args[0])
    if isinstance(lst, ArrayValue):
        lst = lst.data
    if not isinstance(lst, list) or not lst:
        raise SanyanSyntaxError('选取 的参数必须是非空列表')
    return _random.choice(lst)


def op_shuffle(evaluator, args):
    """乱序(列表) — 返回随机打乱后的新列表"""
    if not args:
        raise SanyanSyntaxError('乱序 需要一个列表参数')
    lst = evaluator.eval(args[0])
    if isinstance(lst, ArrayValue):
        lst = list(lst.data)
    elif isinstance(lst, list):
        lst = list(lst)
    else:
        raise SanyanSyntaxError('乱序 的参数必须是列表')
    _random.shuffle(lst)
    return lst


def op_randbytes(evaluator, args):
    """随机字节(长度) — 返回指定长度的随机字节串"""
    if not args:
        return ''
    n = evaluator.eval(args[0]).to_int()
    return bytes(_random.randrange(256) for _ in range(n)).hex()


register('随机', op_random)
register('随机整数', op_randint)
register('选取', op_choice)
register('乱序', op_shuffle)
register('随机字节', op_randbytes)

register_alias('rnd', '随机')
register_alias('randint', '随机整数')
register_alias('choice', '选取')
register_alias('shuffle', '乱序')
register_alias('randbytes', '随机字节')
