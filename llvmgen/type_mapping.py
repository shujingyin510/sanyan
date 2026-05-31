"""三言 LLVM 代码生成 — 类型映射与常量定义。

本模块定义 LLVM IR 基础类型、标记指针（tagged pointer）值追踪类、
内置常量表、算术/比较/逻辑操作映射以及运行时函数声明规范。
"""

from __future__ import annotations

from llvmlite import ir

# ── LLVM 基础类型 ──
_INT = ir.IntType(64)  # 63 位有符号整数（LSB=1 为 tag）
_PTR = ir.PointerType(ir.IntType(8))  # i8* — 变量统一存储类型
_I32 = ir.IntType(32)  # 兼容 32 位参数（列表长度、字符串长度等）
_ZERO = ir.Constant(_INT, 0)
_ONE = ir.Constant(_INT, 1)
_ZERO32 = ir.Constant(_I32, 0)
_ONE32 = ir.Constant(_I32, 1)
_NULL = ir.Constant(_PTR, None)


# ── 值追踪：raw i64 vs boxed i8* ──


class RawValue:
    """未装箱的 i64 整数值（tagged int）。"""

    __slots__ = ('ll_val',)

    def __init__(self, ll_val: ir.Value):
        self.ll_val = ll_val


class BoxedValue:
    """已装箱的 i8* 指针值（堆对象）。"""

    __slots__ = ('ll_val',)

    def __init__(self, ll_val: ir.Value):
        self.ll_val = ll_val


# ── 内置常量 ──
_BUILTIN_CONSTS = {
    '真': 1,
    'true': 1,
    'True': 1,
    '假': 0,
    'false': 0,
    'False': 0,
    '可能': 0,
    'maybe': 0,
    'Maybe': 0,
    '空': 0,
    'nil': 0,
    'null': 0,
    # IoT 设备状态
    '开': 1,
    '亮': 1,
    '关': -1,
    '灭': -1,
    '守': 0,
}

# ── 内置操作名 → LLVM 指令映射 ──
_ARITH_OPS = {
    '加': 'add',
    'add': 'add',
    '减': 'sub',
    'sub': 'sub',
    '乘': 'mul',
    'mul': 'mul',
    '除': 'sdiv',
    'div': 'sdiv',
    '余': 'srem',
    'mod': 'srem',
    '取余': 'srem',
}

_FLOAT_ARITH = {
    '加': 'fadd',
    'add': 'fadd',
    '减': 'fsub',
    'sub': 'fsub',
    '乘': 'fmul',
    'mul': 'fmul',
    '除': 'fdiv',
    'div': 'fdiv',
}

_COMPARE_OPS = {
    '等于': '==',
    'eq': '==',
    '大于': '>',
    'gt': '>',
    '小于': '<',
    'lt': '<',
    '大于等于': '>=',
    'gte': '>=',
    '小于等于': '<=',
    'lte': '<=',
    '不等于': '!=',
    'ne': '!=',
    '不大于': '<=',
    '不小于': '>=',
}

# 逻辑运算
_LOGIC_OPS = {
    '且': 'and',
    'and': 'and',
    '与': 'and',
    '或': 'or',
    'or': 'or',
}

# ── 运行时函数声明规范 ──
# (函数名, 返回类型, [参数类型]) — 使用真实 C 类型（i32 或 i8*）
_RUNTIME_FUNCS: dict[str, tuple] = {
    # 随机数 → i32（C 函数返回 int32_t）
    '随机数': ('rt_random_int', _I32, [_I32, _I32]),
    'randint': ('rt_random_int', _I32, [_I32, _I32]),
    'random': ('rt_random_int', _I32, [_I32, _I32]),
    '随机态': ('rt_random_trit', _I32, []),
    'random_state': ('rt_random_trit', _I32, []),
    '是数字': ('rt_is_number', _I32, [_I32]),
    'is_number': ('rt_is_number', _I32, [_I32]),
    '是字符串': ('rt_is_string', _I32, [_PTR]),
    'is_string': ('rt_is_string', _I32, [_PTR]),
    '是列表': ('rt_is_list', _I32, [_PTR]),
    'is_list': ('rt_is_list', _I32, [_PTR]),
    '应用': ('rt_apply_stub', _PTR, [_PTR, _PTR]),
    '等待': ('rt_sleep', ir.VoidType(), [_I32]),
    'wait': ('rt_sleep', ir.VoidType(), [_I32]),
    '读文件': ('rt_read_file', _PTR, [_PTR]),
    '写文件': ('rt_write_file', ir.VoidType(), [_PTR, _PTR]),
    # 字符串操作
    '连接': ('rt_str_concat', _PTR, [_PTR, _PTR]),
    'concat': ('rt_str_concat', _PTR, [_PTR, _PTR]),
    '整数转字符串': ('rt_int_to_str', _PTR, [_PTR]),
    '字符串': ('rt_int_to_str', _PTR, [_PTR]),
    'to_string': ('rt_int_to_str', _PTR, [_PTR]),
    '取长': ('rt_str_len', _I32, [_PTR]),
    'length': ('rt_str_len', _I32, [_PTR]),
    '字符串相等': ('rt_str_equals', _I32, [_PTR, _PTR]),
    'str_equals': ('rt_str_equals', _I32, [_PTR, _PTR]),
    '分割': ('rt_str_split', _PTR, [_PTR, _PTR]),
    'split': ('rt_str_split', _PTR, [_PTR, _PTR]),
    '子串': ('rt_str_substr', _PTR, [_PTR, _I32, _I32]),
    'substring': ('rt_str_substr', _PTR, [_PTR, _I32, _I32]),
    '包含': ('rt_str_contains', _I32, [_PTR, _PTR]),
    'contains': ('rt_str_contains', _I32, [_PTR, _PTR]),
    '查找': ('rt_str_find', _I32, [_PTR, _PTR]),
    'find': ('rt_str_find', _I32, [_PTR, _PTR]),
    '字列': ('rt_str_to_list', _PTR, [_PTR]),
    'str_to_list': ('rt_str_to_list', _PTR, [_PTR]),
    # 列表操作
    '列表': ('rt_list_new_cap', _PTR, [_I32]),
    'list': ('rt_list_new_cap', _PTR, [_I32]),
    '字典': ('rt_dict_new', _PTR, []),
    'dict': ('rt_dict_new', _PTR, []),
    'dict_contains': ('rt_dict_contains', _I32, [_PTR, _PTR]),
    '含键': ('rt_dict_contains', _I32, [_PTR, _PTR]),
    'get_key': ('rt_dict_get', _PTR, [_PTR, _PTR]),
    'set_key': ('rt_dict_set', ir.VoidType(), [_PTR, _PTR, _PTR]),
    '取键': ('rt_dict_get', _PTR, [_PTR, _PTR]),
    '置键': ('rt_dict_set', ir.VoidType(), [_PTR, _PTR, _PTR]),
    '表长': ('rt_list_len', _I32, [_PTR]),
    'list_len': ('rt_list_len', _I32, [_PTR]),
    '列表合': ('rt_list_concat', _PTR, [_PTR, _PTR]),
    'list_concat': ('rt_list_concat', _PTR, [_PTR, _PTR]),
    '取': ('rt_list_get', _PTR, [_PTR, _I32]),
    'get': ('rt_list_get', _PTR, [_PTR, _I32]),
    'slice': ('rt_list_slice', _PTR, [_PTR, _I32, _I32]),
    '切片': ('rt_list_slice', _PTR, [_PTR, _I32, _I32]),
    # 输入
    '输入': ('rt_read_input', _PTR, []),
    'input': ('rt_read_input', _PTR, []),
    # 导入
    '导入': ('rt_import', _PTR, [_PTR]),
    'import': ('rt_import', _PTR, [_PTR]),
    '模块调用': ('rt_module_call', _PTR, [_PTR, _PTR, _PTR]),
    'module_call': ('rt_module_call', _PTR, [_PTR, _PTR, _PTR]),
    # IoT 操作（桩）
    '置': ('rt_iot_set', ir.VoidType(), [_PTR, _PTR]),
    '读': ('rt_iot_read', _PTR, [_PTR]),
    '查': ('rt_iot_query', ir.VoidType(), [_PTR]),
    '对': ('rt_iot_with', ir.VoidType(), [_PTR, _PTR]),
    'write': ('rt_iot_set', ir.VoidType(), [_PTR, _PTR]),
    'read': ('rt_iot_read', _PTR, [_PTR]),
    'query': ('rt_iot_query', ir.VoidType(), [_PTR]),
    'with': ('rt_iot_with', ir.VoidType(), [_PTR, _PTR]),
    # 异常
    'rt_throw': ('rt_throw', ir.VoidType(), [_PTR]),
    'throw': ('rt_throw', ir.VoidType(), [_PTR]),
    # 浮点
    'rt_float_new': ('rt_float_new', _PTR, [ir.DoubleType()]),
    'rt_unbox_float': ('rt_unbox_float', ir.DoubleType(), [_PTR]),
    'rt_int_to_float': ('rt_int_to_float', _PTR, [_PTR]),
    'rt_print_float': ('rt_print_float', ir.VoidType(), [_PTR]),
    # JSON（桩）
    '解析JSON': ('rt_json_parse', _PTR, [_PTR]),
    'from_json': ('rt_json_parse', _PTR, [_PTR]),
    '转JSON': ('rt_json_stringify', _PTR, [_PTR]),
    'to_json': ('rt_json_stringify', _PTR, [_PTR]),
    # HTTP（桩）
    'http读': ('rt_http_get', _PTR, [_PTR]),
    'http写': ('rt_http_post', _PTR, [_PTR, _PTR]),
    # 正则（桩）
    '正则匹配': ('rt_regex_match', _PTR, [_PTR, _PTR]),
    '正则搜索': ('rt_regex_search', _PTR, [_PTR, _PTR]),
    '正则查找': ('rt_regex_findall', _PTR, [_PTR, _PTR]),
    '正则替换': ('rt_regex_replace', _PTR, [_PTR, _PTR, _PTR]),
    '正则分割': ('rt_regex_split', _PTR, [_PTR, _PTR]),
    # 文件读写（别名）
    'read_file': ('rt_read_file', _PTR, [_PTR]),
    'write_file': ('rt_write_file', ir.VoidType(), [_PTR, _PTR]),
    # 数学
    'pow': ('rt_math_pow', _I32, [_I32, _I32]),
    'sqrt': ('rt_math_sqrt', _I32, [_I32]),
    '平方根': ('rt_math_sqrt', _I32, [_I32]),
    'abs': ('rt_math_abs', _I32, [_I32]),
    '绝对值': ('rt_math_abs', _I32, [_I32]),
    'floor': ('rt_math_floor', _I32, [_I32]),
    '向下取整': ('rt_math_floor', _I32, [_I32]),
    'ceil': ('rt_math_ceil', _I32, [_I32]),
    '向上取整': ('rt_math_ceil', _I32, [_I32]),
    'round': ('rt_math_round', _I32, [_I32]),
    '四舍五入': ('rt_math_round', _I32, [_I32]),
    'ngt': ('rt_math_ngt', _I32, [_I32, _I32]),
    'nlt': ('rt_math_nlt', _I32, [_I32, _I32]),
    'sleep': ('rt_sleep', ir.VoidType(), [_I32]),
    'reduce': ('rt_list_reduce', _PTR, [_PTR, _PTR]),
    # 时间
    'time': ('rt_time_now', _I32, []),
    '当前时间': ('rt_time_now', _I32, []),
    # 字符串扩展（桩）
    'reverse': ('rt_str_reverse', _PTR, [_PTR]),
    '反转': ('rt_str_reverse', _PTR, [_PTR]),
    'startswith': ('rt_str_startswith', _I32, [_PTR, _PTR]),
    '前缀': ('rt_str_startswith', _I32, [_PTR, _PTR]),
    'endswith': ('rt_str_endswith', _I32, [_PTR, _PTR]),
    '后缀': ('rt_str_endswith', _I32, [_PTR, _PTR]),
    'replace': ('rt_str_replace', _PTR, [_PTR, _PTR, _PTR]),
    '替换': ('rt_str_replace', _PTR, [_PTR, _PTR, _PTR]),
    'trim': ('rt_str_trim', _PTR, [_PTR]),
    '去空白': ('rt_str_trim', _PTR, [_PTR]),
    'upper': ('rt_str_upper', _PTR, [_PTR]),
    '大写': ('rt_str_upper', _PTR, [_PTR]),
    'lower': ('rt_str_lower', _PTR, [_PTR]),
    '小写': ('rt_str_lower', _PTR, [_PTR]),
    'join': ('rt_str_join', _PTR, [_PTR, _PTR]),
    '合并': ('rt_str_join', _PTR, [_PTR, _PTR]),
    'sort': ('rt_list_sort', _PTR, [_PTR]),
    '排序': ('rt_list_sort', _PTR, [_PTR]),
    'sum': ('rt_list_sum', _I32, [_PTR]),
    '求和': ('rt_list_sum', _I32, [_PTR]),
    'count': ('rt_list_count', _I32, [_PTR, _PTR]),
    '计数': ('rt_list_count', _I32, [_PTR, _PTR]),
    'unique': ('rt_list_unique', _PTR, [_PTR]),
    '去重': ('rt_list_unique', _PTR, [_PTR]),
    # 容器扩展
    'set_element': ('rt_list_set', ir.VoidType(), [_PTR, _I32, _PTR]),
    '置元素': ('rt_list_set', ir.VoidType(), [_PTR, _I32, _PTR]),
    # 数学补充
    '幂': ('rt_math_pow', _I32, [_I32, _I32]),
}  # yapf: disable


# ── 字符串 / 数字辅助函数 ──


def _to_float_str(s: str) -> float | None:
    """尝试将字符串解析为浮点数，返回 None 表示失败。"""
    try:
        f = float(s)
        if '.' in s or 'e' in s.lower():
            return f
    except ValueError:
        pass
    return None


def _to_int(s: str) -> int | None:
    """尝试解析数字字符串，失败返回 None。"""
    s = s.strip()
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return int(float(s))
    except ValueError:
        return None


def _is_string_literal(s: str) -> bool:
    """判断字符串是否是加引号的字面量。"""
    if len(s) >= 2:
        if (s[0] == '"' and s[-1] == '"') or (s[0] == "'" and s[-1] == "'"):
            return True
        if s[0] in '\u201c\u2018' and s[-1] in '\u201d\u2019':
            return True
    return False


def _unquote(s: str) -> str:
    """去掉字符串两端的引号并处理转义序列。"""
    if not _is_string_literal(s):
        return s
    s = s[1:-1]
    # 处理转义序列（与 eval_helpers.parse_string_literal 一致）
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
