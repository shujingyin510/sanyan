"""三言值系统：定义 TritValue、FunctionValue、ModuleValue 等核心类型及异常体系。"""

from __future__ import annotations
from typing import Any, Callable, Dict, List, Optional, Set, Union
from core.ternary_core import TritValue, ArrayValue


def to_num(v: Any) -> Union[int, float, Any]:
    """将 TritValue 或可数值化的值转为 int/float。
    若无法数值化则原样返回（兼容非数值相等比较）。
    """
    if isinstance(v, TritValue):
        return v.to_float() if v.is_float() else v.to_int()
    if isinstance(v, (int, float)):
        return v
    try:
        s = str(v)
        return float(s) if '.' in s else int(s)
    except (ValueError, TypeError):
        return v


class ReturnException(Exception):
    def __init__(self, value: Any) -> None:
        self.value = value


class BreakException(Exception):
    pass


class SanyanError(Exception):
    pass


class SanyanNameError(NameError, SanyanError):
    pass


class SanyanSyntaxError(SyntaxError, SanyanError):
    pass


class SanyanTypeError(TypeError, SanyanError):
    pass


class SanyanValueError(ValueError, SanyanError):
    pass


class SanyanRuntimeError(RuntimeError, SanyanError):
    pass


class SanyanConstraintDenied(SanyanRuntimeError):
    """能力约束拒绝：`任务{约束{…}}` 块内调用了未授权的能力类，或超出 限时 预算。

    因=约束（认知/权限分层律，D4）——恒为「假」，不是「可能」：解释器确定知道
    「没资格」，非「不知道」。直取式算子抛此错；信封式算子将来捕获后转 判假·因=约束。

    reason 携带 因（约束 / 超时）——给程序看，让 尝试/捕获 区分「无资格」与「超预算」。"""

    def __init__(self, message: str = '', reason: str = '约束') -> None:
        super().__init__(message)
        self.reason = reason


class SanyanKeyError(KeyError, SanyanError):
    pass


class SanyanAttributeError(AttributeError, SanyanError):
    pass


class SanyanIOError(OSError, SanyanError):
    """文件/I/O 操作错误（如读取失败、写入失败）"""

    pass


class SanyanIndexError(IndexError, SanyanError):
    """索引越界错误（列表/数组访问越界）"""

    pass


class ContinueException(Exception):
    pass


class SrcNode(list):
    """带源码位置的 AST 节点。

    设计说明：继承 list 以兼容所有期望 list 的代码路径（求值、遍历），
    同时通过 line/col 属性携带源码位置信息。
    isinstance(node, SrcNode) 可以区分代码节点与数据列表。
    """

    __slots__ = ('line', 'col')

    def __new__(cls, items: tuple = (), line: int = 0, col: int = 0) -> SrcNode:
        obj = super().__new__(cls)
        obj.line = line  # type: ignore[attr-defined]
        obj.col = col  # type: ignore[attr-defined]
        return obj

    def __repr__(self) -> str:
        items = super().__repr__()
        if self.line or self.col:  # type: ignore[attr-defined]
            return f'<SrcNode L{self.line}:C{self.col} {items}>'  # type: ignore[attr-defined]
        return f'<SrcNode {items}>'


def _get_type_name(value: Any) -> str:
    if isinstance(value, TritValue):
        return '数字'
    if isinstance(value, str):
        return '字符串'
    if isinstance(value, list):
        return '列表'
    if isinstance(value, dict):
        return '字典'
    return '未知'


def check_type(value: Any, expected_type: str, param_name: str = '') -> None:
    type_checks: Dict[str, Callable[[Any], bool]] = {
        # 中文名
        '数字': lambda v: isinstance(v, TritValue),
        '字符串': lambda v: isinstance(v, str),
        '列表': lambda v: isinstance(v, list),
        '字典': lambda v: isinstance(v, dict),
        '布尔': lambda v: isinstance(v, TritValue) and v.to_int() in (1, -1),
        '三态': lambda v: isinstance(v, TritValue),
        # 英文别名（糖解析器产生）
        'int': lambda v: isinstance(v, (int, TritValue)),
        'float': lambda v: isinstance(v, (int, float, TritValue)),
        'str': lambda v: isinstance(v, str),
        'list': lambda v: isinstance(v, list),
        'dict': lambda v: isinstance(v, dict),
        'num': lambda v: isinstance(v, (int, float, TritValue)),
        'any': lambda v: True,
    }

    is_optional = expected_type.startswith('?')
    base_type = expected_type[1:] if is_optional else expected_type

    if is_optional:
        if isinstance(value, TritValue) and value.to_int() == 0:
            return

    # 效应类型：确定[X] / 不确定[X] — 从内层类型开始检查
    for _eff_prefix in ('确定[', '不确定['):
        if base_type.startswith(_eff_prefix) and base_type.endswith(']'):
            inner_type = base_type[len(_eff_prefix) : -1]
            # 先检查基础类型
            if inner_type in type_checks and not type_checks[inner_type](value):
                actual = _get_type_name(value)
                label = f"参数 '{param_name}' " if param_name else ''
                raise SanyanTypeError(
                    f"{label}期望类型 '{expected_type}'（基础类型 '{inner_type}'），但得到 '{actual}'"
                )
            # 确定[X] 额外要求信度 >= 0.99
            if _eff_prefix == '确定[' and isinstance(value, TritValue):
                if value.confidence < 0.99:
                    label = f"参数 '{param_name}' " if param_name else ''
                    raise SanyanTypeError(
                        f"{label}期望 '{expected_type}'（信度≥0.99），但实际信度={value.confidence:.2f}"
                    )
            return

    if base_type not in type_checks:
        return

    if not type_checks[base_type](value):
        actual = _get_type_name(value)
        label = f"参数 '{param_name}' " if param_name else ''
        raise SanyanTypeError(f"{label}期望类型 '{expected_type}'，但得到 '{actual}'")


class FunctionValue:
    """三言函数值，包含参数、闭包、类型注解。"""

    __slots__ = ('params', 'body', 'evaluator', 'closure_vars', 'param_types', 'return_type')

    def __init__(
        self,
        params: List[str],
        body: List[Any],
        evaluator: Optional[Any] = None,
        closure_vars: Optional[Dict[str, Any]] = None,
        param_types: Optional[Dict[str, str]] = None,
    ) -> None:
        self.params = params
        self.body = body
        self.evaluator = evaluator
        self.closure_vars = closure_vars
        self.param_types = param_types or {}
        self.return_type = self.param_types.pop('__return__', None) if self.param_types else None

    def call(self, evaluator: Any, args: List[Any]) -> TritValue:
        if len(args) != len(self.params):
            raise SanyanSyntaxError(
                f'函数 λ{self.params} 需要 {len(self.params)} 个参数，但提供了 {len(args)} 个: {args}'
            )
        evaluator.push_scope()

        if self.closure_vars:
            for k, v in self.closure_vars.items():
                evaluator.set_var(k, v)

        for param, arg_node in zip(self.params, args):
            if isinstance(arg_node, (TritValue, ArrayValue, str, int, list, dict)):
                val = arg_node
            else:
                val = evaluator.eval(arg_node)
            if param in self.param_types:
                check_type(val, self.param_types[param], param)
            evaluator.set_var(param, val)

        try:
            result = None
            for expr in self.body:
                try:
                    result = evaluator.eval(expr)
                except ReturnException as ret:
                    result = ret.value
                    break
            # 无返回语句或空函数体 → 默认返回中性值 0（三态约定）
            result = result if result is not None else TritValue(0)
            if self.return_type:
                check_type(result, self.return_type, '返回值')
            return result
        finally:
            if self.closure_vars:
                for k in self.closure_vars:
                    if k in evaluator.scope_vars:
                        self.closure_vars[k] = evaluator.scope_vars[k]
            evaluator.pop_scope()

    def __repr__(self) -> str:
        return f'<函数 λ {self.params}>'


def call_function(evaluator: Any, func: Union[str, FunctionValue], args: List[Any]) -> Any:
    if isinstance(func, str):
        # 如果是字符串，直接尝试通过 evaluator 的 _apply 方法调用（避免直接在此处引用 SanyanEvaluator 造成循环依赖）
        if hasattr(evaluator, '_apply'):
            return evaluator._apply(func, args)
        else:
            return evaluator.eval([func] + args)
    elif isinstance(func, FunctionValue):
        return func.call(evaluator, args)
    else:
        raise SanyanTypeError(f'不可调用的对象: {type(func)}')


class ModuleValue:
    """三言模块值，封装变量、命令、导出列表。"""

    __slots__ = ('vars', 'commands', 'exports')

    def __init__(
        self,
        vars: Dict[str, Any],
        commands: Dict[str, Any],
        exports: Optional[Set[str]] = None,
    ) -> None:
        self.vars = dict(vars)
        self.commands = dict(commands)
        self.exports = exports  # None = 全部导出

    def is_exported(self, name: str) -> bool:
        if self.exports is None:
            return True
        return name in self.exports

    def call(self, evaluator: Any, args: List[Any]) -> TritValue:
        if len(args) < 1:
            raise SanyanSyntaxError('模块调用需要至少一个参数（函数名），但未提供')
        func_name = args[0]
        func_args = args[1:]
        if func_name in self.commands:
            cmd_def = self.commands[func_name]
            params = cmd_def[0]
            body = cmd_def[1]

            evaluator.push_scope()
            for k, v in self.vars.items():
                evaluator.set_var(k, v)
            for p, v in zip(params, func_args):
                evaluator.set_var(p, v)

            saved_commands = dict(evaluator.commands)
            evaluator.commands.update(self.commands)
            try:
                result = None
                for expr in body:
                    try:
                        result = evaluator.eval(expr)
                    except ReturnException as ret:
                        result = ret.value
                        break
                for k in self.vars.keys():
                    if k in evaluator.scope_vars:
                        self.vars[k] = evaluator.scope_vars[k]
                return result if result is not None else TritValue(0)
            finally:
                evaluator.commands.clear()
                evaluator.commands.update(saved_commands)
                evaluator.pop_scope()
        else:
            raise SanyanNameError(f'模块中未定义操作: {func_name}')
