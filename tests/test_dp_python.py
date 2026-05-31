"""Python 版 parse_sanyan 测试（镜像 dp.c 的 7 项测试）

dp.c 使用 LLVM 编译的 parse_sanyan() C 入口，
本测试使用 Python lexer+parser 实现相同的解析逻辑，
确保 CI 中无需 C 编译器也可覆盖解析正确性。

注意：Python S-expression 解析器将列表中的数字保持为字符串，
顶层单数则解析为 Python int，字符串字面量保留引号。
"""



import unittest
from lexer import tokenize
from parser import parse


def parse_sanyan(source: str):
    """Python 版 parse_sanyan：lexer + parser"""
    tokens = tokenize(source)
    ast = parse(tokens)
    return ast


class TestParseSanyan(unittest.TestCase):
    """镜像 dp.c 的 7 项测试"""

    def test_int(self):
        ast = parse_sanyan('42')
        # S 表达式解析器将所有 token 保持为字符串
        self.assertEqual(ast, '42')

    def test_string(self):
        ast = parse_sanyan('"hello"')
        # 字符串字面量保留引号
        self.assertEqual(ast, '"hello"')

    def test_identifier(self):
        ast = parse_sanyan('x')
        self.assertEqual(ast, 'x')

    def test_list_add(self):
        ast = parse_sanyan('(add 1 2)')
        self.assertIsInstance(ast, list)
        self.assertEqual(ast[0], 'add')
        # S 表达式保持所有 token 为字符串
        self.assertEqual(ast[1], '1')
        self.assertEqual(ast[2], '2')

    def test_list_if(self):
        ast = parse_sanyan('(if 1 2 3)')
        self.assertIsInstance(ast, list)
        self.assertEqual(ast[0], 'if')

    def test_list_set(self):
        ast = parse_sanyan('(set x 42)')
        self.assertIsInstance(ast, list)
        self.assertEqual(ast[0], 'set')
        self.assertEqual(ast[1], 'x')

    def test_lambda(self):
        ast = parse_sanyan('(fn (f x) (return x))')
        self.assertIsInstance(ast, list)
        self.assertEqual(ast[0], 'fn')
        self.assertEqual(ast[1][0], 'f')
        self.assertEqual(ast[1][1], 'x')

    def test_nested_sexpr(self):
        ast = parse_sanyan('(add (mul 2 3) 4)')
        self.assertIsInstance(ast, list)
        self.assertEqual(ast[0], 'add')
        self.assertEqual(ast[1][0], 'mul')

    def test_multi_expr(self):
        """多表达式顶层返回第一个表达式（非 do 包裹）"""
        code = """
            (fn parse_sanyan (source) (lex source))
            (fn lex (s) (char_at s 0))
        """
        ast = parse_sanyan(code)
        self.assertIsInstance(ast, list)
        self.assertEqual(ast[0], 'fn')

    def test_utf8_identifiers(self):
        ast = parse_sanyan('(词法分析 source)')
        self.assertIsInstance(ast, list)
        self.assertEqual(ast[0], '词法分析')
        self.assertEqual(ast[1], 'source')


if __name__ == '__main__':
    unittest.main()
