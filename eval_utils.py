"""求值工具模块：纯函数，无求值器依赖。

提供字符串/数值解析、标识符检查、三态值解包、置信度传播。
供 evaluator.py 和 ops/*.py 共用。
"""

from __future__ import annotations
from typing import Any, Optional
from ternary_core import TritValue


def parse_string_literal(s: str) -> str:
    """解析字符串字面量的转义序列"""
    result = []
    i = 0
    while i < len(s):
        if s[i] == '\\' and i + 1 < len(s):
            esc = s[i + 1]
            if esc == 'n':
                result.append('\n')
                i += 2
            elif esc == 't':
                result.append('\t')
                i += 2
            elif esc == 'r':
                result.append('\r')
                i += 2
            elif esc == '\\':
                result.append('\\')
                i += 2
            elif esc == '"':
                result.append('"')
                i += 2
            elif esc == "'":
                result.append("'")
                i += 2
            elif esc == 'u' and i + 5 < len(s):
                try:
                    result.append(chr(int(s[i + 2 : i + 6], 16)))
                    i += 6
                except ValueError:
                    result.append(s[i])
                    i += 1
            else:
                result.append(s[i])
                i += 1
        else:
            result.append(s[i])
            i += 1
    return ''.join(result)


# 数值解析缓存
_NUMERIC_LITERAL_CACHE: dict[str, Optional[TritValue]] = {}


def parse_numeric_literal(node: str) -> Optional[TritValue]:
    """解析数值字面量字符串（支持十进制和十六进制）"""
    cache = _NUMERIC_LITERAL_CACHE
    if node in cache:
        return cache[node]
    result = _parse_numeric_literal_impl(node)
    # 缓存常用长度的字符串
    if len(node) <= 10:
        cache[node] = result
    return result


def _parse_numeric_literal_impl(node: str) -> Optional[TritValue]:
    """解析数值字面量字符串（实际实现）"""
    try:
        if node.startswith('0x') or node.startswith('0X'):
            return TritValue(int(node, 16))
        stripped = node.replace('.', '', 1).replace('-', '', 1)
        if stripped.isdigit():
            return TritValue(float(node)) if '.' in node else TritValue(int(node))
    except ValueError:
        pass
    return None


def is_valid_identifier(s: str) -> bool:
    """检查是否为有效标识符"""
    if not s:
        return False
    for c in s:
        if c.isalnum() or c == '_' or c == '.' or '\u4e00' <= c <= '\u9fff' or '\u3400' <= c <= '\u4dbf':
            continue
        return False
    return True


def unwrap_trit(value: Any) -> Any:
    """从 TritValue 中提取原始值（字符串→str，数值→int，列表/字典→原值）。
    非 TritValue 原样返回。用于 ops 中统一处理三态值。
    """
    if isinstance(value, TritValue):
        if value.is_string():
            return value.to_payload()
        if value.is_list():
            return value.to_payload()
        if value.is_dict():
            return value.to_payload()
        return value.to_int()
    return value


def propagated_confidence(*values: Any) -> float:
    """计算贝叶斯传播置信度：所有 TritValue 输入置信度的乘积。

    传播规则: C_result = C_a × C_b × C_c × ...
    独立贝叶斯更新: 每个不确定源独立贡献，置信度累积衰减。
    纯 Python 值（非 TritValue）视为置信度 1.0。
    用于所有算术/比较/逻辑运算的自动置信度级联。
    """
    c = 1.0
    for v in values:
        if isinstance(v, TritValue):
            c *= v.confidence
    return max(0.0, min(1.0, c))


def ensure_trit(v: Any) -> Any:
    """将 raw Python 值包装为 TritValue，若已是 TritValue 则原样返回。

    用于 ops 边界统一化——eval() 可能返回 TritValue 或 raw int/str/float。
    调用方用此函数归一化，避免类型检查散落各处。
    TODO: 后续重构 eval() 统一返回 TritValue 后可移除此函数。
    """
    if isinstance(v, TritValue):
        return v
    if isinstance(v, int):
        return TritValue(v)
    if isinstance(v, float):
        return TritValue(v)
    if isinstance(v, str):
        return TritValue(v)
    return v  # list/dict/None 保持原样


def to_float(v: Any) -> float:
    """将 TritValue 或 raw 值转为 float。用于三态值的浮点保护。"""
    try:
        if hasattr(v, 'to_int'):
            return float(v.to_int())
        return float(v)
    except Exception:
        return 0.0
