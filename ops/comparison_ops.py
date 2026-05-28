"""比较操作：等于、大于、小于等"""

from ternary_core import TritValue
from values import SanyanSyntaxError, SanyanTypeError
from ops.registry import register


class ComparisonOps:
    @staticmethod
    def comparison(evaluator, op, args):
        if len(args) != 2:
            raise SanyanSyntaxError(f'{op} 需要两个参数')
        a_val = evaluator.eval(args[0])
        b_val = evaluator.eval(args[1])

        def to_num(v):
            if isinstance(v, TritValue):
                return v.to_float() if v.is_float() else v.to_int()
            if isinstance(v, (int, float)):
                return v
            if isinstance(v, str):
                if evaluator.skin_manager:
                    state = evaluator.skin_manager.is_ternary_word(v)
                    if state is not None:
                        return state
                try:
                    return float(v) if '.' in v else int(v)
                except (ValueError, TypeError):
                    pass
            return None

        a = to_num(a_val)
        b = to_num(b_val)
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
            return TritValue(1 if truth else -1)

        if op in ('eq', 'ne'):
            result = (a_val == b_val) if op == 'eq' else (a_val != b_val)
            return TritValue(1 if result else -1)
        raise SanyanTypeError(f"无法将 '{a_val if a is None else b_val}' 转换为数值用于比较")

    @staticmethod
    def equals_op(evaluator, args):
        a = evaluator.eval(args[0])
        b = evaluator.eval(args[1])
        if isinstance(a, TritValue) and isinstance(b, TritValue):
            return TritValue(1 if a.symbol == b.symbol else -1)
        return TritValue(1 if a == b else 0)


register('eq', ComparisonOps.comparison, 'eq')
register('gt', ComparisonOps.comparison, 'gt')
register('lt', ComparisonOps.comparison, 'lt')
register('ne', ComparisonOps.comparison, 'ne')
register('gte', ComparisonOps.comparison, 'gte')
register('lte', ComparisonOps.comparison, 'lte')
register('ngt', ComparisonOps.comparison, 'ngt')
register('nlt', ComparisonOps.comparison, 'nlt')
register('same', ComparisonOps.equals_op)
