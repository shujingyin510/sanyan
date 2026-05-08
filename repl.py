"""REPL 交互环境与演示程序"""
from lexer import tokenize
from parser import parse
from evaluator import SanyanEvaluator
from sugar import SugarConverter
from skin import SkinManager


def demo(skin_mgr):
    print("\n========== 三言 v3.4 演示 ==========")
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


def repl():
    skin_mgr = SkinManager('chinese')
    env = SanyanEvaluator(skin_manager=skin_mgr)
    print("三言 v3.4 REPL (母语可定制)")
    print("输入 :lang english 切换英文，:lang chinese 切换中文")
    print("输入（退出）或（exit）离开")
    while True:
        try:
            code = input("三言> ").strip()
            code = code.replace('\u3000', ' ')   # 全角空格 → 半角空格
            if not code:
                continue
            if code in ('（退出）', '退出', '（exit）', 'exit'):
                break
            if code.startswith(':lang'):
                if code.startswith(':maxloop'):
                    parts = code.split()
                    if len(parts) == 2 and parts[1].isdigit():
                        env.max_loop_steps = int(parts[1])
                        print(f"最大循环步数已设为: {env.max_loop_steps}")
                    continue
                parts = code.split()
                if len(parts) == 2:
                    lang = parts[1]
                    if lang in ('chinese', 'english'):
                        skin_mgr.switch_skin(lang)
                        print(f"皮肤已切换至 {skin_mgr.lang}")
                    else:
                        print("支持的语言：chinese, english")
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
                except EOFError:
                    break
                if not next_line:
                    continue
                code += "\n" + next_line

            # 优先尝试糖语法，失败静默回退原生解析
            ast = None
            try:
                ast = SugarConverter.convert(code, skin_mgr)
            except SyntaxError:
                pass   # 糖语法失败属于正常情况（如用户输入 S 表达式），不回显错误

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

            try:
                result = env.eval(ast)
            except KeyboardInterrupt:
                print("\n  操作已中断（Ctrl+C）。")
                continue
            except Exception as e:
                print(f"  错误: {e}")
                print(f"    输入内容: {code}")
                continue

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
                        from ops.io_ops import IOOps
                        formatted = IOOps.format_value(result)
                        print(f"  => {formatted}")
                    except:
                        print(f"  => {result}")
        except KeyboardInterrupt:
            print("\n  操作已中断。")
            continue
        except Exception as e:
            print(f"  错误: {e}")
            print(f"    输入内容: {code}")