"""REPL 交互环境与演示程序"""
from lexer import tokenize
from parser import parse
from evaluator import SanyanEvaluator
from sugar import SugarConverter

def _is_sugar(code):
    stripped = code.lstrip()
    if (stripped.startswith('(') or stripped.startswith('（')) and (')' in code or '）' in code):
        return False
    if '{' in code and '}' in code:
        return True
    if (';' in code or '；' in code) and any(
        kw in code for kw in (
            '设', '若', '循环', '输出', '查', '置', '调试', '输入',
            '连接', '取长', '绝对值', '随机数', '平方根', '最大值', '最小值',
            '加载', '映射', '过滤', '归并', '应用', '函数'
        )
    ):
        return True
    return False


def repl():
    print("三言 v3.4 REPL (支持中英文语法、中缀表达式)")
    print("输入（退出）或（exit）离开")
    env = SanyanEvaluator()
    while True:
        try:
            code = input("三言> ").strip()
            if not code:
                continue
            if code in ('（退出）', '退出', '（exit）', 'exit'):
                break

            if _is_sugar(code):
                ast = SugarConverter.convert(code)
                result = env.eval(ast)
            else:
                tokens = tokenize(code)
                if not tokens:
                    continue
                ast = parse(tokens)
                result = env.eval(ast)

            if result:
                should_print = True
                if isinstance(ast, list) and len(ast) > 0:
                    if ast[0] in ('输出', '查'):
                        should_print = False
                    elif ast[0] == '做' and len(ast) > 1:
                        last_stmt = ast[-1]
                        if isinstance(last_stmt, list) and len(last_stmt) > 0 and last_stmt[0] in ('输出', '查'):
                            should_print = False
                if should_print:
                    try:
                        print(f"  => {result.symbol}   (整数值: {result.to_int()})")
                    except AttributeError:
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