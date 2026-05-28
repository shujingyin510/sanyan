"""三言 AST → LLVM IR 代码生成器"""

from __future__ import annotations
from llvmlite import ir
from ternary_core import TritValue

# ── 类型定义 ──
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
    __slots__ = ('ll_val',)

    def __init__(self, ll_val: ir.Value):
        self.ll_val = ll_val


class BoxedValue:
    __slots__ = ('ll_val',)

    def __init__(self, ll_val: ir.Value):
        self.ll_val = ll_val


# 内置常量
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
    # 导入（桩）
    '导入': ('rt_import', _PTR, []),
    'import': ('rt_import', _PTR, []),
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
    'pow': ('rt_math_pow', _I32, [_I32, _I32]),
    '幂': ('rt_math_pow', _I32, [_I32, _I32]),
}  # yapf: disable


def _to_float_str(s: str) -> float | None:
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
    """去掉字符串两端的引号。"""
    if _is_string_literal(s):
        return s[1:-1]
    return s


class CodegenContext:
    """编译上下文：模块、IR 构建器、符号表。"""

    def __init__(self, module_name: str = 'main', module_prefix: str = ''):
        self.module = ir.Module(name=module_name)
        self.module_prefix = module_prefix
        try:
            from llvmlite import binding as _llvm_bind

            self.module.triple = _llvm_bind.get_default_triple()
        except Exception:
            self.module.triple = 'x86_64-pc-linux-gnu'
        self._printf = None
        self._builder: ir.IRBuilder | None = None
        self._entry_block: ir.Block | None = None
        self._scope: dict[str, ir.Value] = {}  # 当前函数作用域
        self._env: dict[str, RawValue | BoxedValue] = {}  # SSA 值追踪（raw i64 优先）
        self._funcs: dict[str, ir.Function] = {}  # 已定义的函数
        self._current_func: ir.Function | None = None
        self._globals: dict[str, ir.GlobalVariable] = {}  # 模块级全局变量
        self._global_inits: list[tuple[str, ir.Value | int | str]] = []  # 全局变量初始化
        self._loop_stack: list[tuple[ir.Block, ir.Block]] = []  # (header, exit) 循环上下文
        self._rt_funcs: dict[str, ir.Function] = {}  # 已声明的运行时函数
        self._try_depth: int = 0  # 当前嵌套 try 深度
        # 声明异常全局（所有函数都可访问）
        g_error = ir.GlobalVariable(self.module, _PTR, name='g_error')
        g_error.initializer = _NULL
        g_error.linkage = 'common'
        self._rt_funcs['g_error'] = g_error
        # 声明外部运行时函数
        self._declare_runtime()

    def _declare_runtime(self):
        """声明外部运行时函数（printf 等）。"""
        if self._printf is None:
            fnty = ir.FunctionType(_I32, [_PTR], var_arg=True)
            self._printf = ir.Function(self.module, fnty, name='printf')

    def _get_runtime_func(self, op: str) -> ir.Function | None:
        """获取或声明运行时函数。"""
        spec = _RUNTIME_FUNCS.get(op)
        if spec is None:
            return None
        name, ret_type, param_types = spec
        if name in self._rt_funcs:
            return self._rt_funcs[name]
        fn_type = ir.FunctionType(ret_type, param_types)
        func = ir.Function(self.module, fn_type, name=name)
        self._rt_funcs[name] = func
        return func

    @property
    def builder(self) -> ir.IRBuilder:
        if self._builder is None:
            raise RuntimeError('builder 未初始化，先调用 begin_function()')
        return self._builder

    @property
    def _func(self) -> ir.Function:
        """当前正在编译的函数（断言非 None）。"""
        assert self._current_func is not None, '当前无活跃函数'
        return self._current_func

    def _add_block(self, name: str = '') -> ir.Block:
        """在当前函数追加基本块。"""
        return self._func.append_basic_block(name=name)

    def begin_function(self, name: str, param_names: list[str]) -> ir.Function:
        if self.module_prefix and name != 'main':
            name = f'san_{self.module_prefix}__{name}'
        if name in self._funcs:
            func = self._funcs[name]
            self._current_func = func
            self._scope = {}
            self._env = {}
            self._allocas = {}
            entry = func.blocks[0]
            entry.instructions.clear()
            self._builder = ir.IRBuilder(entry)
            self._entry_block = entry
            for i, pname in enumerate(param_names):
                alloca = self._builder.alloca(_PTR, name=pname)
                self._builder.store(func.args[i], alloca)
                self._scope[pname] = alloca
            return func

        fnty = ir.FunctionType(_PTR, [_PTR] * len(param_names))
        func = ir.Function(self.module, fnty, name=name)
        func.attributes.add('alwaysinline')
        for i, pname in enumerate(param_names):
            func.args[i].name = pname
        self._funcs[name] = func
        self._current_func = func
        self._scope = {}
        self._env = {}
        self._allocas = {}
        entry = func.append_basic_block(name='entry')
        self._builder = ir.IRBuilder(entry)
        self._entry_block = entry
        for i, pname in enumerate(param_names):
            alloca = self._builder.alloca(_PTR, name=pname)
            self._builder.store(func.args[i], alloca)
            self._scope[pname] = alloca
        return func

    def end_function(self):
        """结束当前函数（如果未显式返回则补 ret null）。"""
        if not self.builder.block.is_terminated:
            self.builder.ret(_NULL)

    def _box_int(self, int_val: ir.Value) -> ir.Value:
        shifted = self.builder.shl(int_val, _ONE, name='box_shl')
        tagged = self.builder.or_(shifted, _ONE, name='box_tag')
        return self.builder.inttoptr(tagged, _PTR, name='box')

    def _unbox_int(self, ptr_val: ir.Value) -> ir.Value:
        raw = self.builder.ptrtoint(ptr_val, _INT, name='unbox_raw')
        return self.builder.ashr(raw, _ONE, name='unbox')

    def _to_raw(self, val) -> 'RawValue':
        if isinstance(val, RawValue):
            return val
        if isinstance(val, BoxedValue):
            return RawValue(self._unbox_int(val.ll_val))
        return RawValue(self._unbox_int(val))

    def _to_boxed(self, val) -> 'BoxedValue':
        if isinstance(val, BoxedValue):
            return val
        if isinstance(val, RawValue):
            return BoxedValue(self._box_int(val.ll_val))
        return BoxedValue(val)

    def _to_bool_i1(self, val) -> ir.Value:
        if isinstance(val, RawValue):
            if isinstance(val.ll_val.type, ir.IntType) and val.ll_val.type.width == 1:
                return val.ll_val
            return self.builder.icmp_signed('!=', val.ll_val, _ZERO, name='to_bool')
        raw = self._unbox_int(val.ll_val if isinstance(val, BoxedValue) else val)
        return self.builder.icmp_signed('!=', raw, _ZERO, name='to_bool')

    def _is_tagged_int(self, ptr_val: ir.Value) -> ir.Value:
        """检查 tagged 指针是否为整数（bit0 == 1）。返回 i1。"""
        raw = self.builder.ptrtoint(ptr_val, _INT, name='tag_raw')
        tagged = self.builder.and_(raw, _ONE, name='tag_bit')
        return self.builder.icmp_signed('!=', tagged, _ZERO, name='is_int')

    def _to_i64(self, val: ir.Value) -> ir.Value:
        if isinstance(val.type, ir.IntType):
            return val
        return self._unbox_int(val)

    def emit_print_int(self, value: ir.Value):
        fmt = self._make_global_string('%lld\n')
        self.builder.call(self._printf, [fmt, self._to_i64(value)])

    def emit_print_str(self, value: ir.Value):
        """通过 rt_print_str 打印 rt_str_t 字符串。"""
        fn = self._get_or_declare('rt_print_str', ir.VoidType(), [_PTR])
        self.builder.call(fn, [value])

    def emit_print(self, fmt: str, value: ir.Value):
        """生成 printf 调用。"""
        fmt_ptr = self._make_global_string(fmt)
        self.builder.call(self._printf, [fmt_ptr, value])

    def _get_or_declare(self, name: str, ret_type, param_types: list) -> ir.Function:
        """获取或声明一个外部函数。"""
        if name in self._rt_funcs:
            return self._rt_funcs[name]
        fn_type = ir.FunctionType(ret_type, param_types)
        func = ir.Function(self.module, fn_type, name=name)
        self._rt_funcs[name] = func
        return func

    def _make_global_string(self, s: str) -> ir.Value:
        n = len(self.module.globals)
        data = bytearray(s + '\0', 'utf-8')
        c = ir.Constant(ir.ArrayType(ir.IntType(8), len(data)), data)
        gv = ir.GlobalVariable(self.module, c.type, name=f'.str.{n}')
        gv.linkage = 'private'
        gv.global_constant = True
        gv.initializer = c
        return self.builder.gep(gv, [_ZERO32, _ZERO32], inbounds=True)

    def _make_rt_string(self, s: str) -> ir.Value:
        """创建运行时字符串常量（rt_str_t 格式：{i32 len, [N x i8] data}）。

        生成的全局变量带 4 字节长度前缀，可直接作为 rt_str_t* 传给运行时函数。
        _cstr() 无需启发式检测。返回 i8* 以兼容统一变量类型。
        """
        n = len(self.module.globals)
        encoded = s.encode('utf-8')
        slen = len(encoded)
        data_bytes = bytearray(encoded) + b'\x00'
        # 构建 {i32, [N x i8]} 结构体常量
        st_ty = ir.LiteralStructType([_I32, _I32, ir.ArrayType(ir.IntType(8), slen + 1)])
        type_f = ir.Constant(_I32, 1)  # OBJ_STRING = 1
        len_f = ir.Constant(_I32, slen)
        data_f = ir.Constant(ir.ArrayType(ir.IntType(8), slen + 1), data_bytes)
        c = ir.Constant(st_ty, [type_f, len_f, data_f])
        gv = ir.GlobalVariable(self.module, st_ty, name=f'.rt_str.{n}')
        gv.linkage = 'private'
        gv.global_constant = True
        gv.initializer = c
        raw = self.builder.gep(gv, [_ZERO32, ir.Constant(_I32, 2), _ZERO32], inbounds=True)
        return self.builder.bitcast(raw, _PTR, name=f'.rt_str_p{n}')

    def _get_alloca(self, name: str, is_int: bool = True) -> ir.Value:
        if name not in self._allocas:
            ty = _INT if is_int else _PTR
            saved = self.builder.block
            self.builder.position_at_start(self._entry_block)
            alloca = self.builder.alloca(ty, name=name)
            self.builder.position_at_end(saved)
            self._allocas[name] = (alloca, is_int)
        return self._allocas[name][0]

    def _entry_alloca(self, name: str) -> ir.Value:
        saved_pos = self.builder.block
        self.builder.position_at_start(self._entry_block)
        alloca = self.builder.alloca(_PTR, name=name)
        self.builder.position_at_end(saved_pos)
        return alloca

    def get_var(self, name: str) -> ir.Value:
        if name in self._allocas:
            alloca, is_int = self._allocas[name]
            val = self.builder.load(alloca, name=name)
            return RawValue(val) if is_int else val
        if name in self._scope:
            return BoxedValue(self.builder.load(self._scope[name], name=name))
        if name in self._globals:
            return BoxedValue(self.builder.load(self._globals[name], name=name))
        if name in self._funcs:
            raise NameError(f'{name} 是函数，不能当作变量')
        raise NameError(f'编译错误: 未定义变量 {name}')

    def set_var(self, name: str, value):
        if isinstance(value, RawValue):
            value = self._box_int(value.ll_val)
        elif isinstance(value, BoxedValue):
            value = value.ll_val
        if isinstance(value.type, ir.PointerType):
            boxed = value
            raw = self._unbox_int(value)
        else:
            boxed = self._box_int(value)
            raw = value
        if name in self._allocas:
            alloca, is_int = self._allocas[name]
            self.builder.store(raw if is_int else boxed, alloca)
            return
        if name in self._scope:
            self.builder.store(boxed, self._scope[name])
            return
        if name in self._globals:
            self.builder.store(boxed, self._globals[name])
            return
        alloca = self._get_alloca(name, is_int=True)
        self.builder.store(raw, alloca)

    def set_var_raw(self, name: str, raw_val: ir.Value):
        alloca, is_int = self._allocas[name]
        if is_int:
            self.builder.store(raw_val, alloca)
        else:
            self.builder.store(self._box_int(raw_val), alloca)

    def create_global(self, name: str, init_value: ir.Value | None = None):
        """创建模块级全局变量（编译时可见）。"""
        if name in self._globals:
            return
        gv = ir.GlobalVariable(self.module, _PTR, name=name)
        gv.linkage = 'internal'
        gv.initializer = _NULL
        self._globals[name] = gv
        if init_value is not None:
            self._global_inits.append((name, init_value))

    def compile_fn_body(self, name: str, param_names: list[str], body: list):
        """编译函数体（处理 定义 AST）。最后表达式若非返回则隐式返回。"""
        self.begin_function(name, param_names)
        result = None
        for i, stmt in enumerate(body):
            result = compile_node(stmt, self)
            # 隐式返回：最后一条语句非返回时，将其值作为返回值
            if i == len(body) - 1 and not self.builder.block.is_terminated:
                if isinstance(stmt, list) and stmt[0] in ('返回', 'return'):
                    pass  # 已有显式返回
                elif result is not None:
                    if isinstance(result, RawValue):
                        result = self._box_int(result.ll_val)
                    elif isinstance(result, BoxedValue):
                        result = result.ll_val
                    self.builder.ret(result)
        self.end_function()

    def verify(self) -> str:
        try:
            return str(self.module)
        except Exception as e:
            raise RuntimeError(f'LLVM IR 生成失败: {e}') from e

    def verify_opt(self) -> str:
        ir_text = str(self.module)
        try:
            from llvmlite import binding
            from llvmlite.binding.newpassmanagers import PassBuilder, PipelineTuningOptions

            binding.initialize_all_targets()
            binding.initialize_native_asmprinter()
            llvm_mod = binding.parse_assembly(ir_text)
            tm = binding.Target.from_default_triple().create_target_machine()
            pto = PipelineTuningOptions()
            pb = PassBuilder(tm, pto)
            mpm = pb.getModulePassManager()
            mpm.run(llvm_mod, pb)
            return str(llvm_mod)
        except Exception:
            return ir_text


# ── 辅助函数 ──


def _unwrap_block(node):
    """展开 做/do 块，返回内部表达式列表。空节点返回空列表。"""
    if not isinstance(node, list):
        return [node]
    if len(node) == 0:
        return []
    if node[0] in ('做', 'do'):
        return node[1:]
    return [node]


# ── 辅助编译函数 ──


def _compile_if(args: list, cg: CodegenContext) -> ir.Value | None:
    """编译 若/if 结构，支持 再若/else-if 和 否则/else。

    AST 格式（合并后）:
      ['若', cond, then]                              — 纯 if
      ['若', cond, then, else]                        — if-else
      ['若', cond, then, ['若', c2, t2]]               — if-elif (嵌套)
      ['若', cond, then, ['再若', c2], body2, '否则', else] — if-elif-else
    """
    # 收集所有分支：(cond, body)
    branches: list[tuple[ir.Value | list, list]] = []
    final_else: list | None = None

    branches.append((args[0], args[1]))
    i = 2
    while i < len(args):
        item = args[i]
        if isinstance(item, list) and len(item) > 0:
            if item[0] == '若':
                # 嵌套的 elif（糖解析器的嵌套 若）
                branches.append((item[1], item[2]))
                i += 1
            elif item[0] == '再若':
                # 合并后的再若：[再若, cond]
                cond_node = item[1] if len(item) > 1 else _ZERO
                i += 1
                body_node = args[i] if i < len(args) else _ZERO
                i += 1
                branches.append((cond_node, body_node))
            elif item[0] == '否则':
                # 合并后的否则体列表
                final_else = item[1:]
                i += 1
            elif len(args) == 3 and i == 2:
                # 简单 if-else：第三参数是 else 分支
                final_else = [item]
                i += 1
            else:
                i += 1
        elif isinstance(item, str) and item == '否则':
            i += 1
            if i < len(args):
                final_else = [args[i]]
            i += 1
        else:
            i += 1

    merge_block = cg._add_block(name='if_merge')
    result_alloca = cg._entry_alloca('if_res')
    cg.builder.store(_NULL, result_alloca)

    for cond_node, body_node in branches:
        test_block = cg._add_block(name='if_test')
        body_block = cg._add_block(name='if_body')
        next_test = cg._add_block(name='if_next')

        cg.builder.branch(test_block)
        cg.builder.position_at_start(test_block)
        cond_val = compile_node(cond_node, cg)
        cond = cg._to_bool_i1(cond_val)
        cg.builder.cbranch(cond, body_block, next_test)

        cg.builder.position_at_start(body_block)
        body_val = compile_node(body_node, cg)
        if not cg.builder.block.is_terminated:
            if body_val is not None:
                cg.builder.store(body_val, result_alloca)
            cg.builder.branch(merge_block)

        cg.builder.position_at_start(next_test)

    if final_else is not None:
        else_block = cg._add_block(name='if_else')
        cg.builder.branch(else_block)
        cg.builder.position_at_start(else_block)
        for e in final_else:
            else_val = compile_node(e, cg)
        if not cg.builder.block.is_terminated:
            if else_val is not None:
                cg.builder.store(else_val, result_alloca)
            cg.builder.branch(merge_block)
    else:
        cg.builder.branch(merge_block)

    cg.builder.position_at_start(merge_block)
    return cg.builder.load(result_alloca, name='if_result')


def _compile_judge(args: list, cg: CodegenContext) -> ir.Value | None:
    """编译 判/三态分支。AST: ['判', val, true_body, maybe_body, false_body]"""
    val = cg._to_bool_i1(compile_node(args[0], cg))

    true_block = cg._add_block(name='judge_true')
    maybe_block = cg._add_block(name='judge_maybe')
    false_block = cg._add_block(name='judge_false')
    merge_block = cg._add_block(name='judge_end')

    # switch on value: 1→真, 0→可能, -1→假
    sw = cg.builder.switch(val, false_block)
    sw.add_case(_ONE, true_block)
    sw.add_case(_ZERO, maybe_block)

    phi_incoming: list[tuple[ir.Value, ir.Block]] = []

    cg.builder.position_at_start(true_block)
    tv = compile_node(args[1], cg) if len(args) > 1 else _NULL
    if not cg.builder.block.is_terminated:
        cg.builder.branch(merge_block)
        phi_incoming.append((tv if tv is not None else _NULL, true_block))

    cg.builder.position_at_start(maybe_block)
    mv = compile_node(args[2], cg) if len(args) > 2 else _NULL
    if not cg.builder.block.is_terminated:
        cg.builder.branch(merge_block)
        phi_incoming.append((mv if mv is not None else _NULL, maybe_block))

    cg.builder.position_at_start(false_block)
    fv = compile_node(args[3], cg) if len(args) > 3 else _NULL
    if not cg.builder.block.is_terminated:
        cg.builder.branch(merge_block)
        phi_incoming.append((fv if fv is not None else _NULL, false_block))

    cg.builder.position_at_start(merge_block)
    if phi_incoming:
        phi = cg.builder.phi(_PTR, name='judge_result')
        for v, blk in phi_incoming:
            phi.add_incoming(v, blk)
        return phi
    return _NULL


def _compile_lambda(args: list, cg: CodegenContext) -> ir.Value:
    params = args[0] if args and isinstance(args[0], list) else []
    body = args[1] if len(args) > 1 else []
    body_stmts = _unwrap_block(body)
    n = len([k for k in cg._funcs if k.startswith('__lambda_')])
    name = f'__lambda_{n}'
    saved_scope = dict(cg._scope)
    saved_allocas = dict(cg._allocas)
    saved_builder = cg._builder
    saved_entry = cg._entry_block
    saved_func = cg._current_func
    cg.begin_function(name, params)
    for stmt in body_stmts:
        compile_node(stmt, cg)
    cg.end_function()
    cg._scope = saved_scope
    cg._allocas = saved_allocas
    cg._builder = saved_builder
    cg._entry_block = saved_entry
    cg._current_func = saved_func
    func = cg._funcs[name]
    return cg.builder.bitcast(func, _PTR, name=f'{name}_ptr')


def _compile_try_catch(args: list, cg: CodegenContext) -> ir.Value | None:
    if len(args) < 2:
        raise SyntaxError('尝试 需要 (try_body 捕获 (err) catch_body)')

    try_body = args[0]
    catch_spec = args[1]

    if not isinstance(catch_spec, list) or len(catch_spec) < 2 or catch_spec[0] not in ('捕获', 'catch'):
        raise SyntaxError('尝试 需要 捕获 (变量) { 体 }')

    error_var = catch_spec[1]
    if isinstance(error_var, list):
        error_var = error_var[0] if len(error_var) > 0 else '错误'
    catch_body_stmts = _unwrap_block(catch_spec[2]) if len(catch_spec) > 2 else []

    if isinstance(try_body, list) and len(try_body) > 0 and try_body[0] in ('做', 'do'):
        try_stmts = try_body[1:]
    else:
        try_stmts = [try_body]

    g_error = cg._rt_funcs['g_error']

    catch_block = cg._add_block(name='catch_body')
    after_block = cg._add_block(name='try_after')

    # 清除错误状态，标记进入 try 深度
    cg.builder.store(_NULL, g_error)
    cg._try_depth += 1

    # 每个语句后立即检查 @g_error，发现则跳到 catch
    for stmt in try_stmts:
        compile_node(stmt, cg)
        if cg.builder.block.is_terminated:
            break
        err = cg.builder.load(g_error, name='try_err')
        err_int = cg.builder.ptrtoint(err, _INT, name='try_err_int')
        has_err = cg.builder.icmp_signed('!=', err_int, _ZERO, name='try_has')
        next_stmt = cg._add_block(name='try_next')
        cg.builder.cbranch(has_err, catch_block, next_stmt)
        cg.builder.position_at_start(next_stmt)

    if cg.builder.block.is_terminated:
        cg._try_depth -= 1
        return _NULL
    cg.builder.branch(after_block)

    # catch 块
    cg.builder.position_at_start(catch_block)
    err_msg = cg.builder.load(g_error, name='err_msg')
    cg.set_var(error_var, err_msg)
    for stmt in catch_body_stmts:
        compile_node(stmt, cg)
    cg.builder.store(_NULL, g_error)
    if not cg.builder.block.is_terminated:
        cg.builder.branch(after_block)

    cg.builder.position_at_start(after_block)
    cg._try_depth -= 1
    return _NULL


def _maybe_unwind(cg: CodegenContext) -> None:
    if cg._try_depth > 0:
        return
    g_error = cg._rt_funcs.get('g_error')
    if not g_error or cg.builder.block.is_terminated:
        return
    err = cg.builder.load(g_error, name='unwind_err')
    err_int = cg.builder.ptrtoint(err, _INT, name='unwind_int')
    has_err = cg.builder.icmp_signed('!=', err_int, _ZERO, name='unwind_has')
    no_err = cg._add_block(name='no_unwind')
    do_unwind = cg._add_block(name='do_unwind')
    cg.builder.cbranch(has_err, do_unwind, no_err)
    cg.builder.position_at_start(do_unwind)
    cg.builder.ret(err)
    cg.builder.position_at_start(no_err)


def _compile_for(args: list, cg: CodegenContext) -> ir.Value | None:
    """编译 遍历/for 循环。

    AST 格式:
      ['遍历', var, start, end, body]  — 范围遍历
      ['遍历', var, container, body]    — 容器遍历（阶段 3 桩）
    """
    if len(args) < 3:
        raise SyntaxError('遍历 需要 (变量名 起始 结束 体) 或 (变量名 容器 体)')

    var_name = args[0]
    body = args[-1]
    body_exprs = _unwrap_block(body)
    is_range = len(args) >= 4

    if is_range:
        start_val = compile_node(args[1], cg)
        end_val = compile_node(args[2], cg)
    else:
        # 容器遍历：生成 i = 0..len-1 的范围循环
        container = compile_node(args[1], cg)
        len_func = cg._get_runtime_func('表长')
        assert len_func is not None
        len_val = cg.builder.call(len_func, [container], name='list_len')
        len_i32 = len_val  # i32 from rt_list_len
        len_i64 = cg.builder.zext(len_i32, _INT, name='len_widen')
        end_i64 = cg.builder.sub(len_i64, _ONE, name='end_idx')
        start_val = cg._box_int(_ZERO)
        end_val = cg._box_int(end_i64)
        is_range = True
        # 包装原体：在每轮循环中加入 取元素 → 设变量
        get_func = cg._get_runtime_func('取')
        assert get_func is not None
        _orig_body = body_exprs

        def _make_container_body():
            idx_ptr = cg.builder.load(loop_var, name='idx_ptr')
            idx_i64 = cg._unbox_int(idx_ptr)
            idx_i32 = cg.builder.trunc(idx_i64, _I32, name='idx_i32')
            elem = cg.builder.call(get_func, [container, idx_i32], name='elem')
            cg.set_var(var_name, elem)
            for e in _orig_body:
                compile_node(e, cg)

        body_exprs = [('__container_body__', _make_container_body)]

    # 分配循环变量
    loop_var = cg._entry_alloca(var_name)
    cg.builder.store(start_val, loop_var)
    saved = cg._scope.get(var_name)
    cg._scope[var_name] = loop_var

    loop_h = cg._add_block(name='for_h')
    loop_b = cg._add_block(name='for_b')
    loop_e = cg._add_block(name='for_e')

    cg._loop_stack.append((loop_h, loop_e))
    cg.builder.branch(loop_h)

    cg.builder.position_at_start(loop_h)
    cur = cg._unbox_int(cg.builder.load(loop_var, name=f'{var_name}_val'))
    end_i32 = cg._unbox_int(end_val)
    cond = cg.builder.icmp_signed('<=', cur, end_i32, name='for_cond')
    cg.builder.cbranch(cond, loop_b, loop_e)

    cg.builder.position_at_start(loop_b)
    for expr in body_exprs:
        if isinstance(expr, tuple) and expr[0] == '__container_body__':
            expr[1]()  # 调用回调生成容器遍历体
        else:
            compile_node(expr, cg)
    cur_val = cg._unbox_int(cg.builder.load(loop_var, name=f'{var_name}_next'))
    next_val = cg._box_int(cg.builder.add(cur_val, _ONE))
    cg.builder.store(next_val, loop_var)
    if not cg.builder.block.is_terminated:
        cg.builder.branch(loop_h)

    cg.builder.position_at_start(loop_e)
    if saved is not None:
        cg._scope[var_name] = saved
    else:
        cg._scope.pop(var_name, None)
    cg._loop_stack.pop()
    return _NULL


def _check_div_zero(lhs: ir.Value, rhs: ir.Value, cg: CodegenContext):
    """插入零除运行时检查。若 rhs == 0，调用 rt_throw。"""
    is_zero = cg.builder.icmp_signed('==', rhs, _ZERO, name='div_zero')
    if isinstance(is_zero.type, ir.IntType) and is_zero.type.width == 1:
        ok_block = cg._add_block(name='div_ok')
        err_block = cg._add_block(name='div_err')
        cg.builder.cbranch(is_zero, err_block, ok_block)

        cg.builder.position_at_start(err_block)
        # 声明或复用 rt_throw
        if 'rt_throw' not in cg._rt_funcs:
            ft = ir.FunctionType(ir.VoidType(), [_PTR])
            throw_fn = ir.Function(cg.module, ft, name='rt_throw')
            cg._rt_funcs['rt_throw'] = throw_fn
        else:
            throw_fn = cg._rt_funcs['rt_throw']
        msg = cg._make_rt_string('除零错误')
        cg.builder.call(throw_fn, [msg], name='throw_div0')
        cg.builder.branch(ok_block)

        cg.builder.position_at_start(ok_block)


def _is_float_call(val: ir.Value) -> bool:
    return isinstance(val, ir.Instruction) and val.opname == 'call' and val.callee.name == 'rt_float_new'


def _val_to_double(val, is_float: bool, cg: CodegenContext) -> ir.Value:
    if isinstance(val, RawValue):
        return cg.builder.sitofp(val.ll_val, ir.DoubleType(), name='tof')
    v = val.ll_val if isinstance(val, BoxedValue) else val
    if is_float:
        return cg.builder.call(cg._get_runtime_func('rt_unbox_float'), [v], name='unbox_f')
    raw = cg.builder.ptrtoint(v, _INT, name='tof_raw')
    ival = cg.builder.ashr(raw, _ONE, name='tof_int')
    return cg.builder.sitofp(ival, ir.DoubleType(), name='tof')


def _check_div_zero_f(lhs: ir.Value, rhs: ir.Value, cg: CodegenContext) -> None:
    is_zero = cg.builder.fcmp_ordered('==', rhs, ir.Constant(ir.DoubleType(), 0.0), name='fdivz')
    ok_block = cg._add_block(name='fdiv_ok')
    err_block = cg._add_block(name='fdiv_err')
    cg.builder.cbranch(is_zero, err_block, ok_block)
    cg.builder.position_at_start(err_block)
    msg = cg._make_rt_string('除零错误')
    throw_fn = cg._get_runtime_func('rt_throw') or cg._rt_funcs.get('rt_throw')
    if throw_fn:
        cg.builder.call(throw_fn, [msg], name='throw_fdiv')
    cg.builder.ret(msg)
    cg.builder.position_at_start(ok_block)


def _compile_list_create(args: list, cg: CodegenContext) -> ir.Value:
    """编译 列表(元素...) → rt_list_new_cap(N) + rt_list_push_item × N。"""
    cap = ir.Constant(_I32, max(len(args), 4))
    result = cg.builder.call(cg._get_runtime_func('list'), [cap], name='list_new')
    push_name = 'rt_list_push_item'
    if push_name not in cg._rt_funcs:
        ft = ir.FunctionType(ir.VoidType(), [_PTR, _PTR])
        push_fn = ir.Function(cg.module, ft, name=push_name)
        cg._rt_funcs[push_name] = push_fn
    else:
        push_fn = cg._rt_funcs[push_name]
    for a in args:
        elem = compile_node(a, cg)
        cg.builder.call(push_fn, [result, elem], name='push')
    return result


def _compile_dict_create(args: list, cg: CodegenContext) -> ir.Value:
    """编译 字典(k1,v1,k2,v2...) → rt_dict_new + rt_dict_set × N/2。"""
    new_fn = cg._get_runtime_func('dict')
    assert new_fn is not None
    result = cg.builder.call(new_fn, [], name='dict_new')
    set_name = 'rt_dict_set'
    if set_name not in cg._rt_funcs:
        ft = ir.FunctionType(ir.VoidType(), [_PTR, _PTR, _PTR])
        set_fn = ir.Function(cg.module, ft, name=set_name)
        cg._rt_funcs[set_name] = set_fn
    else:
        set_fn = cg._rt_funcs[set_name]
    for i in range(0, len(args), 2):
        if i + 1 < len(args):
            key = compile_node(args[i], cg)
            val = compile_node(args[i + 1], cg)
            cg.builder.call(set_fn, [result, key, val], name='dict_set')
    return result


def _compile_fold(op: str, args: list, func: ir.Function, cg: CodegenContext) -> ir.Value:
    """变参操作的折叠编译：两两调用运行时函数。

    连接 自动对非字符串参数调用 rt_int_to_str 转换。
    """
    spec = _RUNTIME_FUNCS[op]
    param_types = spec[2]
    ret_type = spec[1]
    is_str_op = op in ('连接', 'concat')

    def _to_str(val: ir.Value) -> ir.Value:
        """如果值不是全局字符串常量，调用 rt_int_to_str 转换。"""
        if is_str_op and not _from_global_string(val):
            to_str_func = cg._get_runtime_func('整数转字符串')
            assert to_str_func is not None
            return cg.builder.call(to_str_func, [val], name='to_str')
        return val

    def _call(a, b):
        a_u = cg._unbox_int(a) if isinstance(param_types[0], ir.IntType) else a
        b_u = cg._unbox_int(b) if isinstance(param_types[1], ir.IntType) else b
        r = cg.builder.call(func, [a_u, b_u], name=f'rt_{op}')
        if isinstance(ret_type, ir.IntType):
            return cg._box_int(r)
        return r

    compiled = [compile_node(a, cg) for a in args]
    # 自动 int→str 转换
    if is_str_op:
        compiled = [_to_str(v) for v in compiled]
    result = compiled[0]
    for i in range(1, len(compiled)):
        result = _call(result, compiled[i])
    return result


def _quote_if_ident(arg: object) -> object:
    """如果参数是裸标识符（非数字、非字符串字面量），加双引号变成字符串字面量。"""
    if isinstance(arg, str) and not _is_string_literal(arg) and _to_int(arg) is None:
        return f'"{arg}"'
    return arg


def _dispatch_runtime(op: str, args: list, func: ir.Function, cg: CodegenContext) -> ir.Value | None:
    """将内置操作分发到运行时函数调用，处理装箱/拆箱。"""
    compiled = [compile_node(a, cg) for a in args]
    spec = _RUNTIME_FUNCS.get(op)
    if spec is None:
        raise NameError(f'编译错误: 未定义的运行时函数 {op}')
    param_types = spec[2]
    ret_type = spec[1]
    # 根据运行时函数的真实参数类型拆箱
    compiled_unwrapped = []
    for c in compiled:
        if isinstance(c, RawValue):
            compiled_unwrapped.append(cg._box_int(c.ll_val))
        elif isinstance(c, BoxedValue):
            compiled_unwrapped.append(c.ll_val)
        else:
            compiled_unwrapped.append(c)

    call_args = []
    for i, ptype in enumerate(param_types):
        if i >= len(compiled_unwrapped):
            call_args.append(ir.Constant(ptype, 0) if isinstance(ptype, ir.IntType) else _NULL)
        elif isinstance(ptype, ir.IntType):
            call_args.append(cg._unbox_int(compiled_unwrapped[i]))
            if ptype != _INT:
                call_args[-1] = cg.builder.trunc(call_args[-1], ptype, name='trunc')
        else:
            call_args.append(compiled_unwrapped[i])
    ret = cg.builder.call(func, call_args, name=f'rt_{op}')
    if isinstance(ret_type, ir.IntType):
        if ret_type != _INT:
            ret = cg.builder.zext(ret, _INT, name='zext')
        return cg._box_int(ret)
    if isinstance(ret_type, ir.VoidType):
        return _NULL
    return ret


def _from_global_string(val: ir.Value) -> bool:
    """判断值是否来自全局字符串常量（GEP 指令或常量）。"""
    if isinstance(val, ir.Constant) and isinstance(val.constant, ir.GEPConstant):
        return True
    if hasattr(val, 'opname') and val.opname == 'getelementptr':
        return True
    return False


def _to_i8_ptr(val, cg):
    if isinstance(val, RawValue):
        return cg._box_int(val.ll_val)
    if isinstance(val, BoxedValue):
        return val.ll_val
    return val


def compile_node(node, cg: CodegenContext) -> ir.Value | None:
    result = _compile_node_inner(node, cg)
    if isinstance(result, RawValue):
        return cg._box_int(result.ll_val)
    if isinstance(result, BoxedValue):
        return result.ll_val
    return result


def _compile_node_inner(node, cg: CodegenContext) -> ir.Value | None:
    """递归编译 AST 节点，返回 i8* 值。"""

    # 字面量 → i8*
    if isinstance(node, float):
        return cg.builder.call(
            cg._get_runtime_func('rt_float_new'),
            [ir.Constant(ir.DoubleType(), node)],
            name='float_new',
        )
    if isinstance(node, int):
        return RawValue(ir.Constant(_INT, node))

    if isinstance(node, TritValue):
        return RawValue(ir.Constant(_INT, node.to_int()))

    if isinstance(node, str):
        if node in _BUILTIN_CONSTS:
            return RawValue(ir.Constant(_INT, _BUILTIN_CONSTS[node]))
        # 字符串字面量 → i8* (rt_str_t 格式)
        if _is_string_literal(node):
            return cg._make_rt_string(_unquote(node))
        # 浮点数字字符串 → rt_float_new
        ft = _to_float_str(node)
        if ft is not None:
            return cg.builder.call(
                cg._get_runtime_func('rt_float_new'),
                [ir.Constant(ir.DoubleType(), ft)],
                name='float_new',
            )
        n = _to_int(node)
        if n is not None:
            return RawValue(ir.Constant(_INT, n))
        # 零参内置函数（如 time）→ 自动调用
        rt = cg._get_runtime_func(node)
        if rt is not None:
            return _dispatch_runtime(node, [], rt, cg)
        return cg.get_var(node)

    if not isinstance(node, list) or len(node) < 1:
        raise SyntaxError(f'无法识别的 AST 节点: {node}')

    op = node[0]
    args = node[1:]

    # ── 内置二元算术（整数 i64 内联 / 浮点 fadd 内联 + 自动提升）──
    arith = _ARITH_OPS.get(op)
    if arith is not None:
        if len(args) < 1:
            raise SyntaxError(f'{op} 需要参数')
        # 一元操作（减/取负）
        if len(args) == 1:
            if op in ('减', 'sub'):
                v = cg._to_raw(_compile_node_inner(args[0], cg)).ll_val
                return RawValue(cg.builder.sub(_ZERO, v, name='neg_tmp'))
            raise SyntaxError(f'{op} 需要两个参数')
        lv = compile_node(args[0], cg)
        rv = compile_node(args[1], cg)
        l_is_float = _is_float_call(lv)
        r_is_float = _is_float_call(rv)
        if l_is_float or r_is_float:
            lf = _val_to_double(lv, l_is_float, cg)
            rf = _val_to_double(rv, r_is_float, cg)
            fop = _FLOAT_ARITH.get(op, 'fadd')
            if op in ('除', 'div'):
                _check_div_zero_f(lf, rf, cg)
            result = cg.builder.call(
                cg._get_runtime_func('rt_float_new'),
                [getattr(cg.builder, fop)(lf, rf)],
                name='float_result',
            )
            _maybe_unwind(cg)
            return result
        l_raw = cg._to_raw(lv).ll_val
        r_raw = cg._to_raw(rv).ll_val
        if op in ('除', 'div', '余', 'mod'):
            _check_div_zero(l_raw, r_raw, cg)
        return RawValue(getattr(cg.builder, arith)(l_raw, r_raw, name=f'{op}_tmp'))

    # ── 内置比较（raw i64 → icmp → RawValue(i1/i64)）──
    cmp_op = _COMPARE_OPS.get(op)
    if cmp_op is not None:
        if len(args) < 2:
            raise SyntaxError(f'{op} 需要两个参数')
        l_raw = cg._to_raw(compile_node(args[0], cg)).ll_val
        r_raw = cg._to_raw(compile_node(args[1], cg)).ll_val
        cond = cg.builder.icmp_signed(cmp_op, l_raw, r_raw, name=f'{op}_tmp')
        return RawValue(cg.builder.zext(cond, _INT, name=f'{op}_bool'))

    # ── 逻辑运算 ──
    logic_op = _LOGIC_OPS.get(op)
    if logic_op is not None:
        if len(args) < 2:
            raise SyntaxError(f'{op} 需要两个参数')
        l_bool = cg._to_bool_i1(compile_node(args[0], cg))
        r_bool = cg._to_bool_i1(compile_node(args[1], cg))
        res = cg.builder.and_(l_bool, r_bool) if logic_op == 'and' else cg.builder.or_(l_bool, r_bool)
        return RawValue(cg.builder.zext(res, _INT, name=f'{op}_bool'))

    # ── 非 ──
    if op in ('非', 'not'):
        if len(args) < 1:
            raise SyntaxError(f'{op} 需要至少一个参数')
        b = cg._to_bool_i1(compile_node(args[0], cg))
        return RawValue(cg.builder.zext(cg.builder.not_(b), _INT, name='not_bool'))

    # ── 判 三态分支 (判 expr { 真: .. 可能: .. 假: .. }) ──
    if op in ('判', 'judge'):
        if len(args) < 2:
            raise SyntaxError(f'{op} 需要 (值 真分支 [可能分支] [假分支])')
        return _compile_judge(args, cg)

    # ── 函数 匿名 lambda ──
    if op in ('函数', 'lambda'):
        return _compile_lambda(args, cg)

    # ── 尝试 (尝试 body 捕获 (err) handler) — 必须在运行时调度之前 ──
    if op in ('尝试', 'try'):
        return _compile_try_catch(args, cg)

    # ── 跳出/继续 (循环控制) ──
    if op in ('跳出', 'break', '继续', 'continue'):
        if not cg._loop_stack:
            raise SyntaxError(f'{op} 必须在循环内使用')
        _loop_h, _loop_e = cg._loop_stack[-1]
        if op in ('跳出', 'break'):
            cg.builder.branch(_loop_e)
        else:
            cg.builder.branch(_loop_h)
        return _NULL

    # ── 运行时函数调用 ──
    rt_func = cg._get_runtime_func(op)
    if rt_func is not None:
        # IoT 操作：自动为裸标识符参数加引号
        if op in ('读', '查', '置', '对', 'read', 'query', 'write', 'with'):
            args = [_quote_if_ident(a) for a in args]
        # list/列表 需要逐个 push 元素
        if op in ('列表', 'list'):
            return _compile_list_create(args, cg)
        # dict/字典 需要逐对 set
        if op in ('字典', 'dict'):
            return _compile_dict_create(args, cg)
        # 连接/列表合 支持变参：两两折叠调用
        if op in ('连接', 'concat', '列表合', 'list_concat') and len(args) > 2:
            return _compile_fold(op, args, rt_func, cg)
        result = _dispatch_runtime(op, args, rt_func, cg)
        _maybe_unwind(cg)
        return result

    # ── 定义变量 (设 name value) ──
    if op in ('设', 'set'):
        if len(args) < 2:
            raise SyntaxError(f'{op} 需要 (变量名 值)')
        name = args[0]
        if not isinstance(name, str):
            raise SyntaxError(f'变量名必须是字符串: {name}')
        val = _compile_node_inner(args[1], cg)
        is_int_val = (
            isinstance(args[1], (int, float))
            or (isinstance(args[1], list) and len(args[1]) > 0 and args[1][0] in _ARITH_OPS)
            or (isinstance(args[1], str) and _to_int(args[1]) is not None)
        )
        if isinstance(val, RawValue):
            cg._get_alloca(name, is_int=True)
            cg.set_var_raw(name, val.ll_val)
        elif isinstance(val, (ir.Instruction, BoxedValue)):
            bv = val.ll_val if isinstance(val, BoxedValue) else val
            if name in cg._allocas and cg._allocas[name][1]:
                # i64 alloca 存 heap 值 → 转为 tagged int
                raw = cg._unbox_int(bv) if isinstance(bv.type, ir.PointerType) else bv
                cg.set_var_raw(name, raw)
            else:
                cg._get_alloca(name, is_int=False)
                cg.set_var(name, bv)
        else:
            cg.set_var(name, val)
        return val

    # ── 顺序块 (做 expr1 expr2 ...) ──
    if op in ('做', 'do'):
        result = None
        for stmt in args:
            result = compile_node(stmt, cg)
        return result

    # ── 输出 (输出 expr) ──
    if op in ('输出', 'print'):
        if args:
            raw = args[0]
            val = compile_node(raw, cg)
            if val is None:
                return _NULL
            if isinstance(val, RawValue):
                cg.emit_print_int(cg._box_int(val.ll_val))
                return _NULL
            pval = val.ll_val if isinstance(val, BoxedValue) else val
            is_int = cg._is_tagged_int(pval)
            int_block = cg._add_block(name='pr_int')
            heap_block = cg._add_block(name='pr_heap')
            pr_done = cg._add_block(name='pr_done')
            cg.builder.cbranch(is_int, int_block, heap_block)

            cg.builder.position_at_start(int_block)
            cg.emit_print_int(pval)
            cg.builder.branch(pr_done)

            cg.builder.position_at_start(heap_block)
            htype_ptr = cg.builder.bitcast(pval, ir.PointerType(_I32), name='htype_ptr')
            htype = cg.builder.load(htype_ptr, name='htype')
            is_float = cg.builder.icmp_signed('==', htype, ir.Constant(_I32, 4), name='is_float')
            str_block = cg._add_block(name='pr_str2')
            float_block = cg._add_block(name='pr_float')
            cg.builder.cbranch(is_float, float_block, str_block)

            cg.builder.position_at_start(str_block)
            cg.emit_print_str(pval)
            cg.builder.branch(pr_done)

            cg.builder.position_at_start(float_block)
            cg.builder.call(cg._get_runtime_func('rt_print_float'), [pval], name='pr_float_call')
            cg.builder.branch(pr_done)

            cg.builder.position_at_start(pr_done)
        return _NULL

    # ── 若条件 ──
    if op in ('若', 'if'):
        return _compile_if(args, cg)

    # ── 遍历 (遍历 var 从 start 到 end body) ──
    if op in ('遍历', 'for', 'forin'):
        return _compile_for(args, cg)

    # ── 循环 (循环 条件 体) ──
    if op in ('循环', 'loop'):
        if len(args) < 2:
            raise SyntaxError(f'{op} 需要 (条件 体)')

        body_exprs = _unwrap_block(args[1])
        loop_h = cg._add_block(name='loop_h')
        loop_b = cg._add_block(name='loop_b')
        loop_e = cg._add_block(name='loop_e')
        cg._loop_stack.append((loop_h, loop_e))
        cg.builder.branch(loop_h)

        cg.builder.position_at_start(loop_h)
        cond_val = compile_node(args[0], cg)
        cond = cg._to_bool_i1(cond_val)
        cg.builder.cbranch(cond, loop_b, loop_e)

        cg.builder.position_at_start(loop_b)
        for stmt in body_exprs:
            compile_node(stmt, cg)
        if not cg.builder.block.is_terminated:
            cg.builder.branch(loop_h)

        cg.builder.position_at_start(loop_e)
        cg._loop_stack.pop()
        return _NULL

    # ── 返回 (返回 expr) ──
    if op in ('返回', 'return'):
        val = compile_node(args[0], cg) if args else _NULL
        if isinstance(val, RawValue):
            val = cg._box_int(val.ll_val)
        elif isinstance(val, BoxedValue):
            val = val.ll_val
        cg.builder.ret(val)
        return val

    # ── 函数定义 (定义 name (params) body) ──
    if op in ('定义', 'define', 'fn'):
        if len(args) < 2:
            raise SyntaxError(f'{op} 需要 (名称 参数列表 [体])')
        # fn 格式: ['fn', 'name', ['p1', 'p2'], body_expr...]
        if isinstance(args[0], list):
            name = args[0][0]
            params = args[0][1:]
            body = _unwrap_block(args[1]) if len(args) > 1 else []
        elif op == 'fn' and len(args) >= 3:
            # _bootstrap.san 格式: ['fn', 'name', ['params'], e1, e2, ...]
            name = args[0]
            params = args[1] if isinstance(args[1], list) else []
            body = args[2:]
        else:
            # 定义 格式: ['定义', 'name', ['p1', 'p2'], body]
            name = args[0]
            params = args[1] if isinstance(args[1], list) else []
            body = _unwrap_block(args[2]) if len(args) > 2 else []
        cg.compile_fn_body(name, params, body)
        return _NULL

    # ── 变量作为容器索引：列表名(索引) → 取(列表名, 索引) ──
    if (op in cg._scope or op in cg._globals) and len(args) == 1:
        assert cg._get_runtime_func('取') is not None
        result = _dispatch_runtime('取', [op, args[0]], cg._get_runtime_func('取'), cg)
        _maybe_unwind(cg)
        return result

    # ── 导出 (忽略) ──
    if op in ('导出', 'export'):
        return _NULL

    # ── 函数调用（含点号访问 test.函数名）──
    resolved_op = op
    if '.' in op and op not in cg._funcs:
        # 点号访问：取最后一段作为函数名查找
        resolved_op = op.split('.')[-1]
    if resolved_op in cg._funcs:
        callee = cg._funcs[resolved_op]
        arg_vals = [_unwrap_call_arg(compile_node(a, cg), cg) for a in args]
        result = cg.builder.call(callee, arg_vals, name=f'call_{op}')
        _maybe_unwind(cg)
        return result

    resolved_op = op.split('.')[-1] if '.' in op else op
    if resolved_op in cg._funcs:
        arg_vals = [_unwrap_call_arg(compile_node(a, cg), cg) for a in args]
        result = cg.builder.call(cg._funcs[resolved_op], arg_vals, name=f'call_{op}')
        _maybe_unwind(cg)
        return result
    # 单元素列表 → 变量引用（如 ['lst'] → 'lst'）
    if isinstance(node, list) and len(node) == 1 and isinstance(node[0], str):
        return cg.get_var(node[0])
    raise NameError(f'编译错误: 未定义的操作或函数 {op}')


def _unwrap_call_arg(val, cg: CodegenContext) -> ir.Value:
    if isinstance(val, RawValue):
        return cg._box_int(val.ll_val)
    if isinstance(val, BoxedValue):
        return val.ll_val
    return val


def _merge_if_chain(nodes: list) -> list:
    """规范化：将 再若(elif)/否则(else) 合并到前一个 若 节点中。

    糖解析器输出的 AST 中，再若 和 否则 作为做块中的独立元素存在。
    本函数将它们合并为统一的 若 节点结构。
    """
    result = []
    i = 0
    while i < len(nodes):
        node = nodes[i]
        if isinstance(node, list) and len(node) > 0 and node[0] == '若':
            # 收集后续的 再若 和 否则
            merged = list(node)
            i += 1
            while i < len(nodes):
                nxt = nodes[i]
                if isinstance(nxt, list) and len(nxt) > 0 and nxt[0] == '再若':
                    merged.append(nxt)  # 再若条件 [再若 cond]
                    i += 1
                    if i < len(nodes):
                        nxt_body = nodes[i]
                        if isinstance(nxt_body, list) and len(nxt_body) > 0 and nxt_body[0] in ('做', 'do'):
                            merged.append(nxt_body)  # 再若体
                            i += 1
                elif isinstance(nxt, str) and nxt == '否则':
                    merged.append('否则')
                    i += 1
                    if i < len(nodes):
                        else_body = nodes[i]
                        merged.append(else_body)
                        i += 1
                else:
                    break
            # 递归处理合并后节点内部的 做 块
            merged = _deep_merge(merged)
            result.append(merged)
        elif isinstance(node, list) and len(node) > 0:
            # 递归处理所有列表节点
            result.append(_deep_merge(list(node)))
            i += 1
        else:
            result.append(node)
            i += 1
    return result


def _normalize_fn_format(nodes: list) -> list:
    """将 SugarConverter 的 ['fn', 'name', ['p'], body] 转为标准 ['fn', ['name', 'p'], body]。"""
    result = []
    for node in nodes:
        if isinstance(node, list) and len(node) >= 3 and node[0] == 'fn':
            if isinstance(node[1], str) and isinstance(node[2], list):
                name = node[1]
                params = node[2]
                body = node[3] if len(node) > 3 else []
                result.append(['fn', [name] + params, body])
                continue
        result.append(node)
    return result


def _deep_merge(node):
    """递归对 AST 节点及其所有子节点进行 if-elif-else 合并，并过滤 IoT 关键字。"""
    if isinstance(node, list) and len(node) > 0:
        first = node[0]
        if first in ('做', 'do'):
            # 过滤 IoT 关键字，然后合并
            inner = node[1:]
            inner = _merge_if_chain(inner)
            return [first] + inner
        # 其他节点递归处理子节点
        return [node[0]] + [_deep_merge(c) for c in node[1:]]
    return node


def _resolve_imports(nodes: list, cg: CodegenContext) -> tuple[list, list]:
    """解析 设 var = 导入(\"path\")，编译被导入文件的 定义 到当前模块。
    返回 (处理后的节点列表, 导入的顶层设节点列表)。
    """
    import os

    result = []
    imported_setups = []  # 导入文件中的 设 节点
    for node in nodes:
        if (
            isinstance(node, list)
            and len(node) >= 3
            and node[0] in ('设', 'set')
            and isinstance(node[2], list)
            and node[2][0] in ('导入', 'import')
            and len(node[2]) >= 2
        ):
            path_node = node[2][1]
            if isinstance(path_node, str) and _is_string_literal(path_node):
                path_node = _unquote(path_node)
            path_str = str(path_node)
            search = [path_str, f'stdlib/{path_str}', f'stdlib/{path_str}.san']
            found = None
            for sp in search:
                if os.path.exists(sp):
                    found = sp
                    break
                if not sp.endswith('.san') and os.path.exists(sp + '.san'):
                    found = sp + '.san'
                    break
            if found:
                try:
                    with open(found, 'r', encoding='utf-8') as f:
                        imported_code = f.read()
                    from ops.file_ops import _parse_with_sugar_san
                    from evaluator import SanyanEvaluator

                    tmp_eval = SanyanEvaluator()
                    imported_ast = _parse_with_sugar_san(imported_code, tmp_eval)
                    if imported_ast is None:
                        from sugar import SugarConverter
                        from skin import SkinManager

                        imported_ast = SugarConverter.convert(imported_code, SkinManager('chinese'))
                    if isinstance(imported_ast, list) and len(imported_ast) > 0 and imported_ast[0] in ('做', 'do'):
                        imported_ast = imported_ast[1:]
                    if isinstance(imported_ast, list):
                        # 先处理 设，再处理 定义（确保 定义 内可用全局变量）
                        for inode in imported_ast:
                            if isinstance(inode, list) and len(inode) > 0 and inode[0] in ('设', 'set'):
                                imported_setups.append(inode)
                        for inode in imported_ast:
                            if isinstance(inode, list) and len(inode) > 0 and inode[0] in ('定义', 'define', 'fn'):
                                try:
                                    compile_node(inode, cg)
                                except Exception as _exc:
                                    import sys as _sys2

                                    _name = inode[1] if len(inode) > 1 else '?'
                                    print(f'[import] skip {_name}: {_exc}', file=_sys2.stderr)
                except Exception as _exc2:
                    import sys as _sys3

                    print(f'[import] failed: {_exc2}', file=_sys3.stderr)
            continue
        result.append(node)
    return result, imported_setups


def _make_bootstrap_harness(cg: CodegenContext):
    """为 bootstrap 模块添加 parse_sanyan() ASCII 入口。"""
    cg.begin_function('parse_sanyan', ['source'])
    # 全局变量初始化
    for gname, gval in cg._global_inits:
        if isinstance(gval, (int, float)):
            init_val = cg._box_int(ir.Constant(_INT, int(gval)))
        elif isinstance(gval, str):
            init_val = cg._make_rt_string(gval)
        else:
            # 复杂初始化表达式 → 编译
            if isinstance(gval, list):
                init_val = compile_node(gval, cg)
            else:
                init_val = _NULL
        if init_val is not None:
            cg.builder.store(init_val, cg._globals[gname])
    # 调用 解析(source)
    func = cg._funcs.get('解析')
    if func:
        src = cg.get_var('source')
        result = cg.builder.call(func, [src], name='ast')
        cg.builder.ret(result)
    else:
        cg.builder.ret(_NULL)
    cg.end_function()


def compile_top_level(ast_nodes: list, module_name: str = 'main', module_prefix: str = '') -> CodegenContext:
    cg = CodegenContext(module_name, module_prefix=module_prefix)
    _compile_in_context(ast_nodes, cg)
    return cg


def _compile_in_context(ast_nodes: list, cg: CodegenContext) -> None:
    # 确保顶层是 do 块
    if isinstance(ast_nodes, list) and len(ast_nodes) > 0:
        first = ast_nodes[0]
        if isinstance(first, str) and first not in ('做', 'do'):
            # 单表达式: wrap 为 ['做', node] 防扁平化
            ast_nodes = ['做', ast_nodes]
        elif first not in ('做', 'do'):
            ast_nodes = ['做'] + ast_nodes
    if isinstance(ast_nodes, list) and len(ast_nodes) > 0 and ast_nodes[0] in ('做', 'do'):
        ast_nodes = ast_nodes[1:]

    ast_nodes = _normalize_fn_format(ast_nodes)
    ast_nodes = _merge_if_chain(ast_nodes)

    def collect_and_compile(nodes):
        nodes, imported_setups = _resolve_imports(nodes, cg)
        defs, others = [], []
        for node in nodes:
            if isinstance(node, list) and len(node) > 0 and node[0] in ('定义', 'define', 'fn'):
                defs.append(node)
            else:
                others.append(node)

        for node in others + imported_setups:
            if isinstance(node, list) and len(node) >= 3 and node[0] in ('设', 'set'):
                name = node[1]
                if isinstance(name, str):
                    val = node[2]
                    if isinstance(val, (int, float)):
                        if name.startswith('_'):
                            cg.create_global(name, val)
                        # 数字 — 不预建全局（走 alloca）
                    elif isinstance(val, str):
                        if _is_string_literal(val):
                            pass
                        elif _to_int(val) is not None:
                            if name.startswith('_'):
                                cg.create_global(name, val)
                            # 数字字符串 — 不预建全局
                        else:
                            cg.create_global(name, val)
                            cg._global_inits.append((name, val))
                    else:
                        cg.create_global(name, val)
                        cg._global_inits.append((name, val))

        class _Df:
            def __init__(self, n):
                self.node = n

        deferred: list[_Df] = []
        for node in defs:
            deferred.append(_Df(node))
            if isinstance(node[1], list):
                n, p = node[1][0], node[1][1:]
            elif node[0] == 'fn' and len(node) >= 3:
                n, p = node[1], node[2] if isinstance(node[2], list) else []
            else:
                n = node[1] if isinstance(node[1], str) else str(node[1])
                p = node[2] if len(node) > 2 and isinstance(node[2], list) else []
            cg.begin_function(n, p)
        for d in deferred:
            compile_node(d.node, cg)

        if cg.module.name == 'bootstrap' and '解析' in cg._funcs:
            _make_bootstrap_harness(cg)

        all_other = imported_setups + others
        if cg.module.name != 'bootstrap' and (all_other or cg._global_inits):
            cg.begin_function('main', [])
            for gname, gval in cg._global_inits:
                if isinstance(gval, (int, float)):
                    init_val = cg._box_int(ir.Constant(_INT, int(gval)))
                elif isinstance(gval, str):
                    init_val = cg._make_rt_string(gval)
                else:
                    init_val = _NULL
                cg.builder.store(init_val, cg._globals[gname])
            for node in all_other:
                if isinstance(node, list) and len(node) > 0 and node[0] in ('导入', 'import'):
                    continue
                compile_node(node, cg)
            cg.end_function()
        elif cg.module.name != 'bootstrap':
            cg.begin_function('main', [])
            cg.end_function()

    collect_and_compile(ast_nodes)


def _parse_source(source: str) -> list:
    from llvmgen.compiler import _parse_source as _ps

    return _ps(source)


def _collect_imports(node, collected: set) -> None:
    if isinstance(node, list) and len(node) > 0:
        if node[0] in ('导入', 'import') and len(node) > 1 and isinstance(node[1], str):
            collected.add(node[1])
            return
        for child in node:
            _collect_imports(child, collected)


def _find_module_path(name: str) -> str | None:
    import os

    if len(name) >= 2 and name[0] == '"' and name[-1] == '"':
        name = name[1:-1]

    paths = [name]
    if not name.endswith('.san'):
        paths.append(name + '.san')
    paths.append(os.path.join('stdlib', name if name.endswith('.san') else name + '.san'))

    for p in paths:
        if os.path.exists(p):
            return p
    return None


def compile_program(source: str, module_name: str = 'main') -> 'CodegenContext':
    """编译完整程序，含 import 静态链接。

    递归编译所有 导入 引用的 .san 模块，通过 llvmlite link_modules
    合并到一个 IR 模块中。依赖模块函数名加 san_{module}__ 前缀。
    """
    import os

    ast = _parse_source(source)
    if not isinstance(ast, list):
        raise SyntaxError(f'解析结果不是列表: {type(ast)}')

    imports: set[str] = set()
    _collect_imports(ast, imports)

    cg = compile_top_level(ast, module_name)

    if not imports:
        return cg

    from llvmlite import binding as llvm_bind

    main_mod = llvm_bind.parse_assembly(cg.verify())

    for imp in imports:
        path = _find_module_path(imp)
        if path is None:
            continue
        with open(path, 'r', encoding='utf-8') as f:
            dep_src = f.read()
        dep_ast = _parse_source(dep_src)
        dep_name = os.path.splitext(os.path.basename(path))[0]
        dep_cg = compile_top_level(dep_ast, dep_name, module_prefix=dep_name)
        dep_mod = llvm_bind.parse_assembly(dep_cg.verify())
        llvm_bind.link_modules(dst=main_mod, src=dep_mod)

    cg._linked_ir = str(main_mod)
    return cg
