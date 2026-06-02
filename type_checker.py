"""静态类型检查器：轻量级操作签名验证。

在求值前对已知操作做参数类型断言，不改语言语义。
仅对内置操作检查，用户自定义函数跳过。

类型: int, float, str, list, dict, trit, num(int|float), any
格式: (预期参数类型元组, 返回类型)
"""

from __future__ import annotations
from typing import Any

# ── 类型推断辅助 ──
def _type_of(v: Any) -> str:
    """推断 Python 值的类型名。"""
    if isinstance(v, bool): return 'int'  # bool 归入 int
    if isinstance(v, int): return 'int'
    if isinstance(v, float): return 'float'
    if isinstance(v, str): return 'str'
    if isinstance(v, (list, tuple)): return 'list'
    if isinstance(v, dict): return 'dict'
    if hasattr(v, 'to_int'): return 'trit'  # TritValue
    return 'any'

def _matches(actual: str, expected: str) -> bool:
    """检查实际类型是否匹配预期类型。num 可匹配 int 或 float。"""
    if expected == 'any': return True
    if expected == 'num': return actual in ('int', 'float', 'trit')
    if expected == actual: return True
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
    'gt': (['num', 'num'], 'trit'),
    'lt': (['num', 'num'], 'trit'),
    'gte': (['num', 'num'], 'trit'),
    'lte': (['num', 'num'], 'trit'),
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
    'sleep': (['num'], 'none'),
    'delay': (['num'], 'none'),
    # 随机
    'random': (['int', 'int'], 'int'),
    '随机数': (['int', 'int'], 'int'),
}


def check_types(op: str, args: list, evaluated: list) -> str | None:
    """检查操作的类型签名。返回 None 表示通过，返回错误消息表示类型不匹配。

    仅检查已知操作，用户自定义函数返回 None（跳过检查）。
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
            return (f"操作 '{op}' 的第 {i+1} 个参数类型错误："
                    f"预期 {expected}，实际 {actual}")

    return None
