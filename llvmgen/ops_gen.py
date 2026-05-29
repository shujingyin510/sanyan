"""三言 LLVM 代码生成 — 操作代码生成。

本模块实现各 AST 节点到 LLVM IR 的编译，包括：
- 算术、比较、逻辑运算内联生成
- 若/判/遍历/循环/尝试 等控制流
- 列表/字典/lambda/函数调用
- 运行时函数分发与装箱/拆箱
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
    _ONE,
    _ONE32,
    _PTR,
    _RUNTIME_FUNCS,
    _ZERO,
    _ZERO32,
    _ARITH_OPS,
    BoxedValue,
    RawValue,
    _is_string_literal,
    _to_float_str,
    _to_int,
    _unquote,
)


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
