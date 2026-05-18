"""正则表达式操作"""

import re
from ternary_core import TritValue
from values import SanyanSyntaxError
from ops.registry import register, register_alias


def _to_str(evaluator, val):
    if isinstance(val, TritValue):
        return str(val)
    if isinstance(val, str) and val and val[0] in ('"', "'", '\u201c', '\u2018'):
        return evaluator.eval(val)
    return str(val)


def op_re_match(evaluator, args):
    """正则匹配(模式, 字符串) — 若完全匹配返回真，否则返回假"""
    if len(args) < 2:
        raise SanyanSyntaxError('正则匹配 需要 模式 和 字符串')
    pattern = str(evaluator.eval(args[0]))
    text = str(evaluator.eval(args[1]))
    try:
        return TritValue(1 if re.fullmatch(pattern, text) else 0)
    except re.error as e:
        raise SanyanSyntaxError(f'正则错误: {e}')


def op_re_search(evaluator, args):
    """正则搜索(模式, 字符串) — 返回第一个匹配位置及内容，未匹配返回空"""
    if len(args) < 2:
        raise SanyanSyntaxError('正则搜索 需要 模式 和 字符串')
    pattern = str(evaluator.eval(args[0]))
    text = str(evaluator.eval(args[1]))
    try:
        m = re.search(pattern, text)
        if m is None:
            return ''
        return m.group(0)
    except re.error as e:
        raise SanyanSyntaxError(f'正则错误: {e}')


def op_re_findall(evaluator, args):
    """正则查找(模式, 字符串) — 返回所有匹配的列表"""
    if len(args) < 2:
        raise SanyanSyntaxError('正则查找 需要 模式 和 字符串')
    pattern = str(evaluator.eval(args[0]))
    text = str(evaluator.eval(args[1]))
    try:
        return list(re.findall(pattern, text))
    except re.error as e:
        raise SanyanSyntaxError(f'正则错误: {e}')


def op_re_replace(evaluator, args):
    """正则替换(模式, 替换, 字符串) — 正则匹配替换"""
    if len(args) < 3:
        raise SanyanSyntaxError('正则替换 需要 模式, 替换 和 字符串')
    pattern = str(evaluator.eval(args[0]))
    repl = str(evaluator.eval(args[1]))
    text = str(evaluator.eval(args[2]))
    try:
        return re.sub(pattern, repl, text)
    except re.error as e:
        raise SanyanSyntaxError(f'正则错误: {e}')


def op_re_split(evaluator, args):
    """正则分割(模式, 字符串) — 按正则分割字符串"""
    if len(args) < 2:
        raise SanyanSyntaxError('正则分割 需要 模式 和 字符串')
    pattern = str(evaluator.eval(args[0]))
    text = str(evaluator.eval(args[1]))
    try:
        return re.split(pattern, text)
    except re.error as e:
        raise SanyanSyntaxError(f'正则错误: {e}')


register('正则匹配', op_re_match)
register('正则搜索', op_re_search)
register('正则查找', op_re_findall)
register('正则替换', op_re_replace)
register('正则分割', op_re_split)

register_alias('re_match', '正则匹配')
register_alias('re_search', '正则搜索')
register_alias('re_findall', '正则查找')
register_alias('re_replace', '正则替换')
register_alias('re_split', '正则分割')
