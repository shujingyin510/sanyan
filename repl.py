"""REPL 交互环境与演示程序"""
from lexer import tokenize
from parser import parse
from evaluator import SanyanEvaluator
from sugar import SugarConverter


def repl():
    print("三言 v3.4 REPL (支持中英文语法、中缀表达式、多行输入)")
    print("输入（退出）或（exit）离开")
    env = SanyanEvaluator()
    while True:
        try:
            code = input("三言> ").strip()
            if not code:
                continue
            if code in ('（退出）', '退出', '（exit）', 'exit'):
                break

            # 多行输入支持（糖语法 & 原生语法，兼容全角括号）
            while True:
                # 检查是否需要续行
                if code.rstrip().endswith('{') or code.rstrip().endswith('（'):
                    # 以 { 或 （ 结尾，肯定未结束
                    pass
                else:
                    # 计算括号差值
                    left_p = code.count('(') + code.count('（')
                    right_p = code.count(')') + code.count('）')
                    left_b = code.count('{')
                    right_b = code.count('}')
                    if left_p == right_p and left_b == right_b:
                        break   # 括号匹配，无需续行
                # 需要续行
                try:
                    next_line = input("...   ").strip()
                except EOFError:
                    break   # 用户可能按了 Ctrl+D
                if not next_line:
                    continue
                code += "\n" + next_line

            # 优先尝试糖语法，失败回退原生
            try:
                ast = SugarConverter.convert(code)
                result = env.eval(ast)
            except SyntaxError as e:
                # 糖语法解析失败，先展示错误
                print(f"  糖语法解析错误: {e}")
                # 再回退原生解析
                tokens = tokenize(code)
                if not tokens:
                    continue
                ast = parse(tokens)
                result = env.eval(ast)
            except Exception as e:
                print(f"  错误: {e}")
                print(f"    输入内容: {code}")
                continue

            # 结果打印
            if result:
                should_print = True
                if isinstance(ast, list) and len(ast) > 0:
                    # 这些语句已经自己打印了结果，或者返回字符串等不需要重复打印
                    no_print_ops = ('输出', '查', '若', '循环', '遍历', '定义', '尝试', '连接')
                    if ast[0] in no_print_ops:
                        should_print = False
                    elif ast[0] == '做' and len(ast) > 1:
                        last_stmt = ast[-1]
                        if isinstance(last_stmt, list) and len(last_stmt) > 0 and last_stmt[0] in no_print_ops:
                            should_print = False
                if should_print:
                    # 安全打印：先尝试用三进制显示，失败则直接打印
                    try:
                        if hasattr(result, 'symbol') and hasattr(result, 'to_int'):
                            print(f"  => {result.symbol}   (整数值: {result.to_int()})")
                        else:
                            raise AttributeError
                    except:
                        print(f"  => {result}")
        except Exception as e:
            print(f"  错误: {e}")
            print(f"    输入内容: {code}")

def demo():
    print("\n========== 三言 v3.4 演示 ==========")
    env = SanyanEvaluator()

    env.eval(['定义', '设置设备', ['对象', '状态'], ['对', '对象', '状态']])
    print("1. 智能设备控制")
    env.eval(['设置设备', '灯.亮'])
    env.eval(['查', '灯'])
    env.eval(['设置设备', '窗帘.关'])
    env.eval(['查', '窗帘'])

    print("\n2. 晚安模式（自定义命令）")
    env.eval(['定义', '晚安', [], ['做', ['设置设备', '灯.灭'], ['设置设备', '窗帘.关']]])
    env.eval(['晚安'])
    env.eval(['查', '灯'])
    env.eval(['查', '窗帘'])

    print("\n3. 数学运算与比较")
    env.eval(['设', 'a', 10])
    env.eval(['输出', ['加', 'a', 5]])
    env.eval(['输出', ['大于', 'a', 3]])

    print("\n4. 条件分支")
    env.eval(['若', ['大于', 'a', 5], ['输出', 1], ['输出', 0]])

    print("\n5. 循环")
    env.eval(['设', 'i', 0])
    env.eval(['循环', ['小于', 'i', 3], ['做', ['输出', 'i'], ['设', 'i', ['加', 'i', 1]]]])

    print("\n6. 数学函数")
    env.eval(['输出', ['绝对值', -5]])
    env.eval(['输出', ['平方根', 81]])
    env.eval(['输出', ['随机数', 1, 10]])

    print("\n7. 字符串拼接")
    env.eval(['连接', '你好', '世界'])
    env.eval(['输出', ['取长', 'hello']])

    print("========== 演示结束 ==========\n")