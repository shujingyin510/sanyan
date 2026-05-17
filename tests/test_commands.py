"""Commands 模块单元测试：定义、调用、类型检查、尾递归"""

import sys
import os
import contextlib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
from ternary_core import TritValue
from values import SanyanSyntaxError, SanyanNameError, SanyanTypeError, SanyanRuntimeError
from evaluator import SanyanEvaluator
from skin import SkinManager


class TestCommandsDefine(unittest.TestCase):
    def setUp(self):
        self.env = SanyanEvaluator(skin_manager=SkinManager('chinese'))

    def test_define_normal(self):
        self.env.eval(['fn', '加一', ['x'], ['add', 'x', 1]])
        self.assertIn('加一', self.env.commands)

    def test_define_too_few_args(self):
        with self.assertRaises(SanyanSyntaxError):
            self.env.eval(['fn', 'bad'])

    def test_call_defined_command(self):
        self.env.eval(['fn', '加一', ['x'], ['add', 'x', 1]])
        result = self.env.eval(['加一', 5])
        self.assertEqual(result.to_int(), 6)

    def test_call_undefined_command(self):
        with contextlib.redirect_stdout(None):
            with self.assertRaises(SanyanNameError):
                self.env.eval(['未定义函数', 1])


class TestCheckType(unittest.TestCase):
    def test_type_check_passes(self):
        from values import check_type

        check_type(TritValue(42), '数字', 'x')

    def test_type_check_fails(self):
        from values import check_type

        with self.assertRaises(SanyanTypeError):
            check_type('hello', '数字', 'x')


class TestMatchParams(unittest.TestCase):
    def test_normal_match(self):
        from commands import Commands

        result = Commands._match_params(['a', 'b'], 'f', [1, 2])
        self.assertEqual(result, [1, 2])

    def test_dot_split(self):
        from commands import Commands

        result = Commands._match_params(['obj', 'val'], 'f', ['灯.亮'])
        self.assertEqual(result, ['灯', '亮'])

    def test_colon_split(self):
        from commands import Commands

        result = Commands._match_params(['obj', 'val'], 'f', ['灯：亮'])
        self.assertEqual(result, ['灯', '亮'])

    def test_arg_count_mismatch(self):
        from commands import Commands

        with self.assertRaises(SanyanSyntaxError):
            Commands._match_params(['a', 'b', 'c'], 'f', [1])


class TestTailCall(unittest.TestCase):
    def test_is_tail_call_direct(self):
        from commands import Commands

        self.assertTrue(Commands._is_tail_call(['f', 1], 'f'))

    def test_is_tail_call_via_return(self):
        from commands import Commands

        self.assertTrue(Commands._is_tail_call(['return', ['f', 1]], 'f'))

    def test_is_not_tail_call(self):
        from commands import Commands

        self.assertFalse(Commands._is_tail_call(['g', 1], 'f'))

    def test_tail_call_optimization(self):
        self.env = SanyanEvaluator(skin_manager=SkinManager('chinese'), max_loop_steps=1000)
        # 阶乘（尾递归版）
        self.env.eval(
            [
                'fn',
                '阶乘',
                ['n', 'acc'],
                ['if', ['eq', 'n', 1], ['return', 'acc'], ['阶乘', ['sub', 'n', 1], ['mul', 'n', 'acc']]],
            ]
        )
        result = self.env.eval(['阶乘', 10, 1])
        self.assertEqual(result.to_int(), 3628800)

    def test_recursion_depth_exceeded(self):
        self.env = SanyanEvaluator(skin_manager=SkinManager('chinese'), max_loop_steps=5)
        self.env.eval(['fn', '死循环', ['x'], ['死循环', ['add', 'x', 1]]])
        with contextlib.redirect_stdout(None):
            with self.assertRaises(SanyanRuntimeError):
                self.env.eval(['死循环', 0])


class TestFormatArgs(unittest.TestCase):
    def test_format_trit(self):
        from commands import Commands

        result = Commands._format_args([TritValue(5)])
        self.assertEqual(result, '5')

    def test_format_string_truncated(self):
        from commands import Commands

        result = Commands._format_args(['a' * 30])
        self.assertEqual(result, 'a' * 20 + '...')

    def test_format_list(self):
        from commands import Commands

        result = Commands._format_args([[1, 2, 3]])
        self.assertEqual(result, '[...]')


if __name__ == '__main__':
    unittest.main()
