"""三言 AST → LLVM IR 代码生成器"""

from __future__ import annotations
from llvmlite import ir
from ternary_core import TritValue

# ── 类型定义 ──
_INT = ir.IntType(32)
_PTR = ir.PointerType(ir.IntType(8))  # i8* — 变量统一存储类型
_ZERO = ir.Constant(_INT, 0)
_ONE = ir.Constant(_INT, 1)
_NULL = ir.Constant(_PTR, None)

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
    # 随机数 → i32
    '随机数': ('rt_random_int', _INT, [_INT, _INT]),
    'randint': ('rt_random_int', _INT, [_INT, _INT]),
    # 随机态 → i32（三值：-1/0/1）
    '随机态': ('rt_random_trit', _INT, []),
    # 类型判断 → i32
    '是数字': ('rt_is_number', _INT, [_INT]),
    'is_number': ('rt_is_number', _INT, [_INT]),
    '是字符串': ('rt_is_string', _INT, [_PTR]),
    'is_string': ('rt_is_string', _INT, [_PTR]),
    '是列表': ('rt_is_list', _INT, [_PTR]),
    'is_list': ('rt_is_list', _INT, [_PTR]),
    # 函数应用（桩）
    '应用': ('rt_apply_stub', _PTR, [_PTR, _PTR]),
    # 等待
    '等待': ('rt_sleep', ir.VoidType(), [_INT]),
    'wait': ('rt_sleep', ir.VoidType(), [_INT]),
    # 文件操作
    '读文件': ('rt_read_file', _PTR, [_PTR]),
    '写文件': ('rt_write_file', ir.VoidType(), [_PTR, _PTR]),
    # 字符串操作
    '连接': ('rt_str_concat', _PTR, [_PTR, _PTR]),
    'concat': ('rt_str_concat', _PTR, [_PTR, _PTR]),
    '整数转字符串': ('rt_int_to_str', _PTR, [_PTR]),
    '取长': ('rt_str_len', _INT, [_PTR]),
    'length': ('rt_str_len', _INT, [_PTR]),
    '字符串相等': ('rt_str_equals', _INT, [_PTR, _PTR]),
    'str_equals': ('rt_str_equals', _INT, [_PTR, _PTR]),
    '分割': ('rt_str_split', _PTR, [_PTR, _PTR]),
    'split': ('rt_str_split', _PTR, [_PTR, _PTR]),
    '子串': ('rt_str_substr', _PTR, [_PTR, _INT, _INT]),
    'substring': ('rt_str_substr', _PTR, [_PTR, _INT, _INT]),
    '包含': ('rt_str_contains', _INT, [_PTR, _PTR]),
    'contains': ('rt_str_contains', _INT, [_PTR, _PTR]),
    '查找': ('rt_str_find', _INT, [_PTR, _PTR]),
    'find': ('rt_str_find', _INT, [_PTR, _PTR]),
    # 列表操作
    '列表': ('rt_list_new', _PTR, []),
    'list': ('rt_list_new', _PTR, []),
    '字典': ('rt_dict_new', _PTR, []),
    'dict': ('rt_dict_new', _PTR, []),
    'dict_contains': ('rt_dict_contains', _INT, [_PTR, _PTR]),
    '含键': ('rt_dict_contains', _INT, [_PTR, _PTR]),
    'get_key': ('rt_dict_get', _PTR, [_PTR, _PTR]),
    'set_key': ('rt_dict_set', ir.VoidType(), [_PTR, _PTR, _PTR]),
    '取键': ('rt_dict_get', _PTR, [_PTR, _PTR]),
    '置键': ('rt_dict_set', ir.VoidType(), [_PTR, _PTR, _PTR]),
    '表长': ('rt_list_len', _INT, [_PTR]),
    'list_len': ('rt_list_len', _INT, [_PTR]),
    '列表合': ('rt_list_concat', _PTR, [_PTR, _PTR]),
    'list_concat': ('rt_list_concat', _PTR, [_PTR, _PTR]),
    '取': ('rt_list_get', _PTR, [_PTR, _INT]),
    'get': ('rt_list_get', _PTR, [_PTR, _INT]),
    'slice': ('rt_list_slice', _PTR, [_PTR, _INT, _INT]),
    '切片': ('rt_list_slice', _PTR, [_PTR, _INT, _INT]),
    'str_to_list': ('rt_str_to_list', _PTR, [_PTR]),
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
}  # yapf: disable


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

    def __init__(self, module_name: str = 'main'):
        self.module = ir.Module(name=module_name)
        try:
            from llvmlite import binding as _llvm_bind

            self.module.triple = _llvm_bind.get_default_triple()
        except Exception:
            self.module.triple = 'x86_64-pc-linux-gnu'
        self._printf = None
        self._builder: ir.IRBuilder | None = None
        self._entry_block: ir.Block | None = None
        self._scope: dict[str, ir.Value] = {}  # 当前函数作用域
        self._funcs: dict[str, ir.Function] = {}  # 已定义的函数
        self._current_func: ir.Function | None = None
        self._globals: dict[str, ir.GlobalVariable] = {}  # 模块级全局变量
        self._global_inits: list[tuple[str, ir.Value | int | str]] = []  # 全局变量初始化
        self._loop_stack: list[tuple[ir.Block, ir.Block]] = []  # (header, exit) 循环上下文
        self._rt_funcs: dict[str, ir.Function] = {}  # 已声明的运行时函数
        # 声明外部运行时函数
        self._declare_runtime()

    def _declare_runtime(self):
        """声明外部运行时函数（printf 等）。"""
        if self._printf is None:
            fnty = ir.FunctionType(_INT, [_PTR], var_arg=True)
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
        """创建函数并进入其 entry 块。若已存在则复用（清空旧指令）。"""
        if name in self._funcs:
            func = self._funcs[name]
            self._current_func = func
            self._scope = {}
            # 清空旧 entry 块指令，重新填充
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
        for i, pname in enumerate(param_names):
            func.args[i].name = pname
        self._funcs[name] = func
        self._current_func = func
        self._scope = {}
        entry = func.append_basic_block(name='entry')
        self._builder = ir.IRBuilder(entry)
        self._entry_block = entry
        for i, pname in enumerate(param_names):
            alloca = self._builder.alloca(_PTR, name=pname)
            self._builder.store(func.args[i], alloca)
            self._scope[pname] = alloca
        return func

        fnty = ir.FunctionType(_PTR, [_PTR] * len(param_names))
        func = ir.Function(self.module, fnty, name=name)
        for i, pname in enumerate(param_names):
            func.args[i].name = pname
        self._funcs[name] = func
        self._current_func = func
        self._scope = {}
        entry = func.append_basic_block(name='entry')
        self._builder = ir.IRBuilder(entry)
        self._entry_block = entry
        for i, pname in enumerate(param_names):
            alloca = self._builder.alloca(_PTR, name=pname)
            self._builder.store(func.args[i], alloca)
            self._scope[pname] = alloca
        return func

        fnty = ir.FunctionType(_PTR, [_PTR] * len(param_names))
        func = ir.Function(self.module, fnty, name=name)
        for i, pname in enumerate(param_names):
            func.args[i].name = pname
        self._funcs[name] = func
        self._current_func = func
        self._scope = {}
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
        """i32 → tagged i8* 装箱。值左移1位, bit0=1 标记为整数。"""
        shifted = self.builder.shl(int_val, _ONE, name='box_shl')
        tagged = self.builder.or_(shifted, _ONE, name='box_tag')
        return self.builder.inttoptr(tagged, _PTR, name='box')

    def _unbox_int(self, ptr_val: ir.Value) -> ir.Value:
        """tagged i8* → i32 拆箱。ptrtoint 后右移1位去除 tag。"""
        raw = self.builder.ptrtoint(ptr_val, _INT, name='unbox_raw')
        return self.builder.lshr(raw, _ONE, name='unbox')

    def _is_tagged_int(self, ptr_val: ir.Value) -> ir.Value:
        """检查 tagged 指针是否为整数（bit0 == 1）。返回 i1。"""
        raw = self.builder.ptrtoint(ptr_val, _INT, name='tag_raw')
        tagged = self.builder.and_(raw, _ONE, name='tag_bit')
        return self.builder.icmp_signed('!=', tagged, _ZERO, name='is_int')

    def _to_i32(self, val: ir.Value) -> ir.Value:
        """将值转为 i32：若已是 i32 直接返回，若是 i8* 则拆箱。"""
        if isinstance(val.type, ir.IntType):
            return val
        return self._unbox_int(val)

    def emit_print_int(self, value: ir.Value):
        """生成 printf(\"%d\\n\", i32) 调用。自动拆箱 i8*。"""
        fmt = self._make_global_string('%d\n')
        self.builder.call(self._printf, [fmt, self._to_i32(value)])

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
        return self.builder.gep(gv, [_ZERO, _ZERO], inbounds=True)

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
        st_ty = ir.LiteralStructType([_INT, ir.ArrayType(ir.IntType(8), slen + 1)])
        len_f = ir.Constant(_INT, slen)
        data_f = ir.Constant(ir.ArrayType(ir.IntType(8), slen + 1), data_bytes)
        c = ir.Constant(st_ty, [len_f, data_f])
        gv = ir.GlobalVariable(self.module, st_ty, name=f'.rt_str.{n}')
        gv.linkage = 'private'
        gv.global_constant = True
        gv.initializer = c
        raw = self.builder.gep(gv, [_ZERO, _ZERO], inbounds=True)
        return self.builder.bitcast(raw, _PTR, name=f'.rt_str_p{n}')

    def _entry_alloca(self, name: str) -> ir.Value:
        """在函数 entry 块创建 alloca（确保支配所有使用）。"""
        saved_pos = self.builder.block
        self.builder.position_at_start(self._entry_block)
        alloca = self.builder.alloca(_PTR, name=name)
        self.builder.position_at_end(saved_pos)
        return alloca

    def get_var(self, name: str) -> ir.Value:
        """加载变量值，返回 i8*（需调用方按需拆箱为 i32）。先查局部变量，再查全局变量。"""
        if name in self._scope:
            return self.builder.load(self._scope[name], name=name)
        if name in self._globals:
            return self.builder.load(self._globals[name], name=name)
        if name in self._funcs:
            raise NameError(f'{name} 是函数，不能当作变量')
        raise NameError(f'编译错误: 未定义变量 {name}')

    def set_var(self, name: str, value: ir.Value):
        """存储变量值。i32 自动装箱为 i8*，i8* 直接存储。"""
        if isinstance(value.type, ir.PointerType):
            pass
        else:
            value = self._box_int(value)
        if name in self._scope:
            self.builder.store(value, self._scope[name])
        elif name in self._globals:
            self.builder.store(value, self._globals[name])
        else:
            alloca = self._entry_alloca(name)
            self.builder.store(value, alloca)
            self._scope[name] = alloca

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
                    self.builder.ret(result)
        self.end_function()

    def verify(self) -> str:
        """验证模块并返回 IR 文本。"""
        try:
            return str(self.module)
        except Exception as e:
            raise RuntimeError(f'LLVM IR 生成失败: {e}') from e


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
        cond = cg.builder.icmp_signed('!=', cg._unbox_int(cond_val), _ZERO, name='if_cond')
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
    val = cg._unbox_int(compile_node(args[0], cg))

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
    """编译匿名函数 函数(params) { body } 为命名函数，返回函数指针。"""
    params = args[0] if args and isinstance(args[0], list) else []
    body = args[1] if len(args) > 1 else []
    body_stmts = _unwrap_block(body)
    n = len([k for k in cg._funcs if k.startswith('__lambda_')])
    name = f'__lambda_{n}'
    cg.begin_function(name, params)
    for stmt in body_stmts:
        compile_node(stmt, cg)
    cg.end_function()
    func = cg._funcs[name]
    return cg.builder.bitcast(func, _PTR, name=f'{name}_ptr')


def _compile_try_catch(args: list, cg: CodegenContext) -> ir.Value | None:
    """编译 尝试/捕获 异常处理。

    AST 格式: ['尝试', try_body, ['捕获', error_var, catch_body...]]
    """
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

    # 展开 try 体
    if isinstance(try_body, list) and len(try_body) > 0 and try_body[0] in ('做', 'do'):
        try_stmts = try_body[1:]
    else:
        try_stmts = [try_body]

    # 调用 rt_try_begin
    if 'rt_try_begin' not in cg._rt_funcs:
        ft = ir.FunctionType(ir.VoidType(), [])
        try_func = ir.Function(cg.module, ft, name='rt_try_begin')
        cg._rt_funcs['rt_try_begin'] = try_func
    else:
        try_func = cg._rt_funcs['rt_try_begin']
    cg.builder.call(try_func, [], name='try_begin')

    # 执行 try 体
    for stmt in try_stmts:
        compile_node(stmt, cg)

    # 若 try 体已终止（如 return），跳过 catch
    if cg.builder.block.is_terminated:
        return _NULL

    # 检查异常
    fnty = ir.FunctionType(_INT, [])
    rt_check = ir.Function(cg.module, fnty, name='rt_try_check')
    has_err = cg.builder.call(rt_check, [], name='has_err')
    cond = cg.builder.icmp_signed('!=', has_err, _ZERO, name='catch_cond')

    catch_block = cg._add_block(name='catch_body')
    after_block = cg._add_block(name='try_after')
    cg.builder.cbranch(cond, catch_block, after_block)

    # catch 体
    cg.builder.position_at_start(catch_block)
    e_fnty = ir.FunctionType(_PTR, [])
    rt_get_err = ir.Function(cg.module, e_fnty, name='rt_try_get_error')
    err_val = cg.builder.call(rt_get_err, [], name='err_msg')
    cg.set_var(error_var, err_val)
    for stmt in catch_body_stmts:
        compile_node(stmt, cg)
    # 清除错误
    end_fnty = ir.FunctionType(ir.VoidType(), [])
    rt_end = ir.Function(cg.module, end_fnty, name='rt_try_end')
    cg.builder.call(rt_end, [], name='try_clear')
    if not cg.builder.block.is_terminated:
        cg.builder.branch(after_block)

    cg.builder.position_at_start(after_block)
    return _NULL


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
        len_i32 = cg._unbox_int(len_val) if isinstance(len_val.type, ir.PointerType) else len_val
        end_i32 = cg.builder.sub(len_i32, _ONE, name='end_idx')
        start_val = cg._box_int(_ZERO)
        end_val = cg._box_int(end_i32)
        is_range = True
        # 包装原体：在每轮循环中加入 取元素 → 设变量
        get_func = cg._get_runtime_func('取')
        assert get_func is not None
        _orig_body = body_exprs

        def _make_container_body():
            # 在循环体内取元素
            idx_ptr = cg.builder.load(loop_var, name='idx_ptr')
            idx_i32 = cg._unbox_int(idx_ptr)
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


def _compile_list_create(args: list, cg: CodegenContext) -> ir.Value:
    """编译 列表(元素...) → rt_list_new + rt_list_push_item × N。"""
    new_fn = cg._get_runtime_func('list')
    assert new_fn is not None
    result = cg.builder.call(new_fn, [], name='list_new')
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
    call_args = []
    for i, ptype in enumerate(param_types):
        if i >= len(compiled):
            call_args.append(_ZERO if isinstance(ptype, ir.IntType) else _NULL)
        elif isinstance(ptype, ir.IntType):
            call_args.append(cg._unbox_int(compiled[i]))
        else:
            call_args.append(compiled[i])
    ret = cg.builder.call(func, call_args, name=f'rt_{op}')
    # 返回值若为 i32 则装箱
    if isinstance(ret_type, ir.IntType):
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


def compile_node(node, cg: CodegenContext) -> ir.Value | None:
    """递归编译 AST 节点，返回 i8* 值。"""

    # 字面量 → i8*
    if isinstance(node, (int, float)):
        return cg._box_int(ir.Constant(_INT, int(node)))

    # TritValue (sugar.san 解析结果)
    if isinstance(node, TritValue):
        return cg._box_int(ir.Constant(_INT, node.to_int()))

    if isinstance(node, str):
        # 内置常量
        if node in _BUILTIN_CONSTS:
            return cg._box_int(ir.Constant(_INT, _BUILTIN_CONSTS[node]))
        # 字符串字面量 → i8* (rt_str_t 格式)
        if _is_string_literal(node):
            return cg._make_rt_string(_unquote(node))
        n = _to_int(node)
        if n is not None:
            return cg._box_int(ir.Constant(_INT, n))
        return cg.get_var(node)

    if not isinstance(node, list) or len(node) < 1:
        raise SyntaxError(f'无法识别的 AST 节点: {node}')

    op = node[0]
    args = node[1:]

    # ── 内置二元算术（i8* → unbox → op → rebox → i8*）──
    arith = _ARITH_OPS.get(op)
    if arith is not None:
        if len(args) < 2:
            raise SyntaxError(f'{op} 需要两个参数')
        lhs = cg._unbox_int(compile_node(args[0], cg))
        rhs = cg._unbox_int(compile_node(args[1], cg))
        # 除/余：零除检查
        if op in ('除', 'div', '余', 'mod'):
            _check_div_zero(lhs, rhs, cg)
        return cg._box_int(getattr(cg.builder, arith)(lhs, rhs, name=f'{op}_tmp'))

    # ── 内置比较（i8* → unbox → icmp → zext → rebox）──
    cmp_op = _COMPARE_OPS.get(op)
    if cmp_op is not None:
        if len(args) < 2:
            raise SyntaxError(f'{op} 需要两个参数')
        lhs = cg._unbox_int(compile_node(args[0], cg))
        rhs = cg._unbox_int(compile_node(args[1], cg))
        cond = cg.builder.icmp_signed(cmp_op, lhs, rhs, name=f'{op}_tmp')
        return cg._box_int(cg.builder.zext(cond, _INT, name=f'{op}_bool'))

    # ── 逻辑运算 ──
    logic_op = _LOGIC_OPS.get(op)
    if logic_op is not None:
        if len(args) < 2:
            raise SyntaxError(f'{op} 需要两个参数')
        lhs = cg._unbox_int(compile_node(args[0], cg))
        rhs = cg._unbox_int(compile_node(args[1], cg))
        lb = cg.builder.icmp_signed('!=', lhs, _ZERO, name=f'{op}_lb')
        rb = cg.builder.icmp_signed('!=', rhs, _ZERO, name=f'{op}_rb')
        res = cg.builder.and_(lb, rb) if logic_op == 'and' else cg.builder.or_(lb, rb)
        return cg._box_int(cg.builder.zext(res, _INT, name=f'{op}_bool'))

    # ── 非 ──
    if op in ('非', 'not'):
        if len(args) < 1:
            raise SyntaxError(f'{op} 需要至少一个参数')
        val = cg._unbox_int(compile_node(args[0], cg))
        b = cg.builder.icmp_signed('!=', val, _ZERO, name='not_val')
        return cg._box_int(cg.builder.zext(cg.builder.not_(b), _INT, name='not_bool'))

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
        if op in ('列表', 'list') and len(args) > 0:
            return _compile_list_create(args, cg)
        # dict/字典 需要逐对 set
        if op in ('字典', 'dict') and len(args) > 0:
            return _compile_dict_create(args, cg)
        # 连接/列表合 支持变参：两两折叠调用
        if op in ('连接', 'concat', '列表合', 'list_concat') and len(args) > 2:
            return _compile_fold(op, args, rt_func, cg)
        return _dispatch_runtime(op, args, rt_func, cg)

    # ── 定义变量 (设 name value) ──
    if op in ('设', 'set'):
        if len(args) < 2:
            raise SyntaxError(f'{op} 需要 (变量名 值)')
        name = args[0]
        if not isinstance(name, str):
            raise SyntaxError(f'变量名必须是字符串: {name}')
        val = compile_node(args[1], cg)
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
            # 使用 tag 区分 int/str：bit0=1 → 整数, bit0=0 → 字符串指针
            is_int = cg._is_tagged_int(val)
            int_block = cg._add_block(name='pr_int')
            str_block = cg._add_block(name='pr_str')
            pr_done = cg._add_block(name='pr_done')
            cg.builder.cbranch(is_int, int_block, str_block)

            cg.builder.position_at_start(int_block)
            cg.emit_print_int(val)
            cg.builder.branch(pr_done)

            cg.builder.position_at_start(str_block)
            cg.emit_print_str(val)
            cg.builder.branch(pr_done)

            cg.builder.position_at_start(pr_done)
        return _NULL

    # ── 若条件 ──
    if op in ('若', 'if'):
        return _compile_if(args, cg)

    # ── 遍历 (遍历 var 从 start 到 end body) ──
    if op in ('遍历', 'for'):
        return _compile_for(args, cg)

    # ── 循环 (循环 条件 体) ──
    if op in ('循环', 'loop'):
        if len(args) < 2:
            raise SyntaxError(f'{op} 需要 (条件 体)')

        body_exprs = _unwrap_block(args[1])

        loop_h = cg._add_block(name='loop_h')
        loop_b = cg._add_block(name='loop_b')
        loop_e = cg._add_block(name='loop_e')

        cg._loop_stack.append((loop_h, loop_e))  # push 循环上下文
        cg.builder.branch(loop_h)

        cg.builder.position_at_start(loop_h)
        cond_val = compile_node(args[0], cg)
        cond = cg.builder.icmp_signed('!=', cg._unbox_int(cond_val), _ZERO, name='loop_cond')
        cg.builder.cbranch(cond, loop_b, loop_e)

        cg.builder.position_at_start(loop_b)
        for stmt in body_exprs:
            compile_node(stmt, cg)
        if not cg.builder.block.is_terminated:
            cg.builder.branch(loop_h)

        cg.builder.position_at_start(loop_e)
        cg._loop_stack.pop()  # pop
        return _NULL

    # ── 返回 (返回 expr) ──
    if op in ('返回', 'return'):
        val = compile_node(args[0], cg) if args else _NULL
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
        return _dispatch_runtime('取', [op, args[0]], cg._get_runtime_func('取'), cg)

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
        arg_vals = [compile_node(a, cg) for a in args]
        return cg.builder.call(callee, arg_vals, name=f'call_{op}')

    # ── 未知操作 → 当作前向引用函数调用 ──
    resolved_op = op.split('.')[-1] if '.' in op else op
    if resolved_op in cg._funcs:
        arg_vals = [compile_node(a, cg) for a in args]
        return cg.builder.call(cg._funcs[resolved_op], arg_vals, name=f'call_{op}')
    raise NameError(f'编译错误: 未定义的操作或函数 {op}')


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


def compile_top_level(ast_nodes: list, module_name: str = 'main') -> CodegenContext:
    """编译顶层 AST 节点列表。返回 CodegenContext 用于验证/导出。"""
    cg = CodegenContext(module_name)

    # 若顶层是单个 做/do 块，展开其内部语句
    if isinstance(ast_nodes, list) and len(ast_nodes) > 0 and ast_nodes[0] in ('做', 'do'):
        ast_nodes = ast_nodes[1:]

    # 规范化 fn 格式: ['fn', 'name', ['p'], body] → ['fn', ['name', 'p'], body]
    ast_nodes = _normalize_fn_format(ast_nodes)

    # 规范化：合并 再若/否则 到前一个 若 节点
    ast_nodes = _merge_if_chain(ast_nodes)

    def collect_and_compile(nodes):
        """三遍：全局变量 → 函数定义 → main(顶层代码)。"""
        nodes, imported_setups = _resolve_imports(nodes, cg)

        defs = []
        others = []
        for node in nodes:
            if isinstance(node, list) and len(node) > 0 and node[0] in ('定义', 'define', 'fn'):
                defs.append(node)
            else:
                others.append(node)

        # 第 0 遍：预创建顶层 设 为全局变量
        for node in others + imported_setups:
            if isinstance(node, list) and len(node) >= 3 and node[0] in ('设', 'set'):
                name = node[1]
                if isinstance(name, str) and not name.startswith('_'):
                    val = node[2]
                    if isinstance(val, (int, float)):
                        cg.create_global(name, val)
                    elif isinstance(val, str) and _is_string_literal(val):
                        cg.create_global(name, _unquote(val))
                    else:
                        # 复杂表达式（dict, list 等）→ 存 AST 节点
                        cg.create_global(name, val)
                        # Mark that this needs runtime init
                        cg._global_inits.append((name, val))

        # 第一遍：先注册所有函数名（预创建空函数），解决前向引用
        class _DeferredFn:
            def __init__(self, node):
                self.node = node

        deferred: list[_DeferredFn] = []
        for node in defs:
            deferred.append(_DeferredFn(node))
            # fn 格式: ['fn', 'name', ['p1', ...], body...]
            if isinstance(node[1], list):
                name = node[1][0]
                params = node[1][1:]
            elif node[0] == 'fn' and len(node) >= 3:
                # _bootstrap.san 格式: ['fn', 'name', ['p'], e1, ...]
                name = node[1]
                params = node[2] if isinstance(node[2], list) else []
            else:
                name = node[1] if isinstance(node[1], str) else str(node[1])
                params = node[2] if len(node) > 2 and isinstance(node[2], list) else []
            cg.begin_function(name, params)
            # 不调用 end_function：留空体让第二遍填充

        # 第二遍：重新编译每个函数体
        for d in deferred:
            compile_node(d.node, cg)

        # 若编译 bootstrap，添加 ASCII 入口包装
        if module_name == 'bootstrap' and '解析' in cg._funcs:
            _make_bootstrap_harness(cg)

        # 第三遍：编译顶层代码（放入 main 函数），含全局变量初始化
        # bootstrap 模块由 harness 提供 main，跳过
        all_others = imported_setups + others
        if module_name != 'bootstrap' and (all_others or cg._global_inits):
            cg.begin_function('main', [])
            # 全局变量初始化
            for gname, gval in cg._global_inits:
                if isinstance(gval, (int, float)):
                    init_val = cg._box_int(ir.Constant(_INT, int(gval)))
                elif isinstance(gval, str):
                    init_val = cg._make_rt_string(gval)
                else:
                    init_val = _NULL
                cg.builder.store(init_val, cg._globals[gname])
            for node in all_others:
                compile_node(node, cg)
            cg.end_function()
        elif module_name != 'bootstrap':
            cg.begin_function('main', [])
            cg.end_function()

    collect_and_compile(ast_nodes)
    return cg
