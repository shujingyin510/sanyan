"""模糊测试：随机输入抗性验证"""

import sys, os, random, string, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lexer import tokenize
from parser import parse
from sugar import SugarConverter


def _random_string(max_len=80):
    """生成随机字符串（含非法字符、全角、Unicode）"""
    chars = (
        string.ascii_letters + string.digits + '　（）；：，。？！＂＃＄％＆＇＋－＊／＝＾＠～、｜｛｝【】《》'
        + string.punctuation + ' \n\t\r' + 'αβγ你好世界abc123'
    )
    length = random.randint(0, max_len)
    return ''.join(random.choice(chars) for _ in range(length))


def _random_native_code():
    """生成随机 token 序列（非语法导向，仅测试解析器健壮性）"""
    templates = [
        lambda: f'({_random_string(10)})',
        lambda: f'{_random_string(5)} {_random_string(5)}',
        lambda: '(' * random.randint(1, 5) + _random_string(10) + ')' * random.randint(0, 5),
        lambda: f'设 {_random_string(3)} = {random.randint(-100, 100)}',
        lambda: f'输出({_random_string(5)})',
    ]
    return random.choice(templates)()


class TestFuzzingNative(unittest.TestCase):
    """对本机解析器 (parse) 进行模糊测试"""

    def test_fuzz_random_strings(self):
        for i in range(500):
            code = _random_string(60)
            try:
                tokens = tokenize(code)
                parse(tokens)
            except (SyntaxError, RecursionError, SystemExit):
                pass
            except Exception as e:
                self.fail(f'Unexpected exception for input {code!r}: {e.__class__.__name__}: {e}')

    def test_fuzz_native_code(self):
        for i in range(500):
            code = _random_native_code()
            try:
                tokens = tokenize(code)
                parse(tokens)
            except (SyntaxError, RecursionError, SystemExit):
                pass
            except Exception as e:
                self.fail(f'Unexpected exception for native code {code!r}: {e.__class__.__name__}: {e}')

    def test_fuzz_extreme_brackets(self):
        """极端括号不匹配场景"""
        for depth in [10, 50, 100, 200]:
            code = '(' * depth + 'x' + ')' * (depth - 1)
            try:
                tokens = tokenize(code)
                parse(tokens)
            except (SyntaxError, RecursionError):
                pass
            except Exception as e:
                self.fail(f'Extreme bracket test failed at depth {depth}: {e.__class__.__name__}: {e}')

    def test_fuzz_empty_and_whitespace(self):
        for src in ['', '   ', '\n\n\n', '\t\t', ' \t\n ']:
            tokens = tokenize(src)
            ast = parse(tokens)
            self.assertIsNone(ast)


class TestFuzzingSugar(unittest.TestCase):
    """对糖语法解析器 (SugarConverter) 进行模糊测试"""

    def test_fuzz_random_strings(self):
        for i in range(500):
            code = _random_string(60)
            try:
                SugarConverter.convert(code)
            except (SyntaxError, RecursionError):
                pass
            except Exception as e:
                self.fail(f'Sugar fuzz failed for {code!r}: {e.__class__.__name__}: {e}')

    def test_fuzz_extreme_nesting(self):
        """深层嵌套块"""
        for depth in [10, 20, 30, 50]:
            code = '若 (真) { ' * depth + '输出(1)' + ' }' * depth
            try:
                SugarConverter.convert(code)
            except (SyntaxError, RecursionError):
                pass
            except Exception as e:
                self.fail(f'Sugar nesting depth {depth}: {e.__class__.__name__}: {e}')

    def test_fuzz_unclosed_constructs(self):
        """未闭合的语句构造"""
        cases = [
            '设 x = ',
            '若 (x > 5) { 输出(x) ',
            '遍历 i 从 1 到 10 { ',
            '定义 foo (x) { ',
            '尝试 { 设 a=1 ',
        ]
        for code in cases:
            try:
                SugarConverter.convert(code)
            except (SyntaxError, RecursionError):
                pass
            except Exception as e:
                self.fail(f'Unclosed construct {code!r}: {e.__class__.__name__}: {e}')


if __name__ == '__main__':
    unittest.main()
