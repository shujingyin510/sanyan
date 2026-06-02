"""三态逻辑操作：且、或、非。信度守恒定律：
且 = min(所有输入置信度)   — 木桶效应，弱项决定全局
或 = max(所有输入置信度)   — 只要有一条高信度路径，输出就有把握
非 = 保持输入置信度        — 只翻值，不改信度
"""

from ternary_core import BT, TernaryALU, TritValue
from values import SanyanValueError
from ops.registry import register


class LogicOps:
    @staticmethod
    def logic_op(evaluator, op, args):
        if op == 'and':
            if len(args) == 0:
                return TritValue(0)
            vals = [evaluator.eval(a) for a in args]
            result_trits = vals[0].value
            for i in range(1, len(vals)):
                result_trits = TernaryALU.tritwise_and(result_trits, vals[i].value)
            # 且 (AND): 取信度 min（木桶效应）
            all_confidence = [v.confidence for v in vals if isinstance(v, TritValue)]
            c = min(all_confidence) if all_confidence else 1.0
            return TritValue(BT.to_int(result_trits), confidence=c)
        elif op == 'or':
            if len(args) == 0:
                return TritValue(0)
            vals = [evaluator.eval(a) for a in args]
            result_trits = vals[0].value
            for i in range(1, len(vals)):
                result_trits = TernaryALU.tritwise_or(result_trits, vals[i].value)
            # 或 (OR): 取信度 max（最强链）
            all_confidence = [v.confidence for v in vals if isinstance(v, TritValue)]
            c = max(all_confidence) if all_confidence else 1.0
            return TritValue(BT.to_int(result_trits), confidence=c)
        elif op == 'not':
            a = evaluator.eval(args[0])
            res = TernaryALU.tritwise_not(a.value)
            # 非 (NOT): 保持输入信度（只翻值）
            c = a.confidence if isinstance(a, TritValue) else 1.0
            return TritValue(BT.to_int(res), confidence=c)
        raise SanyanValueError(f'未知的逻辑操作: {op}')


register('and', LogicOps.logic_op, 'and')
register('or', LogicOps.logic_op, 'or')
register('not', LogicOps.logic_op, 'not')
