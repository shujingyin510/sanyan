"""输入/输出、文件、时间、类型判断等"""
import time
from ternary_core import TritValue
from values import call_function   # 替换原来的 Builtins 依赖

class IOOps:
    @staticmethod
    def output(evaluator, args):
        if len(args) == 0:
            return TritValue(0)
        val = evaluator.eval(args[0])
        if isinstance(val, TritValue):
            print(f"  => {val.to_int()}  (三进制: {val.symbol})")
        elif isinstance(val, str):
            print(f"  => {val}")
        else:
            print(f"  => {val}")
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
        print("=== 调试信息 ===")
        print("变量:")
        for name, val in evaluator.vars.items():
            print(f"  {name}: {val}")
        print("传感器:")
        for name, val in evaluator.sensors.items():
            print(f"  {name}: {val.symbol} (int: {val.to_int()})")
        print("执行器:")
        for name, val in evaluator.actuators.items():
            print(f"  {name}: {val.symbol} (int: {val.to_int()})")
        print("================")
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