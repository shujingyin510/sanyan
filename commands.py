"""自定义命令：定义与调用"""
from values import ReturnException, BreakException, SanyanSyntaxError, SanyanNameError
from ternary_core import TritValue

class Commands:
    @staticmethod
    def define(evaluator, args):
        if len(args) < 3:
            raise SanyanSyntaxError("定义 需要名称、参数列表和体")
        cmd_name = args[0]
        if isinstance(cmd_name, list):
            cmd_name = cmd_name[0]
        params = args[1]
        # 检查是否有类型标注
        param_types = {}
        if len(args) > 2 and isinstance(args[2], dict):
            param_types = args[2]
            body = args[3:]
        else:
            body = args[2:]
        evaluator.commands[cmd_name] = (params, body, param_types)
        return TritValue(0)

    @staticmethod
    def _check_type(value, expected_type, param_name):
        """检查值是否符合预期类型"""
        from values import SanyanTypeError
        type_checks = {
            '数字': lambda v: isinstance(v, TritValue),
            '字符串': lambda v: isinstance(v, str),
            '列表': lambda v: isinstance(v, list),
            '字典': lambda v: isinstance(v, dict),
            '布尔': lambda v: isinstance(v, TritValue) and v.to_int() in (1, -1),
            '三态': lambda v: isinstance(v, TritValue),
        }
        if expected_type in type_checks:
            if not type_checks[expected_type](value):
                actual_type = '未知'
                if isinstance(value, TritValue):
                    actual_type = '数字'
                elif isinstance(value, str):
                    actual_type = '字符串'
                elif isinstance(value, list):
                    actual_type = '列表'
                elif isinstance(value, dict):
                    actual_type = '字典'
                raise SanyanTypeError(f"参数 '{param_name}' 期望类型 '{expected_type}'，但得到 '{actual_type}'")

    @staticmethod
    def _is_tail_call(expr, func_name):
        """检测表达式是否是对指定函数的尾调用"""
        if isinstance(expr, list) and len(expr) > 0 and expr[0] == func_name:
            return True
        # 检测 return(f(args)) 模式
        if isinstance(expr, list) and len(expr) == 2 and expr[0] == 'return':
            inner = expr[1]
            if isinstance(inner, list) and len(inner) > 0 and inner[0] == func_name:
                return True
        return False

    @staticmethod
    def _format_args(args):
        """格式化参数用于显示"""
        parts = []
        for a in args:
            if isinstance(a, TritValue):
                parts.append(str(a.to_int()))
            elif isinstance(a, str):
                if len(a) > 20:
                    parts.append(a[:20] + '...')
                else:
                    parts.append(a)
            elif isinstance(a, list):
                parts.append('[...]')
            else:
                parts.append(str(a))
        return ', '.join(parts)

    @staticmethod
    def call(evaluator, op, args):
        evaluator.call_depth += 1
        if evaluator.call_depth > evaluator.max_call_depth:
            evaluator.call_depth -= 1
            # 打印调用栈
            Commands._print_call_stack(evaluator, op, args)
            raise RecursionError("命令调用超过了最大递归深度")
        
        # 压入调用栈
        evaluator.call_stack.append((op, args))
        
        try:
            if op not in evaluator.commands:
                available = list(evaluator.commands.keys())[:10]
                hint = f"，可用命令: {available}" if available else ""
                raise SanyanNameError(f"未定义的操作: '{op}'{hint}")
            cmd_def = evaluator.commands[op]
            params = cmd_def[0]
            body = cmd_def[1]
            param_types = cmd_def[2] if len(cmd_def) > 2 else {}
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
            
            # 检测尾递归：最后一个表达式是否是对自身的调用
            last_expr = body[-1] if body else None
            is_tail_recursive = Commands._is_tail_call(last_expr, op)
            
            # 尾递归优化：转换为循环
            if is_tail_recursive:
                max_iterations = evaluator.max_loop_steps * 10  # 尾递归允许更多迭代
                iteration = 0
                while iteration < max_iterations:
                    # 作用域隔离
                    saved_vars = dict(evaluator.vars)
                    # 求值参数
                    for param, arg_node in zip(params, args):
                        if isinstance(arg_node, str) and not arg_node.isdigit() \
                                and arg_node not in TritValue.STATE_MAP \
                                and arg_node not in evaluator.vars:
                            value = arg_node
                        else:
                            value = evaluator.eval(arg_node)
                        # 类型检查
                        if param in param_types:
                            Commands._check_type(value, param_types[param], param)
                        evaluator.vars[param] = value
                    # 执行函数体（除了最后一个尾调用表达式）
                    result = None
                    try:
                        for expr in body[:-1]:
                            try:
                                result = evaluator.eval(expr)
                            except ReturnException as ret:
                                result = ret.value
                                evaluator.vars = saved_vars
                                return result if result is not None else TritValue(0)
                        # 执行尾调用表达式，获取新参数
                        tail_expr = last_expr
                        if isinstance(tail_expr, list) and tail_expr[0] == 'return':
                            tail_expr = tail_expr[1]
                        # 求值新参数（在当前作用域中）
                        new_args = tail_expr[1:]
                        args = []
                        for arg in new_args:
                            args.append(evaluator.eval(arg))
                        # 恢复变量表，准备下一次迭代
                        evaluator.vars = saved_vars
                    except ReturnException as ret:
                        evaluator.vars = saved_vars
                        return ret.value if ret.value is not None else TritValue(0)
                    iteration += 1
                raise RecursionError("尾递归超过了最大迭代次数")
            
            # 非尾递归：正常执行
            # 作用域隔离：保存整个变量表，创建新的局部作用域
            saved_vars = dict(evaluator.vars)
            # 求值参数（在旧作用域中求值，避免参数表达式访问新变量）
            for param, arg_node in zip(params, args):
                if isinstance(arg_node, str) and not arg_node.isdigit() \
                        and arg_node not in TritValue.STATE_MAP \
                        and arg_node not in evaluator.vars:
                    value = arg_node
                else:
                    value = evaluator.eval(arg_node)
                # 类型检查
                if param in param_types:
                    Commands._check_type(value, param_types[param], param)
                evaluator.vars[param] = value
            result = None
            try:
                for expr in body:
                    try:
                        result = evaluator.eval(expr)
                    except ReturnException as ret:
                        result = ret.value
                        break
            finally:
                # 恢复原始变量表（函数内创建的变量全部丢弃）
                evaluator.vars = saved_vars
            return result if result is not None else TritValue(0)
        except Exception as e:
            # 发生错误时打印调用栈
            if not isinstance(e, (ReturnException, BreakException)):
                Commands._print_call_stack(evaluator, op, args)
            raise
        finally:
            # 弹出调用栈
            if evaluator.call_stack:
                evaluator.call_stack.pop()
            evaluator.call_depth -= 1

    @staticmethod
    def _print_call_stack(evaluator, current_op, current_args):
        """打印调用栈"""
        print("\n=== 调用栈 ===")
        # 打印当前调用
        formatted_args = Commands._format_args(current_args)
        print(f"  at {current_op}({formatted_args})")
        # 打印之前的调用（从栈顶到栈底）
        for i in range(len(evaluator.call_stack) - 1, -1, -1):
            op, args = evaluator.call_stack[i]
            formatted_args = Commands._format_args(args)
            print(f"  at {op}({formatted_args})")
        print("==============\n")