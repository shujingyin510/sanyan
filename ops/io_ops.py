"""输入/输出、文件、时间、类型判断等"""
import time
from ternary_core import TritValue
from values import call_function, SanyanSyntaxError
from values import ModuleValue, FunctionValue

# 延迟导入避免循环依赖
def _get_commands():
    from commands import Commands
    return Commands

class IOOps:
    @staticmethod
    def format_value(val):
        """将三言值格式化为美观字符串，容器附三进制注释"""
        from ternary_core import TritValue, ArrayValue
        
        if isinstance(val, list):
            items_int = []
            items_trit = []
            for v in val:
                if isinstance(v, TritValue):
                    items_int.append(str(v.to_int()))
                    items_trit.append(str(v.symbol))
                else:
                    items_int.append(str(v))
                    items_trit.append('?')
            base = '[' + ', '.join(items_int) + ']'
            if items_trit and not all(t == '?' for t in items_trit):
                base += '（三进制: ' + ', '.join(items_trit) + '）'
            return base
        elif isinstance(val, ArrayValue):
            return IOOps.format_value(val.data)   # 重用列表格式化
        elif isinstance(val, dict):
            # 字典简单显示，可扩展
            return str(val)
        elif isinstance(val, TritValue):
            return f"{val.to_int()}（三进制: {val.symbol}）"
        else:
            return str(val)

    @staticmethod
    def output(evaluator, args):
        if len(args) == 0:
            return TritValue(0)
        val = evaluator.eval(args[0])
        formatted = IOOps.format_value(val)
        print(f"  => {formatted}")
        return val

    @staticmethod
    def input_op(evaluator, args):
        prompt = "请输入一个值: "
        if args:
            prompt = str(args[0])
        user_input = input(prompt).strip()
        if user_input.isdigit() or (user_input.startswith('-') and user_input[1:].isdigit()):
            return TritValue(int(user_input))
        if user_input in TritValue.STATE_MAP:
            return TritValue.from_string(user_input)
        raise ValueError(f"无法识别的输入: {user_input}")

    @staticmethod
    def debug_op(evaluator, args):
        # 检查是否是断点模式
        if args:
            mode = evaluator.eval(args[0])
            if isinstance(mode, str) and mode == '断点':
                return IOOps._breakpoint(evaluator)
        
        # 普通调试信息
        print("=== 调试信息 ===")
        print(f"调用栈深度: {evaluator.call_depth}")
        if evaluator.call_stack:
            Commands = _get_commands()
            last_op, last_args = evaluator.call_stack[-1]
            formatted = Commands._format_args(last_args) if last_args else ""
            print(f"最近调用: {last_op}({formatted})")
        print("变量:")
        for name, val in evaluator.vars.items():
            type_name = type(val).__name__
            if isinstance(val, TritValue):
                type_name = '三值整数'
                print(f"  {name}: {val} (类型: {type_name}, 三进制: {val.symbol})")
            elif isinstance(val, str):
                type_name = '字符串'
                print(f"  {name}: \"{val}\" (类型: {type_name}, 长度: {len(val)})")
            elif isinstance(val, list):
                type_name = '列表'
                print(f"  {name}: {val} (类型: {type_name}, 长度: {len(val)})")
            elif isinstance(val, dict):
                type_name = '字典'
                print(f"  {name}: {val} (类型: {type_name}, 键数: {len(val)})")
            elif isinstance(val, FunctionValue):
                type_name = '函数'
                print(f"  {name}: {val} (类型: {type_name})")
            elif isinstance(val, ModuleValue):
                type_name = '模块'
                print(f"  {name}: {val} (类型: {type_name})")
            else:
                print(f"  {name}: {val} (类型: {type_name})")
        print("传感器:")
        for name, val in evaluator.sensors.items():
            print(f"  {name}: {val.symbol} (int: {val.to_int()})")
        print("执行器:")
        for name, val in evaluator.actuators.items():
            print(f"  {name}: {val.symbol} (int: {val.to_int()})")
        print("================")
        return TritValue(0)

    @staticmethod
    def _breakpoint(evaluator):
        """断点调试：暂停执行，进入交互式调试模式"""
        print("\n=== 断点 ===")
        print("命令: (继续) 继续执行, (变量) 查看变量, (传感器) 查看传感器, (执行器) 查看执行器")
        print("输入表达式可求值，输入 (继续) 恢复执行")
        
        while True:
            try:
                cmd = input("调试> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n继续执行...")
                break
            
            if not cmd:
                continue
            
            if cmd in ('（继续）', '继续', '(继续)', 'continue', 'c'):
                print("继续执行...")
                break
            elif cmd in ('（变量）', '变量', '(变量)', 'vars', 'v'):
                print("变量:")
                for name, val in evaluator.vars.items():
                    print(f"  {name}: {val}")
            elif cmd in ('（传感器）', '传感器', '(传感器)', 'sensors', 's'):
                print("传感器:")
                for name, val in evaluator.sensors.items():
                    print(f"  {name}: {val.symbol} (int: {val.to_int()})")
            elif cmd in ('（执行器）', '执行器', '(执行器)', 'actuators', 'a'):
                print("执行器:")
                for name, val in evaluator.actuators.items():
                    print(f"  {name}: {val.symbol} (int: {val.to_int()})")
            elif cmd in ('（帮助）', '帮助', '(帮助)', 'help', 'h', '?'):
                print("命令:")
                print("  (继续) / c - 继续执行")
                print("  (变量) / v - 查看所有变量")
                print("  (传感器) / s - 查看传感器状态")
                print("  (执行器) / a - 查看执行器状态")
                print("  (帮助) / h - 显示此帮助")
                print("  其他输入将作为三言表达式求值")
            else:
                # 尝试作为表达式求值
                try:
                    from sugar import SugarConverter
                    ast = SugarConverter.convert(cmd, evaluator.skin_manager)
                    result = evaluator.eval(ast)
                    if result is not None:
                        from ops.io_ops import IOOps
                        formatted = IOOps.format_value(result)
                        print(f"  => {formatted}")
                except Exception as e:
                    print(f"  错误: {e}")
        
        return TritValue(0)

    @staticmethod
    def time_now(evaluator, args):
        return TritValue(int(time.time()))

    @staticmethod
    def sleep_op(evaluator, args):
        if len(args) != 1:
            raise SyntaxError("等待 需要一个参数（秒数）")
        sec = evaluator.eval(args[0]).to_int()
        try:
            time.sleep(sec)
        except KeyboardInterrupt:
            raise RuntimeError("等待被用户中断（Ctrl+C）")
        return TritValue(0)

    @staticmethod
    def read_file_op(evaluator, args):
        if len(args) != 1:
            raise SyntaxError("读文件 需要文件路径")
        path = evaluator.eval(args[0])
        if hasattr(path, 'to_int'):
            path = str(path.to_int())
        with open(str(path), 'r', encoding='utf-8') as f:
            content = f.read()
        return content

    @staticmethod
    def write_file_op(evaluator, args):
        if len(args) != 2:
            raise SyntaxError("写文件 需要路径和内容")
        path = evaluator.eval(args[0])
        content = evaluator.eval(args[1])
        if hasattr(path, 'to_int'):
            path = str(path.to_int())
        if not isinstance(content, str):
            content = str(content)
        with open(str(path), 'w', encoding='utf-8') as f:
            f.write(content)
        return TritValue(0)

    @staticmethod
    def is_number(evaluator, args):
        if len(args) != 1:
            raise SyntaxError("是数字 需要一个参数")
        val = evaluator.eval(args[0])
        if isinstance(val, TritValue):
            return TritValue(1)
        return TritValue(-1)

    @staticmethod
    def is_string(evaluator, args):
        if len(args) != 1:
            raise SyntaxError("是字符串 需要一个参数")
        val = evaluator.eval(args[0])
        if isinstance(val, str):
            return TritValue(1)
        return TritValue(-1)

    @staticmethod
    def str_equals(evaluator, args):
        if len(args) != 2:
            raise SyntaxError("字符串相等 需要两个参数")
        a = evaluator.eval(args[0])
        b = evaluator.eval(args[1])
        if isinstance(a, str) and isinstance(b, str):
            return TritValue(1 if a == b else -1)
        return TritValue(-1)

    @staticmethod
    def _load_file(evaluator, args):
        if len(args) != 1:
            raise SyntaxError("加载 需要文件路径")
        path = args[0]
        if isinstance(path, list):
            path = path[0]
        # 自动路径解析
        import os
        if isinstance(path, str) and not os.sep in path and not path.endswith('.san'):
            candidate = os.path.join('stdlib', path + '.san')
            if os.path.exists(candidate):
                path = candidate
        with open(path, 'r', encoding='utf-8') as f:
            code = f.read()
        if not code.strip():
            return TritValue(0)
        if '{' in code or ';' in code or '；' in code:
            from sugar import SugarConverter
            ast = SugarConverter.convert(code, evaluator.skin_manager)
            return evaluator.eval(ast)
        else:
            from lexer import tokenize
            from parser import parse
            lines = code.splitlines()
            last_result = TritValue(0)
            for line in lines:
                line = line.strip()
                if not line or line.startswith('；') or line.startswith(';') or line.startswith('//'):
                    continue
                tokens = tokenize(line)
                if not tokens:
                    continue
                ast = parse(tokens)
                last_result = evaluator.eval(ast)
            return last_result
        
    @staticmethod
    def import_module(evaluator, args):
        if len(args) != 1:
            raise SanyanSyntaxError("导入 需要一个文件路径")
        path = evaluator.eval(args[0])
        if hasattr(path, 'to_int'):
            path = str(path.to_int())
        # 自动路径解析：无后缀且无路径分隔符时，尝试 stdlib/xxx.san
        import os
        if not os.sep in path and not path.endswith('.san'):
            candidate = os.path.join('stdlib', path + '.san')
            if os.path.exists(candidate):
                path = candidate
        with open(path, 'r', encoding='utf-8') as f:
            code = f.read()
        if not code.strip():
            return ModuleValue({}, {})
        # 在独立求值器中执行代码，不污染当前环境
        from evaluator import SanyanEvaluator
        module_env = SanyanEvaluator(skin_manager=evaluator.skin_manager)
        if '{' in code or ';' in code or '；' in code:
            from sugar import SugarConverter
            ast = SugarConverter.convert(code, module_env.skin_manager)
        else:
            from lexer import tokenize
            from parser import parse
            tokens = tokenize(code)
            ast = parse(tokens)
        module_env.eval(ast)
        return ModuleValue(module_env.vars, module_env.commands)