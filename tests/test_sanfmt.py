"""三言源码格式化器测试 — 覆盖 sanfmt.py 所有核心函数"""

import unittest
from sanfmt import _kw, _needs_parens, _fmt_expr, _fmt_body, _fmt_if, _fmt_stmt
from sanfmt import _reinsert_inline_comments, format_code


class TestKeywordMapping(unittest.TestCase):
    """关键字映射测试"""

    def test_binary_ops(self):
        self.assertEqual(_kw('add'), '加')
        self.assertEqual(_kw('sub'), '减')
        self.assertEqual(_kw('mul'), '乘')
        self.assertEqual(_kw('div'), '除')
        self.assertEqual(_kw('mod'), '余')
        self.assertEqual(_kw('pow'), '幂')

    def test_comparison_ops(self):
        self.assertEqual(_kw('eq'), '等于')
        self.assertEqual(_kw('neq'), '不等于')
        self.assertEqual(_kw('gt'), '大于')
        self.assertEqual(_kw('gte'), '大于等于')
        self.assertEqual(_kw('lt'), '小于')
        self.assertEqual(_kw('lte'), '小于等于')

    def test_logic_ops(self):
        self.assertEqual(_kw('and'), '且')
        self.assertEqual(_kw('or'), '或')
        self.assertEqual(_kw('not'), '非')

    def test_flow_keywords(self):
        self.assertEqual(_kw('if'), '若')
        self.assertEqual(_kw('else'), '否则')
        self.assertEqual(_kw('elif'), '再若')
        self.assertEqual(_kw('for'), '遍历')
        self.assertEqual(_kw('fn'), '定义')
        self.assertEqual(_kw('set'), '设')
        self.assertEqual(_kw('return'), '返回')
        self.assertEqual(_kw('do'), '做')

    def test_extra_display_names(self):
        self.assertEqual(_kw('concat'), '连接')
        self.assertEqual(_kw('length'), '取长')
        self.assertEqual(_kw('substring'), '子串')
        self.assertEqual(_kw('split'), '分割')
        self.assertEqual(_kw('find'), '查找')
        self.assertEqual(_kw('trim'), '去空白')
        self.assertEqual(_kw('upper'), '大写')
        self.assertEqual(_kw('lower'), '小写')
        self.assertEqual(_kw('starts'), '前缀')
        self.assertEqual(_kw('ends'), '后缀')

    def test_unmapped_passthrough(self):
        self.assertEqual(_kw('未知命令'), '未知命令')
        self.assertEqual(_kw('custom_op'), 'custom_op')


class TestParensNeeded(unittest.TestCase):
    """括号需求判断测试"""

    def test_non_list_node(self):
        self.assertFalse(_needs_parens('abc', 20))
        self.assertFalse(_needs_parens(42, 20))
        self.assertFalse(_needs_parens([], 20))

    def test_non_binary_op(self):
        self.assertFalse(_needs_parens(['fn', 'x', [], 'x'], 20))

    def test_lower_prec_no_parens(self):
        self.assertFalse(_needs_parens(['add', 1, 2], 10, False))
        self.assertFalse(_needs_parens(['mul', 1, 2], 10, False))

    def test_higher_prec_needs_parens(self):
        self.assertTrue(_needs_parens(['add', 1, 2], 30, False))

    def test_equal_prec_no_parens_left(self):
        self.assertFalse(_needs_parens(['add', 1, 2], 20, False))

    def test_equal_prec_needs_parens_right(self):
        self.assertTrue(_needs_parens(['add', 1, 2], 20, True))


class TestFormatExpr(unittest.TestCase):
    """表达式格式化测试"""

    def test_string(self):
        self.assertEqual(_fmt_expr('"hello"'), '"hello"')
        self.assertEqual(_fmt_expr('变量名'), '变量名')

    def test_integer_float(self):
        self.assertEqual(_fmt_expr(42), '42')
        self.assertEqual(_fmt_expr(3.14), '3.14')

    def test_empty_list(self):
        self.assertEqual(_fmt_expr([]), '[]')

    def test_binary_ops(self):
        self.assertEqual(_fmt_expr(['add', 1, 2]), '1 加 2')
        self.assertEqual(_fmt_expr(['sub', 10, 3]), '10 减 3')
        self.assertEqual(_fmt_expr(['mul', 3, 4]), '3 乘 4')
        self.assertEqual(_fmt_expr(['div', 10, 2]), '10 除 2')
        self.assertEqual(_fmt_expr(['mod', 10, 3]), '10 余 3')
        self.assertEqual(_fmt_expr(['pow', 2, 3]), '2 幂 3')

    def test_comparison_ops(self):
        self.assertEqual(_fmt_expr(['eq', 5, 5]), '5 等于 5')
        self.assertEqual(_fmt_expr(['neq', 5, 6]), '5 不等于 6')
        self.assertEqual(_fmt_expr(['gt', 5, 3]), '5 大于 3')
        self.assertEqual(_fmt_expr(['lt', 3, 5]), '3 小于 5')
        self.assertEqual(_fmt_expr(['gte', 5, 5]), '5 大于等于 5')
        self.assertEqual(_fmt_expr(['lte', 3, 5]), '3 小于等于 5')

    def test_nested_binary_ops_with_parens(self):
        result = _fmt_expr(['mul', ['add', 1, 2], 3])
        self.assertEqual(result, '(1 加 2) 乘 3')

    def test_nested_binary_ops_no_parens(self):
        result = _fmt_expr(['add', ['mul', 1, 2], 3])
        self.assertEqual(result, '1 乘 2 加 3')

    def test_right_associative_parens(self):
        result = _fmt_expr(['sub', 10, ['sub', 5, 3]])
        self.assertEqual(result, '10 减 (5 减 3)')

    def test_not_operation(self):
        self.assertEqual(_fmt_expr(['not', 1]), '非(1)')

    def test_function_call_style(self):
        result = _fmt_expr(['concat', '"a"', '"b"'])
        self.assertEqual(result, '连接("a", "b")')
        result = _fmt_expr(['length', '"hello"'])
        self.assertEqual(result, '取长("hello")')
        result = _fmt_expr(['random', 1, 10])
        self.assertEqual(result, '随机数(1, 10)')


class TestFormatBody(unittest.TestCase):
    """函数体格式化测试"""

    def test_do_block(self):
        result = _fmt_body(['do', ['set', 'x', 1], ['print', 'x']], 0)
        self.assertIn('设 x = 1', result)
        self.assertIn('输出(x)', result)

    def test_do_block_nested_indent(self):
        result = _fmt_body(['do', ['set', 'x', 1]], 2)
        self.assertIn('设 x = 1', result)
        self.assertTrue(result.startswith('        '))

    def test_empty_do(self):
        result = _fmt_body(['do'], 0)
        self.assertEqual(result, '')

    def test_single_statement(self):
        result = _fmt_body(['set', 'x', 1], 0)
        self.assertIn('设 x = 1', result)


class TestFormatIf(unittest.TestCase):
    """条件语句格式化测试"""

    def test_simple_if(self):
        ast = ['if', ['gt', 'x', 0], ['do', ['print', '"正数"']]]
        result = _fmt_if(ast, 0)
        self.assertIn('若 (x 大于 0)', result)
        self.assertIn('输出("正数")', result)

    def test_if_else(self):
        ast = ['if', ['gt', 'x', 0], ['do', ['print', '"正数"']], ['do', ['print', '"非正"']]]
        result = _fmt_if(ast, 0)
        self.assertIn('若 (x 大于 0)', result)
        self.assertIn('否则', result)
        self.assertIn('输出("非正")', result)

    def test_if_elif_else(self):
        ast = [
            'if',
            ['gt', 'x', 0],
            ['do', ['print', '"正值"']],
            ['if', ['eq', 'x', 0], ['do', ['print', '"零"']], ['do', ['print', '"负值"']]],
        ]
        result = _fmt_if(ast, 0)
        self.assertIn('若 (x 大于 0)', result)
        self.assertIn('再若 (x 等于 0)', result)
        self.assertIn('否则', result)
        self.assertIn('输出("负值")', result)

    def test_if_elif_no_else(self):
        ast = ['if', ['gt', 'x', 0], ['do', ['print', '"A"']], ['if', ['lt', 'x', 0], ['do', ['print', '"B"']]]]
        result = _fmt_if(ast, 0)
        self.assertIn('再若', result)
        self.assertNotIn('否则', result)


class TestFormatStmt(unittest.TestCase):
    """语句格式化测试"""

    def test_primitive_types(self):
        self.assertEqual(_fmt_stmt('"hello"').strip(), '"hello"')
        self.assertEqual(_fmt_stmt(42).strip(), '42')
        self.assertEqual(_fmt_stmt(3.14).strip(), '3.14')
        self.assertEqual(_fmt_stmt([]).strip(), '[]')

    def test_do_statement(self):
        result = _fmt_stmt(['do', ['set', 'x', 1], ['print', 'x']])
        self.assertIn('设 x = 1', result)
        self.assertIn('输出(x)', result)

    def test_empty_do_statement(self):
        result = _fmt_stmt(['do'])
        self.assertEqual(result.strip(), '{}')

    def test_set_statement(self):
        result = _fmt_stmt(['set', 'x', 1])
        self.assertEqual(result.strip(), '设 x = 1')
        result = _fmt_stmt(['set', 'name', '"hello"'])
        self.assertIn('设 name = "hello"', result)

    def test_return_statement(self):
        result = _fmt_stmt(['return', 42])
        self.assertEqual(result.strip(), '返回(42)')
        result = _fmt_stmt(['return'])
        self.assertEqual(result.strip(), '返回()')

    def test_break_continue(self):
        self.assertEqual(_fmt_stmt(['break']).strip(), '跳出')
        self.assertEqual(_fmt_stmt(['continue']).strip(), '继续')

    def test_print_statement(self):
        result = _fmt_stmt(['print', '"hello"']).strip()
        self.assertEqual(result, '输出("hello")')

    def test_if_statement(self):
        ast = ['if', ['gt', 'x', 0], ['do', ['print', '"A"']]]
        result = _fmt_stmt(ast)
        self.assertIn('若', result)
        self.assertIn('输出', result)

    def test_for_range_statement(self):
        ast = ['for', 'i', 0, 10, ['do', ['print', 'i']]]
        result = _fmt_stmt(ast)
        self.assertIn('遍历 i 从 0 到 10', result)
        self.assertIn('输出(i)', result)

    def test_forin_statement(self):
        ast = ['forin', 'item', 'lst', ['do', ['print', 'item']]]
        result = _fmt_stmt(ast)
        self.assertIn('遍历 item 在 lst', result)
        self.assertIn('输出(item)', result)

    def test_loop_statement(self):
        ast = ['loop', ['lt', 'i', 10], ['do', ['set', 'i', ['add', 'i', 1]]]]
        result = _fmt_stmt(ast)
        self.assertIn('循环 (i 小于 10)', result)

    def test_fn_statement(self):
        ast = ['fn', 'add', ['a', 'b'], {'a': 'int', 'b': 'int'}, ['do', ['return', ['add', 'a', 'b']]]]
        result = _fmt_stmt(ast)
        self.assertIn('定义 add(a: int, b: int)', result)
        self.assertIn('返回(a 加 b)', result)

    def test_fn_no_types(self):
        ast = ['fn', 'id', ['x'], ['do', ['return', 'x']]]
        result = _fmt_stmt(ast)
        self.assertIn('定义 id(x)', result)

    def test_try_catch_with_var(self):
        ast = ['try', ['do', ['print', '"A"']], 'e', ['do', ['print', 'e']]]
        result = _fmt_stmt(ast)
        self.assertIn('尝试', result)
        self.assertIn('捕获 (e)', result)

    def test_try_catch_no_var(self):
        ast = ['try', ['do', ['print', '"A"']], ['do', ['print', '"E"']]]
        result = _fmt_stmt(ast)
        self.assertIn('尝试', result)
        self.assertIn('捕获', result)

    def test_fallback_function_call(self):
        result = _fmt_stmt(['自定义命令', 'arg1', 'arg2'])
        self.assertIn('自定义命令(arg1, arg2)', result)


class TestCommentReinsertion(unittest.TestCase):
    """注释重插入测试"""

    def test_no_comments_returns_unchanged(self):
        formatted = '设 x = 1\n输出(x)\n'
        result = _reinsert_inline_comments(formatted, '')
        self.assertEqual(result, formatted)

    def test_inline_comment_restored(self):
        source = '设 x = 1  // 初始化\n输出(x)\n'
        formatted = '设 x = 1\n输出(x)\n'
        result = _reinsert_inline_comments(formatted, source)
        self.assertIn('// 初始化', result)

    def test_standalone_comment_prepended(self):
        source = '// 文件头部注释\n设 x = 1\n'
        formatted = '设 x = 1\n'
        result = _reinsert_inline_comments(formatted, source)
        self.assertIn('// 文件头部注释', result)
        self.assertTrue(result.index('// 文件头部注释') < result.index('设'))

    def test_include_lines_ignored(self):
        source = '#include "lib.san"\n设 x = 1  // 注释\n'
        formatted = '设 x = 1\n'
        result = _reinsert_inline_comments(formatted, source)
        self.assertIn('// 注释', result)
        self.assertNotIn('#include', result)

    def test_fullwidth_comment_markers(self):
        source = '设 x = 1  ／／ 全角注释\n输出(x)\n'
        formatted = '设 x = 1\n输出(x)\n'
        result = _reinsert_inline_comments(formatted, source)
        self.assertIn('／／ 全角注释', result)

    def test_ambiguous_comments_skipped(self):
        source = '设 x = 1  // a\n设 x = 1  // b\n'
        formatted = '设 x = 1\n'
        result = _reinsert_inline_comments(formatted, source)
        self.assertNotIn('//', result)


class TestFormatCode(unittest.TestCase):
    """主入口 format_code 测试"""

    def test_simple_expression(self):
        result = format_code(['print', '"hello"'])
        self.assertIn('输出("hello")', result)

    def test_with_source_comments(self):
        source = '输出("hello")  // 打招呼\n'
        result = format_code(['print', '"hello"'], source=source)
        self.assertIn('// 打招呼', result)

    def test_full_program(self):
        ast = [
            'do',
            ['set', 'x', 10],
            ['if', ['gt', 'x', 0], ['do', ['print', '"正数"']], ['do', ['print', '"非正"']]],
            ['fn', 'sqr', ['n'], ['do', ['return', ['mul', 'n', 'n']]]],
        ]
        result = format_code(ast)
        self.assertIn('设 x = 10', result)
        self.assertIn('若 (x 大于 0)', result)
        self.assertIn('否则', result)
        self.assertIn('定义 sqr(n)', result)
        self.assertIn('返回(n 乘 n)', result)


if __name__ == '__main__':
    unittest.main()
