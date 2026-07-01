"""静态类型检查器：轻量级操作签名验证。

在求值前对已知操作做参数类型断言，不改语言语义。
仅对内置操作检查，用户自定义函数跳过。

类型: int, float, str, list, dict, trit, num(int|float), any
泛型: 列表<T>, 字典<K, V>
效应类型: 确定[X]（信度≥0.99）、不确定[X]（任意信度）
格式: (预期参数类型元组, 返回类型)
"""

from __future__ import annotations
from typing import Any


# ── 类型推断辅助 ──
def _type_of(v: Any) -> str:
    """推断 Python 值的类型名。"""
    if isinstance(v, bool):
        return 'int'  # bool 归入 int
    if isinstance(v, int):
        return 'int'
    if isinstance(v, float):
        return 'float'
    if isinstance(v, str):
        return 'str'
    if isinstance(v, (list, tuple)):
        return 'list'
    if isinstance(v, dict):
        return 'dict'
    if hasattr(v, 'to_int'):
        return 'trit'  # TritValue
    return 'any'


def _matches(actual: str, expected: str) -> bool:
    """检查实际类型是否匹配预期类型。num 可匹配 int 或 float。
    效应类型：确定[X] 严格匹配，不确定[X] 兼容确定[X]。
    泛型：列表<T> 匹配 列表<任意>，字典<K,V> 匹配 字典<任意,任意>。
    """
    if expected == 'any':
        return True
    if expected == 'num':
        return actual in ('int', 'float', 'trit')

    # 效应类型子类型关系
    # 确定[X] 只匹配 确定[X]（严格）
    if expected.startswith('确定[') and expected.endswith(']'):
        return actual == expected
    # 不确定[X] 兼容 确定[X] 和 不确定[X]（确定可以流向不确定）
    if expected.startswith('不确定[') and expected.endswith(']'):
        inner = expected[len('不确定[') : -1]
        return actual in (expected, f'确定[{inner}]')

    # 泛型容器匹配
    if expected.startswith('列表<') and expected.endswith('>'):
        if actual == 'list':
            return True  # 普通 list 匹配任何泛型 list
        if actual.startswith('列表<') and actual.endswith('>'):
            inner_expected = expected[3:-1]
            inner_actual = actual[3:-1]
            return _matches(inner_actual, inner_expected)
        return False

    if expected.startswith('字典<') and expected.endswith('>'):
        if actual == 'dict':
            return True  # 普通 dict 匹配任何泛型 dict
        if actual.startswith('字典<') and actual.endswith('>'):
            parts_expected = expected[3:-1].split(', ', 1)
            parts_actual = actual[3:-1].split(', ', 1)
            if len(parts_expected) == 2 and len(parts_actual) == 2:
                return _matches(parts_actual[0], parts_expected[0]) and _matches(parts_actual[1], parts_expected[1])
        return False

    if expected == actual:
        return True
    return False


# ── 操作类型签名表 ──
# 键 = 内部操作名（英文）。值 = (参数类型列表, 返回类型)
_TYPE_SIGS: dict[str, tuple[list[str], str]] = {
    # 算术
    'add': (['num', 'num'], 'num'),
    '加': (['num', 'num'], 'num'),
    'sub': (['num', 'num'], 'num'),
    '减': (['num', 'num'], 'num'),
    'mul': (['num', 'num'], 'num'),
    '乘': (['num', 'num'], 'num'),
    'div': (['num', 'num'], 'num'),
    '除': (['num', 'num'], 'num'),
    'mod': (['num', 'num'], 'num'),
    '余': (['num', 'num'], 'num'),
    # 比较
    'eq': (['any', 'any'], 'trit'),
    '等于': (['any', 'any'], 'trit'),
    'ne': (['any', 'any'], 'trit'),
    '不等于': (['any', 'any'], 'trit'),
    'gt': (['num', 'num'], 'trit'),
    '大于': (['num', 'num'], 'trit'),
    'lt': (['num', 'num'], 'trit'),
    '小于': (['num', 'num'], 'trit'),
    'gte': (['num', 'num'], 'trit'),
    '大于等于': (['num', 'num'], 'trit'),
    'lte': (['num', 'num'], 'trit'),
    '小于等于': (['num', 'num'], 'trit'),
    # 逻辑
    'and': (['trit', 'trit'], 'trit'),
    '与': (['trit', 'trit'], 'trit'),
    'or': (['trit', 'trit'], 'trit'),
    '或': (['trit', 'trit'], 'trit'),
    'not': (['trit'], 'trit'),
    '非': (['trit'], 'trit'),
    # 字符串
    'concat': (['str', 'str'], 'str'),
    '连接': (['str', 'str'], 'str'),
    'strlen': (['str'], 'int'),
    '取长': (['str'], 'int'),
    'length': (['str'], 'int'),
    'substr': (['str', 'int', 'int'], 'str'),
    '子串': (['str', 'int', 'int'], 'str'),
    'substring': (['str', 'int', 'int'], 'str'),
    'str_equals': (['str', 'str'], 'trit'),
    '字符串相等': (['str', 'str'], 'trit'),
    'str_contains': (['str', 'str'], 'trit'),
    '字符串包含': (['str', 'str'], 'trit'),
    # 列表
    'list_len': (['list'], 'int'),
    '表长': (['list'], 'int'),
    'get': (['list', 'int'], 'any'),
    '取': (['list', 'int'], 'any'),
    'slice': (['list', 'int', 'int'], 'list'),
    '切片': (['list', 'int', 'int'], 'list'),
    'list_concat': (['list', 'list'], 'list'),
    '列表合': (['list', 'list'], 'list'),
    'set_element': (['list', 'int', 'any'], 'list'),
    '置元素': (['list', 'int', 'any'], 'list'),
    # 字典
    'get_key': (['dict', 'any'], 'any'),
    '取键': (['dict', 'any'], 'any'),
    'set_key': (['dict', 'any', 'any'], 'dict'),
    '置键': (['dict', 'any', 'any'], 'dict'),
    'dict_contains': (['dict', 'any'], 'trit'),
    '含键': (['dict', 'any'], 'trit'),
    'dict_keys': (['dict'], 'list'),
    '字典键列表': (['dict'], 'list'),
    'delete_key': (['dict', 'any'], 'dict'),
    '删除键': (['dict', 'any'], 'dict'),
    # 类型检查
    'is_dict': (['any'], 'trit'),
    '是字典': (['any'], 'trit'),
    'is_list': (['any'], 'trit'),
    '是列表': (['any'], 'trit'),
    'is_string': (['any'], 'trit'),
    '是字符串': (['any'], 'trit'),
    'is_number': (['any'], 'trit'),
    '是数字': (['any'], 'trit'),
    # IO
    'read_file': (['str'], 'str'),
    '读文件': (['str'], 'str'),
    'write_file': (['str', 'str'], 'int'),
    '写文件': (['str', 'str'], 'int'),
    'output': (['any'], 'none'),
    '输出': (['any'], 'none'),
    # 转换
    'to_string': (['any'], 'str'),
    '转字符串': (['any'], 'str'),
    'to_number': (['str'], 'num'),
    '转数字': (['str'], 'num'),
    # 时间
    'timestamp': ([], 'int'),
    '时间戳': ([], 'int'),
    'sleep': (['num'], 'none'),
    '等待': (['num'], 'none'),
    'delay': (['num'], 'none'),
    # 随机
    'random': (['int', 'int'], 'int'),
    '随机数': (['int', 'int'], 'int'),
}


def check_types(op: str, args: list, evaluated: list) -> str | None:
    """检查操作的类型签名。返回 None 表示通过，返回错误消息表示类型不匹配。

    仅检查已知操作，用户自定义函数返回 None（跳过检查）。
    支持协议类型检查。
    """
    sig = _TYPE_SIGS.get(op)
    if sig is None:
        return None  # 未知操作，跳过

    param_types, ret_type = sig

    if len(evaluated) < len(param_types):
        # 参数不足，跳过（运行时求值器会报错）
        return None

    for i, (expected, actual_val) in enumerate(zip(param_types, evaluated)):
        actual = _type_of(actual_val)
        if not _matches(actual, expected):
            # 检查是否为协议类型
            try:
                from core.protocols import check_type_protocol

                protocol_err = check_type_protocol(actual_val, expected)
                if protocol_err:
                    return f"操作 '{op}' 的第 {i + 1} 个参数不满足协议: {protocol_err}"
            except ImportError:
                pass
            return f"操作 '{op}' 的第 {i + 1} 个参数类型错误：预期 {expected}，实际 {actual}"

    return None
