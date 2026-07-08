"""对抗性边界契约（0708 对抗探针固化）——健壮性回归钉。

核心契约：**任何畸形/极端输入，语言都只能有三种结局——正常求值、抛清晰的
`SanyanError`（可读、带定位）、或被内置上限兜住；绝不允许裸 Python 异常穿透、
进程崩溃（RecursionError/MemoryError）或无限挂起。**

覆盖编程语言常见边界：解析容错、数值边界、求值失控、容器越界、类型错配。
探针曾用这批输入钓出 `1.2.3` 畸形数字裸 `ValueError` 穿透（_eval_dot_symbol
的 `split('.')` 解包）——本文件把契约钉死，防回归。
"""

import pytest

from core.evaluator import SanyanEvaluator
from core.lexer import tokenize
from core.parser import parse_program
from core.values import SanyanError

_DEEP = '(输出 ' + '(加 1 ' * 2000 + '1' + ')' * 2000 + ')'  # 超深嵌套（Python 递归限制须被包住）


def _run(src):
    env = SanyanEvaluator(max_loop_steps=50000)
    r = None
    for form in parse_program(tokenize(src), src):
        r = env.eval(form)
    return r


# 契约主体：这批输入必须"要么正常返回、要么抛 SanyanError"——非 SanyanError 的
# 异常会自然传播、被 pytest 判失败（裸穿透/崩溃当场现形）；挂起由 CI 超时兜住。
_GRACEFUL = [
    '',  # 空文件
    '   \n\t ',  # 纯空白
    '(',  # 孤左括号
    '(加 1 2',  # 缺右括号
    '(输出 "未闭合字符串',  # 未闭合字符串
    '(加 1.2.3 0)',  # 畸形数字（曾裸穿透）
    '(输出 a.b.c)',  # 多级点符号作为值
    '(输出 x：y：z)',  # 多级全角冒号作为值
    '(除 1 0)',  # 除零
    '(幂 2 -1)',  # 负数幂
    '(未定义符号xyz)',  # 未定义
    '(加 "字符串" 5)',  # 类型错配
    '(取 (列表 1 2 3) 100)',  # 越界
    '(取 (列表) 0)',  # 空列表越界
    '(取键 (字典) "无")',  # 缺键
    '(加 99999999999999999999999999999999 1)',  # 超大整数
    '(设 ' + 'x' * 20000 + ' 1)',  # 超长标识符
    '(定义 f (n) (f n)) (f 1)',  # 深递归无基例
    '(循环 真 (设 x 1))',  # 无限循环（max_loop_steps 兜）
    _DEEP,  # 超深嵌套
]


@pytest.mark.parametrize('src', _GRACEFUL, ids=range(len(_GRACEFUL)))
def test_malformed_input_never_bare_traceback(src):
    try:
        _run(src)
    except SanyanError:
        pass  # 清晰错误 = 合格；其它异常传播 → 失败（裸穿透/崩溃被抓）


def test_malformed_number_gives_syntax_error():
    # 探针钓出的 bug 的定向回归钉：畸形数字给清晰语法错误，不裸 ValueError
    with pytest.raises(SanyanError, match='无法解析数字字面量'):
        _run('(加 1.2.3 0)')


def test_legal_floats_unaffected():
    # 修复不得误伤合法浮点
    assert _run('(加 1.5 2.5)').to_int() == 4
    assert _run('(加 -1.5 0.5)').to_int() == -1


def test_division_by_zero_is_clean():
    with pytest.raises(SanyanError, match='除数不能为零'):
        _run('(除 1 0)')


def test_deep_recursion_no_base_case_caught_not_crash():
    # 无基例递归 → 尾递归上限抛 SanyanError，不 RecursionError 崩
    with pytest.raises(SanyanError):
        _run('(定义 g (n) (g n)) (g 1)')


def test_deep_nesting_parse_caught_not_crash():
    # 超深嵌套 → Python 递归限制被解析器包成 SanyanError，不裸崩
    with pytest.raises(SanyanError):
        _run(_DEEP)


def test_container_out_of_bounds_clean():
    with pytest.raises(SanyanError, match='越界'):
        _run('(取 (列表 1 2 3) 100)')


# ── 糖语法前端（用户主用）：同一契约（对抗探针 0708 钓出两处：未闭合裸 SyntaxError、
#     超深嵌套 RecursionError 裸崩——均已收进 SanyanError 家族）──────────────────


def _run_sugar(src):
    from sugar.parser import parse_code

    ast, _comments = parse_code(src)  # 语法错误在此抛 SanyanSyntaxError
    env = SanyanEvaluator(max_loop_steps=50000)
    node = ast if (isinstance(ast, list) and ast and ast[0] == 'do') else ['do', ast]
    return env.eval(node)


_SUGAR_DEEP = '输出(' + '(' * 3000 + '1' + ')' * 3000 + ')'

_SUGAR_GRACEFUL = [
    '',  # 空
    '设 x =',  # 不完整赋值
    '设 x = 1.2.3',  # 畸形数字
    '定义 f() {',  # 未闭合花括号（曾裸 SyntaxError）
    '输出(1',  # 未闭合圆括号
    '输出("未闭合',  # 未闭合字符串
    '输出(1 + + + 2)',  # 连续操作符
    '输出(1 / 0)',  # 除零
    _SUGAR_DEEP,  # 超深嵌套（曾 RecursionError 裸崩）
    '定义 f(n) { 返回(f(n)); }\nf(1)',  # 深递归无基例
    '循环 (真) { 设 x = 1 }',  # 无限循环
    '输出(取(列表(1,2), 99))',  # 越界
    '输出("abc" + 5)',  # 类型错配
    '未定义函数xyz(1, 2)',  # 未定义
    '定义 f() { 若 (真) { 输出(',  # 嵌套未闭合混合
]


@pytest.mark.parametrize('src', _SUGAR_GRACEFUL, ids=range(len(_SUGAR_GRACEFUL)))
def test_sugar_malformed_never_bare_traceback(src):
    try:
        _run_sugar(src)
    except SanyanError:
        pass  # 清晰错误 = 合格；裸 SyntaxError/RecursionError 会传播 → 失败


def test_sugar_unclosed_is_sanyan_error():
    # 定向钉：未闭合结构进 SanyanError 家族（此前抛纯 SyntaxError，catch SanyanError 漏网）
    with pytest.raises(SanyanError):
        _run_sugar('定义 f() {')


def test_sugar_deep_nesting_no_crash():
    # 定向钉：超深嵌套包成 SanyanSyntaxError，不 RecursionError 裸崩
    with pytest.raises(SanyanError, match='嵌套过深'):
        _run_sugar(_SUGAR_DEEP)


# ── 运行时深水区（对抗探针 0708 第二轮：深嵌套 eval 递归 / 深相等 / 大整数显示）──
#     解析能过但 eval 阶段的深递归此前裸 RecursionError 崩（"死亡区间"：太浅正常、
#     太深被解析器兜住、中间地带 eval 裸崩）；大整数十进制显示裸 ValueError。

_RT_DEEP = '(列表 ' * 1000 + '1' + ')' * 1000  # eval 阶段深嵌套（解析通过、求值递归）

_RUNTIME_GRACEFUL = [
    _RT_DEEP,  # 深嵌套列表构造（eval 递归，曾裸 RecursionError）
    '(same ' + _RT_DEEP + ' ' + _RT_DEEP + ')',  # 深相等（先 eval 深参数，同一守护）
    '(输出 (幂 2 100000))',  # 大整数显示（曾裸 ValueError）
    '(幂 2 50000)',  # 大数计算（内部大整数）
    '(定义 f (n) (若 (等于 n 0) 0 (加 1 (f (减 n 1))))) (f 400)',  # 超命令递归上限
]


@pytest.mark.parametrize('src', _RUNTIME_GRACEFUL, ids=range(len(_RUNTIME_GRACEFUL)))
def test_runtime_deepwater_never_crash(src):
    try:
        _run(src)
    except SanyanError:
        pass  # 清晰错误 = 合格；裸 RecursionError/ValueError 会传播 → 失败


def test_deep_nested_eval_caught_not_crash():
    # 定向钉：深嵌套数据的 eval 递归包成 SanyanError，不裸 RecursionError 崩
    with pytest.raises(SanyanError, match='求值嵌套过深'):
        _run(_RT_DEEP)


def test_big_int_display_no_bare_valueerror():
    # 大整数十进制显示不裸 ValueError（给清晰位数信息）——不抛即合格
    _run('(输出 (幂 2 100000))')
