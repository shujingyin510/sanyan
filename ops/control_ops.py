"""控制流操作：若、做、循环、遍历、返回、跳出、异常处理"""

from ternary_core import BT, TritValue, ArrayValue
from values import ReturnException, BreakException, ContinueException, SanyanError, SanyanSyntaxError, SanyanValueError
from ops.list_ops import _as_list
from ops.registry import register


class ControlOps:
    """控制流操作：条件、循环、遍历、变量设置"""

    @staticmethod
    def if_op(evaluator, args):
        if len(args) < 2:
            raise SanyanSyntaxError('if 需要条件和真分支')
        cond = evaluator.eval(args[0])
        if isinstance(cond, TritValue):
            cond_bool = BT.to_int(cond.value) == 1
        elif isinstance(cond, int):
            cond_bool = cond != 0
        elif isinstance(cond, str):
            cond_bool = len(cond) > 0
        elif isinstance(cond, list):
            cond_bool = len(cond) > 0
        elif cond is None:
            cond_bool = False
        else:
            cond_bool = True
        if cond_bool:
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
        if not args:
            raise SanyanSyntaxError('设 需要参数，格式: (设 变量名 值)')
        if len(args) == 1 and isinstance(args[0], list):
            pairs = evaluator._parse_pairs(args[0])
            last_val = TritValue(0)
            for var, val_str in pairs:
                val = TritValue.from_string(val_str)
                evaluator.scope_vars[var] = val
                last_val = val
            return last_val
        if len(args) < 2:
            raise SanyanSyntaxError('设 需要变量名和值，格式: (设 变量名 值)')
        var_name = args[0]
        if isinstance(var_name, list):
            var_name = var_name[0]
        value_node = args[1]
        if (
            isinstance(value_node, list)
            and len(value_node) == 1
            and isinstance(value_node[0], str)
            and value_node[0].isdigit()
        ):
            value = TritValue(int(value_node[0]))
        else:
            value = evaluator.eval(value_node)
        evaluator.scope_vars[var_name] = value
        return value

    @staticmethod
    def loop_op(evaluator, args):
        if len(args) < 2:
            raise SanyanSyntaxError('循环 需要条件和体')
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
            raise SanyanSyntaxError('遍历 需要 变量名 起始 结束 体')
        var_name = args[0]
        start = evaluator.eval(args[1]).to_int()
        end = evaluator.eval(args[2]).to_int()
        body = args[3:]
        result = TritValue(0)
        for i in range(start, end + 1):
            evaluator.scope_vars[var_name] = TritValue(i)
            try:
                for expr in body:
                    result = evaluator.eval(expr)
            except BreakException:
                break
            except ContinueException:
                continue  # Python 的 continue，进入下一次 i 迭代
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
            raise SanyanSyntaxError('尝试 需要两个参数：尝试体和捕获体')
        try_body = args[0]
        catch_spec = args[1]
        if not isinstance(catch_spec, list) or len(catch_spec) < 2 or catch_spec[0] not in ('捕获', 'catch'):
            raise SanyanSyntaxError('捕获体格式应为 (捕获 (错误变量) 体...)')
        error_var = catch_spec[1]
        if isinstance(error_var, list):
            if len(error_var) != 1:
                raise SanyanSyntaxError('捕获的错误变量必须是一个标识符')
            error_var = error_var[0]
        catch_body = catch_spec[2:]

        try:
            return evaluator.eval(try_body)
        except SanyanError as e:
            # 只捕获语言层异常
            # 如果错误变量是 _（discard 模式），跳过作用域赋值
            if error_var != '_':
                saved = None
                if error_var in evaluator.scope_vars:
                    saved = evaluator.scope_vars[error_var]
                evaluator.scope_vars[error_var] = str(e)
            else:
                saved = None
            try:
                result = None
                for expr in catch_body:
                    result = evaluator.eval(expr)
                return result if result is not None else TritValue(0)
            finally:
                if error_var != '_':
                    if saved is not None:
                        evaluator.scope_vars[error_var] = saved
                    else:
                        if error_var in evaluator.scope_vars:
                            del evaluator.scope_vars[error_var]
        # 其他异常（如 AttributeError）不捕获，直接向上抛出

    @staticmethod
    def judge_op(evaluator, args):
        """判: 三态分支(len=4) 或 多值匹配(len>=4, label是字符串)"""
        if len(args) < 2:
            raise SanyanSyntaxError('判 需要一个表达式和分支体')

        # 经典三态分支: (判 值 真分支 可能分支 假分支) — 刚好4个参数且无字符串label
        if len(args) == 4 and not any(
            isinstance(args[i], str) and args[i] in ('真', '可能', '假', 'true', 'maybe', 'false', '默认')
            for i in range(1, 4)
        ):
            val = evaluator.eval(args[0])
            int_val = val.to_int() if isinstance(val, TritValue) else int(val)
            if int_val == 1:
                return evaluator.eval(args[1])
            elif int_val == 0:
                return evaluator.eval(args[2])
            else:
                return evaluator.eval(args[3])

        # 多值匹配: (判 val 'a' body1 'b' body2 ... '默认' default)
        val = evaluator.eval(args[0])
        for i in range(1, len(args), 2):
            if i + 1 >= len(args):
                break
            label = args[i]
            body = args[i + 1]
            if isinstance(label, str) and label == '默认':
                return evaluator.eval(body)
            label_val = evaluator.eval(label)
            match = False
            if isinstance(val, TritValue):
                lv = label_val.to_int() if isinstance(label_val, TritValue) else label_val
                match = val.to_int() == lv
            else:
                match = str(val) == str(label_val)
            if match:
                return evaluator.eval(body)
        return TritValue(0)

    @staticmethod
    def continue_op(evaluator, args):
        raise ContinueException()

    @staticmethod
    def forin_op(evaluator, args):
        if len(args) < 3:
            raise SanyanSyntaxError('遍历-在 需要 变量名 容器 体')
        var_name = args[0]
        container = evaluator.eval(args[1])
        body = args[2:]
        result = TritValue(0)
        if isinstance(container, (list, ArrayValue)):
            container = _as_list(container)
            for item in container:
                evaluator.scope_vars[var_name] = item
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
                evaluator.scope_vars[var_name] = ch
                try:
                    for expr in body:
                        result = evaluator.eval(expr)
                except BreakException:
                    break
                except ContinueException:
                    continue
        else:
            raise SanyanSyntaxError('遍历-在 只支持列表、数组或字符串')
        return result

    @staticmethod
    def export_op(evaluator, args):
        return TritValue(0)

    @staticmethod
    def assert_op(evaluator, args):
        """断言(条件, 消息): 条件为假时抛 SanyanValueError"""
        if len(args) < 1:
            raise SanyanSyntaxError('断言 需要条件 [, 消息]')
        cond = evaluator.eval(args[0])
        ok = False
        if isinstance(cond, TritValue):
            ok = cond.to_int() == 1
        elif isinstance(cond, int):
            ok = cond != 0
        elif isinstance(cond, str):
            ok = len(cond) > 0
        elif isinstance(cond, list):
            ok = len(cond) > 0
        if not ok:
            msg = evaluator.eval(args[1]) if len(args) >= 2 else '断言失败'
            if isinstance(msg, TritValue) and msg.is_string():
                msg = msg.to_payload()
            raise SanyanValueError(str(msg))
        return TritValue(0)

    @staticmethod
    def do_while_op(evaluator, args):
        """做-直到: (做-直到 body cond) 先执行体再检查条件，至少执行一次"""
        if len(args) != 2:
            raise SanyanSyntaxError('做-直到 需要体和条件')
        body = args[0]
        cond_expr = args[1]
        result = None
        while True:
            result = evaluator.eval(body)
            cond = evaluator.eval(cond_expr)
            ok = False
            if isinstance(cond, TritValue):
                ok = cond.to_int() == 1
            elif isinstance(cond, int):
                ok = cond != 0
            if ok:
                break
        return result if result is not None else TritValue(0)


# 注册控制流操作
register('if', ControlOps.if_op)
register('do', ControlOps.do_op)
register('loop', ControlOps.loop_op)
register('for', ControlOps.traversal_op)
register('forin', ControlOps.forin_op)
register('return', ControlOps.return_op)
register('返回', ControlOps.return_op)
# 退出 — 内部控制流返回（备用），行为同 return（触发 ReturnException），不发射 RET 操作码
register('退出', ControlOps.return_op)
register('break', ControlOps.break_op)
register('continue', ControlOps.continue_op)
register('try', ControlOps.try_catch)
register('judge', ControlOps.judge_op)
register('set', ControlOps.define_var)
register('export', ControlOps.export_op)
register('assert', ControlOps.assert_op)
register('do_while', ControlOps.do_while_op)
