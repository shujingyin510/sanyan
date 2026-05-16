"""三言 —— 中文三进制编程语言（主入口）"""
import sys
from repl import demo, repl
from VERSION import VERSION
from evaluator import SanyanEvaluator
from sugar import SugarConverter
from ternary_core import TritValue
from skin import SkinManager

def main():
    args = sys.argv[1:]

    # --ast-json 标志：输出 AST JSON 并退出
    if '--ast-json' in args:
        idx = args.index('--ast-json')
        if idx + 1 >= len(args):
            print("错误: --ast-json 需要文件路径")
            sys.exit(1)
        filepath = args[idx + 1]
        from ast_json import ast_from_file, ast_to_json
        ast = ast_from_file(filepath)
        import json
        print(json.dumps(ast_to_json(ast), ensure_ascii=False, indent=2))
        sys.exit(0)

    # --profile 标志
    profiling = '--profile' in args
    positional = [a for a in args if not a.startswith('--')]

    if positional:
        filepath = positional[0]
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

        from preprocess import preprocess_includes
        code = preprocess_includes(code)

        skin_mgr = SkinManager('chinese')
        env = SanyanEvaluator(skin_manager=skin_mgr)
        if profiling:
            env.profile_start()

        ast = None
        sugar_error = None
        try:
            ast = SugarConverter.convert(code, skin_mgr)
        except SyntaxError as e:
            sugar_error = str(e)

        if ast is None:
            from lexer import tokenize
            from parser import parse
            try:
                tokens = tokenize(code)
                ast = parse(tokens)
            except SyntaxError as e:
                msg = str(e)
                if sugar_error:
                    msg = f"{msg}\n  (sugar 语法解析也失败: {sugar_error})"
                print(f"语法错误: {msg}")
                import traceback
                traceback.print_exc()
                sys.exit(1)

        try:
            result = env.eval(ast)
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"执行错误: {e}")
            sys.exit(1)

        if profiling:
            print(env.profile_report())

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
                    if result.is_float():
                        print(f"结果: {result.to_float()}")
                    else:
                        print(f"结果: {result.to_int()}")
                else:
                    print(f"结果: {result}")
        sys.exit(0)
    else:
        print(f"欢迎来到「三言 v{VERSION}」—— 母语可定制的三进制编程语言")
        print("=" * 50)
        demo(SkinManager('chinese'))
        repl()

if __name__ == '__main__':
    main()
