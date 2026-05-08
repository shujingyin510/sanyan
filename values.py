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

class ContinueException(Exception):
    pass

class FunctionValue:
    def __init__(self, params, body, evaluator=None):
        self.params = params
        self.body = body
        self.evaluator = evaluator

    def call(self, evaluator, args):
        if len(args) != len(self.params):
            raise SyntaxError(f"函数需要 {len(self.params)} 个参数，但提供了 {len(args)} 个")
        saved = {}
        for param, arg_node in zip(self.params, args):
            if param in evaluator.vars:
                saved[param] = evaluator.vars[param]
            try:
                val = evaluator.eval(arg_node)
            except:
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
            return result if result is not None else 0
        finally:
            for param in self.params:
                if param in saved:
                    evaluator.vars[param] = saved[param]
                else:
                    if param in evaluator.vars:
                        del evaluator.vars[param]

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
    def __init__(self, vars, commands):
        self.vars = dict(vars)
        self.commands = dict(commands)

    def call(self, evaluator, args):
        if len(args) < 1:
            raise SyntaxError("模块调用需要至少一个参数（函数名）")
        func_name = args[0]
        func_args = args[1:]
        # 查找命令
        if func_name in self.commands:
            params, body = self.commands[func_name]
            # 创建临时执行环境，用模块变量覆盖 evaluator 的局部变量
            saved = {}
            for p, v in zip(params, func_args):
                saved[p] = evaluator.vars.get(p)
                evaluator.vars[p] = evaluator.eval(v) if isinstance(v, list) else v
            try:
                result = None
                for expr in body:
                    try:
                        result = evaluator.eval(expr)
                    except ReturnException as ret:
                        result = ret.value
                        break
                return result if result is not None else TritValue(0)
            finally:
                for p in params:
                    if p in saved and saved[p] is not None:
                        evaluator.vars[p] = saved[p]
                    else:
                        if p in evaluator.vars:
                            del evaluator.vars[p]
        else:
            raise SanyanNameError(f"模块中未定义操作: {func_name}")