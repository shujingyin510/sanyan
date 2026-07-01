"""三态工具操作：移位、翻转、压缩、解压、解析、枚举、结构体、信念"""

from core.ternary_core import TritValue
from core.values import SanyanSyntaxError
from ops.registry import register
import time


def _trit_shift(evaluator, args):
    """三态移位(x, n) — trit 位左移 n 位 (×3^n 等价)"""
    if len(args) != 2:
        raise SanyanSyntaxError('三态移位 需要值和位数')
    val = evaluator.eval(args[0])
    n = evaluator.eval(args[1])
    n = n.to_int() if isinstance(n, TritValue) else int(n)
    v = val.to_int() if isinstance(val, TritValue) else int(val)
    c = val.confidence if isinstance(val, TritValue) else 1.0
    result = v * (3**n)
    return TritValue(result, confidence=c)


register('trit_shift', _trit_shift)


def _trit_flip(evaluator, args):
    """三态翻转(x) — 所有 trit 翻转: 真↔假, 可能不变"""
    if len(args) != 1:
        raise SanyanSyntaxError('三态翻转 需要一个值')
    val = evaluator.eval(args[0])
    v = val.to_int() if isinstance(val, TritValue) else int(val)
    c = val.confidence if isinstance(val, TritValue) else 1.0
    return TritValue(-v, confidence=c)


register('trit_flip', _trit_flip)


def _trit_compress(evaluator, args):
    """三态压缩(...) — 多个 trit 打包为字节列表。每字节存 3 trit (0-26)。
    三态压缩(+,-,0,+,-,0) → [15] (3^2×1 + 3^1×(-1) + 3^0×0 = 8, ...)"""
    vals = [evaluator.eval(a) for a in args]
    result = []
    buf = []
    for v in vals:
        iv = v.to_int() if isinstance(v, TritValue) else int(v)
        iv = max(-1, min(1, iv)) + 1  # -1→0, 0→1, 1→2
        buf.append(iv)
        if len(buf) == 3:
            byte_val = buf[0] * 9 + buf[1] * 3 + buf[2] * 1
            result.append(TritValue(byte_val))
            buf = []
    if buf:
        while len(buf) < 3:
            buf.append(1)  # 补 0 (可能)
        byte_val = buf[0] * 9 + buf[1] * 3 + buf[2] * 1
        result.append(TritValue(byte_val))
    return result


register('trit_compress', _trit_compress)


def _trit_decompress(evaluator, args):
    """三态解压(字节列表) → 展开为 trit 值列表"""
    bytes_list = [evaluator.eval(a) for a in args]
    result = []
    for b in bytes_list:
        bv = b.to_int() if isinstance(b, TritValue) else int(b)
        for shift in (9, 3, 1):
            digit = (bv // shift) % 3
            result.append(TritValue(digit - 1))
    return result


register('trit_decompress', _trit_decompress)


def _parse_hex(evaluator, args):
    """解析十六进制(\"0xFF\" 或 \"FF\"): 字符串转整数"""
    if len(args) != 1:
        raise SanyanSyntaxError('解析十六进制 需要一个字符串')
    s = evaluator.eval(args[0])
    if isinstance(s, TritValue) and s.is_string():
        s = s.to_payload()
    s = str(s).replace('0x', '').replace('0X', '')
    return TritValue(int(s, 16))


def _parse_bin(evaluator, args):
    """解析二进制(\"0b1010\" 或 \"1010\"): 字符串转整数"""
    if len(args) != 1:
        raise SanyanSyntaxError('解析二进制 需要一个字符串')
    s = evaluator.eval(args[0])
    if isinstance(s, TritValue) and s.is_string():
        s = s.to_payload()
    s = str(s).replace('0b', '').replace('0B', '')
    return TritValue(int(s, 2))


register('parse_hex', _parse_hex)
register('parse_bin', _parse_bin)


# ── 枚举与结构体 ──


def _enum_op(evaluator, args):
    """枚举(红=1, 绿=2, 蓝=3): 键值对字典，键自动转字符串"""
    result = {}
    for a in args:
        val = evaluator.eval(a)
        if isinstance(val, dict):
            result.update(val)
        elif isinstance(val, str) and '=' in val:
            k, v = val.split('=', 1)
            k = k.strip()
            v = v.strip()
            result[k] = int(v) if v.lstrip('-').isdigit() else v
    return result


def _struct_op(evaluator, args):
    """结构体(x=1, y=2, name=\"老王\"): 命名字段字典"""
    return _enum_op(evaluator, args)  # 同枚举，共用实现


register('enum', _enum_op)
register('struct', _struct_op)


def _belief_op(evaluator, args):
    """信念(命题, 信度, 来源, 时间) — 创建一个结构化信念。
    返回字典: {命题: str, 值: TritValue, 信度: float, 来源: str, 时间: float}
    是 Agent 记忆的基本单元。"""
    if len(args) < 1:
        raise SanyanSyntaxError('信念 需要命题 [, 信度, 来源]')
    statement = evaluator.eval(args[0])
    if isinstance(statement, TritValue) and statement.is_string():
        statement = statement.to_payload()
    statement = str(statement)

    val = TritValue(1)  # 默认肯定命题
    confidence = 1.0
    source = ''
    ts = time.time()

    if len(args) >= 2:
        v = evaluator.eval(args[1])
        if isinstance(v, TritValue):
            confidence = v.confidence
            val = v
        else:
            confidence = float(v)
    if len(args) >= 3:
        s = evaluator.eval(args[2])
        source = s.to_payload() if (isinstance(s, TritValue) and s.is_string()) else str(s)
    if len(args) >= 4:
        t = evaluator.eval(args[3])
        ts = t.to_float() if isinstance(t, TritValue) else float(t)

    return {'命题': statement, '值': val, '信度': confidence, '来源': source, '时间': ts}


def _belief_set_op(evaluator, args):
    """信念集(b1, b2, ...) — 创建信念列表。Agent 记忆容器。"""
    beliefs = []
    for a in args:
        val = evaluator.eval(a)
        beliefs.append(val)
    return beliefs


register('belief', _belief_op)
register('belief_set', _belief_set_op)

# 中文别名
from ops.registry import register_alias as _ra  # noqa: E402

_ra('三态移位', 'trit_shift')
_ra('三态翻转', 'trit_flip')
_ra('三态压缩', 'trit_compress')
_ra('三态解压', 'trit_decompress')
_ra('解析十六进制', 'parse_hex')
_ra('解析二进制', 'parse_bin')
_ra('枚举', 'enum')
_ra('结构体', 'struct')
_ra('信念', 'belief')
_ra('信念集', 'belief_set')
