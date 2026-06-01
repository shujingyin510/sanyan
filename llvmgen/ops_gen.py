"""三言 LLVM 代码生成 — 操作代码生成（主入口）。

本模块实现 AST 节点到 LLVM IR 的主编译逻辑：
- compile_node / _compile_node_inner — 递归编译 AST 节点
- 算术、比较、逻辑运算内联生成
- 变量定义、函数定义、循环、输出等

控制流编译（若/判/遍历/尝试）见 ops_gen_control.py。
算术辅助与容器编译见 ops_gen_helpers.py。
"""

from __future__ import annotations

from llvmlite import ir
from ternary_core import TritValue

from llvmgen.ir_builder import CodegenContext, _unwrap_block
from llvmgen.type_mapping import (
    _BUILTIN_CONSTS,
    _COMPARE_OPS,
    _FLOAT_ARITH,
    _INT,
    _I32,
    _LOGIC_OPS,
    _NULL,
    _ZERO,
    _ARITH_OPS,
    BoxedValue,
    RawValue,
    _is_string_literal,
    _to_float_str,
    _to_int,
    _unquote,
)

# 从拆分模块导入
from llvmgen.ops_gen_control import (
    _compile_if,
    _compile_judge,
    _compile_lambda,
    _compile_try_catch,
    _maybe_unwind,
    _compile_for,
)
from llvmgen.ops_gen_helpers import (
    _check_div_zero,
    _check_div_zero_f,
    _compile_dict_create,
    _compile_fold,
    _compile_list_create,
    _dispatch_runtime,
    _is_float_call,
    _quote_if_ident,
    _unwrap_call_arg,
    _val_to_double,
)


# ── 公共入口 ──


def compile_node(node, cg: CodegenContext) -> ir.Value | None:
    result = _compile_node_inner(node, cg)
    if isinstance(result, RawValue):
        return cg._box_int(result.ll_val)
    if isinstance(result, BoxedValue):
        return result.ll_val
    return result


def _compile_raw(node, cg: CodegenContext):
    """编译节点，保留原始类型信息（RawValue 不装箱）。

    用于算术/比较/逻辑的内部操作数——避免 装箱→拆箱 的来回。
    调用方需自行处理可能返回的 RawValue 或指针值。
    """
    return _compile_node_inner(node, cg)


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
        # 先查变量（优先于零参内置函数）
        try:
            return cg.get_var(node)
        except NameError:
            pass
        # 零参内置函数（如 time）→ 自动调用
        rt = cg._get_runtime_func(node)
        if rt is not None:
            return _dispatch_runtime(node, [], rt, cg)
        raise NameError(f'编译错误: 未定义变量 {node}')

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
        lv = _compile_raw(args[0], cg)
        rv = _compile_raw(args[1], cg)
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
            # AST 级别常量检测：若除数恒为 0，跳过 div-zero 检查和 sdiv
            div_by_const_zero = isinstance(args[1], (int, str)) and str(args[1]) == '0'
            if not div_by_const_zero:
                _check_div_zero(l_raw, r_raw, cg)
                return RawValue(getattr(cg.builder, arith)(l_raw, r_raw, name=f'{op}_tmp'))
            # 常量除零：返回 0（此路径不应被到达）
            return RawValue(_ZERO)
        return RawValue(getattr(cg.builder, arith)(l_raw, r_raw, name=f'{op}_tmp'))

    # ── 内置比较（raw i64 → icmp → RawValue(i1/i64)）──
    cmp_op = _COMPARE_OPS.get(op)
    if cmp_op is not None:
        if len(args) < 2:
            raise SyntaxError(f'{op} 需要两个参数')
        l_raw = cg._to_raw(_compile_raw(args[0], cg)).ll_val
        r_raw = cg._to_raw(_compile_raw(args[1], cg)).ll_val
        cond = cg.builder.icmp_signed(cmp_op, l_raw, r_raw, name=f'{op}_tmp')
        return RawValue(cg.builder.zext(cond, _INT, name=f'{op}_bool'))

    # ── 逻辑运算 ──
    logic_op = _LOGIC_OPS.get(op)
    if logic_op is not None:
        if len(args) < 2:
            raise SyntaxError(f'{op} 需要两个参数')
        l_bool = cg._to_bool_i1(_compile_raw(args[0], cg))
        r_bool = cg._to_bool_i1(_compile_raw(args[1], cg))
        res = cg.builder.and_(l_bool, r_bool) if logic_op == 'and' else cg.builder.or_(l_bool, r_bool)
        return RawValue(cg.builder.zext(res, _INT, name=f'{op}_bool'))

    # ── 非 ──
    if op in ('非', 'not'):
        if len(args) < 1:
            raise SyntaxError(f'{op} 需要至少一个参数')
        b = cg._to_bool_i1(_compile_raw(args[0], cg))
        return RawValue(cg.builder.zext(cg.builder.not_(b), _INT, name='not_bool'))

    # ── 判 三态分支 ──
    if op in ('判', 'judge'):
        if len(args) < 2:
            raise SyntaxError(f'{op} 需要 (值 真分支 [可能分支] [假分支])')
        return _compile_judge(args, cg)

    # ── 函数 匿名 lambda ──
    if op in ('函数', 'lambda'):
        return _compile_lambda(args, cg)

    # ── 尝试 (尝试 body 捕获 (err) handler) ──
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
        if isinstance(val, RawValue):
            cg._get_alloca(name, is_int=True)
            cg.set_var_raw(name, val.ll_val)
        elif isinstance(val, (ir.Instruction, BoxedValue)):
            bv = val.ll_val if isinstance(val, BoxedValue) else val
            if name in cg._allocas and cg._allocas[name][1]:
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

    # ── 再若/否则 — 在 sugar.san fallback 中作为独立节点，跳过（_compile_if 已处理）
    if op in ('再若', '否则', 'elif', 'else'):
        return _NULL

    # ── 遍历 ──
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
    # 单元素列表 → 变量引用（排除字符串字面量）
    if isinstance(node, list) and len(node) == 1 and isinstance(node[0], str):
        if not (node[0].startswith('"') or node[0].startswith("'")):
            return cg.get_var(node[0])
    raise NameError(f'编译错误: 未定义的操作或函数 {op}')
