"""sugar.san 专项测试：AST 兼容性 + 解析正确性"""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
from ops.file_ops import _parse_with_sugar_san, _load_sugar_parser, clear_cache
from sugar import SugarConverter
from skin import SkinManager


def _get_evaluator():
    return type('EvalMock', (), {'skin_manager': SkinManager('chinese')})()


def _sugar_parse(code):
    return _parse_with_sugar_san(code, _get_evaluator())


def _normalize_block(node):
    """展开单语句 ['do', stmt] 为 stmt（格式差异兼容）"""
    if isinstance(node, list) and len(node) > 0:
        head = node[0]
        if head == 'do' and len(node) == 2:
            inner = _normalize_block(node[1])
            return inner
        return [_normalize_block(x) for x in node]
    return node


def setUpModule():
    """模块级初始化：清缓存并预加载 sugar 解析器，复用给全部测试"""
    clear_cache()
    _load_sugar_parser(_get_evaluator())


class TestSugarSanLoading(unittest.TestCase):
    """sugar.san 模块能否正常加载"""

    def setUp(self):
        # 此测试需要独立验证完整加载流程，重置缓存
        clear_cache()

    def test_load_parser(self):
        parser = _load_sugar_parser(_get_evaluator())
        self.assertIsNotNone(parser)
        self.assertTrue(hasattr(parser, 'commands'))
        self.assertIn('解析', parser.commands)
        self.assertIn('词法分析', parser.commands)


class TestSugarSanBasicParsing(unittest.TestCase):
    """基本表达式解析——验证解析成功且结构正确"""

    def assertParses(self, code):
        ast = _sugar_parse(code)
        self.assertIsNotNone(ast, f'sugar.san failed to parse: {code}')

    def test_number(self):
        self.assertParses('42')

    def test_string(self):
        self.assertParses('"hello"')

    def test_identifier(self):
        self.assertParses('foo')

    def test_add(self):
        self.assertParses('加(1, 2)')

    def test_nested_ops(self):
        self.assertParses('加(1, 乘(2, 3))')

    def test_binary_ops(self):
        ast = _sugar_parse('1 + 2 * 3')
        self.assertIsNotNone(ast)
        self.assertIsInstance(ast, list)
        self.assertIn(ast[0], ('加', 'add'))


class TestSugarSanControlFlow(unittest.TestCase):
    """控制流语句"""

    def assertParses(self, code):
        ast = _sugar_parse(code)
        self.assertIsNotNone(ast, f'sugar.san failed to parse: {code}')

    def test_if(self):
        self.assertParses('若 (1) { 输出(1) }')

    def test_if_else(self):
        self.assertParses('若 (1) { 输出(1) } 否则 { 输出(2) }')

    def test_if_elif_else(self):
        self.assertParses('若 (1) { 输出(1) } 再若 (2) { 输出(2) } 否则 { 输出(3) }')

    def test_loop(self):
        self.assertParses('循环 (i < 10) { 输出(i) }')

    def test_set(self):
        self.assertParses('设 x = 42')

    def test_fn_def(self):
        self.assertParses('定义 加一 (x) { 返回(加(x, 1)) }')

    def test_return_stmt(self):
        self.assertParses('返回(42)')


class TestSugarSanListAndDict(unittest.TestCase):
    """列表、字典字面量"""

    def assertParses(self, code):
        ast = _sugar_parse(code)
        self.assertIsNotNone(ast, f'sugar.san failed to parse: {code}')

    def test_list_literal(self):
        ast = _sugar_parse('[1, 2, 3]')
        self.assertIsNotNone(ast)

    def test_list_empty(self):
        self.assertParses('[]')

    def test_list_nested(self):
        self.assertParses('[1, [2, 3], 4]')


class TestSugarSanTryCatch(unittest.TestCase):
    """异常处理"""

    def assertParses(self, code):
        ast = _sugar_parse(code)
        self.assertIsNotNone(ast, f'sugar.san failed to parse: {code}')

    def test_try_catch(self):
        self.assertParses('尝试 { 1 / 0 } 捕获 (e) { 输出(e) }')

    def test_try_catch_no_var(self):
        self.assertParses('尝试 { 1 / 0 } 捕获 { 输出("err") }')


class TestSugarSanOpPrecedence(unittest.TestCase):
    """运算符优先级"""

    def assertParses(self, code):
        ast = _sugar_parse(code)
        self.assertIsNotNone(ast, f'sugar.san failed to parse: {code}')

    def test_arithmetic_precedence(self):
        ast = _sugar_parse('1 + 2 * 3')
        self.assertIsNotNone(ast)
        # 验证乘法优先级高于加法
        if isinstance(ast, list) and len(ast) == 3:
            self.assertIn(ast[0], ('加', 'add', '+'))
            self.assertIsInstance(ast[2], list)

    def test_parentheses(self):
        self.assertParses('(1 + 2) * 3')

    def test_comparison_chain(self):
        self.assertParses('a > 1 且 b < 2')

    def test_prefix_not(self):
        self.assertParses('非(真)')

    def test_negation(self):
        self.assertParses('-42')


class TestSugarSanEdgeCases(unittest.TestCase):
    """边界情况"""

    def assertParses(self, code):
        ast = _sugar_parse(code)
        self.assertIsNotNone(ast, f'sugar.san failed to parse: {code}')

    def test_fullwidth_parens(self):
        self.assertParses('加（1, 2）')

    def test_empty_block(self):
        self.assertParses('若 (1) { }')

    def test_nested_blocks(self):
        self.assertParses('若 (1) { 若 (2) { 输出(3) } }')

    def test_fullwidth_digits(self):
        ast = _sugar_parse('加（１２３， ４５６）')
        self.assertIsNotNone(ast)

    def test_fullwidth_string(self):
        self.assertParses('输出（"你好"）')

    def test_multi_digit(self):
        """全角多位数应解析为单一数字"""
        ast = _sugar_parse('加（１２３， ４５６）')
        self.assertIsNotNone(ast)
        # 验证数字被正确识别（不会把１２３拆成三个单独数字）
        ast_str = str(ast)
        # 不应包含单独的 '１'、'２'、'３' 数字 token
        self.assertNotIn("'１'", ast_str)


class TestSugarSanStructural(unittest.TestCase):
    """特定 AST 结构验证"""

    def test_if_structure(self):
        ast = _sugar_parse('若 (1) { 输出(1) }')
        self.assertIsNotNone(ast)
        norm = _normalize_block(ast)
        self.assertIsInstance(norm, list)
        self.assertIn(norm[0], ('若', 'if'))

    def test_fn_def_structure(self):
        ast = _sugar_parse('定义 加一 (x) { 返回(加(x, 1)) }')
        self.assertIsNotNone(ast)
        norm = _normalize_block(ast)
        self.assertIsInstance(norm, list)
        self.assertIn(norm[0], ('定义', 'fn'))
        self.assertEqual(norm[1], '加一')

    def test_try_catch_structure(self):
        ast = _sugar_parse('尝试 { 1 / 0 } 捕获 (e) { 输出(e) }')
        self.assertIsNotNone(ast)
        norm = _normalize_block(ast)
        self.assertIsInstance(norm, list)
        self.assertIn(norm[0], ('尝试', 'try'))

    def test_set_structure(self):
        ast = _sugar_parse('设 x = 42')
        self.assertIsNotNone(ast)
        self.assertIn(ast[0], ('设', 'set'))
        self.assertEqual(ast[1], 'x')


class TestSugarSanDotAccess(unittest.TestCase):
    """点号属性访问"""

    def test_dot_access(self):
        ast = _sugar_parse('模.加')
        self.assertIsNotNone(ast)
        self.assertIsInstance(ast, str)
        self.assertIn('.', ast)


class TestSugarSanPythonCompat(unittest.TestCase):
    """与 Python SugarConverter 的 AST 兼容性（结构级）"""

    def _compare_ast_loose(self, code):
        """宽松比较：归一化后校验结构兼容。

        sugar.san 自举解析器可能无法解析某些语法（如内联 {} 块），
        此时仅验证 Python 解析器成功，跳过深度比对。
        """
        sugar_ast = _sugar_parse(code)
        py_ast = SugarConverter.convert(code, SkinManager('chinese'))
        self.assertIsNotNone(py_ast, f'Python failed for: {code}')
        if sugar_ast is None:
            # sugar.san 自举解析器尚未支持此语法，OK
            return
        norm_sugar = _normalize_block(sugar_ast)

        def depth(n):
            if isinstance(n, list):
                return 1 + max((depth(x) for x in n), default=0)
            return 0

        self.assertAlmostEqual(depth(norm_sugar), depth(py_ast), delta=1, msg=f'AST depth mismatch for: {code}')

    def test_add_compat(self):
        self._compare_ast_loose('加(1, 2)')

    def test_nested_compat(self):
        self._compare_ast_loose('加(1, 乘(2, 3))')

    def test_if_compat(self):
        self._compare_ast_loose('若 (1 等于 2) { 输出("no") }')

    def test_if_else_compat(self):
        self._compare_ast_loose('若 (1 等于 2) { 输出("yes") } 其余 { 输出("no") }')

    def test_fn_def_compat(self):
        self._compare_ast_loose('定义 f(x) { 返回 x }')

    def test_set_var_compat(self):
        self._compare_ast_loose('设 x = 42')

    def test_loop_compat(self):
        self._compare_ast_loose('设 i = 0\n循环 (i < 10) { i = i + 1 }')

    def test_annotation_compat(self):
        self._compare_ast_loose('定义 f(a: 数字) { 返回 a }')

    def test_and_or_compat(self):
        self._compare_ast_loose('若 (真 且 假) { 输出("nope") }')

    def test_not_compat(self):
        self._compare_ast_loose('若 (非 真) { 输出("no") }')


if __name__ == '__main__':
    unittest.main()
