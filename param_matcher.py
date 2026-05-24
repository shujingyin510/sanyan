"""参数匹配模块：从 commands.py 提取的参数解析和类型检查逻辑"""

from values import SanyanSyntaxError, check_type
from ternary_core import TritValue


def match_params(params: list, op: str, args: list) -> list:
    """匹配参数列表，支持点号和冒号分隔的参数"""
    if len(params) == len(args):
        return args
    if len(params) == 2 and len(args) == 1 and isinstance(args[0], str):
        sole = args[0]
        if '.' in sole:
            return sole.split('.', 1)
        if '：' in sole:
            return sole.split('：', 1)
    raise SanyanSyntaxError(f"命令 '{op}' 需要 {len(params)} 个参数，但提供了 {len(args)} 个")


def evaluate_args(evaluator, params: list, args: list, param_types: dict) -> list:
    evaluated = []
    for param, arg_node in zip(params, args):
        if isinstance(arg_node, list):
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
    """解析命令定义，返回 (params, body, param_types, return_type)"""
    if op not in evaluator.commands:
        available = list(evaluator.commands.keys())[:10]
        hint = f'，可用命令: {available}' if available else ''
        from values import SanyanNameError

        raise SanyanNameError(f"未定义的操作: '{op}'{hint}")
    cmd_def = evaluator.commands[op]
    if len(cmd_def) >= 4:
        return cmd_def[0], cmd_def[1], cmd_def[2], cmd_def[3]
    param_types = cmd_def[2] if len(cmd_def) > 2 else {}
    return cmd_def[0], cmd_def[1], param_types, None


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
