from ternary_core import TritValue

"""三言中的值类型和异常"""
class ReturnException(Exception):
    def __init__(self, value):
        self.value = value

class BreakException(Exception):
    pass

class SanyanError(Exception):
    """语言层面异常基类"""
    pass

class SanyanNameError(NameError, SanyanError):
    pass

class SanyanSyntaxError(SyntaxError, SanyanError):
    pass

class SanyanTypeError(TypeError, SanyanError):
    pass

class ContinueException(Exception):
    pass

class FunctionValue:
    __slots__ = ('params', 'body', 'evaluator', 'closure_vars')

    def __init__(self, params, body, evaluator=None, closure_vars=None):
        self.params = params
        self.body = body
        self.evaluator = evaluator
        self.closure_vars = closure_vars

    def call(self, evaluator, args):
        if len(args) != len(self.params):
            raise SanyanSyntaxError(
                f"函数 λ{self.params} 需要 {len(self.params)} 个参数，但提供了 {len(args)} 个: {args}"
            )
        # 作用域隔离：保存整个变量表
        saved_vars = dict(evaluator.vars)
        # 合并闭包变量（闭包变量作为底层，当前作用域覆盖）
        if self.closure_vars:
            for k, v in self.closure_vars.items():
                if k not in evaluator.vars:
                    evaluator.vars[k] = v
        for param, arg_node in zip(self.params, args):
            try:
                val = evaluator.eval(arg_node)
            except Exception:
                val = arg_node
            evaluator.vars[param] = val

        try:
            result = None
            for expr in self.body:
                try:
                    result = evaluator.eval(expr)
                except ReturnException as ret:
                    result = ret.value
                    break
            # 将闭包变量的修改写回（实现变量引用语义）
            if self.closure_vars:
                for k in self.closure_vars:
                    if k in evaluator.vars and k not in saved_vars:
                        self.closure_vars[k] = evaluator.vars[k]
                    elif k in evaluator.vars and k in saved_vars:
                        if evaluator.vars[k] is not saved_vars[k]:
                            self.closure_vars[k] = evaluator.vars[k]
            return result if result is not None else 0
        finally:
            # 恢复原始变量表
            evaluator.vars = saved_vars

    def __repr__(self):
        return f"<函数 λ {self.params}>"


def call_function(evaluator, func, args):
    """通用函数调用：func 可以是字符串、FunctionValue 或自定义命令名"""
    if isinstance(func, str):
        from evaluator import SanyanEvaluator
        if isinstance(evaluator, SanyanEvaluator):
            return evaluator._apply(func, args)
        else:
            return evaluator.eval([func] + args)
    elif isinstance(func, FunctionValue):
        return func.call(evaluator, args)
    else:
        raise TypeError(f"不可调用的对象: {type(func)}")
    
class ModuleValue:
    """隔离的模块环境，包含变量和命令"""
    __slots__ = ('vars', 'commands')

    def __init__(self, vars, commands):
        self.vars = dict(vars)
        self.commands = dict(commands)

    def call(self, evaluator, args):
        if len(args) < 1:
            raise SanyanSyntaxError("模块调用需要至少一个参数（函数名），但未提供")
        func_name = args[0]
        func_args = args[1:]
        # 查找命令
        if func_name in self.commands:
            cmd_def = self.commands[func_name]
            params = cmd_def[0]
            body = cmd_def[1]
            # 作用域隔离：保存整个变量表，注入模块变量
            saved_vars = dict(evaluator.vars)
            # 注入模块的变量到求值器
            for k, v in self.vars.items():
                evaluator.vars[k] = v
            for p, v in zip(params, func_args):
                evaluator.vars[p] = v
            try:
                result = None
                for expr in body:
                    try:
                        result = evaluator.eval(expr)
                    except ReturnException as ret:
                        result = ret.value
                        break
                # 保存模块变量的更改
                for k in self.vars.keys():
                    if k in evaluator.vars:
                        self.vars[k] = evaluator.vars[k]
                return result if result is not None else TritValue(0)
            finally:
                # 恢复原始变量表
                evaluator.vars = saved_vars
        else:
            raise SanyanNameError(f"模块中未定义操作: {func_name}")