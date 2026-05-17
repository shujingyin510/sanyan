"""三态逻辑操作：且、或、非"""

from ternary_core import BT, TernaryALU, TritValue
from values import SanyanValueError
from ops.registry import register


class LogicOps:
    @staticmethod
    def logic_op(evaluator, op, args):
        if op in ('and', 'or'):
            if len(args) == 0:
                return TritValue(0)
            result = evaluator.eval(args[0])
            for i in range(1, len(args)):
                next_val = evaluator.eval(args[i])
                if op == 'and':
                    res_trits = TernaryALU.tritwise_and(result.value, next_val.value)
                else:
                    res_trits = TernaryALU.tritwise_or(result.value, next_val.value)
                result = TritValue(BT.to_int(res_trits))
            return result
        elif op == 'not':
            a = evaluator.eval(args[0])
            res = TernaryALU.tritwise_not(a.value)
            return TritValue(BT.to_int(res))
        raise SanyanValueError(f'未知的逻辑操作: {op}')


register('and', LogicOps.logic_op, 'and')
register('or', LogicOps.logic_op, 'or')
register('not', LogicOps.logic_op, 'not')
