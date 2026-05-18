"""沙箱操作：沙箱、沙箱开"""

from ops.registry import register, register_alias
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
    from ops.dispatcher import resolve_op_name

    restrict(ops=[resolve_op_name(evaluator, op) for op in blocked])
    return TritValue(0)


def _sandbox_unblock(evaluator, args):
    unblock()
    return TritValue(0)


register('沙箱', _sandbox_restrict)
register('沙箱开', _sandbox_unblock)

register_alias('sandbox', '沙箱')
register_alias('sandbox_unblock', '沙箱开')
