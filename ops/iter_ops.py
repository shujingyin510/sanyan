"""函数式操作：Lambda、映射、过滤、归并、应用、模块调用。"""

from ternary_core import TritValue, ArrayValue
from values import FunctionValue, ModuleValue, call_function
from values import SanyanSyntaxError, SanyanTypeError, SanyanValueError
from ops.registry import register


def _make_lambda(evaluator, args):
    """Lambda 表达式：函数(参数列表, 体...)"""
    if len(args) < 2:
        raise SanyanSyntaxError('λ 需要参数列表和体')
    params = args[0]
    if not isinstance(params, list):
        raise SanyanSyntaxError('λ 的参数必须是列表')
    body = args[1:]
    closure_vars = evaluator.all_scoped_vars()
    return FunctionValue(params, body, closure_vars=closure_vars)


def _apply(evaluator, args):
    """应用函数：应用(函数, 参数...)"""
    if len(args) < 1:
        raise SanyanSyntaxError('应用 需要函数和参数')
    func = evaluator.eval(args[0])
    func_args = [evaluator.eval(a) for a in args[1:]]
    return call_function(evaluator, func, func_args)


def _map_op(evaluator, args):
    """映射：映射(函数, 容器) → 新列表"""
    if len(args) != 2:
        raise SanyanSyntaxError('映射 需要函数和容器')
    func = evaluator.eval(args[0])
    container = evaluator.eval(args[1])
    if not isinstance(container, (list, ArrayValue)):
        raise SanyanTypeError('第二个参数必须是列表或数组')
    result = []
    for item in container:
        res = call_function(evaluator, func, [item])
        result.append(res)
    return result


def _filter_op(evaluator, args):
    """过滤：过滤(谓词, 容器) → 筛选后列表"""
    if len(args) != 2:
        raise SanyanSyntaxError('过滤 需要谓词和容器')
    pred = evaluator.eval(args[0])
    container = evaluator.eval(args[1])
    if not isinstance(container, (list, ArrayValue)):
        raise SanyanTypeError('第二个参数必须是列表或数组')
    result = []
    for item in container:
        res = call_function(evaluator, pred, [item])
        if isinstance(res, TritValue) and res.to_int() == 1:
            result.append(item)
    return result


def _reduce_op(evaluator, args):
    """归并：归并(二元函数, 容器 [, 初始值])"""
    if len(args) < 2 or len(args) > 3:
        raise SanyanSyntaxError('归并 需要二元函数、容器和可选的初始值')
    func = evaluator.eval(args[0])
    container = evaluator.eval(args[1])
    if not isinstance(container, (list, ArrayValue)):
        raise SanyanTypeError('第二个参数必须是列表或数组')
    if len(container) == 0 and len(args) < 3:
        raise SanyanValueError('空容器且无初始值，无法归并')
    if len(args) == 3:
        accumulator = evaluator.eval(args[2])
        start_idx = 0
    else:
        accumulator = container[0]
        start_idx = 1
    for i in range(start_idx, len(container)):
        accumulator = call_function(evaluator, func, [accumulator, container[i]])
    return accumulator


def _module_call(evaluator, args):
    """模块函数调用：module_call(模块, 函数名, 参数...)"""
    if len(args) < 2:
        raise SanyanSyntaxError('模块调用 需要至少2个参数')
    mod = evaluator.eval(args[0])
    if not isinstance(mod, ModuleValue):
        raise SanyanTypeError('第一个参数必须是模块')
    func_name = evaluator.eval(args[1])
    if not isinstance(func_name, str):
        raise SanyanTypeError('第二个参数必须是字符串')
    call_args = [evaluator.eval(a) for a in args[2:]]
    return mod.call(evaluator, [func_name] + call_args)


# ── 注册 ──
register('lambda', _make_lambda)
register('apply', _apply)
register('map', _map_op)
register('filter', _filter_op)
register('reduce', _reduce_op)
register('module_call', _module_call)
