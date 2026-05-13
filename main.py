"""三言 —— 中文三进制编程语言 v3.5（主入口）"""
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

        # #include 预处理器
        import os
        lines = code.split('\n')
        processed = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('#include') or stripped.startswith('＃include'):
                parts = stripped.split(None, 1)
                if len(parts) == 2:
                    path = parts[1].strip('"').strip("'").strip('＂').strip('＇')
                    if not os.sep in path and not path.endswith('.san'):
                        candidate = os.path.join('stdlib', path + '.san')
                        if os.path.exists(candidate):
                            path = candidate
                    if os.path.exists(path):
                        with open(path, 'r', encoding='utf-8') as f:
                            included = f.read()
                        processed.append(included)
                    else:
                        processed.append(f'／／ #include {path} (文件不存在，已跳过)')
                else:
                    processed.append(line)
            else:
                processed.append(line)
        code = '\n'.join(processed)

        skin_mgr = SkinManager('chinese')
        env = SanyanEvaluator(skin_manager=skin_mgr)
        try:
            has_sugar = False
            in_str = False
            str_ch = ''
            in_comment = False
            for ch in code:
                if in_comment:
                    if ch == '\n':
                        in_comment = False
                    continue
                if in_str:
                    if ch == str_ch:
                        in_str = False
                    continue
                if ch in ('"', '\u201c', '\u2018'):
                    in_str = True
                    str_ch = '"' if ch == '"' else ('\u201d' if ch == '\u201c' else '\u2019')
                    continue
                if ch == '/' and code[code.index(ch)+1:code.index(ch)+2] == '/':
                    in_comment = True
                    continue
                if ch == '／' and code[code.index(ch)+1:code.index(ch)+2] == '／':
                    in_comment = True
                    continue
                if ch == '{' or ch == ';':
                    has_sugar = True
                    break
            if has_sugar:
                ast = SugarConverter.convert(code, skin_mgr)
            else:
                from lexer import tokenize
                from parser import parse
                tokens = tokenize(code)
                ast = parse(tokens)
                if ast is None:
                    ast = []
        except SyntaxError as e:
            print(f"语法错误: {e}")
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
        print("欢迎来到「三言 v3.5」—— 母语可定制的三进制编程语言")
        print("=" * 50)
        demo(SkinManager('chinese'))
        repl()