"""数学函数：绝对值、最大值、平方根、三角函数、对数、随机数、取整、三进制解析"""
import math
import random
from ternary_core import BT, TernaryALU, TritValue, ternary_sin, ternary_cos, ternary_tan, ternary_sqrt, ternary_log, ternary_log10
from values import SanyanSyntaxError, SanyanTypeError, SanyanValueError
from ops.registry import register


class MathFuncsOps:
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
        if isinstance(val, TritValue) and val.precision > 0:
            prec = val.precision
            result = ternary_sqrt(val.value, prec)
            return TritValue(result, prec)
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
        if isinstance(val, TritValue) and val.precision > 0:
            prec = val.precision
            return TritValue(ternary_sin(val.value, prec), prec)
        x = val.to_float() if isinstance(val, TritValue) else float(val)
        return TritValue(math.sin(x))

    @staticmethod
    def math_cos(evaluator, args):
        if len(args) != 1:
            raise SanyanSyntaxError("余弦 需要一个参数")
        val = evaluator.eval(args[0])
        if isinstance(val, TritValue) and val.precision > 0:
            prec = val.precision
            return TritValue(ternary_cos(val.value, prec), prec)
        x = val.to_float() if isinstance(val, TritValue) else float(val)
        return TritValue(math.cos(x))

    @staticmethod
    def math_tan(evaluator, args):
        if len(args) != 1:
            raise SanyanSyntaxError("正切 需要一个参数")
        val = evaluator.eval(args[0])
        if isinstance(val, TritValue) and val.precision > 0:
            prec = val.precision
            return TritValue(ternary_tan(val.value, prec), prec)
        x = val.to_float() if isinstance(val, TritValue) else float(val)
        return TritValue(math.tan(x))

    @staticmethod
    def math_log(evaluator, args):
        if len(args) < 1 or len(args) > 2:
            raise SanyanSyntaxError("对数 需要一个或两个参数")
        val = evaluator.eval(args[0])
        if isinstance(val, TritValue) and val.precision > 0:
            prec = val.precision
            x_trits = val.value
            x_val = BT.to_float(x_trits, prec)
            if x_val <= 0:
                raise SanyanValueError("对数的参数必须为正数")
            if len(args) == 2:
                base = evaluator.eval(args[1])
                if isinstance(base, TritValue) and base.precision > 0:
                    ln_b = ternary_log(x_trits, prec)
                    ln_a = ternary_log(base.value, prec)
                    return TritValue(TernaryALU.fixed_div(ln_b, ln_a, prec), prec)
                return TritValue(math.log(x_val, base.to_float()))
            return TritValue(ternary_log(x_trits, prec), prec)
        val_f = val.to_float()
        if val_f <= 0:
            raise SanyanValueError("对数的参数必须为正数")
        if len(args) == 2:
            base = evaluator.eval(args[1]).to_float()
            return TritValue(math.log(val_f, base))
        return TritValue(math.log(val_f))

    @staticmethod
    def math_log10(evaluator, args):
        if len(args) != 1:
            raise SanyanSyntaxError("常用对数 需要一个参数")
        val = evaluator.eval(args[0])
        if isinstance(val, TritValue) and val.precision > 0:
            prec = val.precision
            return TritValue(ternary_log10(val.value, prec), prec)
        val_f = val.to_float()
        if val_f <= 0:
            raise SanyanValueError("常用对数的参数必须为正数")
        return TritValue(math.log10(val_f))

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
        from ops.arithmetic_ops import ArithmeticOps
        return ArithmeticOps.arithmetic(evaluator, 'pow', args)

    @staticmethod
    def ternary_parse(evaluator, args):
        if len(args) != 1:
            raise SanyanSyntaxError("三进制 需要一个参数")
        s = evaluator.eval(args[0])
        if not isinstance(s, str):
            raise SanyanTypeError("三进制 的参数必须是字符串")
        trits = []
        for ch in s:
            if ch == '+': trits.append(1)
            elif ch == '0': trits.append(0)
            elif ch == '-': trits.append(-1)
            else: raise SanyanValueError(f"无效三进制字符: {ch}")
        if not trits: raise SanyanValueError("三进制字符串不能为空")
        return TritValue(trits)

register('abs', MathFuncsOps.math_abs)
register('max', MathFuncsOps.math_max)
register('min', MathFuncsOps.math_min)
register('sqrt', MathFuncsOps.math_sqrt)
register('random', MathFuncsOps.math_random)
register('random_state', MathFuncsOps.math_random_state)
register('sin', MathFuncsOps.math_sin)
register('cos', MathFuncsOps.math_cos)
register('tan', MathFuncsOps.math_tan)
register('log', MathFuncsOps.math_log)
register('log10', MathFuncsOps.math_log10)
register('floor', MathFuncsOps.math_floor)
register('ceil', MathFuncsOps.math_ceil)
register('round', MathFuncsOps.math_round)
register('math_pow', MathFuncsOps.math_pow)
register('ternary', MathFuncsOps.ternary_parse)
