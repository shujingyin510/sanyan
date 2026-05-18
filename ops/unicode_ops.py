"""Unicode / URL 编码操作"""

import urllib.parse
from ternary_core import TritValue
from ops.registry import register, register_alias


def _to_str(val):
    if isinstance(val, str):
        return val
    if isinstance(val, TritValue):
        return str(val)
    return str(val)


def op_url_encode(evaluator, args):
    """url编码(字符串) — URL 百分号编码"""
    if not args:
        return ''
    s = _to_str(evaluator.eval(args[0]) if not isinstance(args[0], str) else args[0])
    return urllib.parse.quote(s, safe='')


def op_url_decode(evaluator, args):
    """url解码(编码串) — URL 百分号解码"""
    if not args:
        return ''
    s = _to_str(evaluator.eval(args[0]) if not isinstance(args[0], str) else args[0])
    try:
        return urllib.parse.unquote(s)
    except Exception:
        return s


def op_unicode_escape(evaluator, args):
    """unicode编码(字符串) — 返回 \\uXXXX 转义形式"""
    if not args:
        return ''
    s = _to_str(evaluator.eval(args[0]) if not isinstance(args[0], str) else args[0])
    return s.encode('unicode_escape').decode('ascii')


def op_unicode_unescape(evaluator, args):
    """unicode解码(转义串) — 从 \\uXXXX 还原"""
    if not args:
        return ''
    s = _to_str(evaluator.eval(args[0]) if not isinstance(args[0], str) else args[0])
    try:
        return s.encode('ascii').decode('unicode_escape')
    except Exception:
        return s


def op_ord(evaluator, args):
    """字符码(字符) — 返回字符的 Unicode 码点"""
    if not args:
        return TritValue(0)
    s = _to_str(evaluator.eval(args[0]) if not isinstance(args[0], str) else args[0])
    if s:
        return TritValue(ord(s[0]))
    return TritValue(0)


def op_chr(evaluator, args):
    """字符(码点) — 从 Unicode 码点返回字符"""
    if not args:
        return ''
    n = evaluator.eval(args[0]).to_int() if isinstance(args[0], TritValue) else int(args[0])
    try:
        return chr(n)
    except (ValueError, OverflowError):
        return ''


register('url编码', op_url_encode)
register('url解码', op_url_decode)
register('unicode编码', op_unicode_escape)
register('unicode解码', op_unicode_unescape)
register('字符码', op_ord)
register('字符', op_chr)

register_alias('url_encode', 'url编码')
register_alias('url_decode', 'url解码')
register_alias('unicode_escape', 'unicode编码')
register_alias('unicode_unescape', 'unicode解码')
register_alias('ord', '字符码')
register_alias('chr', '字符')
