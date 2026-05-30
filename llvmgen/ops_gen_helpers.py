"""三言 LLVM 代码生成 — 算术辅助与容器编译。

浮点转换、除零检查、列表/字典创建、运行时分发等辅助函数。
从 ops_gen.py 拆分而来。
"""

from __future__ import annotations

from llvmlite import ir

from llvmgen.ir_builder import CodegenContext
from llvmgen.type_mapping import (
    _I32,
    _INT,
    _NULL,
    _ONE,
    _PTR,
    _RUNTIME_FUNCS,
    _ZERO,
    BoxedValue,
    RawValue,
    _is_string_literal,
    _to_int,
    _unquote,
)


# 延迟导入 compile_node 避免循环依赖
def _get_compile_node():
    """获取 compile_node 函数引用（延迟导入避免循环依赖）。"""
    from llvmgen.ops_gen import compile_node

    return compile_node


def _check_div_zero(lhs: ir.Value, rhs: ir.Value, cg: CodegenContext):
    """插入零除运行时检查。若 rhs == 0，调用 rt_throw。

    当检测条件是常量 true（即除数恒为 0）时，直接 emit unreachable。
    这避免了 rt_throw 总被执行从而污染 g_error 影响后续 unwind 检查。
    (div 1 0) 在三言中用作 panic 路径，正常流程不应到达。
    """
    is_zero = cg.builder.icmp_signed('==', rhs, _ZERO, name='div_zero')

    if isinstance(is_zero, ir.Constant) and is_zero.constant == 1:
        cg.builder.unreachable()
        return

    if isinstance(is_zero.type, ir.IntType) and is_zero.type.width == 1:
        ok_block = cg._add_block(name='div_ok')
        err_block = cg._add_block(name='div_err')
        cg.builder.cbranch(is_zero, err_block, ok_block)

        cg.builder.position_at_start(err_block)
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
    """判断值是否来自 rt_float_new 调用（即浮点数字面量）。"""
    return isinstance(val, ir.Instruction) and val.opname == 'call' and val.callee.name == 'rt_float_new'


def _val_to_double(val, is_float: bool, cg: CodegenContext) -> ir.Value:
    """将值转换为 LLVM double 类型。

    处理三种情况：
    - RawValue（未装箱整数）→ sitofp
    - 浮点值（is_float=True）→ rt_unbox_float
    - 标记指针（tagged int）→ ptrtoint + ashr + sitofp
    """
    if isinstance(val, RawValue):
        return cg.builder.sitofp(val.ll_val, ir.DoubleType(), name='tof')
    v = val.ll_val if isinstance(val, BoxedValue) else val
    if is_float:
        return cg.builder.call(cg._get_runtime_func('rt_unbox_float'), [v], name='unbox_f')
    raw = cg.builder.ptrtoint(v, _INT, name='tof_raw')
    ival = cg.builder.ashr(raw, _ONE, name='tof_int')
    return cg.builder.sitofp(ival, ir.DoubleType(), name='tof')


def _check_div_zero_f(lhs: ir.Value, rhs: ir.Value, cg: CodegenContext) -> None:
    """浮点除零检查。若 rhs == 0.0，调用 rt_throw 并返回错误。"""
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
    compile_node = _get_compile_node()
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
    compile_node = _get_compile_node()
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
    compile_node = _get_compile_node()
    is_str_op = op in ('连接', 'concat')

    def _to_str(v):
        """将非字符串值转换为字符串（调用 rt_int_to_str）。"""
        if isinstance(v, RawValue):
            int_to_str = cg._get_runtime_func('rt_int_to_str')
            return cg.builder.call(int_to_str, [cg._box_int(v.ll_val)], name='to_str')
        if isinstance(v, BoxedValue):
            return v.ll_val
        return v

    def _call(a, b):
        """调用运行时函数处理两个操作数。"""
        return cg.builder.call(func, [a, b], name=f'rt_{op}')

    compiled = [compile_node(a, cg) for a in args]
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
    compile_node = _get_compile_node()
    compiled = [compile_node(a, cg) for a in args]
    spec = _RUNTIME_FUNCS.get(op)
    if spec is None:
        raise NameError(f'编译错误: 未定义的运行时函数 {op}')
    param_types = spec[2]
    ret_type = spec[1]
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
            ret = cg.builder.sext(ret, _INT, name='sext')
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
    """将值转换为 i8* 指针（装箱 RawValue 或提取 BoxedValue）。"""
    if isinstance(val, RawValue):
        return cg._box_int(val.ll_val)
    if isinstance(val, BoxedValue):
        return val.ll_val
    return val


def _unwrap_call_arg(val, cg: CodegenContext) -> ir.Value:
    """解包函数调用参数：RawValue 装箱，BoxedValue 提取底层指针。"""
    if isinstance(val, RawValue):
        return cg._box_int(val.ll_val)
    if isinstance(val, BoxedValue):
        return val.ll_val
    return val
