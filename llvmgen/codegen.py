"""三言 AST → LLVM IR 代码生成器"""

from __future__ import annotations
from llvmlite import ir

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
    # 等待
    '等待': ('rt_sleep', ir.VoidType(), [_INT]),
    'wait': ('rt_sleep', ir.VoidType(), [_INT]),
    # 文件操作
    '读文件': ('rt_read_file', _PTR, [_PTR]),
    '写文件': ('rt_write_file', ir.VoidType(), [_PTR, _PTR]),
    # 字符串操作
    '连接': ('rt_str_concat', _PTR, [_PTR, _PTR]),
    'concat': ('rt_str_concat', _PTR, [_PTR, _PTR]),
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
        self.module.triple = 'x86_64-pc-linux-gnu'
        self._printf = None
        self._builder: ir.IRBuilder | None = None
        self._entry_block: ir.Block | None = None
        self._scope: dict[str, ir.Value] = {}  # 当前函数作用域
        self._funcs: dict[str, ir.Function] = {}  # 已定义的函数
        self._current_func: ir.Function | None = None
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
        """创建函数并进入其 entry 块。所有变量存储为 i8*。"""
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
        # 参数分配局部变量 (i8*)
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
        """i32 → i8* 装箱。"""
        return self.builder.inttoptr(int_val, _PTR, name='box')

    def _unbox_int(self, ptr_val: ir.Value) -> ir.Value:
        """i8* → i32 拆箱。"""
        return self.builder.ptrtoint(ptr_val, _INT, name='unbox')

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
        """生成 printf(\"%s\\n\", value) 调用。"""
        fmt = self._make_global_string('%s\n')
        self.builder.call(self._printf, [fmt, value])

    def emit_print(self, fmt: str, value: ir.Value):
        """生成 printf 调用。"""
        fmt_ptr = self._make_global_string(fmt)
        self.builder.call(self._printf, [fmt_ptr, value])

    def _make_global_string(self, s: str) -> ir.Value:
        n = len(self.module.globals)
        c = ir.Constant(ir.ArrayType(ir.IntType(8), len(s) + 1), bytearray(s + '\0', 'utf-8'))
        gv = ir.GlobalVariable(self.module, c.type, name=f'.str.{n}')
        gv.linkage = 'private'
        gv.global_constant = True
        gv.initializer = c
        return self.builder.gep(gv, [_ZERO, _ZERO], inbounds=True)

    def get_var(self, name: str) -> ir.Value:
        """加载变量值，返回 i8*（需调用方按需拆箱为 i32）。"""
        if name in self._scope:
            return self.builder.load(self._scope[name], name=name)
        if name in self._funcs:
            raise NameError(f'{name} 是函数，不能当作变量')
        raise NameError(f'编译错误: 未定义变量 {name}')

    def set_var(self, name: str, value: ir.Value):
        """存储变量值。i32 自动装箱为 i8*，i8* 直接存储。"""
        if isinstance(value.type, ir.PointerType):
            pass  # 已是指针，直接存储
        else:
            value = self._box_int(value)
        if name in self._scope:
            self.builder.store(value, self._scope[name])
        else:
            alloca = self.builder.alloca(_PTR, name=name)
            self.builder.store(value, alloca)
            self._scope[name] = alloca

    def compile_fn_body(self, name: str, param_names: list[str], body: list):
        """编译函数体（处理 定义 AST）。"""
        self.begin_function(name, param_names)
        for stmt in body:
            compile_node(stmt, self)
        self.end_function()

    def verify(self) -> str:
        """验证模块并返回 IR 文本。"""
        try:
            return str(self.module)
        except Exception as e:
            raise RuntimeError(f'LLVM IR 生成失败: {e}') from e


# ── 辅助函数 ──


def _unwrap_block(node):
    """展开 做/do 块，返回内部表达式列表。"""
    if isinstance(node, list) and len(node) > 0 and node[0] in ('做', 'do'):
        return node[1:]
    if isinstance(node, list):
        return node
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
    phi_incoming: list[tuple[ir.Value, ir.Block]] = []

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
            cg.builder.branch(merge_block)
            phi_incoming.append((body_val if body_val is not None else _ZERO, body_block))

        cg.builder.position_at_start(next_test)

    if final_else is not None:
        else_block = cg._add_block(name='if_else')
        cg.builder.branch(else_block)
        cg.builder.position_at_start(else_block)
        for e in final_else:
            else_val = compile_node(e, cg)
        if not cg.builder.block.is_terminated:
            cg.builder.branch(merge_block)
            phi_incoming.append((else_val if else_val is not None else _ZERO, else_block))
    else:
        cg.builder.branch(merge_block)

    cg.builder.position_at_start(merge_block)
    if phi_incoming:
        phi = cg.builder.phi(_PTR, name='if_result')
        for val, blk in phi_incoming:
            phi.add_incoming(val, blk)
        return phi
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
        # 容器遍历：桩 — 编译容器表达式但不迭代
        compile_node(args[1], cg)
        return _NULL

    # 分配循环变量
    loop_var = cg.builder.alloca(_PTR, name=var_name)
    cg.builder.store(start_val, loop_var)
    saved = cg._scope.get(var_name)
    cg._scope[var_name] = loop_var

    loop_h = cg._add_block(name='for_h')
    loop_b = cg._add_block(name='for_b')
    loop_e = cg._add_block(name='for_e')

    cg.builder.branch(loop_h)

    cg.builder.position_at_start(loop_h)
    cur = cg._unbox_int(cg.builder.load(loop_var, name=f'{var_name}_val'))
    end_i32 = cg._unbox_int(end_val)
    cond = cg.builder.icmp_signed('<=', cur, end_i32, name='for_cond')
    cg.builder.cbranch(cond, loop_b, loop_e)

    cg.builder.position_at_start(loop_b)
    for expr in body_exprs:
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
    return _NULL


def _compile_fold(op: str, args: list, func: ir.Function, cg: CodegenContext) -> ir.Value:
    """变参操作的折叠编译：两两调用运行时函数。

    例如: 连接(a, b, c, d) → rt_str_concat(rt_str_concat(rt_str_concat(a, b), c), d)
    """
    spec = _RUNTIME_FUNCS[op]
    param_types = spec[2]
    ret_type = spec[1]

    def _call(a, b):
        a_u = cg._unbox_int(a) if isinstance(param_types[0], ir.IntType) else a
        b_u = cg._unbox_int(b) if isinstance(param_types[1], ir.IntType) else b
        r = cg.builder.call(func, [a_u, b_u], name=f'rt_{op}')
        if isinstance(ret_type, ir.IntType):
            return cg._box_int(r)
        return r

    compiled = [compile_node(a, cg) for a in args]
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
            call_args.append(_NULL)
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

    if isinstance(node, str):
        # 内置常量
        if node in _BUILTIN_CONSTS:
            return cg._box_int(ir.Constant(_INT, _BUILTIN_CONSTS[node]))
        # 字符串字面量 → i8*
        if _is_string_literal(node):
            return cg._make_global_string(_unquote(node))
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

    # ── 运行时函数调用 ──
    rt_func = cg._get_runtime_func(op)
    if rt_func is not None:
        # IoT 操作：自动为裸标识符参数加引号
        if op in ('读', '查', '置', '对', 'read', 'query', 'write', 'with'):
            args = [_quote_if_ident(a) for a in args]
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
            # 字符串字面量直接打印
            if isinstance(raw, str) and _is_string_literal(raw):
                cg.emit_print_str(cg._make_global_string(_unquote(raw)))
                return _NULL
            val = compile_node(raw, cg)
            if val is None:
                return _NULL
            # 判断：若值是指向全局字符串常量的 GEP，按字符串打印
            if _from_global_string(val):
                cg.emit_print_str(val)
            else:
                cg.emit_print_int(val)
        return _NULL

    # ── 若条件 ──
    if op in ('若', 'if'):
        return _compile_if(args, cg)

    # ── 遍历 (遍历 var 从 start 到 end body) ──
    if op in ('遍历', 'for'):
        return _compile_for(args, cg)

    # ── 尝试 (尝试 body 捕获 (err) handler) — 阶段 3 简化为只执行 try 体 ──
    if op in ('尝试', 'try'):
        return compile_node(args[0], cg)

    # ── 循环 (循环 条件 体) ──
    if op in ('循环', 'loop'):
        if len(args) < 2:
            raise SyntaxError(f'{op} 需要 (条件 体)')

        # 展开 做/do 包裹的体
        body_exprs = _unwrap_block(args[1])

        loop_h = cg._add_block(name='loop_h')
        loop_b = cg._add_block(name='loop_b')
        loop_e = cg._add_block(name='loop_e')

        cg.builder.branch(loop_h)

        # 条件块
        cg.builder.position_at_start(loop_h)
        cond_val = compile_node(args[0], cg)
        cond = cg.builder.icmp_signed('!=', cg._unbox_int(cond_val), _ZERO, name='loop_cond')
        cg.builder.cbranch(cond, loop_b, loop_e)

        # 体块
        cg.builder.position_at_start(loop_b)
        for stmt in body_exprs:
            compile_node(stmt, cg)
        if not cg.builder.block.is_terminated:
            cg.builder.branch(loop_h)

        cg.builder.position_at_start(loop_e)
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
        name = args[0]
        if not isinstance(name, str):
            name = args[0][0] if isinstance(args[0], list) else str(args[0])
        params = args[1] if isinstance(args[1], list) else []
        body = _unwrap_block(args[2]) if len(args) > 2 else []
        cg.compile_fn_body(name, params, body)
        return _NULL

    # ── 变量作为容器索引：列表名(索引) → 取(列表名, 索引) ──
    if op in cg._scope and len(args) == 1:
        assert cg._get_runtime_func('取') is not None
        return _dispatch_runtime('取', [op, args[0]], cg._get_runtime_func('取'), cg)

    # ── 函数调用 ──
    if op in cg._funcs:
        callee = cg._funcs[op]
        arg_vals = [compile_node(a, cg) for a in args]
        return cg.builder.call(callee, arg_vals, name=f'call_{op}')

    # ── 未知操作 → 当作前向引用函数调用 ──
    arg_vals = [compile_node(a, cg) for a in args]
    if op in cg._funcs:
        return cg.builder.call(cg._funcs[op], arg_vals, name=f'call_{op}')
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


def compile_top_level(ast_nodes: list, module_name: str = 'main') -> CodegenContext:
    """编译顶层 AST 节点列表。返回 CodegenContext 用于验证/导出。"""
    cg = CodegenContext(module_name)

    # 若顶层是单个 做/do 块，展开其内部语句
    if isinstance(ast_nodes, list) and len(ast_nodes) > 0 and ast_nodes[0] in ('做', 'do'):
        ast_nodes = ast_nodes[1:]

    # 过滤裸露的 IoT 关键字（糖解析器不支持 置/读/查 语法时产生）

    # 规范化：合并 再若/否则 到前一个 若 节点
    ast_nodes = _merge_if_chain(ast_nodes)

    def collect_and_compile(nodes):
        """两遍：先收集 定义，再编译 设/表达式/调用。"""
        defs = []
        others = []
        for node in nodes:
            if isinstance(node, list) and len(node) > 0 and node[0] in ('定义', 'define', 'fn'):
                defs.append(node)
            else:
                others.append(node)

        # 第一遍：收集所有函数定义
        for node in defs:
            compile_node(node, cg)

        # 第二遍：编译顶层代码（放入 main 函数）
        if others:
            cg.begin_function('main', [])
            for node in others:
                compile_node(node, cg)
            cg.end_function()
        else:
            # 没有顶层代码则生成空 main
            cg.begin_function('main', [])
            cg.end_function()

    collect_and_compile(ast_nodes)
    return cg
