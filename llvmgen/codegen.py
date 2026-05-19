"""三言 AST → LLVM IR 代码生成器"""

from __future__ import annotations
from llvmlite import ir

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
}

_TYPE = ir.IntType(32)
_ZERO = ir.Constant(_TYPE, 0)
_ONE = ir.Constant(_TYPE, 1)


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
        # 声明外部运行时函数
        self._declare_runtime()

    def _declare_runtime(self):
        """声明外部运行时函数（printf 等）。"""
        if self._printf is None:
            fnty = ir.FunctionType(_TYPE, [ir.PointerType(ir.IntType(8))], var_arg=True)
            self._printf = ir.Function(self.module, fnty, name='printf')

    @property
    def builder(self) -> ir.IRBuilder:
        if self._builder is None:
            raise RuntimeError('builder 未初始化，先调用 begin_function()')
        return self._builder

    def begin_function(self, name: str, param_names: list[str]) -> ir.Function:
        """创建函数并进入其 entry 块。"""
        fnty = ir.FunctionType(_TYPE, [_TYPE] * len(param_names))
        func = ir.Function(self.module, fnty, name=name)
        for i, pname in enumerate(param_names):
            func.args[i].name = pname
        self._funcs[name] = func
        self._current_func = func
        self._scope = {}
        entry = func.append_basic_block(name='entry')
        self._builder = ir.IRBuilder(entry)
        self._entry_block = entry
        # 参数分配局部变量
        for i, pname in enumerate(param_names):
            alloca = self._builder.alloca(_TYPE, name=pname)
            self._builder.store(func.args[i], alloca)
            self._scope[pname] = alloca
        return func

    def end_function(self):
        """结束当前函数（如果未显式返回则补 ret 0）。"""
        if not self._builder.block.is_terminated:
            self._builder.ret(_ZERO)

    def emit_print_int(self, value: ir.Value):
        """生成 printf(\"%d\\n\", value) 调用。"""
        fmt = self._make_global_string('%d\n')
        self.builder.call(self._printf, [fmt, value])

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
        if name in self._scope:
            return self.builder.load(self._scope[name], name=name)
        if name in self._funcs:
            raise NameError(f'{name} 是函数，不能当作变量')
        raise NameError(f'编译错误: 未定义变量 {name}')

    def set_var(self, name: str, value: ir.Value):
        if name in self._scope:
            self.builder.store(value, self._scope[name])
        else:
            alloca = self.builder.alloca(_TYPE, name=name)
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

    merge_block = cg._current_func.append_basic_block(name='if_merge')
    phi_incoming: list[tuple[ir.Value, ir.Block]] = []

    for cond_node, body_node in branches:
        test_block = cg._current_func.append_basic_block(name='if_test')
        body_block = cg._current_func.append_basic_block(name='if_body')
        next_test = cg._current_func.append_basic_block(name='if_next')

        cg.builder.branch(test_block)
        cg.builder.position_at_start(test_block)
        cond_val = compile_node(cond_node, cg)
        cond = cg.builder.icmp_signed('!=', cond_val, _ZERO, name='if_cond')
        cg.builder.cbranch(cond, body_block, next_test)

        cg.builder.position_at_start(body_block)
        body_val = compile_node(body_node, cg)
        if not cg.builder.block.is_terminated:
            cg.builder.branch(merge_block)
            phi_incoming.append((body_val if body_val is not None else _ZERO, body_block))

        cg.builder.position_at_start(next_test)

    if final_else is not None:
        else_block = cg._current_func.append_basic_block(name='if_else')
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
        phi = cg.builder.phi(_TYPE, name='if_result')
        for val, blk in phi_incoming:
            phi.add_incoming(val, blk)
        return phi
    return _ZERO


def _compile_for(args: list, cg: CodegenContext) -> ir.Value | None:
    """编译 遍历/for 循环。

    AST 格式: ['遍历', var_name, start_expr, end_expr, body]
    """
    if len(args) < 4:
        raise SyntaxError('遍历 需要 (变量名 起始 结束 体)')

    var_name = args[0]
    start_val = compile_node(args[1], cg)
    end_val = compile_node(args[2], cg)
    body = args[3]
    if isinstance(body, list) and len(body) > 0 and body[0] in ('做', 'do'):
        body_exprs = body[1:]
    else:
        body_exprs = [body]

    # 分配循环变量
    loop_var = cg.builder.alloca(_TYPE, name=var_name)
    cg.builder.store(start_val, loop_var)
    saved = cg._scope.get(var_name)
    cg._scope[var_name] = loop_var

    loop_h = cg._current_func.append_basic_block(name='for_h')
    loop_b = cg._current_func.append_basic_block(name='for_b')
    loop_e = cg._current_func.append_basic_block(name='for_e')

    cg.builder.branch(loop_h)

    cg.builder.position_at_start(loop_h)
    cur = cg.builder.load(loop_var, name=f'{var_name}_val')
    cond = cg.builder.icmp_signed('<=', cur, end_val, name='for_cond')
    cg.builder.cbranch(cond, loop_b, loop_e)

    cg.builder.position_at_start(loop_b)
    for expr in body_exprs:
        compile_node(expr, cg)
    next_val = cg.builder.add(cg.builder.load(loop_var, name=f'{var_name}_next'), _ONE)
    cg.builder.store(next_val, loop_var)
    if not cg.builder.block.is_terminated:
        cg.builder.branch(loop_h)

    cg.builder.position_at_start(loop_e)
    if saved is not None:
        cg._scope[var_name] = saved
    else:
        cg._scope.pop(var_name, None)
    return _ZERO


# ── 主编译函数 ──


def compile_node(node, cg: CodegenContext) -> ir.Value | None:
    """递归编译 AST 节点，返回 LLVM Value（可能为 None 表示无返回值）。"""

    # 字面量
    if isinstance(node, (int, float)):
        return ir.Constant(_TYPE, int(node))

    if isinstance(node, str):
        # 字符串字面量 → 全局常量指针
        if _is_string_literal(node):
            s = _unquote(node)
            return cg._make_global_string(s)
        n = _to_int(node)
        if n is not None:
            return ir.Constant(_TYPE, n)
        return cg.get_var(node)

    if not isinstance(node, list) or len(node) < 1:
        raise SyntaxError(f'无法识别的 AST 节点: {node}')

    op = node[0]
    args = node[1:]

    # ── 内置二元算术 ──
    arith = _ARITH_OPS.get(op)
    if arith is not None:
        if len(args) < 2:
            raise SyntaxError(f'{op} 需要两个参数')
        lhs = compile_node(args[0], cg)
        rhs = compile_node(args[1], cg)
        return getattr(cg.builder, arith)(lhs, rhs, name=f'{op}_tmp')

    # ── 内置比较 ──
    cmp_op = _COMPARE_OPS.get(op)
    if cmp_op is not None:
        if len(args) < 2:
            raise SyntaxError(f'{op} 需要两个参数')
        lhs = compile_node(args[0], cg)
        rhs = compile_node(args[1], cg)
        cond = cg.builder.icmp_signed(cmp_op, lhs, rhs, name=f'{op}_tmp')
        return cg.builder.zext(cond, _TYPE, name=f'{op}_bool')

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
                s = _unquote(raw)
                str_ptr = cg._make_global_string(s)
                cg.emit_print_str(str_ptr)
                return _ZERO
            val = compile_node(raw, cg)
            # 判断是否为字符串指针 (i8*)
            if isinstance(val.type, ir.PointerType) and isinstance(val.type.pointee, ir.IntType):
                cg.emit_print_str(val)
            else:
                cg.emit_print_int(val)
        else:
            cg.emit_print_int(_ZERO)
        return _ZERO

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

        loop_h = cg._current_func.append_basic_block(name='loop_h')
        loop_b = cg._current_func.append_basic_block(name='loop_b')
        loop_e = cg._current_func.append_basic_block(name='loop_e')

        cg.builder.branch(loop_h)

        # 条件块
        cg.builder.position_at_start(loop_h)
        cond_val = compile_node(args[0], cg)
        cond = cg.builder.icmp_signed('!=', cond_val, _ZERO, name='loop_cond')
        cg.builder.cbranch(cond, loop_b, loop_e)

        # 体块
        cg.builder.position_at_start(loop_b)
        for stmt in args[1] if isinstance(args[1], list) else [args[1]]:
            compile_node(stmt, cg)
        if not cg.builder.block.is_terminated:
            cg.builder.branch(loop_h)

        cg.builder.position_at_start(loop_e)
        return _ZERO

    # ── 返回 (返回 expr) ──
    if op in ('返回', 'return'):
        val = compile_node(args[0], cg) if args else _ZERO
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
        body = args[2] if len(args) > 2 else []
        # 函数体展开（若包在 做 中）
        if isinstance(body, list) and len(body) > 0 and body[0] in ('做', 'do'):
            body = body[1:]
        elif not isinstance(body, list):
            body = [body]
        cg.compile_fn_body(name, params, body)
        return _ZERO

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
    """递归对 AST 节点及其所有子节点进行 if-elif-else 合并。"""
    if isinstance(node, list) and len(node) > 0:
        first = node[0]
        if first in ('做', 'do'):
            # 做块内部需要合并再若/否则
            inner = _merge_if_chain(list(node[1:]))
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
