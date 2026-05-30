"""三言 LLVM 代码生成 — 控制流编译。

编译 若/判/遍历/循环/尝试 等控制流 AST 节点到 LLVM IR。
从 ops_gen.py 拆分而来。
"""

from __future__ import annotations

from llvmlite import ir

from llvmgen.ir_builder import CodegenContext, _unwrap_block
from llvmgen.type_mapping import _INT, _I32, _NULL, _ONE, _PTR, _ZERO


# 延迟导入 compile_node 避免循环依赖
def _get_compile_node():
    """获取 compile_node 函数引用（延迟导入避免循环依赖）。"""
    from llvmgen.ops_gen import compile_node

    return compile_node


def _compile_if(args: list, cg: CodegenContext) -> ir.Value | None:
    """编译 若/if 结构，支持 再若/else-if 和 否则/else。

    AST 格式（合并后）:
      ['若', cond, then]                              — 纯 if
      ['若', cond, then, else]                        — if-else
      ['若', cond, then, ['若', c2, t2]]               — if-elif (嵌套)
      ['若', cond, then, ['再若', c2], body2, '否则', else] — if-elif-else
    """
    compile_node = _get_compile_node()

    # 收集所有分支：(cond, body)
    branches: list[tuple[ir.Value | list, list]] = []
    final_else: list | None = None

    branches.append((args[0], args[1]))
    i = 2
    while i < len(args):
        item = args[i]
        if isinstance(item, list) and len(item) > 0:
            if item[0] == '若':
                branches.append((item[1], item[2]))
                i += 1
            elif item[0] == '再若':
                cond_node = item[1] if len(item) > 1 else _ZERO
                i += 1
                body_node = args[i] if i < len(args) else _ZERO
                i += 1
                branches.append((cond_node, body_node))
            elif item[0] == '否则':
                final_else = item[1:]
                i += 1
            elif len(args) == 3 and i == 2:
                final_else = [item]
                i += 1
            else:
                i += 1
        elif isinstance(item, str) and item == '否则':
            i += 1
            if i < len(args):
                final_else = [args[i]]
            i += 1
        elif len(args) == 3 and i == 2:
            final_else = [item]
            i += 1
        else:
            i += 1

    merge_block = cg._add_block(name='if_merge')
    result_alloca = cg._entry_alloca('if_res')
    cg.builder.store(_NULL, result_alloca)

    has_terminated_branch = False
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
        else:
            has_terminated_branch = True

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
            has_terminated_branch = True
    else:
        cg.builder.branch(merge_block)

    cg.builder.position_at_start(merge_block)
    result = cg.builder.load(result_alloca, name='if_result')
    return result


def _compile_judge(args: list, cg: CodegenContext) -> ir.Value | None:
    """编译 判/三态分支。AST: ['判', val, true_body, maybe_body, false_body]"""
    compile_node = _get_compile_node()
    val = cg._to_bool_i1(compile_node(args[0], cg))

    true_block = cg._add_block(name='judge_true')
    maybe_block = cg._add_block(name='judge_maybe')
    false_block = cg._add_block(name='judge_false')
    merge_block = cg._add_block(name='judge_end')

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
    """编译匿名函数（lambda）。

    创建独立函数，编译函数体，返回函数指针。
    保存/恢复调用者的编译上下文（作用域、分配器、构建器）。
    """
    compile_node = _get_compile_node()
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
    """编译 尝试/捕获 异常处理结构。

    在每个 try 语句后检查 @g_error，若非空则跳转到 catch 块。
    catch 块中将错误信息绑定到变量，执行处理体后清除错误状态。
    """
    compile_node = _get_compile_node()
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

    cg.builder.store(_NULL, g_error)
    cg._try_depth += 1

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
    """检查 @g_error 并生成异常展开代码。

    若不在 try 块内且 g_error 非空，生成条件分支：
    - 有错误：加载错误值并 ret（展开到调用者）
    - 无错误：继续正常执行
    """
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
      ['遍历', var, container, body]    — 容器遍历
    """
    compile_node = _get_compile_node()
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
        container = compile_node(args[1], cg)
        len_func = cg._get_runtime_func('表长')
        assert len_func is not None
        len_val = cg.builder.call(len_func, [container], name='list_len')
        len_i32 = len_val
        len_i64 = cg.builder.zext(len_i32, _INT, name='len_widen')
        end_i64 = cg.builder.sub(len_i64, _ONE, name='end_idx')
        start_val = cg._box_int(_ZERO)
        end_val = cg._box_int(end_i64)
        is_range = True
        get_func = cg._get_runtime_func('取')
        assert get_func is not None
        _orig_body = body_exprs

        def _make_container_body():
            """生成容器遍历体：取元素 → 设变量 → 执行原始体。"""
            idx_ptr = cg.builder.load(loop_var, name='idx_ptr')
            idx_i64 = cg._unbox_int(idx_ptr)
            idx_i32 = cg.builder.trunc(idx_i64, _I32, name='idx_i32')
            elem = cg.builder.call(get_func, [container, idx_i32], name='elem')
            cg.set_var(var_name, elem)
            for e in _orig_body:
                compile_node(e, cg)

        body_exprs = [('__container_body__', _make_container_body)]

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
            expr[1]()
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
