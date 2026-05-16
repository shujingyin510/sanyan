"""糖语法解析器回归测试 — 验证 AST 结构正确性（unittest 格式）"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

import unittest
from sugar import SugarConverter


class TestSugarParserAST(unittest.TestCase):
    def assertAST(self, code, validator):
        ast = SugarConverter.convert(code)
        self.assertIsInstance(ast, list)
        self.assertTrue(len(ast) > 0)
        self.assertTrue(validator(ast), f"AST 结构校验失败: {ast}")

    def test_set(self):
        self.assertAST("设 x = 10",
                       lambda ast: ast[0] == 'set' and ast[1] == 'x' and ast[2] == '10')

    def test_set_short(self):
        self.assertAST("x = 5",
                       lambda ast: ast[0] == 'set' and ast[1] == 'x' and ast[2] == '5')

    def test_print(self):
        self.assertAST("输出(x)",
                       lambda ast: ast[0] == 'print' and ast[1] == 'x')

    def test_if(self):
        self.assertAST("若 (x > 5) { 输出(x) }",
                       lambda ast: ast[0] == 'if' and ast[1][0] == 'gt' and ast[2][0] == 'print')

    def test_if_elif_else(self):
        self.assertAST("若 (x > 5) { 输出(1) } 再若 (x < 0) { 输出(-1) } 否则 { 输出(0) }",
                       lambda ast: ast[0] == 'if' and len(ast) == 4 and ast[3][0] == 'if')

    def test_loop(self):
        self.assertAST("循环 (x < 10) { x = x + 1 }",
                       lambda ast: ast[0] == 'loop' and ast[1][0] == 'lt' and ast[2][0] == 'set')

    def test_for(self):
        self.assertAST("遍历 i 从 1 到 10 { 输出(i) }",
                       lambda ast: ast[0] == 'for' and ast[1] == 'i' and ast[2] == '1' and ast[3] == '10' and ast[4][0] == 'print')

    def test_fn(self):
        self.assertAST("定义 平方 (x) { x * x }",
                       lambda ast: ast[0] == 'fn' and ast[1] == '平方' and ast[2] == ['x'])

    def test_lambda(self):
        self.assertAST("设 加倍 = 函数(x) { x * 2 }",
                       lambda ast: ast[0] == 'set' and ast[2][0] == 'lambda' and ast[2][1] == ['x'])

    def test_template(self):
        self.assertAST("输出(模板{温度: ${x}°C})",
                       lambda ast: ast[0] == 'print' and ast[1][0] == 'concat')

    def test_judge(self):
        self.assertAST("判 x { 真 { 输出(1) } 可能 { 输出(0) } 假 { 输出(-1) } }",
                       lambda ast: ast[0] == 'judge' and ast[1] == 'x')

    def test_try(self):
        self.assertAST('尝试 { 设 a = 读文件("no.txt") } 捕获 (e) { 输出(e) }',
                       lambda ast: ast[0] == 'try' and ast[2][0] == '捕获')

    def test_read_sensor(self):
        self.assertAST("设 y = 读(人体)",
                       lambda ast: ast[0] == 'set' and ast[2][0] == 'read')

    def test_not_prefix(self):
        self.assertAST("输出(非 真)",
                       lambda ast: ast[0] == 'print' and ast[1][0] == 'not')

    def test_list_literal(self):
        self.assertAST("设 lst = 列表(1, 2, 3)",
                       lambda ast: ast[0] == 'set' and ast[2][0] == '列表')

    def test_dict(self):
        self.assertAST('设 d = 字典("a", 1, "b", 2)',
                       lambda ast: ast[0] == 'set' and ast[2][0] == '字典')

    def test_array(self):
        self.assertAST("设 arr = 数组(5, 0)",
                       lambda ast: ast[0] == 'set' and ast[2][0] == '数组')

    def test_container_index(self):
        self.assertAST("输出(lst(0))",
                       lambda ast: ast[0] == 'print' and ast[1][0] == 'lst')

    def test_map(self):
        self.assertAST("映射(函数(x) { x * 2 }, 列表(1,2))",
                       lambda ast: ast[0] == '映射' and ast[1][0] == 'lambda')

    def test_concat(self):
        self.assertAST('输出(连接("a", "b"))',
                       lambda ast: ast[0] == 'print' and ast[1][0] == '连接')

    def test_fullwidth_symbols(self):
        self.assertAST("设 a＝5；输出（a＋2）",
                       lambda ast: ast[0] == 'do' and ast[1][0] == 'set')

    def test_fullwidth_string_period(self):
        self.assertAST('输出("测试。")',
                       lambda ast: ast[0] == 'print' and isinstance(ast[1], str) and '。' in ast[1])


class TestSugarParserNegative(unittest.TestCase):
    def test_empty_string(self):
        ast = SugarConverter.convert("")
        self.assertIsNone(ast)

    def test_whitespace_only(self):
        ast = SugarConverter.convert("   \n  ")
        self.assertIsNone(ast)

    def test_comment_only(self):
        ast = SugarConverter.convert("// 注释")
        self.assertIsNone(ast)

    def test_hash_comment_only(self):
        ast = SugarConverter.convert("# 注释")
        self.assertIsNone(ast)

    def test_unmatched_bracket_throws(self):
        with self.assertRaises(SyntaxError):
            SugarConverter.convert("设 x = (1")

    def test_unclosed_string_throws(self):
        with self.assertRaises(SyntaxError):
            SugarConverter.convert('输出("hello)')


if __name__ == '__main__':
    unittest.main()
