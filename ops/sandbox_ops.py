"""沙箱操作：沙箱、沙箱开"""

from ops.registry import register
from sandbox import restrict, unblock
from values import SanyanSyntaxError, TritValue


def _sandbox_restrict(evaluator, args):
    if not args:
        raise SanyanSyntaxError('沙箱需要至少一个参数')
    blocked = []
    for a in args:
        if isinstance(a, str):
            blocked.append(a)
        elif isinstance(a, TritValue):
            blocked.append(str(a))
    restrict(ops=blocked)
    return TritValue(0)


def _sandbox_unblock(evaluator, args):
    unblock()
    return TritValue(0)


register('沙箱', _sandbox_restrict)
register('沙箱开', _sandbox_unblock)
