"""三言 LLVM 代码生成 — IR 构建器。

本模块提供 CodegenContext 类，封装 LLVM 模块、IRBuilder、
符号表、变量作用域管理、装箱/拆箱、运行时函数声明等低级 IR 构建操作。
"""

from __future__ import annotations

from llvmlite import ir

from llvmgen.type_mapping import (
    _INT,
    _I32,
    _NULL,
    _ONE,
    _ONE32,
    _PTR,
    _RUNTIME_FUNCS,
    _ZERO,
    _ZERO32,
    BoxedValue,
    RawValue,
)


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
        return self.builder.bitcast(gv, _PTR, name=f'.rt_str_p{n}')

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
        from llvmgen.ops_gen import compile_node  # 延迟导入避免循环依赖

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
