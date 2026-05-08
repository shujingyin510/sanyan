"""算术、比较、逻辑、数学函数、随机数"""
import math
import random
from ternary_core import BT, TernaryALU, TritValue

class MathOps:
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
        raise ValueError(f"未知的逻辑操作: {op}")

    @staticmethod
    def comparison(evaluator, op, args):
        if len(args) != 2:
            raise SyntaxError(f"{op} 需要两个参数")
        a_val = evaluator.eval(args[0])
        b_val = evaluator.eval(args[1])

        def to_int(v):
            if isinstance(v, TritValue):
                return v.to_int()
            if isinstance(v, int):
                return v
            if isinstance(v, str):
                if evaluator.skin_manager:
                    state = evaluator.skin_manager.is_ternary_word(v)
                    if state is not None:
                        return state
                try:
                    return int(v)
                except:
                    pass
            raise TypeError(f"无法将 '{v}' 转换为整数用于比较")

        a = to_int(a_val)
        b = to_int(b_val)
        truth = False
        if op == 'eq':   truth = a == b
        elif op == 'gt': truth = a > b
        elif op == 'lt': truth = a < b
        elif op == 'ne': truth = a != b
        elif op == 'gte': truth = a >= b
        elif op == 'lte': truth = a <= b
        return TritValue(1 if truth else -1)

    @staticmethod
    def arithmetic(evaluator, op, args):
        if op == 'add':
            try:
                total = 0
                for arg in args:
                    total += evaluator.eval(arg).to_int()
                return TritValue(total)
            except (AttributeError, TypeError):
                parts = []
                for arg in args:
                    val = evaluator.eval(arg)
                    if isinstance(val, str): parts.append(val)
                    elif isinstance(val, TritValue): parts.append(str(val.to_int()))
                    else: parts.append(str(val))
                return ''.join(parts)
        elif op == 'sub':
            if len(args) < 2:
                raise SyntaxError("减 需要至少两个参数")
            result = evaluator.eval(args[0]).to_int()
            for arg in args[1:]:
                result -= evaluator.eval(arg).to_int()
            return TritValue(result)
        elif op == 'mul':
            result = 1
            for arg in args:
                result *= evaluator.eval(arg).to_int()
            return TritValue(result)
        elif op == 'div':
            if len(args) != 2:
                raise SyntaxError("除 需要两个参数")
            a = evaluator.eval(args[0]).to_int()
            b = evaluator.eval(args[1]).to_int()
            if b == 0: raise ValueError("除数不能为零")
            return TritValue(a // b)
        elif op == 'mod':
            if len(args) != 2: raise SyntaxError("余 需要两个参数")
            a = evaluator.eval(args[0]).to_int()
            b = evaluator.eval(args[1]).to_int()
            return TritValue(a % b)
        elif op == 'pow':
            if len(args) != 2: raise SyntaxError("幂 需要两个参数")
            a = evaluator.eval(args[0]).to_int()
            b = evaluator.eval(args[1]).to_int()
            return TritValue(a ** b)
        elif op == 'digit':
            if len(args) != 2: raise SyntaxError("取位 需要数字和位置")
            num = evaluator.eval(args[0]).to_int()
            pos = evaluator.eval(args[1]).to_int()
            digit = (abs(num) // (10 ** pos)) % 10
            return TritValue(digit)
        raise ValueError(f"未知的算术操作: {op}")

    @staticmethod
    def equals_op(evaluator, args):
        a = evaluator.eval(args[0])
        b = evaluator.eval(args[1])
        return TritValue(1 if a.symbol == b.symbol else -1)

    @staticmethod
    def math_abs(evaluator, args):
        if len(args) != 1:
            raise SyntaxError("绝对值 需要一个参数")
        val = evaluator.eval(args[0]).to_int()
        return TritValue(abs(val))

    @staticmethod
    def math_max(evaluator, args):
        if len(args) < 2:
            raise SyntaxError("最大值 需要至少两个参数")
        max_val = None
        for arg in args:
            v = evaluator.eval(arg).to_int()
            if max_val is None or v > max_val:
                max_val = v
        return TritValue(max_val)

    @staticmethod
    def math_min(evaluator, args):
        if len(args) < 2:
            raise SyntaxError("最小值 需要至少两个参数")
        min_val = None
        for arg in args:
            v = evaluator.eval(arg).to_int()
            if min_val is None or v < min_val:
                min_val = v
        return TritValue(min_val)

    @staticmethod
    def math_sqrt(evaluator, args):
        if len(args) != 1:
            raise SyntaxError("平方根 需要一个参数")
        val = evaluator.eval(args[0]).to_int()
        if val < 0:
            raise ValueError("负数不能开平方根")
        return TritValue(int(math.isqrt(val)))

    @staticmethod
    def math_random(evaluator, args):
        if len(args) == 0:
            return TritValue(random.choice([0, 1]))
        elif len(args) == 1:
            end = evaluator.eval(args[0]).to_int()
            return TritValue(random.randint(0, end))
        elif len(args) == 2:
            start = evaluator.eval(args[0]).to_int()
            end = evaluator.eval(args[1]).to_int()
            return TritValue(random.randint(start, end))
        else:
            raise SyntaxError("随机数 最多接受两个参数")

    @staticmethod
    def math_random_state(evaluator, args):
        return TritValue(random.choice([1, 0, -1]))