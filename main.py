"""三言 —— 中文三进制编程语言 v3.4（主入口）"""
import sys
from repl import demo, repl
from evaluator import SanyanEvaluator
from sugar import SugarConverter
from ternary_core import TritValue
from skin import SkinManager

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

        skin_mgr = SkinManager('chinese')
        env = SanyanEvaluator(skin_manager=skin_mgr)
        try:
            ast = SugarConverter.convert(code, skin_mgr)
        except SyntaxError:
            # 糖语法失败 → 回退到原生 S 表达式解析
            from lexer import tokenize
            from parser import parse
            tokens = tokenize(code)
            if not tokens:
                sys.exit(0)
            ast = parse(tokens)

        try:
            result = env.eval(ast)
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"执行错误: {e}")
            sys.exit(1)

        if result is not None:
            def _has_output_like(node):
                if isinstance(node, list) and len(node) > 0:
                    if node[0] in ('print', 'concat', 'query', 'debug', '输出', '连接', '查', '调试'):
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
        sys.exit(0)
    else:
        print("欢迎来到「三言 v3.4」—— 母语可定制的三进制编程语言")
        print("=" * 50)
        demo(SkinManager('chinese'))
        repl()