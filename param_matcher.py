"""参数匹配模块：从 commands.py 提取的参数解析和类型检查逻辑

支持默认参数：当调用参数少于定义参数时，用默认值填充。
"""

from values import SanyanSyntaxError, check_type
from ternary_core import TritValue


def match_params(params: list, op: str, args: list, defaults: dict | None = None, rest_param: str = '') -> list:
    """匹配参数列表，支持默认参数填充和可变参数。

    可变参数: 当 rest_param 非空时，超过 params 数量的参数打包为列表赋给 rest_param。
    """
    if defaults is None:
        defaults = {}
    if len(params) == len(args):
        return args
    # 点号/冒号分隔的两参数快捷语法
    if len(params) == 2 and len(args) == 1 and isinstance(args[0], str):
        sole = args[0]
        if '.' in sole:
            return sole.split('.', 1)
        if '：' in sole:
            return sole.split('：', 1)
    # 可变参数: 多余参数打包到 rest_param（追加到 args 末尾）
    if rest_param and len(args) > len(params):
        return list(args[:len(params)]) + [args[len(params):]]
    # 默认参数填充
    if len(args) < len(params):
        missing_params = params[len(args):]
        can_fill = all(p in defaults for p in missing_params)
        if can_fill:
            return list(args) + [defaults[p] for p in missing_params]
    raise SanyanSyntaxError(f"命令 '{op}' 需要 {len(params)} 个参数，但提供了 {len(args)} 个")


def evaluate_args(evaluator, params: list, args: list, param_types: dict) -> list:
    evaluated = []
    for param, arg_node in zip(params, args):
        if isinstance(arg_node, list):
            if len(arg_node) > 0 and isinstance(arg_node[0], str):
                value = evaluator.eval(arg_node)
            else:
                value = arg_node
        elif (
            isinstance(arg_node, str)
            and not arg_node.isdigit()
            and arg_node not in TritValue.STATE_MAP
            and not evaluator.has_var(arg_node)
        ):
            value = arg_node
            if (
                len(value) >= 2
                and value[0] in ('"', "'", '\u201c', '\u2018')
                and value[-1] in ('"', "'", '\u201d', '\u2019')
            ):
                value = value[1:-1]
        else:
            value = evaluator.eval(arg_node)
        if param in param_types:
            check_type(value, param_types[param], param)
        evaluated.append(value)
    return evaluated


def resolve_command(evaluator, op: str):
    """解析命令定义，返回 (params, body, param_types, return_type, defaults, rest_param)"""
    if op not in evaluator.commands:
        available = list(evaluator.commands.keys())[:10]
        hint = f'，可用命令: {available}' if available else ''
        from values import SanyanNameError
        raise SanyanNameError(f"未定义的操作: '{op}'{hint}")
    cmd_def = evaluator.commands[op]
    if len(cmd_def) >= 6:
        return cmd_def[0], cmd_def[1], cmd_def[2], cmd_def[3], cmd_def[4], cmd_def[5]
    if len(cmd_def) >= 5:
        return cmd_def[0], cmd_def[1], cmd_def[2], cmd_def[3], cmd_def[4], ''
    if len(cmd_def) >= 4:
        return cmd_def[0], cmd_def[1], cmd_def[2], cmd_def[3], {}, ''
    param_types = cmd_def[2] if len(cmd_def) > 2 else {}
    return cmd_def[0], cmd_def[1], param_types, None, {}, ''


def format_args(args: list) -> str:
    """格式化参数用于显示"""
    parts = []
    for a in args:
        if isinstance(a, TritValue):
            parts.append(str(a.to_int()))
        elif isinstance(a, str):
            if len(a) > 20:
                parts.append(a[:20] + '...')
            else:
                parts.append(a)
        elif isinstance(a, list):
            parts.append('[...]')
        else:
            parts.append(str(a))
    return ', '.join(parts)
