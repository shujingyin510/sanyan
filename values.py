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