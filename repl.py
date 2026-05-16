"""REPL 交互环境与演示程序"""
import os
from lexer import tokenize
from parser import parse
from evaluator import SanyanEvaluator
from sugar import SugarConverter
from skin import SkinManager
from runtime import BUILTIN_OPS
from ops.io_ops import IOOps

# REPL 历史记录
_history_file = os.path.expanduser('~/.sanyan_history')
try:
    import readline
    readline.set_history_length(1000)
    if os.path.exists(_history_file):
        readline.read_history_file(_history_file)
except ImportError:
    readline = None


def demo(skin_mgr: SkinManager) -> None:
    print("\n========== 三言 v3.10.0 演示 ==========")
    env = SanyanEvaluator(skin_manager=skin_mgr)

    # 1. 智能设备控制
    env.eval(['fn', '设置设备', ['对象', '状态'], ['context', '对象', '状态']])
    print("1. 智能设备控制")
    env.eval(['设置设备', '灯.亮'])
    env.eval(['query', '灯'])
    env.eval(['设置设备', '窗帘.关'])
    env.eval(['query', '窗帘'])

    # 2. 晚安模式
    print("\n2. 晚安模式（自定义命令）")
    env.eval(['fn', '晚安', [], ['do', ['设置设备', '灯.灭'], ['设置设备', '窗帘.关']]])
    env.eval(['晚安'])
    env.eval(['query', '灯'])
    env.eval(['query', '窗帘'])

    # 3. 数学运算与比较
    print("\n3. 数学运算与比较")
    env.eval(['set', 'a', 10])
    env.eval(['print', ['add', 'a', 5]])
    env.eval(['print', ['gt', 'a', 3]])

    # 4. 条件分支
    print("\n4. 条件分支")
    env.eval(['if', ['gt', 'a', 5], ['print', 1], ['print', 0]])

    # 5. 循环
    print("\n5. 循环")
    env.eval(['set', 'i', 0])
    env.eval(['loop', ['lt', 'i', 3], ['do', ['print', 'i'], ['set', 'i', ['add', 'i', 1]]]])

    # 6. 数学函数
    print("\n6. 数学函数")
    env.eval(['print', ['abs', -5]])
    env.eval(['print', ['sqrt', 81]])
    env.eval(['print', ['random', 1, 10]])

    # 7. 字符串拼接（注意字符串参数需要双引号）
    print("\n7. 字符串拼接")
    env.eval(['concat', '"你好"', '"世界"'])
    env.eval(['print', ['length', '"hello"']])

    print("========== 演示结束 ==========\n")


_BUILTIN_KEYWORDS = sorted(
    BUILTIN_OPS | {
        '再若', '否则', '真', '假', '可能',
        '开', '关', '守', '切换中文', '切换英文', '退出',
    }
)

def _make_completer(env):
    def completer(text, state):
        matches = []
        # 内置关键字
        for kw in _BUILTIN_KEYWORDS:
            if kw.startswith(text):
                matches.append(kw)
        # 当前变量名
        for name in env.all_scoped_vars():
            if name.startswith(text):
                matches.append(name)
        # 当前命令名
        for name in env.commands:
            if name.startswith(text):
                matches.append(name)
        # REPL 命令
        for cmd in [':lang', ':maxloop', 'exit', '退出']:
            if cmd.startswith(text):
                matches.append(cmd)
        matches.sort()
        if state < len(matches):
            return matches[state]
        return None
    return completer

def repl() -> None:
    skin_mgr = SkinManager('chinese')
    env = SanyanEvaluator(skin_manager=skin_mgr)

    # 设置自动补全
    if readline:
        readline.set_completer(_make_completer(env))
        readline.parse_and_bind('tab: complete')

    print("三言 v3.10.0 REPL (母语可定制)")
    print("输入 切换英文/:lang english 切换英文，切换中文/:lang chinese 切换中文")
    print("输入 退出/exit 离开，Tab 键自动补全")
    while True:
        try:
            code = input("三言> ").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            break
        try:
            code = code.replace('\u3000', ' ')   # 全角空格 → 半角空格
            if not code:
                continue
            if code in ('（退出）', '退出', '（exit）', 'exit'):
                break
            if code in ('切换中文', '（切换中文）'):
                skin_mgr.switch_skin('chinese')
                print(f"皮肤已切换至 {skin_mgr.lang}")
                continue
            if code in ('切换英文', '（切换英文）'):
                skin_mgr.switch_skin('english')
                print(f"皮肤已切换至 {skin_mgr.lang}")
                continue
            if code.startswith(':maxloop'):
                parts = code.split()
                if len(parts) == 2 and parts[1].isdigit():
                    env.max_loop_steps = int(parts[1])
                    print(f"最大循环步数已设为: {env.max_loop_steps}")
                continue
            if code.startswith(':lang'):
                parts = code.split()
                if len(parts) == 2:
                    lang = parts[1]
                    if lang in ('chinese', 'english', '中文', '英文'):
                        skin_mgr.switch_skin(lang)
                        print(f"皮肤已切换至 {skin_mgr.lang}")
                    else:
                        print("支持的语言：chinese/中文, english/英文")
                continue

            # 多行输入支持
            while True:
                if code.rstrip().endswith('{') or code.rstrip().endswith('（'):
                    pass
                else:
                    left_p = code.count('(') + code.count('（')
                    right_p = code.count(')') + code.count('）')
                    left_b = code.count('{')
                    right_b = code.count('}')
                    if left_p == right_p and left_b == right_b:
                        break
                try:
                    next_line = input("...   ").strip()
                except (KeyboardInterrupt, EOFError):
                    break
                if not next_line:
                    continue
                code += "\n" + next_line

            # 优先尝试糖语法，失败静默回退原生解析
            ast = None
            try:
                ast = SugarConverter.convert(code, skin_mgr)
            except SyntaxError:
                pass

            if ast is None:
                tokens = tokenize(code)
                if tokens:
                    try:
                        ast = parse(tokens)
                    except SyntaxError as e:
                        print(f"  语法错误: {e}")
                        continue

            if ast is None:
                continue

            result = env.eval(ast)

            if result is not None:
                should_print = True
                if isinstance(ast, list) and len(ast) > 0:
                    no_print_ops = ('print', 'query', '查', '输出', 'if', 'loop', 'for', 'fn', '定义', 'try', '连接', 'concat', '映射', '过滤', '归并')
                    if ast[0] in no_print_ops:
                        should_print = False
                    elif ast[0] == 'do' and len(ast) > 1:
                        last_stmt = ast[-1]
                        if isinstance(last_stmt, list) and len(last_stmt) > 0 and last_stmt[0] in no_print_ops:
                            should_print = False
                if should_print:
                    try:
                        formatted = IOOps.format_value(result)
                        print(f"  => {formatted}")
                    except Exception:
                        print(f"  => {result}")
        except KeyboardInterrupt:
            print("\n  操作已中断。")
        except Exception as e:
            print(f"  错误: {e}")
            print(f"    输入内容: {code}")

    # 保存历史记录
    if readline:
        try:
            readline.write_history_file(_history_file)
        except Exception:
            pass
