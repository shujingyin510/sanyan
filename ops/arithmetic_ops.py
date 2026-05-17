"""算术操作：加、减、乘、除、余、幂、取位"""
from ternary_core import BT, TernaryALU, TritValue
from values import SanyanSyntaxError, SanyanValueError
from ops.registry import register
from values import to_num as _to_num


class ArithmeticOps:
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

register('add', ArithmeticOps.arithmetic, 'add')
register('sub', ArithmeticOps.arithmetic, 'sub')
register('mul', ArithmeticOps.arithmetic, 'mul')
register('div', ArithmeticOps.arithmetic, 'div')
register('mod', ArithmeticOps.arithmetic, 'mod')
register('pow', ArithmeticOps.arithmetic, 'pow')
register('digit', ArithmeticOps.arithmetic, 'digit')
