"""比较操作：等于、大于、小于等

每个比较操作独立注册。比较结果自动传播 TritValue 置信度。
"""

from ternary_core import TritValue
from values import SanyanSyntaxError, SanyanTypeError
from ops.registry import register
from eval_helpers import propagated_confidence


def _to_num(v, skin_manager=None):
    """将值转为数值用于比较。非数值返回 None。"""
    if isinstance(v, TritValue):
        return v.to_float() if v.is_float() else v.to_int()
    if isinstance(v, (int, float)):
        return v
    if isinstance(v, str):
        if skin_manager:
            state = skin_manager.is_ternary_word(v)
            if state is not None:
                return state
        try:
            return float(v) if '.' in v else int(v)
        except (ValueError, TypeError):
            pass
    return None


def _compare(evaluator, op, args):
    """二元比较：将两个操作数转为数值后比较。"""
    if len(args) != 2:
        raise SanyanSyntaxError(f'{op} 需要两个参数')
    a_val = evaluator.eval(args[0])
    b_val = evaluator.eval(args[1])
    a = _to_num(a_val, evaluator.skin_manager)
    b = _to_num(b_val, evaluator.skin_manager)
    if a is not None and b is not None:
        truth = False
        if op == 'eq':
            truth = a == b
        elif op == 'gt':
            truth = a > b
        elif op == 'lt':
            truth = a < b
        elif op == 'ne':
            truth = a != b
        elif op == 'gte':
            truth = a >= b
        elif op == 'lte':
            truth = a <= b
        elif op == 'ngt':
            truth = a <= b
        elif op == 'nlt':
            truth = a >= b
        return TritValue(1 if truth else -1, confidence=propagated_confidence(a_val, b_val))
    if op in ('eq', 'ne'):
        result = (a_val == b_val) if op == 'eq' else (a_val != b_val)
        return TritValue(1 if result else -1, confidence=propagated_confidence(a_val, b_val))
    raise SanyanTypeError(f"无法将 '{a_val if a is None else b_val}' 转换为数值用于比较")


def _equals_op(evaluator, args):
    """三值相等：比较两个值是否完全相同（含三进制符号）。"""
    a = evaluator.eval(args[0])
    b = evaluator.eval(args[1])
    if isinstance(a, TritValue) and isinstance(b, TritValue):
        return TritValue(1 if a.symbol == b.symbol else -1)
    return TritValue(1 if a == b else 0)


# ── 注册 ──
register('eq', _compare, 'eq')
register('gt', _compare, 'gt')
register('lt', _compare, 'lt')
register('ne', _compare, 'ne')
register('gte', _compare, 'gte')
register('lte', _compare, 'lte')
register('ngt', _compare, 'ngt')
register('nlt', _compare, 'nlt')
register('same', _equals_op)
