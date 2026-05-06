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
            # 优先使用糖语法，失败时回退到原生 S‑表达式
            try:
                ast = SugarConverter.convert(code)
                result = env.eval(ast)
            except SyntaxError:
                from lexer import tokenize
                from parser import parse
                tokens = tokenize(code)
                if not tokens:
                    sys.exit(0)
                ast = parse(tokens)
                result = env.eval(ast)

            # 判断是否应该打印最终结果
            if result is not None:
                def _has_output_like(node):
                    if isinstance(node, list) and len(node) > 0:
                        if node[0] in ('输出', '连接', '查', '调试'):
                            return True
                        for child in node[1:]:
                            if _has_output_like(child):
                                return True
                    return False

                if not _has_output_like(ast):
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