"""三态时间操作: 置信度衰减、记忆时效、序列化"""

from core.ternary_core import TritValue
from core.values import SanyanSyntaxError
from ops.registry import register
import time


def _decay_op(evaluator, args):
    """衰减(v, rate, elapsed, ...) — 置信度随时间线性衰减。
    C_new = C_old × (1 - rate × elapsed/86400)
    rate: 每天衰减率 (0.0-1.0)
    elapsed: 经过时间（秒），省略则用现在 - 值._timestamp 自动计算"""
    if len(args) < 2:
        raise SanyanSyntaxError('衰减 需要至少 2 个参数: 值, 衰减率 [, 经过秒数]')
    val = evaluator.eval(args[0])
    rate_v = evaluator.eval(args[1])
    rate = rate_v.to_float() if isinstance(rate_v, TritValue) else float(rate_v)
    if len(args) >= 3:
        e = evaluator.eval(args[2])
        elapsed = e.to_int() if isinstance(e, TritValue) else int(e)
    else:
        # 自动: 从值的创建时间到现在
        if isinstance(val, TritValue) and val._timestamp > 0:
            elapsed = int(time.time() - val._timestamp)
        else:
            elapsed = 86400  # 默认一天
    if not isinstance(val, TritValue):
        return val
    new_c = val.confidence * (1.0 - rate * elapsed / 86400.0)
    new_c = max(0.0, min(1.0, new_c))
    return val.with_confidence(new_c)


def _decay_exp_op(evaluator, args):
    """指数衰减(v, 半衰期) — 置信度指数衰减。
    C_new = C_old × 2^(-elapsed/halflife)"""
    if len(args) < 3:
        raise SanyanSyntaxError('指数衰减 需要 3 个参数: 值, 半衰期(秒), 经过秒数')
    val = evaluator.eval(args[0])
    halflife_v = evaluator.eval(args[1])
    halflife = halflife_v.to_int() if isinstance(halflife_v, TritValue) else int(halflife_v)
    elapsed_v = evaluator.eval(args[2])
    elapsed = elapsed_v.to_int() if isinstance(elapsed_v, TritValue) else int(elapsed_v)
    if not isinstance(val, TritValue):
        return val
    factor = 2.0 ** (-elapsed / max(1, halflife))
    new_c = val.confidence * factor
    new_c = max(0.0, min(1.0, new_c))
    return val.with_confidence(new_c)


def _serialize_op(evaluator, args):
    """序列化(v) — 三态值序列化为紧凑字符串。
    格式: "+0.9" (真, 0.9), "-" (假, 1.0), "0+红外传感器#1" (可能, 1.0, 带来源)"""
    if len(args) != 1:
        raise SanyanSyntaxError('序列化 需要一个参数')
    val = evaluator.eval(args[0])
    # FFI 句柄跨序列化无意义（RFC docs/ffi_plan.md §3.5：进程级 id，反序列化到别处
    # 是悬垂引用）——fail-closed 拒，不把内部 id 静默写进字符串。
    if isinstance(val, dict) and ('__py_handle__' in val or '__c_ptr__' in val or '__c_lib__' in val):
        raise SanyanSyntaxError('序列化 不支持 FFI 句柄（进程级引用，跨序列化无意义）')
    if not isinstance(val, TritValue):
        return str(val)
    symbols = {1: '+', 0: '0', -1: '-'}
    s = symbols.get(val.to_int() if val.is_numeric() else 0, '?')
    if val.is_string():
        return f'"{val.to_payload()}"@{val.confidence:.3f}'
    if val.confidence < 0.999:
        s += f'{val.confidence:.3f}'
    if val._source and val._source != '融合':
        s += f'+{val._source}'
    return s


def _deserialize_op(evaluator, args):
    """反序列化(str) — 紧凑字符串 → TritValue"""
    if len(args) != 1:
        raise SanyanSyntaxError('反序列化 需要一个参数')
    s = evaluator.eval(args[0])
    if isinstance(s, TritValue) and s.is_string():
        s = s.to_payload()
    s = str(s)

    if s.startswith('"') and '@' in s:
        # 字符串格式: "hello"@0.800
        payload, rest = s[1:].split('"@')
        c = float(rest) if rest else 1.0
        return TritValue(payload, confidence=c)

    confidence = 1.0
    source = ''
    rest = s
    if '+' in s[1:]:
        # "+0.900+红外传感器"
        parts = s[1:].split('+', 1)
        confidence = float(parts[0]) if parts[0] else 1.0
        source = parts[1] if len(parts) > 1 else ''

    val_map = {'+': 1, '-': -1, '0': 0}
    v = val_map.get(s[0], 0)
    if v == 0 and s[0] not in val_map:
        return TritValue(0)
    return TritValue(v, confidence=confidence, source=source)


register('decay', _decay_op)
register('decay_exp', _decay_exp_op)
register('serialize', _serialize_op)
register('deserialize', _deserialize_op)
