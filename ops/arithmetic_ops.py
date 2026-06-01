"""算术操作：纯三进制加减乘除余幂取位
每个操作独立注册，消除 if/elif 二次分发。
所有运算自动传播 TritValue 置信度（贝叶斯累积）。
"""

from ternary_core import BT, TernaryALU, TritValue
from ternary_core import _int_at_precision, ternary_log, ternary_exp
from values import SanyanSyntaxError, SanyanValueError, SanyanTypeError
from ops.registry import register
from eval_helpers import propagated_confidence

_DEFAULT_PRECISION = 16


def _to_tritvalue(v):
    """将任意值转为 TritValue（若可能），否则原样返回。"""
    if isinstance(v, TritValue):
        return v
    if isinstance(v, (int, float)):
        return TritValue(v)
    if isinstance(v, str):
        try:
            return TritValue(float(v)) if '.' in v else TritValue(int(v))
        except (ValueError, TypeError):
            return v
    return v


def _align_trits(trits_list, precs_list):
    """将多组 trit 对齐到最高精度。返回 (对齐列表, 目标精度)。"""
    if not trits_list:
        return [], 0
    max_prec = max(precs_list)
    if max_prec == 0:
        return list(trits_list), 0
    result = []
    for trits, prec in zip(trits_list, precs_list):
        if prec == max_prec:
            result.append(trits)
        elif prec == 0:
            result.append(_int_at_precision(BT.to_int(trits), max_prec))
        else:
            factor = 3 ** (max_prec - prec)
            result.append(BT.from_int(BT.to_int(trits) * factor))
    return result, max_prec


def _fold_ternary(op, trits_list):
    """折叠三元 ALU 操作。"""
    result = trits_list[0]
    for t in trits_list[1:]:
        if op == 'add':
            result = TernaryALU.add(result, t)
        elif op == 'sub':
            result = TernaryALU.sub(result, t)
        elif op == 'mul':
            result = TernaryALU.multiply(result, t)
    return result


def _ternary_pow_int(base_trits, exp_int):
    """快速幂：base^exp，exp 为非负整数。"""
    if exp_int == 0:
        return BT.from_int(1)
    result = BT.from_int(1)
    base = base_trits
    e = exp_int
    while e > 0:
        if e & 1:
            result = TernaryALU.multiply(result, base)
        base = TernaryALU.multiply(base, base)
        e >>= 1
    return result


# ═══════════════════════════════════════════════════════════
# 独立操作函数：消除 arithmetic() 中的 if/elif 二次分发
# ═══════════════════════════════════════════════════════════


def _op_add(evaluator, args):
    """加法：支持数字加法和字符串连接。"""
    vals = [_to_tritvalue(evaluator.eval(arg)) for arg in args]
    if all(isinstance(v, TritValue) for v in vals):
        trits_list = [v.value for v in vals]
        precs_list = [v.precision for v in vals]
        aligned, prec = _align_trits(trits_list, precs_list)
        result = _fold_ternary('add', aligned)
        return TritValue(result, prec, confidence=propagated_confidence(*vals))
    parts = []
    for val in vals:
        if isinstance(val, TritValue):
            parts.append(str(val.to_float() if val.is_float() else val.to_int()))
        else:
            parts.append(str(val))
    return ''.join(parts)


def _op_sub(evaluator, args):
    """减法：至少两个参数。"""
    if len(args) < 2:
        raise SanyanSyntaxError('减 需要至少两个参数')
    vals = [_to_tritvalue(evaluator.eval(arg)) for arg in args]
    if not all(isinstance(v, TritValue) for v in vals):
        raise SanyanTypeError('减 的参数必须为数字')
    trits_list = [v.value for v in vals]
    precs_list = [v.precision for v in vals]
    aligned, prec = _align_trits(trits_list, precs_list)
    result = _fold_ternary('sub', aligned)
    return TritValue(result, prec, confidence=propagated_confidence(*vals))


def _op_mul(evaluator, args):
    """乘法：支持整数和定点乘法。"""
    vals = [_to_tritvalue(evaluator.eval(arg)) for arg in args]
    if not all(isinstance(v, TritValue) for v in vals):
        raise SanyanTypeError('乘 的参数必须为数字')
    trits_list = [v.value for v in vals]
    precs_list = [v.precision for v in vals]
    aligned, prec = _align_trits(trits_list, precs_list)
    if prec == 0:
        result = _fold_ternary('mul', aligned)
        return TritValue(result, 0, confidence=propagated_confidence(*vals))
    result = aligned[0]
    for t in aligned[1:]:
        result = TernaryALU.fixed_mul(result, t, prec)
    return TritValue(result, prec, confidence=propagated_confidence(*vals))


def _op_div(evaluator, args):
    """除法：两个参数，除数不能为零。"""
    if len(args) != 2:
        raise SanyanSyntaxError('除 需要两个参数')
    a = _to_tritvalue(evaluator.eval(args[0]))
    b = _to_tritvalue(evaluator.eval(args[1]))
    if not isinstance(a, TritValue) or not isinstance(b, TritValue):
        raise SanyanTypeError('除 的参数必须为数字')
    a_trits, b_trits = a.value, b.value
    if TernaryALU.is_zero(b_trits):
        raise SanyanValueError('除数不能为零')
    a_prec, b_prec = a.precision, b.precision
    if a_prec == 0 and b_prec == 0:
        result = TernaryALU.div(a_trits, b_trits, _DEFAULT_PRECISION)
        val = BT.to_int(result)
        scale = 3**_DEFAULT_PRECISION
        c = propagated_confidence(a, b)
        if val % scale == 0:
            return TritValue(val // scale, confidence=c)
        return TritValue(result, _DEFAULT_PRECISION, confidence=c)
    prec = max(a_prec, b_prec)
    if a_prec != b_prec:
        aligned, _ = _align_trits([a_trits, b_trits], [a_prec, b_prec])
        a_trits, b_trits = aligned
    result = TernaryALU.fixed_div(a_trits, b_trits, prec)
    val = BT.to_int(result)
    scale = 3**prec
    c = propagated_confidence(a, b)
    if val % scale == 0:
        return TritValue(val // scale, confidence=c)
    return TritValue(result, prec, confidence=c)


def _op_mod(evaluator, args):
    """取余：两个参数，除数不能为零。"""
    if len(args) != 2:
        raise SanyanSyntaxError('余 需要两个参数')
    a = _to_tritvalue(evaluator.eval(args[0]))
    b = _to_tritvalue(evaluator.eval(args[1]))
    if not isinstance(a, TritValue) or not isinstance(b, TritValue):
        raise SanyanTypeError('余 的参数必须为数字')
    a_trits, b_trits = a.value, b.value
    if TernaryALU.is_zero(b_trits):
        raise SanyanValueError('除数不能为零')
    a_prec, b_prec = a.precision, b.precision
    if a_prec != b_prec:
        aligned, _ = _align_trits([a_trits, b_trits], [a_prec, b_prec])
        a_trits, b_trits = aligned
        prec = max(a_prec, b_prec)
    else:
        prec = a_prec
    a_int = BT.to_int(a_trits)
    b_int = BT.to_int(b_trits)
    q = a_int // b_int
    q_trits = BT.from_int(q)
    remainder = TernaryALU.sub(a_trits, TernaryALU.multiply(q_trits, b_trits))
    r_int = BT.to_int(remainder)
    if prec > 0:
        return TritValue(BT.from_int(r_int), prec)
    return TritValue(r_int)


def _op_pow(evaluator, args):
    """幂运算：两个参数，指数暂不支持负数。"""
    if len(args) != 2:
        raise SanyanSyntaxError('幂 需要两个参数')
    a = evaluator.eval(args[0])
    b = evaluator.eval(args[1])
    if not isinstance(a, TritValue) or not isinstance(b, TritValue):
        raise SanyanTypeError('幂 的参数必须为数字')
    a_trits, b_trits = a.value, b.value
    a_prec, b_prec = a.precision, b.precision

    if b_prec == 0:
        exp = BT.to_int(b_trits)
        if exp < 0:
            raise SanyanValueError('幂指数暂不支持负数')
        if a_prec == 0:
            result = _ternary_pow_int(a_trits, exp)
            return TritValue(BT.to_int(result))
        prec = a_prec
        result = _ternary_pow_int(a_trits, exp)
        val = BT.to_int(result)
        scale = 3**prec
        if val % scale == 0:
            return TritValue(val // scale)
        return TritValue(result, prec)

    prec = max(a_prec, b_prec)
    if a_prec != b_prec:
        aligned, _ = _align_trits([a_trits, b_trits], [a_prec, b_prec])
        a_trits, b_trits = aligned
    if BT.to_int(a_trits) <= 0:
        raise SanyanValueError('浮点幂的底数必须为正数')
    ln_a = ternary_log(a_trits, prec)
    prod = TernaryALU.fixed_mul(b_trits, ln_a, prec)
    result = ternary_exp(prod, prec)
    val = BT.to_int(result)
    scale = 3**prec
    if val % scale == 0:
        return TritValue(val // scale)
    return TritValue(result, prec)


def _op_digit(evaluator, args):
    """取位：数字和位置。"""
    if len(args) != 2:
        raise SanyanSyntaxError('取位 需要数字和位置')
    num = evaluator.eval(args[0])
    pos = evaluator.eval(args[1])
    if not isinstance(num, TritValue) or not isinstance(pos, TritValue):
        raise SanyanTypeError('取位 的参数必须为数字')
    num_int = BT.to_int(num.value)
    pos_int = BT.to_int(pos.value)
    digit = (abs(num_int) // (10**pos_int)) % 10
    return TritValue(digit)


# ── 注册：每个操作独立函数 ──
register('add', _op_add)
register('sub', _op_sub)
register('mul', _op_mul)
register('div', _op_div)
register('mod', _op_mod)
register('pow', _op_pow)
register('digit', _op_digit)
