"""字典操作：创建、查询、设置、删除、键列表。"""

from core.ternary_core import TritValue
from core.values import SanyanSyntaxError, SanyanTypeError, SanyanKeyError
from ops.registry import register


def _dict_new(evaluator, args):
    """创建字典：字典(键1, 值1, 键2, 值2, ...)"""
    if len(args) % 2 != 0:
        raise SanyanSyntaxError('字典 需要偶数个参数（键值对）')
    d = {}
    for i in range(0, len(args), 2):
        key = evaluator.eval(args[i])
        if isinstance(key, TritValue):
            key = key.to_int()
        value = evaluator.eval(args[i + 1])
        d[key] = value
    return d


def _dict_contains(evaluator, args):
    """字典键检查：含键(字典, 键) → T/F"""
    if len(args) != 2:
        raise SanyanSyntaxError('含键 需要字典和键')
    d = evaluator.eval(args[0])
    if not isinstance(d, dict):
        raise SanyanTypeError('第一个参数必须是字典')
    key = evaluator.eval(args[1])
    if isinstance(key, TritValue):
        key = key.to_int()
    try:
        return TritValue(1 if key in d else -1)
    except TypeError:
        return TritValue(-1)


def _dict_get(evaluator, args):
    """字典取值：取键(字典, 键) 或 取键(字典) → 所有键列表"""
    if len(args) == 1:
        d = evaluator.eval(args[0])
        if not isinstance(d, dict):
            raise SanyanTypeError('第一个参数必须是字典')
        return list(d.keys())
    if len(args) != 2:
        raise SanyanSyntaxError('取键 需要1个(取所有键)或2个(取指定键)参数')
    d = evaluator.eval(args[0])
    if not isinstance(d, dict):
        raise SanyanTypeError('第一个参数必须是字典')
    key = evaluator.eval(args[1])
    if isinstance(key, TritValue):
        key = key.to_int()
    if isinstance(key, list):
        key = tuple(key)
    try:
        return d[key]
    except KeyError:
        keys = list(d.keys())[:10]
        hint = f'（可用键: {keys}）' if keys else '（字典为空）'
        raise SanyanKeyError(f'键不存在: {key!r} {hint}')


def _dict_set(evaluator, args):
    """字典设值：置键(字典, 键, 新值)"""
    if len(args) != 3:
        raise SanyanSyntaxError('置键 需要字典、键和新值')
    d = evaluator.eval(args[0])
    key = evaluator.eval(args[1])
    if isinstance(key, TritValue):
        key = key.to_int()
    value = evaluator.eval(args[2])
    if isinstance(d, list):
        if len(d) > 0 and isinstance(d[-1], dict):
            d[-1][key] = value
            return d
        raise SanyanTypeError('字典栈顶不是字典')
    if not isinstance(d, dict):
        raise SanyanTypeError('第一个参数必须是字典')
    if isinstance(key, list):
        key = tuple(key)
    d[key] = value
    return d


def _dict_keys(evaluator, args):
    """返回字典的所有键列表。"""
    if len(args) != 1:
        raise SanyanSyntaxError('字典键列表 需要一个字典参数')
    d = evaluator.eval(args[0])
    if not isinstance(d, dict):
        raise SanyanTypeError('参数必须是字典')
    return list(d.keys())


def _dict_delete(evaluator, args):
    """删除字典中的指定键。"""
    if len(args) != 2:
        raise SanyanSyntaxError('删除键 需要字典和键')
    d = evaluator.eval(args[0])
    key = evaluator.eval(args[1])
    if not isinstance(d, dict):
        raise SanyanTypeError('第一个参数必须是字典')
    if isinstance(key, TritValue):
        key = key.to_int()
    if key in d:
        del d[key]
    return d


def _str_contains(evaluator, args):
    """检查字符串是否包含子串。"""
    if len(args) != 2:
        raise SanyanSyntaxError('字符串包含 需要两个字符串参数')
    s = evaluator.eval(args[0])
    sub = evaluator.eval(args[1])
    if not isinstance(s, str) or not isinstance(sub, str):
        raise SanyanTypeError('参数必须是字符串')
    return TritValue(1 if sub in s else -1)


# ── 注册 ──
register('dict', _dict_new)
register('dict_contains', _dict_contains)
register('get_key', _dict_get)
register('set_key', _dict_set)
register('dict_keys', _dict_keys)
register('delete_key', _dict_delete)
register('str_contains', _str_contains)
