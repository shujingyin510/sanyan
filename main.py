"""三言 —— 中文三进制编程语言 v3.4（主入口）"""
import sys
from repl import demo, repl
from evaluator import SanyanEvaluator
from sugar import SugarConverter

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
            else:
                from lexer import tokenize
                from parser import parse
                tokens = tokenize(code)
                ast = parse(tokens)
            result = env.eval(ast)
            if result:
                print(f"结果: {result.to_int()}")
        except Exception as e:
            print(f"执行错误: {e}")
            sys.exit(1)
        sys.exit(0)
    else:
        print("欢迎来到「三言 v3.4」—— 模块化中文三进制编程语言")
        print("=" * 50)
        demo()
        repl()