"""沙箱操作：沙箱、沙箱开"""

from ops.registry import register, register_alias, entry_names
from core.sandbox import restrict, unblock
from core.values import SanyanSyntaxError, TritValue


def _dequote(s: str) -> str:
    """去 sugar 字面量引号：['沙箱','"http读"'] 的参数带引号。不去则解析出的名字
    （'"http读"'）永远匹配不上实际算子名（'http读'），沙箱形同虚设——与当年密钥
    读取带引号 bug（system_ops._arg_str）同族。"""
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        return s[1:-1]
    return s


def _sandbox_restrict(evaluator, args):
    if not args:
        raise SanyanSyntaxError('沙箱需要至少一个参数')
    names = []
    for a in args:
        if isinstance(a, str):
            names.append(_dequote(a))
        elif isinstance(a, TritValue):
            names.append(str(a))
    from ops.dispatcher import resolve_op_name

    # 连坐所有别名：只封 http读 拦不住 http_get（同一实现，别名逃逸）。
    blocked: set[str] = set()
    for op in names:
        blocked.update(entry_names(resolve_op_name(evaluator, op)))
    restrict(ops=list(blocked))
    return TritValue(0)


def _sandbox_unblock(evaluator, args):
    unblock()
    return TritValue(0)


register('沙箱', _sandbox_restrict)
register('沙箱开', _sandbox_unblock)

register_alias('sandbox', '沙箱')
register_alias('sandbox_unblock', '沙箱开')
