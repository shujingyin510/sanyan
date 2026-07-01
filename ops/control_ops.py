"""控制流操作：若、做、循环、遍历、返回、跳出、异常处理、三态匹配"""

from ternary_core import BT, TritValue, ArrayValue
from values import ReturnException, BreakException, ContinueException, SanyanError, SanyanSyntaxError, SanyanValueError
from ops.list_ops import _as_list
from ops.registry import register, register_alias


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
                # 类型推断
                evaluator.type_env.infer(var, val)
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
        # 类型检查：检测赋值冲突
        conflict = evaluator.type_env.check_assignment(var_name, value)
        if conflict:
            evaluator._type_warnings.append(conflict)
        # 类型推断
        evaluator.type_env.infer(var_name, value)
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

    @staticmethod
    def ternary_match(evaluator, args):
        """匹配3(值) { 真→..., 可能→..., 假→... } — 三态模式匹配。

        显式三态分支语法，比判()更清晰：
        - 真分支：值为真(1)时执行
        - 可能分支：值为可能(0)时执行
        - 假分支：值为假(-1)时执行

        支持置信度守卫：真(>0.8)→... 表示只在置信度>0.8时匹配
        """
        if len(args) < 2:
            raise SanyanSyntaxError('匹配3 需要值和至少一个分支')

        val = evaluator.eval(args[0])

        # 解析分支：args[1:] 是 [模式1, 体1, 模式2, 体2, ...]
        branches = args[1:]

        for i in range(0, len(branches), 2):
            if i + 1 >= len(branches):
                break

            pattern_node = branches[i]
            body_node = branches[i + 1]

            # 解析模式
            pattern_str = ''
            confidence_threshold = None

            if isinstance(pattern_node, str):
                pattern_str = pattern_node
            elif isinstance(pattern_node, list):
                # 支持 真(>0.8) 格式
                if len(pattern_node) >= 1:
                    pattern_str = pattern_node[0] if isinstance(pattern_node[0], str) else str(pattern_node[0])
                if len(pattern_node) >= 2:
                    # 第二个元素是置信度守卫表达式
                    conf_guard = pattern_node[1]
                    if isinstance(conf_guard, str):
                        # 解析 >0.8 格式
                        if conf_guard.startswith('>') or conf_guard.startswith('>='):
                            op = conf_guard[:2] if conf_guard.startswith('>=') else '>'
                            threshold = float(conf_guard[2:]) if conf_guard.startswith('>=') else float(conf_guard[1:])
                            confidence_threshold = ('>', threshold)
                        elif conf_guard.startswith('<') or conf_guard.startswith('<='):
                            op = conf_guard[:2] if conf_guard.startswith('<=') else '<'
                            threshold = float(conf_guard[2:]) if conf_guard.startswith('<=') else float(conf_guard[1:])
                            confidence_threshold = ('<', threshold)
                    elif isinstance(conf_guard, (int, float)):
                        confidence_threshold = ('>', float(conf_guard))

            # 匹配模式
            matched = False
            int_val = val.to_int() if isinstance(val, TritValue) else (1 if val else 0)

            if pattern_str in ('真', 'true', '1'):
                matched = int_val == 1
            elif pattern_str in ('假', 'false', '-1'):
                matched = int_val == -1
            elif pattern_str in ('可能', 'maybe', '0'):
                matched = int_val == 0
            elif pattern_str in ('默认', 'default', '_'):
                matched = True
            else:
                # 尝试值匹配
                try:
                    pattern_val = evaluator.eval(pattern_node)
                    if isinstance(val, TritValue) and isinstance(pattern_val, TritValue):
                        matched = val.to_int() == pattern_val.to_int()
                    else:
                        matched = str(val) == str(pattern_val)
                except Exception:
                    matched = False

            # 检查置信度守卫
            if matched and confidence_threshold is not None:
                if isinstance(val, TritValue):
                    conf = val.confidence
                    op, threshold = confidence_threshold
                    if op == '>':
                        matched = conf > threshold
                    elif op == '>=':
                        matched = conf >= threshold
                    elif op == '<':
                        matched = conf < threshold
                    elif op == '<=':
                        matched = conf <= threshold
                else:
                    matched = False

            if matched:
                return evaluator.eval(body_node)

        return TritValue(0)

    @staticmethod
    def ternary_match_confidence(evaluator, args):
        """匹配信度(值, 阈值) { 高→..., 中→..., 低→... } — 按置信度区间匹配。

        根据置信度值分三档：
        - 高：置信度 > 阈值（默认0.7）
        - 中：置信度在 [1-阈值, 阈值] 之间
        - 低：置信度 < 1-阈值
        """
        if len(args) < 2:
            raise SanyanSyntaxError('匹配信度 需要值和阈值')

        val = evaluator.eval(args[0])
        threshold_val = evaluator.eval(args[1])
        threshold = threshold_val.to_float() if isinstance(threshold_val, TritValue) else float(threshold_val)

        if not isinstance(val, TritValue):
            # 非三态值，默认高置信度
            conf = 1.0
        else:
            conf = val.confidence

        # 确定置信度区间
        if conf > threshold:
            level = '高'
        elif conf < (1 - threshold):
            level = '低'
        else:
            level = '中'

        # 解析分支
        branches = args[2:]
        for i in range(0, len(branches), 2):
            if i + 1 >= len(branches):
                break

            pattern_node = branches[i]
            body_node = branches[i + 1]

            pattern_str = ''
            if isinstance(pattern_node, str):
                pattern_str = pattern_node
            elif isinstance(pattern_node, list) and pattern_node:
                pattern_str = pattern_node[0] if isinstance(pattern_node[0], str) else str(pattern_node[0])

            if pattern_str in (level, '默认', 'default', '_'):
                return evaluator.eval(body_node)

        return TritValue(0)

    @staticmethod
    def pattern_match(evaluator, args):
        """匹配(value, pattern1, body1, pattern2, body2, ...) — 结构化模式匹配。

        支持:
        - 字面量匹配: (匹配 x 1 "一" 2 "二" _ "其他")
        - 列表解构: (匹配 lst [a, b] (连接 a b) _ "不匹配")
        - 字典解构: (匹配 d {name: n} n _ "不匹配")
        - 守卫条件: (匹配 x [n] (大于 n 0) "正数" _ "其他")
        """
        if len(args) < 2:
            raise SanyanSyntaxError('匹配 需要至少一个值和一个分支')

        value = evaluator.eval(args[0])
        branches = args[1:]

        i = 0
        while i < len(branches) - 1:
            pattern = branches[i]
            body = branches[i + 1]
            i += 2

            # 尝试匹配模式
            bindings = {}
            if _match_pattern(pattern, value, bindings, evaluator):
                # 绑定变量
                for name, val in bindings.items():
                    evaluator.set_var(name, val)
                return evaluator.eval(body)

        # 检查默认分支
        if i < len(branches):
            default = branches[i]
            if isinstance(default, str) and default in ('_', '默认', 'default'):
                return TritValue(0)

        return TritValue(0)


def _match_pattern(pattern, value, bindings, evaluator):
    """递归匹配模式和值。返回 True 如果匹配成功。"""
    # 字面量匹配
    if isinstance(pattern, str):
        # 通配符
        if pattern in ('_', '默认', 'default'):
            return True
        # 变量绑定
        if pattern.startswith('$') or (len(pattern) > 0 and pattern[0].isalpha()):
            bindings[pattern] = value
            return True
        # 字面量比较
        try:
            pat_val = evaluator.eval(pattern)
            if isinstance(pat_val, TritValue) and isinstance(value, TritValue):
                return pat_val.to_int() == value.to_int()
            return pat_val == value
        except Exception:
            return pattern == str(value)

    # 数值字面量
    if isinstance(pattern, (int, float)):
        if isinstance(value, TritValue):
            return value.to_int() == pattern
        return value == pattern

    # 列表解构
    if isinstance(pattern, list):
        if not isinstance(value, (list, ArrayValue)):
            return False

        # 转换为列表
        val_list = list(value) if isinstance(value, list) else [value.get(i) for i in range(value.size)]

        # 检查长度
        if len(pattern) != len(val_list):
            return False

        # 递归匹配每个元素
        for p, v in zip(pattern, val_list):
            if not _match_pattern(p, v, bindings, evaluator):
                return False
        return True

    # 字典解构
    if isinstance(pattern, dict):
        if not isinstance(value, dict):
            return False

        # 检查所有模式键是否存在于值中
        for key in pattern:
            if key not in value:
                return False

        # 递归匹配每个值
        for key, pat_val in pattern.items():
            if not _match_pattern(pat_val, value[key], bindings, evaluator):
                return False
        return True

    return False


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
register('匹配3', ControlOps.ternary_match)
register('匹配信度', ControlOps.ternary_match_confidence)
register('ternary_match', ControlOps.ternary_match)
register('match_confidence', ControlOps.ternary_match_confidence)
register('匹配', ControlOps.pattern_match)
register_alias('match', '匹配')

# 中文别名
_ra = register_alias
_ra('若', 'if')
_ra('做', 'do')
_ra('循环', 'loop')
_ra('遍历', 'for')
_ra('设', 'set')
_ra('跳出', 'break')
_ra('继续', 'continue')
_ra('尝试', 'try')
_ra('判', 'judge')
