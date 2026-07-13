"""尾递归优化模块：从 commands.py 提取的尾调用检测和执行逻辑"""

from typing import Tuple, Optional
from core.values import ReturnException, SanyanRuntimeError
from core.ternary_core import TritValue

_TCO_LOOP_MULTIPLIER = 10


def is_tail_call(expr: list, func_name: str) -> bool:
    """检测表达式是否是对指定函数的尾调用"""
    if isinstance(expr, list) and len(expr) > 0 and expr[0] == func_name:
        return True
    # 检测 return(f(args)) 模式
    if isinstance(expr, list) and len(expr) == 2 and expr[0] == 'return':
        inner = expr[1]
        if isinstance(inner, list) and len(inner) > 0 and inner[0] == func_name:
            return True
    return False


def detect_tail_call(body: list, op: str, params: list, args: list) -> Tuple[list, Optional[list], bool]:
    """检测函数体中的尾调用

    返回: (tail_body, last_expr, is_tco)
    """
    last_expr = body[-1] if body else None
    tail_body = body
    if isinstance(last_expr, list) and len(last_expr) > 0 and last_expr[0] == 'do':
        tail_body = last_expr[1:] if len(last_expr) > 1 else []
        last_expr = tail_body[-1] if tail_body else None
    is_tco = last_expr is not None and is_tail_call(last_expr, op)
    return tail_body, last_expr, is_tco


def run_tail_call(
    evaluator, params: list, tail_body: list, last_expr: Optional[list], op: str, args: list
) -> TritValue:
    """执行尾递归优化的函数调用"""
    from ops.capability import check_deadline  # 惰性导入避免 core→ops 环

    max_iterations = evaluator.max_loop_steps * _TCO_LOOP_MULTIPLIER
    iteration = 0
    while iteration < max_iterations:
        check_deadline(evaluator)  # 限时看门狗（递归也是跑飞向量）
        evaluator.push_scope()
        for param, value in zip(params, args):
            evaluator.set_var(param, value)
        try:
            for expr in tail_body[:-1]:
                try:
                    evaluator.eval(expr)
                except ReturnException as ret:
                    return ret.value if ret.value is not None else TritValue(0)

            tail_expr = last_expr
            if isinstance(tail_expr, list) and tail_expr[0] == 'return':
                tail_expr = tail_expr[1]
            if tail_expr is not None:
                args = [evaluator.eval(arg) for arg in tail_expr[1:]]
            else:
                args = []
        except ReturnException as ret:
            return ret.value if ret.value is not None else TritValue(0)
        finally:
            evaluator.pop_scope()
        iteration += 1
    raise SanyanRuntimeError('尾递归超过了最大迭代次数')


def run_normal(evaluator, params: list, body: list, evaluated_args: list) -> TritValue:
    """执行普通的函数调用（非尾递归优化）"""
    evaluator.push_scope()
    for param, value in zip(params, evaluated_args):
        evaluator.set_var(param, value)
    result = None
    try:
        for expr in body:
            try:
                result = evaluator.eval(expr)
            except ReturnException as ret:
                result = ret.value
                break
    finally:
        evaluator.pop_scope()
    return result if result is not None else TritValue(0)
