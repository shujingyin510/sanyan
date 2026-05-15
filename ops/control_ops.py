"""控制流操作：若、做、循环、遍历、返回、跳出、异常处理"""
from ternary_core import BT, TritValue, ArrayValue
from values import ReturnException, BreakException, ContinueException, SanyanError,SanyanSyntaxError

class ControlOps:
    @staticmethod
    def if_op(evaluator, args):
        if len(args) < 2:
            raise SanyanSyntaxError("if 需要条件和真分支")
        cond = evaluator.eval(args[0])
        if BT.to_int(cond.value) == 1:
            return evaluator.eval(args[1])
        elif len(args) >= 3:
            return evaluator.eval(args[2])
        else:
            return TritValue(0)

    @staticmethod
    def do_op(evaluator, args):
        if not args:
            return TritValue(0)
        result = None
        for statement in args:
            result = evaluator.eval(statement)
        return result if result is not None else TritValue(0)

    @staticmethod
    def define_var(evaluator, args):
        from ternary_core import TritValue
        if not args:
            raise SanyanSyntaxError("设 需要参数，格式: (设 变量名 值)")
        if len(args) == 1 and isinstance(args[0], list):
            pairs = evaluator._parse_pairs(args[0])
            last_val = TritValue(0)
            for var, val_str in pairs:
                val = TritValue.from_string(val_str)
                evaluator.vars[var] = val
                last_val = val
            return last_val
        if len(args) < 2:
            raise SanyanSyntaxError("设 需要变量名和值，格式: (设 变量名 值)")
        var_name = args[0]
        if isinstance(var_name, list):
            var_name = var_name[0]
        value_node = args[1]
        if (isinstance(value_node, list) and len(value_node) == 1
                and isinstance(value_node[0], str) and value_node[0].isdigit()):
            value = TritValue(int(value_node[0]))
        else:
            value = evaluator.eval(value_node)
        evaluator.vars[var_name] = value
        return value

    @staticmethod
    def loop_op(evaluator, args):
        if len(args) < 2:
            raise SanyanSyntaxError("loop 需要条件和体")
        body = args[1:]
        result = TritValue(0)
        local_count = 0
        while local_count < evaluator.max_loop_steps:
            cond = evaluator.eval(args[0])
            if BT.to_int(cond.value) != 1:
                break
            try:
                for statement in body:
                    result = evaluator.eval(statement)
            except BreakException:
                break
            except ContinueException:
                pass
            local_count += 1
        return result

    @staticmethod
    def traversal_op(evaluator, args):
        if len(args) < 4:
            raise SanyanSyntaxError("遍历 需要 变量名 起始 结束 体")
        var_name = args[0]
        start = evaluator.eval(args[1]).to_int()
        end = evaluator.eval(args[2]).to_int()
        body = args[3:]
        result = TritValue(0)
        for i in range(start, end + 1):
            evaluator.vars[var_name] = TritValue(i)
            try:
                for expr in body:
                    result = evaluator.eval(expr)
            except BreakException:
                break
            except ContinueException:
                continue   # Python 的 continue，进入下一次 i 迭代
        return result

    @staticmethod
    def return_op(evaluator, args):
        if len(args) == 0:
            raise ReturnException(TritValue(0))
        value = evaluator.eval(args[0])
        raise ReturnException(value)

    @staticmethod
    def break_op(evaluator, args):
        raise BreakException()

    @staticmethod
    def try_catch(evaluator, args):
        if len(args) != 2:
            raise SanyanSyntaxError("尝试 需要两个参数：尝试体和捕获体")
        try_body = args[0]
        catch_spec = args[1]
        if not isinstance(catch_spec, list) or len(catch_spec) < 2 or catch_spec[0] not in ('捕获', 'catch'):
            raise SanyanSyntaxError("捕获体格式应为 (捕获 (错误变量) 体...)")
        error_var = catch_spec[1]
        if isinstance(error_var, list):
            if len(error_var) != 1:
                raise SanyanSyntaxError("捕获的错误变量必须是一个标识符")
            error_var = error_var[0]
        catch_body = catch_spec[2:]

        try:
            return evaluator.eval(try_body)
        except SanyanError as e:
            # 只捕获语言层异常
            saved = None
            if error_var in evaluator.vars:
                saved = evaluator.vars[error_var]
            evaluator.vars[error_var] = str(e)
            try:
                result = None
                for expr in catch_body:
                    result = evaluator.eval(expr)
                return result if result is not None else TritValue(0)
            finally:
                if saved is not None:
                    evaluator.vars[error_var] = saved
                else:
                    if error_var in evaluator.vars:
                        del evaluator.vars[error_var]
        # 其他异常（如 AttributeError）不捕获，直接向上抛出

    @staticmethod
    def judge_op(evaluator, args):
        if len(args) == 4:
            expr_node, true_body, maybe_body, false_body = args
        elif len(args) == 7:
            expr_node = args[0]
            true_body = maybe_body = false_body = None
            for i in range(1, len(args), 2):
                label = args[i]
                if isinstance(label, list):
                    label = str(label[0]) if len(label) > 0 else ''
                body = args[i + 1]
                matched = False
                if label in ('真', 'true'):
                    true_body = body
                    matched = True
                elif label in ('可能', 'maybe'):
                    maybe_body = body
                    matched = True
                elif label in ('假', 'false'):
                    false_body = body
                    matched = True
                if not matched and hasattr(evaluator, 'skin_manager') and evaluator.skin_manager:
                    state = evaluator.skin_manager.is_ternary_word(label)
                    if state == 1:
                        true_body = body
                    elif state == 0:
                        maybe_body = body
                    elif state == -1:
                        false_body = body
            if true_body is None or maybe_body is None or false_body is None:
                raise SanyanSyntaxError("判 需要 真/可能/假 三个分支")
        else:
            raise SanyanSyntaxError("判 需要一个表达式和三个分支体")
        val = evaluator.eval(expr_node)
        int_val = val.to_int()
        if int_val == 1:
            return evaluator.eval(true_body)
        elif int_val == 0:
            return evaluator.eval(maybe_body)
        else:
            return evaluator.eval(false_body)

    @staticmethod
    def continue_op(evaluator, args):
        raise ContinueException()

    @staticmethod
    def forin_op(evaluator, args):
        if len(args) < 3:
            raise SanyanSyntaxError("遍历-在 需要 变量名 容器 体")
        var_name = args[0]
        container = evaluator.eval(args[1])
        body = args[2:]
        result = TritValue(0)
        if isinstance(container, (list, ArrayValue)):
            for item in container:
                evaluator.vars[var_name] = item
                try:
                    for expr in body:
                        result = evaluator.eval(expr)
                except BreakException:
                    break
                except ContinueException:
                    continue
        elif isinstance(container, str):
            # 字符串遍历：每个字符（已通过字列转为列表，或直接迭代字符）
            for ch in container:
                evaluator.vars[var_name] = ch
                try:
                    for expr in body:
                        result = evaluator.eval(expr)
                except BreakException:
                    break
                except ContinueException:
                    continue
        else:
            raise SanyanSyntaxError("遍历-在 只支持列表、数组或字符串")
        return result

    @staticmethod
    def export_op(evaluator, args):
        return TritValue(0)

# 注册控制流操作
from ops.registry import register
register('if', ControlOps.if_op)
register('do', ControlOps.do_op)
register('loop', ControlOps.loop_op)
register('for', ControlOps.traversal_op)
register('forin', ControlOps.forin_op)
register('return', ControlOps.return_op)
register('break', ControlOps.break_op)
register('continue', ControlOps.continue_op)
register('try', ControlOps.try_catch)
register('judge', ControlOps.judge_op)
register('set', ControlOps.define_var)
register('export', ControlOps.export_op)
