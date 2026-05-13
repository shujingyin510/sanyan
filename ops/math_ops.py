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
                except Exception:
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
        elif op == 'ngt': truth = a <= b
        elif op == 'nlt': truth = a >= b
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
            val = evaluator.eval(args[0]).value
            for arg in args[1:]:
                val = TernaryALU.multiply(val, evaluator.eval(arg).value)
            return TritValue(BT.to_int(val))
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

    @staticmethod
    def math_sin(evaluator, args):
        """正弦(x) - 计算正弦值（参数为弧度）"""
        if len(args) != 1:
            raise SyntaxError("正弦 需要一个参数")
        val = evaluator.eval(args[0])
        if isinstance(val, TritValue):
            x = val.to_int()
        else:
            x = float(val)
        return TritValue(int(math.sin(x) * 1000))  # 返回千分位精度的整数

    @staticmethod
    def math_cos(evaluator, args):
        """余弦(x) - 计算余弦值（参数为弧度）"""
        if len(args) != 1:
            raise SyntaxError("余弦 需要一个参数")
        val = evaluator.eval(args[0])
        if isinstance(val, TritValue):
            x = val.to_int()
        else:
            x = float(val)
        return TritValue(int(math.cos(x) * 1000))  # 返回千分位精度的整数

    @staticmethod
    def math_tan(evaluator, args):
        """正切(x) - 计算正切值（参数为弧度）"""
        if len(args) != 1:
            raise SyntaxError("正切 需要一个参数")
        val = evaluator.eval(args[0])
        if isinstance(val, TritValue):
            x = val.to_int()
        else:
            x = float(val)
        return TritValue(int(math.tan(x) * 1000))  # 返回千分位精度的整数

    @staticmethod
    def math_log(evaluator, args):
        """对数(x) - 计算自然对数"""
        if len(args) != 1:
            raise SyntaxError("对数 需要一个参数")
        val = evaluator.eval(args[0]).to_int()
        if val <= 0:
            raise ValueError("对数的参数必须为正数")
        return TritValue(int(math.log(val)))

    @staticmethod
    def math_log10(evaluator, args):
        """常用对数(x) - 计算以10为底的对数"""
        if len(args) != 1:
            raise SyntaxError("常用对数 需要一个参数")
        val = evaluator.eval(args[0]).to_int()
        if val <= 0:
            raise ValueError("常用对数的参数必须为正数")
        return TritValue(int(math.log10(val)))

    @staticmethod
    def math_floor(evaluator, args):
        """向下取整(x) - 返回不大于x的最大整数"""
        if len(args) != 1:
            raise SyntaxError("向下取整 需要一个参数")
        val = evaluator.eval(args[0])
        if isinstance(val, TritValue):
            return TritValue(val.to_int())  # 整数直接返回
        return TritValue(int(math.floor(float(val))))

    @staticmethod
    def math_ceil(evaluator, args):
        """向上取整(x) - 返回不小于x的最小整数"""
        if len(args) != 1:
            raise SyntaxError("向上取整 需要一个参数")
        val = evaluator.eval(args[0])
        if isinstance(val, TritValue):
            return TritValue(val.to_int())  # 整数直接返回
        return TritValue(int(math.ceil(float(val))))

    @staticmethod
    def math_round(evaluator, args):
        """四舍五入(x) - 四舍五入到最近整数"""
        if len(args) != 1:
            raise SyntaxError("四舍五入 需要一个参数")
        val = evaluator.eval(args[0])
        if isinstance(val, TritValue):
            return TritValue(val.to_int())  # 整数直接返回
        return TritValue(int(round(float(val))))

    @staticmethod
    def math_pow(evaluator, args):
        """幂(base, exp) - 计算base的exp次方"""
        if len(args) != 2:
            raise SyntaxError("幂 需要两个参数")
        base = evaluator.eval(args[0]).to_int()
        exp = evaluator.eval(args[1]).to_int()
        return TritValue(int(math.pow(base, exp)))

    @staticmethod
    def ternary_parse(evaluator, args):
        """三进制(str) - 将三进制字符串转换为三值整数，如 三进制("+-0") → 6"""
        if len(args) != 1:
            raise SyntaxError("三进制 需要一个参数")
        s = evaluator.eval(args[0])
        if not isinstance(s, str):
            raise TypeError("三进制 的参数必须是字符串（含 +, 0, - 字符）")
        from ternary_core import BT, TritValue
        trits = []
        for ch in s:
            if ch == '+':
                trits.append(1)
            elif ch == '0':
                trits.append(0)
            elif ch == '-':
                trits.append(-1)
            else:
                raise ValueError(f"三进制字符串只能包含 '+', '0', '-'，但得到 '{ch}'")
        if not trits:
            raise ValueError("三进制字符串不能为空")
        return TritValue(trits)