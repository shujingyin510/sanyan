"""自定义命令：定义与调用"""
from ternary_core import TritValue
from values import ReturnException, SanyanNameError, SanyanSyntaxError

class Commands:
    @staticmethod
    def define(evaluator, args):
        if len(args) < 3:
            raise SanyanSyntaxError("定义 需要名称、参数列表和体")
        cmd_name = args[0]
        if isinstance(cmd_name, list):
            cmd_name = cmd_name[0]
        params = args[1]
        body = args[2:]
        evaluator.commands[cmd_name] = (params, body)
        return TritValue(0)

    @staticmethod
    def call(evaluator, op, args):
        evaluator.call_depth += 1
        if evaluator.call_depth > evaluator.max_call_depth:
            evaluator.call_depth -= 1
            raise RecursionError("命令调用超过了最大递归深度")
        try:
            if op not in evaluator.commands:
                raise NameError(f"未定义的操作: {op}")
            params, body = evaluator.commands[op]
            # 智能拆分（原有逻辑）
            if len(params) != len(args):
                if len(params) == 2 and len(args) == 1:
                    sole_arg = args[0]
                    if isinstance(sole_arg, str):
                        if '.' in sole_arg:
                            obj, attr = sole_arg.split('.', 1)
                            args = [obj, attr]
                        elif '：' in sole_arg:
                            obj, attr = sole_arg.split('：', 1)
                            args = [obj, attr]
                        else:
                            raise SanyanSyntaxError(f"命令 '{op}' 需要 {len(params)} 个参数，但提供了 {len(args)} 个")
                    else:
                        raise SanyanSyntaxError(f"命令 '{op}' 需要 {len(params)} 个参数，但提供了 {len(args)} 个")
                else:
                    raise SanyanSyntaxError(f"命令 '{op}' 需要 {len(params)} 个参数，但提供了 {len(args)} 个")
            saved = {}
            for param, arg_node in zip(params, args):
                if param in evaluator.vars:
                    saved[param] = evaluator.vars[param]
                if isinstance(arg_node, str) and not arg_node.isdigit() \
                        and arg_node not in TritValue.STATE_MAP \
                        and arg_node not in evaluator.vars:
                    value = arg_node
                else:
                    value = evaluator.eval(arg_node)
                evaluator.vars[param] = value
            result = None
            try:
                for expr in body:
                    try:
                        result = evaluator.eval(expr)
                    except ReturnException as ret:
                        result = ret.value
                        break   # 提前退出循环
            finally:
                for param in params:
                    if param in saved:
                        evaluator.vars[param] = saved[param]
                    else:
                        if param in evaluator.vars:
                            del evaluator.vars[param]
            return result if result is not None else TritValue(0)
        finally:
            evaluator.call_depth -= 1