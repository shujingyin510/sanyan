"""IO 操作模块测试 — 覆盖 format_value、debug_op 等当前未测试的路径"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import unittest
from core.evaluator import SanyanEvaluator
from core.ternary_core import TritValue, ArrayValue
from ops.io_ops import IOOps


class TestFormatValue(unittest.TestCase):
    """值格式化测试 — 覆盖所有分支"""

    def test_format_plain_list(self):
        result = IOOps.format_value([1, 2, 3])
        self.assertEqual(result, '[1, 2, 3]')

    def test_format_list_with_trit_values(self):
        vals = [TritValue(1), TritValue(0), TritValue(-1)]
        result = IOOps.format_value(vals)
        self.assertIn('[1, 0, -1]', result)
        self.assertIn('三进制', result)
        self.assertIn('+', result)
        self.assertIn('0', result)
        self.assertIn('-', result)

    def test_format_list_mixed(self):
        vals = [TritValue(1), 'hello', TritValue(-1)]
        result = IOOps.format_value(vals)
        self.assertIn('hello', result)

    def test_format_list_all_non_trit(self):
        result = IOOps.format_value(['a', 'b', 'c'])
        self.assertIn('[a, b, c]', result)
        self.assertNotIn('三进制', result)

    def test_format_array_value(self):
        arr = ArrayValue(3, TritValue(0))
        arr.set(0, TritValue(1))
        arr.set(1, TritValue(-1))
        arr.set(2, TritValue(0))
        result = IOOps.format_value(arr)
        self.assertIn('三进制', result)

    def test_format_dict(self):
        result = IOOps.format_value({'a': 1, 'b': 2})
        self.assertTrue(isinstance(result, str))

    def test_format_trit_value_int(self):
        result = IOOps.format_value(TritValue(1))
        self.assertIn('1', result)
        self.assertIn('三进制', result)

    def test_format_trit_value_float(self):
        result = IOOps.format_value(TritValue(3.14))
        self.assertIn('3.14', result)
        self.assertIn('三进制', result)

    def test_format_trit_value_negative(self):
        result = IOOps.format_value(TritValue(-1))
        self.assertIn('-1', result)

    def test_format_trit_value_zero(self):
        result = IOOps.format_value(TritValue(0))
        self.assertIn('0', result)

    def test_format_plain_string(self):
        result = IOOps.format_value('hello')
        self.assertEqual(result, 'hello')

    def test_format_none(self):
        result = IOOps.format_value(None)
        self.assertIn('None', result)


class TestIOOpsEdgeCases(unittest.TestCase):
    """IO 操作边缘用例"""

    def setUp(self):
        self.env = SanyanEvaluator()

    def test_print_no_args(self):
        result = self.env.eval(['print'])
        self.assertEqual(result.to_int(), 0)

    def test_print_string(self):
        result = self.env.eval(['print', '"hello"'])
        self.assertEqual(result, 'hello')

    def test_print_number(self):
        result = self.env.eval(['print', '42'])
        self.assertEqual(result.to_int(), 42)

    def test_print_trit_value(self):
        self.env.eval(['set', 'x', ['add', 1, 2]])
        result = self.env.eval(['print', 'x'])
        self.assertEqual(result.to_int(), 3)

    def test_print_list_with_trits(self):
        self.env.eval(['set', 'lst', ['list', ['add', 1, 0], ['add', 2, 0], ['add', -1, 0]]])
        result = self.env.eval(['print', 'lst'])
        self.assertEqual(len(result), 3)

    def test_input_op_no_prompt(self):
        import io
        import sys

        saved = sys.stdin
        try:
            sys.stdin = io.StringIO('42\n')
            result = self.env.eval(['input'])
            sys.stdin = saved
            self.assertEqual(result.to_int(), 42)
        finally:
            sys.stdin = saved

    def test_input_op_with_prompt(self):
        import io
        import sys

        saved = sys.stdin
        try:
            sys.stdin = io.StringIO('-1\n')
            result = self.env.eval(['input', '"值"'])
            sys.stdin = saved
            self.assertEqual(result.to_int(), -1)
        finally:
            sys.stdin = saved

    def test_input_trit_state(self):
        import io
        import sys

        saved = sys.stdin
        try:
            sys.stdin = io.StringIO('真\n')
            result = self.env.eval(['input'])
            sys.stdin = saved
            self.assertIsInstance(result, TritValue)
            self.assertEqual(result.to_int(), 1)
        finally:
            sys.stdin = saved

    def test_input_plain_string(self):
        import io
        import sys

        saved = sys.stdin
        try:
            sys.stdin = io.StringIO('hello\n')
            result = self.env.eval(['input'])
            sys.stdin = saved
            self.assertEqual(result, 'hello')
        finally:
            sys.stdin = saved


class TestDebugOps(unittest.TestCase):
    """调试操作测试"""

    def setUp(self):
        self.env = SanyanEvaluator()
        self.env.set_var('x', TritValue(42))
        self.env.set_var('name', 'test')

    def test_debug_no_args(self):
        result = self.env.eval(['debug'])
        self.assertEqual(result.to_int(), 0)

    def test_debug_with_var(self):
        result = self.env.eval(['debug', '"x"'])
        self.assertEqual(result.to_int(), 0)

    def test_debug_breakpoint_cancelled(self):
        import io
        import sys

        saved = sys.stdin
        try:
            sys.stdin = io.StringIO('c\n')
            result = self.env.eval(['debug', '"断点"'])
            sys.stdin = saved
            self.assertEqual(result.to_int(), 0)
        finally:
            sys.stdin = saved


if __name__ == '__main__':
    unittest.main()
