"""三言 —— 中文三进制编程语言 v3.4（主入口）"""
import sys
from repl import demo, repl
from evaluator import SanyanEvaluator
from sugar import SugarConverter
from ternary_core import TritValue

if __name__ == '__main__':
    if len(sys.argv) > 1:
        filepath = sys.argv[1]
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                code = f.read()
        except FileNotFoundError:
            print(f"错误: 文件不存在 - {filepath}")
            sys.exit(1)
        except UnicodeDecodeError:
            print(f"错误: 文件编码不是UTF-8 - {filepath}")
            sys.exit(1)

        if not code.strip():
            sys.exit(0)

        env = SanyanEvaluator()
        try:
            if '{' in code or ';' in code:
                ast = SugarConverter.convert(code)
                result = env.eval(ast)
            else:
                from lexer import tokenize
                from parser import parse
                tokens = tokenize(code)
                ast = parse(tokens)
                result = env.eval(ast)

            # 判断最后一条语句是否是「输出」，避免重复打印
            if result is not None:
                last_is_output = False
                last_is_output = False
                if isinstance(ast, list) and len(ast) > 0:
                    # 这些语句的返回值通常没有展示意义
                    control_flow_ops = ('输出', '连接', '遍历', '循环', '若', '做')
                    if ast[0] in control_flow_ops:
                        last_is_output = True
                    elif ast[0] == '做' and len(ast) > 1:
                        last_stmt = ast[-1]
                        if isinstance(last_stmt, list) and len(last_stmt) > 0 and last_stmt[0] in control_flow_ops:
                            last_is_output = True
                if not last_is_output:
                    if isinstance(result, TritValue):
                        print(f"结果: {result.to_int()}")
                    else:
                        print(f"结果: {result}")
        except Exception as e:
            print(f"执行错误: {e}")
            sys.exit(1)
        sys.exit(0)
    else:
        print("欢迎来到「三言 v3.4」—— 模块化中文三进制编程语言")
        print("=" * 50)
        demo()
        repl()