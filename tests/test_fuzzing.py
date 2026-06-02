"""基础模糊测试：随机输入验证解析器不崩溃"""

import unittest
import random
import string

from lexer import tokenize
from parser import parse


class TestFuzzParser(unittest.TestCase):
    """S-表达式解析器模糊测试"""

    def test_random_tokens(self):
        """随机 token 序列不崩溃"""
        tokens = list('()"hello"')
        for _ in range(100):
            seq = ''.join(random.choice(tokens) for _ in range(random.randint(1, 20)))
            try:
                tokenize(seq)
            except Exception as e:
                if not isinstance(e, (SystemExit, KeyboardInterrupt)):
                    self.fail(f'词法分析崩溃: {e}\n输入: {repr(seq)}')

    def test_balanced_parens(self):
        """平衡括号应成功解析"""
        for _ in range(50):
            depth = random.randint(0, 5)
            seq = '(' * depth + 'x' + ')' * depth
            try:
                tokens = tokenize(seq)
                ast = parse(tokens)
                self.assertIsNotNone(ast)
            except Exception as e:
                self.fail(f'平衡括号解析失败: {e}\n输入: {repr(seq)}')

    def test_unbalanced_parens(self):
        """不平衡括号不崩溃"""
        for _ in range(50):
            seq = '(' * random.randint(1, 10) + 'x' + ')' * random.randint(0, 10)
            tokens = tokenize(seq)
            try:
                parse(tokens)
            except Exception as e:
                if not isinstance(e, (SystemExit, KeyboardInterrupt, SyntaxError)):
                    self.fail(f'不平衡括号崩溃: {e}\n输入: {repr(seq)}')

    def test_random_strings(self):
        """随机字符串不崩溃"""
        for _ in range(50):
            s = ''.join(random.choice(string.printable) for _ in range(random.randint(1, 100)))
            try:
                tokens = tokenize(f'"{s}"')
                parse(tokens)  # noqa: F841
            except Exception as e:
                if not isinstance(e, (SystemExit, KeyboardInterrupt, SyntaxError)):
                    self.fail(f'随机字符串崩溃: {e}')


if __name__ == '__main__':
    unittest.main()
