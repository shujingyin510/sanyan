"""三言中的值类型和异常"""
from typing import Any, Optional
from ternary_core import TritValue, ArrayValue


def to_num(v):
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

class SanyanKeyError(KeyError, SanyanError):
    pass

class SanyanAttributeError(AttributeError, SanyanError):
    pass

class ContinueException(Exception):
    pass

class FunctionValue:
    __slots__ = ('params', 'body', 'evaluator', 'closure_vars')

    def __init__(self, params: list, body: list, evaluator=None, closure_vars: Optional[dict] = None) -> None:
        self.params = params
        self.body = body
        self.evaluator = evaluator
        self.closure_vars = closure_vars

    def call(self, evaluator, args: list) -> TritValue:
        if len(args) != len(self.params):
            raise SanyanSyntaxError(
                f"函数 λ{self.params} 需要 {len(self.params)} 个参数，但提供了 {len(args)} 个: {args}"
            )
        evaluator.push_scope()

        if self.closure_vars:
            for k, v in self.closure_vars.items():
                evaluator.set_var(k, v)

        for param, arg_node in zip(self.params, args):
            # 如果参数已经是值类型，直接使用；否则求值
            if isinstance(arg_node, (TritValue, ArrayValue, str, int, list, dict)):
                val = arg_node
            else:
                val = evaluator.eval(arg_node)
            evaluator.set_var(param, val)

        try:
            result = None
            for expr in self.body:
                try:
                    result = evaluator.eval(expr)
                except ReturnException as ret:
                    result = ret.value
                    break
            return result if result is not None else TritValue(0)
        finally:
            if self.closure_vars:
                for k in self.closure_vars:
                    if k in evaluator.scope_vars:
                        self.closure_vars[k] = evaluator.scope_vars[k]
            evaluator.pop_scope()

    def __repr__(self):
        return f"<函数 λ {self.params}>"


def call_function(evaluator, func, args: list) -> Any:
    if isinstance(func, str):
        # 如果是字符串，直接尝试通过 evaluator 的 _apply 方法调用（避免直接在此处引用 SanyanEvaluator 造成循环依赖）
        if hasattr(evaluator, '_apply'):
            return evaluator._apply(func, args)
        else:
            return evaluator.eval([func] + args)
    elif isinstance(func, FunctionValue):
        return func.call(evaluator, args)
    else:
        raise SanyanTypeError(f"不可调用的对象: {type(func)}")

class ModuleValue:
    __slots__ = ('vars', 'commands', 'exports')

    def __init__(self, vars: dict, commands: dict, exports: Optional[set] = None) -> None:
        self.vars = dict(vars)
        self.commands = dict(commands)
        self.exports = exports  # None = 全部导出

    def is_exported(self, name: str) -> bool:
        if self.exports is None:
            return True
        return name in self.exports

    def call(self, evaluator, args: list) -> TritValue:
        if len(args) < 1:
            raise SanyanSyntaxError("模块调用需要至少一个参数（函数名），但未提供")
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
            raise SanyanNameError(f"模块中未定义操作: {func_name}")
