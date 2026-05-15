"""算术、比较、逻辑、数学函数、随机数"""
import math
import random
from ternary_core import BT, TernaryALU, TritValue
from values import SanyanSyntaxError, SanyanTypeError, SanyanValueError

def _to_num(v):
    """将 TritValue 或原始值转换为数值（保留浮点精度）"""
    if isinstance(v, TritValue):
        return v.to_float() if v.is_float() else v.to_int()
    try:
        s = str(v)
        return float(s) if '.' in s else int(s)
    except (ValueError, TypeError):
        return float(v)

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
        raise SanyanValueError(f"未知的逻辑操作: {op}")

    @staticmethod
    def comparison(evaluator, op, args):
        if len(args) != 2:
            raise SanyanSyntaxError(f"{op} 需要两个参数")
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
                except Exception:
                    pass
            raise SanyanTypeError(f"无法将 '{v}' 转换为数值用于比较")

        a = to_num(a_val)
        b = to_num(b_val)
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
                vals = [evaluator.eval(arg) for arg in args]
                nums = [_to_num(v) for v in vals]
                if any(isinstance(n, float) for n in nums):
                    total = 0.0
                    for n in nums:
                        total += float(n)
                    return TritValue(total)
                total = 0
                for n in nums:
                    total += int(n)
                return TritValue(total)
            except (AttributeError, TypeError, ValueError):
                parts = []
                for arg in args:
                    val = evaluator.eval(arg)
                    if isinstance(val, TritValue):
                        parts.append(str(val.to_float() if val.is_float() else val.to_int()))
                    else:
                        parts.append(str(val))
                return ''.join(parts)
        elif op == 'sub':
            if len(args) < 2:
                raise SanyanSyntaxError("减 需要至少两个参数")
            vals = [evaluator.eval(arg) for arg in args]
            nums = [_to_num(v) for v in vals]
            if any(isinstance(n, float) for n in nums):
                result = float(nums[0])
                for n in nums[1:]:
                    result -= float(n)
                return TritValue(result)
            else:
                result = int(nums[0])
                for n in nums[1:]:
                    result -= int(n)
                return TritValue(result)
        elif op == 'mul':
            vals = [evaluator.eval(arg) for arg in args]
            nums = [_to_num(v) for v in vals]
            if any(isinstance(n, float) for n in nums):
                result = float(nums[0])
                for n in nums[1:]:
                    result *= float(n)
                return TritValue(result)
            else:
                val = vals[0].value if isinstance(vals[0], TritValue) else BT.from_int(int(nums[0]))
                for idx, arg_val in enumerate(vals[1:]):
                    other = arg_val.value if isinstance(arg_val, TritValue) else BT.from_int(int(nums[idx+1]))
                    val = TernaryALU.multiply(val, other)
                return TritValue(BT.to_int(val))
        elif op == 'div':
            if len(args) != 2:
                raise SanyanSyntaxError("除 需要两个参数")
            a = evaluator.eval(args[0])
            b = evaluator.eval(args[1])
            a_num = a.to_float() if isinstance(a, TritValue) else float(a)
            b_num = b.to_float() if isinstance(b, TritValue) else float(b)
            if b_num == 0: raise SanyanValueError("除数不能为零")
            res = a_num / b_num
            if res.is_integer() and not (isinstance(a, TritValue) and a.is_float()) and not (isinstance(b, TritValue) and b.is_float()):
                return TritValue(int(res))
            return TritValue(res)
        elif op == 'mod':
            if len(args) != 2: raise SanyanSyntaxError("余 需要两个参数")
            a = evaluator.eval(args[0])
            b = evaluator.eval(args[1])
            a_num = a.to_float() if isinstance(a, TritValue) else float(a)
            b_num = b.to_float() if isinstance(b, TritValue) else float(b)
            res = a_num % b_num
            if res.is_integer() and not (isinstance(a, TritValue) and a.is_float()) and not (isinstance(b, TritValue) and b.is_float()):
                return TritValue(int(res))
            return TritValue(res)
        elif op == 'pow':
            if len(args) != 2: raise SanyanSyntaxError("幂 需要两个参数")
            a = evaluator.eval(args[0])
            b = evaluator.eval(args[1])
            a_num = a.to_float() if isinstance(a, TritValue) else float(a)
            b_num = b.to_float() if isinstance(b, TritValue) else float(b)
            res = a_num ** b_num
            if isinstance(res, complex):
                raise SanyanValueError("幂运算结果为复数，暂不支持")
            if res.is_integer() and not (isinstance(a, TritValue) and a.is_float()) and not (isinstance(b, TritValue) and b.is_float()):
                return TritValue(int(res))
            return TritValue(res)
        elif op == 'digit':
            if len(args) != 2: raise SanyanSyntaxError("取位 需要数字和位置")
            num = evaluator.eval(args[0]).to_int()
            pos = evaluator.eval(args[1]).to_int()
            digit = (abs(num) // (10 ** pos)) % 10
            return TritValue(digit)
        raise SanyanValueError(f"未知的算术操作: {op}")

    @staticmethod
    def equals_op(evaluator, args):
        a = evaluator.eval(args[0])
        b = evaluator.eval(args[1])
        return TritValue(1 if a.symbol == b.symbol else -1)

    @staticmethod
    def math_abs(evaluator, args):
        if len(args) != 1:
            raise SanyanSyntaxError("绝对值 需要一个参数")
        val = evaluator.eval(args[0])
        num = val.to_float() if isinstance(val, TritValue) else float(val)
        res = abs(num)
        if isinstance(val, TritValue) and not val.is_float():
            return TritValue(int(res))
        return TritValue(res)

    @staticmethod
    def math_max(evaluator, args):
        if len(args) < 2:
            raise SanyanSyntaxError("最大值 需要至少两个参数")
        vals = [evaluator.eval(arg) for arg in args]
        nums = [v.to_float() if isinstance(v, TritValue) else float(v) for v in vals]
        res = max(nums)
        if any(v.is_float() if isinstance(v, TritValue) else isinstance(v, float) for v in vals):
            return TritValue(float(res))
        return TritValue(int(res))

    @staticmethod
    def math_min(evaluator, args):
        if len(args) < 2:
            raise SanyanSyntaxError("最小值 需要至少两个参数")
        vals = [evaluator.eval(arg) for arg in args]
        nums = [v.to_float() if isinstance(v, TritValue) else float(v) for v in vals]
        res = min(nums)
        if any(v.is_float() if isinstance(v, TritValue) else isinstance(v, float) for v in vals):
            return TritValue(float(res))
        return TritValue(int(res))

    @staticmethod
    def math_sqrt(evaluator, args):
        if len(args) != 1:
            raise SanyanSyntaxError("平方根 需要一个参数")
        val = evaluator.eval(args[0])
        num = val.to_float() if isinstance(val, TritValue) else float(val)
        if num < 0:
            raise SanyanValueError("负数不能开平方根")
        res = math.sqrt(num)
        if res.is_integer() and isinstance(val, TritValue) and not val.is_float():
            return TritValue(int(res))
        return TritValue(res)

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
            raise SanyanSyntaxError("随机数 最多接受两个参数")

    @staticmethod
    def math_random_state(evaluator, args):
        return TritValue(random.choice([1, 0, -1]))

    @staticmethod
    def math_sin(evaluator, args):
        if len(args) != 1:
            raise SanyanSyntaxError("正弦 需要一个参数")
        val = evaluator.eval(args[0])
        x = val.to_float() if isinstance(val, TritValue) else float(val)
        return TritValue(math.sin(x))

    @staticmethod
    def math_cos(evaluator, args):
        if len(args) != 1:
            raise SanyanSyntaxError("余弦 需要一个参数")
        val = evaluator.eval(args[0])
        x = val.to_float() if isinstance(val, TritValue) else float(val)
        return TritValue(math.cos(x))

    @staticmethod
    def math_tan(evaluator, args):
        if len(args) != 1:
            raise SanyanSyntaxError("正切 需要一个参数")
        val = evaluator.eval(args[0])
        x = val.to_float() if isinstance(val, TritValue) else float(val)
        return TritValue(math.tan(x))

    @staticmethod
    def math_log(evaluator, args):
        if len(args) < 1 or len(args) > 2:
            raise SanyanSyntaxError("对数 需要一个或两个参数")
        val = evaluator.eval(args[0]).to_float()
        if val <= 0:
            raise SanyanValueError("对数的参数必须为正数")
        if len(args) == 2:
            base = evaluator.eval(args[1]).to_float()
            return TritValue(math.log(val, base))
        return TritValue(math.log(val))

    @staticmethod
    def math_log10(evaluator, args):
        if len(args) != 1:
            raise SanyanSyntaxError("常用对数 需要一个参数")
        val = evaluator.eval(args[0]).to_float()
        if val <= 0:
            raise SanyanValueError("常用对数的参数必须为正数")
        return TritValue(math.log10(val))

    @staticmethod
    def math_floor(evaluator, args):
        if len(args) != 1:
            raise SanyanSyntaxError("向下取整 需要一个参数")
        val = evaluator.eval(args[0])
        num = val.to_float() if isinstance(val, TritValue) else float(val)
        return TritValue(int(math.floor(num)))

    @staticmethod
    def math_ceil(evaluator, args):
        if len(args) != 1:
            raise SanyanSyntaxError("向上取整 需要一个参数")
        val = evaluator.eval(args[0])
        num = val.to_float() if isinstance(val, TritValue) else float(val)
        return TritValue(int(math.ceil(num)))

    @staticmethod
    def math_round(evaluator, args):
        if len(args) != 1:
            raise SanyanSyntaxError("四舍五入 需要一个参数")
        val = evaluator.eval(args[0])
        num = val.to_float() if isinstance(val, TritValue) else float(val)
        return TritValue(int(round(num)))

    @staticmethod
    def math_pow(evaluator, args):
        return MathOps.arithmetic(evaluator, 'pow', args)

    @staticmethod
    def ternary_parse(evaluator, args):
        if len(args) != 1:
            raise SanyanSyntaxError("三进制 需要一个参数")
        s = evaluator.eval(args[0])
        if not isinstance(s, str):
            raise SanyanTypeError("三进制 的参数必须是字符串")
        from ternary_core import TritValue
        trits = []
        for ch in s:
            if ch == '+': trits.append(1)
            elif ch == '0': trits.append(0)
            elif ch == '-': trits.append(-1)
            else: raise SanyanValueError(f"无效三进制字符: {ch}")
        if not trits: raise SanyanValueError("三进制字符串不能为空")
        return TritValue(trits)
