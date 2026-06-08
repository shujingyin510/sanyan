"""三态容器操作: 列表、字典，每个元素带独立置信度"""

from ternary_core import TritValue
from values import SanyanSyntaxError, SanyanTypeError, SanyanValueError
from ops.registry import register


def _trit_list(evaluator, args):
    """三态列(a, b, c) — 创建三态列表。每个元素自动包装为 TritValue。"""
    vals = [evaluator.eval(a) for a in args]
    result = []
    for v in vals:
        if isinstance(v, TritValue):
            result.append(v)
        elif isinstance(v, (int, float)):
            result.append(TritValue(v))
        elif isinstance(v, str):
            result.append(TritValue(v))
        else:
            result.append(v)
    return result  # Python list of TritValues


def _trit_get(evaluator, args):
    """三态取(lst, idx) — 取列表元素，保持其置信度。"""
    if len(args) != 2:
        raise SanyanSyntaxError('三态取 需要列表和索引')
    lst = evaluator.eval(args[0])
    idx = evaluator.eval(args[1])
    if isinstance(idx, TritValue):
        idx = idx.to_int()
    if not isinstance(lst, list):
        raise SanyanTypeError('三态取 的第一个参数必须是列表')
    if idx < 0 or idx >= len(lst):
        raise SanyanTypeError(f'三态取 索引越界: {idx}')
    return lst[idx]


def _trit_set(evaluator, args):
    """三态置(lst, idx, val) — 设置列表元素，保持其置信度。"""
    if len(args) != 3:
        raise SanyanSyntaxError('三态置 需要列表、索引和值')
    lst = evaluator.eval(args[0])
    idx = evaluator.eval(args[1])
    val = evaluator.eval(args[2])
    if isinstance(idx, TritValue):
        idx = idx.to_int()
    if not isinstance(lst, list):
        raise SanyanTypeError('三态置 的第一个参数必须是列表')
    if idx < 0 or idx >= len(lst):
        raise SanyanValueError(f'三态置 索引 {idx} 越界（列表长度 {len(lst)}）')
    lst[idx] = val if isinstance(val, TritValue) else TritValue(val)
    return TritValue(0)


def _trit_list_len(evaluator, args):
    """三态列长(lst) — 列表长度"""
    if len(args) != 1:
        raise SanyanSyntaxError('三态列长 需要一个参数')
    lst = evaluator.eval(args[0])
    if not isinstance(lst, list):
        raise SanyanTypeError('三态列长 的参数必须是列表')
    return TritValue(len(lst))


def _trit_list_map(evaluator, args):
    """三态映射(lst, fn) — 对列表每个元素应用函数，保持独立信度。"""
    if len(args) != 2:
        raise SanyanSyntaxError('三态映射 需要列表和函数名')
    lst = evaluator.eval(args[0])
    fn_name = args[1]
    if isinstance(fn_name, list):
        fn_name = fn_name[0] if fn_name else ''
    if not isinstance(lst, list):
        raise SanyanTypeError('三态映射 的第一个参数必须是列表')
    result = []
    for item in lst:
        r = evaluator.eval([fn_name, item])
        result.append(r)
    return result


def _trit_dict(evaluator, args):
    """三态字典(k1=v1, k2=v2) — 创建三态字典，值保留信度。"""
    if len(args) % 2 != 0:
        raise SanyanSyntaxError('三态字典 需要成对的键和值')
    result = {}
    for i in range(0, len(args), 2):
        key = evaluator.eval(args[i])
        val = evaluator.eval(args[i + 1])
        if isinstance(key, TritValue) and key.is_string():
            key = key.to_payload()
        if isinstance(key, TritValue):
            key = str(key.to_int())
        val = val if isinstance(val, TritValue) else TritValue(val)
        result[key] = val
    return result


def _trit_key_get(evaluator, args):
    """三态键(d, key) — 取字典值，保持信度。"""
    if len(args) != 2:
        raise SanyanSyntaxError('三态键 需要字典和键名')
    d = evaluator.eval(args[0])
    key = evaluator.eval(args[1])
    if isinstance(key, TritValue) and key.is_string():
        key = key.to_payload()
    if isinstance(key, TritValue):
        key = str(key.to_int())
    if not isinstance(d, dict):
        raise SanyanTypeError('三态键 的第一个参数必须是字典')
    if key not in d:
        return TritValue(0)  # 不存在→可能
    return d[key]


def _trit_key_set(evaluator, args):
    """三态置键(d, key, val) — 设置字典值，保持信度。"""
    if len(args) != 3:
        raise SanyanSyntaxError('三态置键 需要字典、键名和值')
    d = evaluator.eval(args[0])
    key = evaluator.eval(args[1])
    val = evaluator.eval(args[2])
    if isinstance(key, TritValue) and key.is_string():
        key = key.to_payload()
    if isinstance(key, TritValue):
        key = str(key.to_int())
    d[key] = val if isinstance(val, TritValue) else TritValue(val)
    return TritValue(0)


register('trit_list', _trit_list)
register('trit_get', _trit_get)
register('trit_set', _trit_set)
register('trit_list_len', _trit_list_len)
register('trit_list_map', _trit_list_map)
register('trit_dict', _trit_dict)
register('trit_key_get', _trit_key_get)
register('trit_key_set', _trit_key_set)
