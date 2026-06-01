"""自定义命令：定义与调用

支持默认参数：定义 foo (x, y = 10) { 返回 x 加 y }
参数列表中带 = 的参数有默认值，调用时可省略。
"""

from __future__ import annotations
from typing import Any, TYPE_CHECKING
from values import SanyanError, SanyanSyntaxError, check_type
from ternary_core import TritValue
from ops.registry import register
from tail_call import detect_tail_call, run_tail_call, run_normal, is_tail_call
from param_matcher import match_params, evaluate_args, resolve_command, format_args

if TYPE_CHECKING:
    from evaluator import SanyanEvaluator


def _parse_params(raw_params: list) -> tuple[list, dict]:
    """解析参数列表，提取默认值。

    输入: ['x', 'y', '=', '10'] 或 ['x', 'y']
    输出: (['x', 'y'], {'y': '10'})  — 参数名列表 + 默认值字典
    """
    params: list[str] = []
    defaults: dict[str, Any] = {}
    i = 0
    while i < len(raw_params):
        p = raw_params[i]
        if p == '=':
            # 前一个参数有默认值
            if params and i + 1 < len(raw_params):
                defaults[params[-1]] = raw_params[i + 1]
                i += 2
            else:
                i += 1
        elif isinstance(p, str):
            params.append(p)
            i += 1
        else:
            i += 1
    return params, defaults


class Commands:
    """自定义命令：定义、调用、类型检查、尾递归优化、默认参数"""

    @staticmethod
    def define(evaluator: SanyanEvaluator, args: list) -> TritValue:
        if len(args) < 3:
            raise SanyanSyntaxError('定义 需要名称、参数列表和体')
        cmd_name = args[0]
        if isinstance(cmd_name, list):
            cmd_name = cmd_name[0]
        raw_params = args[1]
        param_types = {}
        if len(args) > 2 and isinstance(args[2], dict):
            param_types = args[2]
            body = args[3:]
        else:
            body = args[2:]
        return_type = param_types.pop('__return__', None) if param_types else None
        # 解析参数列表，提取默认值
        params, defaults = _parse_params(raw_params)
        evaluator.commands[cmd_name] = (params, body, param_types, return_type, defaults)
        return TritValue(0)

    @staticmethod
    def _is_tail_call(expr: list, func_name: str) -> bool:
        """检测表达式是否是对指定函数的尾调用（向后兼容）"""
        return is_tail_call(expr, func_name)

    @staticmethod
    def _match_params(params: list, op: str, args: list) -> list:
        """匹配参数列表（向后兼容）"""
        return match_params(params, op, args)

    @staticmethod
    def _format_args(args: list) -> str:
        """格式化参数用于显示（向后兼容）"""
        return format_args(args)

    @staticmethod
    def call(evaluator: SanyanEvaluator, op: str, args: list) -> Any:
        evaluator.call_depth += 1
        if evaluator.call_depth > evaluator.max_call_depth:
            evaluator.call_depth -= 1
            from values import SanyanRuntimeError

            raise SanyanRuntimeError('命令调用超过了最大递归深度')
        evaluator.call_stack.append((op, args))
        try:
            params, body, param_types, return_type, defaults = resolve_command(evaluator, op)
            args = match_params(params, op, args, defaults)
            evaluated_args = evaluate_args(evaluator, params, args, param_types)
            tail_body, last_expr, is_tco = detect_tail_call(body, op, params, evaluated_args)
            if is_tco:
                result = run_tail_call(evaluator, params, tail_body, last_expr, op, evaluated_args)
            else:
                result = run_normal(evaluator, params, body, evaluated_args)
            if return_type:
                check_type(result, return_type, f'返回值 ({op})')
            return result
        except SanyanError:
            raise
        finally:
            if evaluator.call_stack:
                evaluator.call_stack.pop()
            evaluator.call_depth -= 1

    @staticmethod
    def _print_call_stack(evaluator: SanyanEvaluator, current_op: str, current_args: list) -> None:
        """打印调用栈"""
        print('\n=== 调用栈 ===')
        # 打印当前调用
        formatted_args = format_args(current_args)
        print(f'  at {current_op}({formatted_args})')
        # 打印之前的调用（从栈顶到栈底）
        for i in range(len(evaluator.call_stack) - 1, -1, -1):
            op, args = evaluator.call_stack[i]
            formatted_args = format_args(args)
            print(f'  at {op}({formatted_args})')
        print('==============\n')


# 注册 fn（函数定义）操作
register('fn', Commands.define)
