"""IO 操作模块测试 — 覆盖 format_value、debug_op 等当前未测试的路径"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import io
import unittest
from contextlib import redirect_stdout
from unittest import mock
from core.evaluator import SanyanEvaluator
from core.ternary_core import TritValue, ArrayValue
from core.values import ModuleValue, SanyanSyntaxError, SanyanTypeError, SanyanValueError
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


class TestFormatValueMore(unittest.TestCase):
    """format_value 边缘分支。"""

    def test_format_list_with_float_trit(self):
        out = IOOps.format_value([TritValue(3.5), TritValue(1)])
        self.assertIn('3.5', out)

    def test_format_huge_int_guarded(self):
        # 超大整数十进制转换触发 Python int→str 位数上限，应给位数信息而非崩溃
        out = IOOps.format_value(TritValue(10**5000))
        self.assertIn('大整数', out)


class TestDebugTypeBranches(unittest.TestCase):
    """debug 遍历各类型变量的分支。"""

    def setUp(self):
        self.env = SanyanEvaluator()

    def _debug(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.env.eval(['debug'])
        return buf.getvalue()

    def test_debug_list_dict_other(self):
        self.env.eval(['set', 'lst', ['list', 1, 2]])
        self.env.set_var('d', {'a': 1})
        self.env.set_var('f', 3.14)  # 非 Trit/str/list/dict → else 分支
        out = self._debug()
        self.assertIn('列表', out)
        self.assertIn('字典', out)

    def test_debug_module_value(self):
        self.env.set_var('m', ModuleValue({}, {}, set()))
        self.assertIn('模块', self._debug())


class TestBreakpointBranches(unittest.TestCase):
    """_breakpoint 交互命令分支（mock input）。"""

    def setUp(self):
        self.env = SanyanEvaluator()

    def test_breakpoint_all_commands(self):
        seq = ['变量', '传感器', '执行器', '帮助', '设 y = 5', '继续']
        buf = io.StringIO()
        with redirect_stdout(buf), mock.patch('builtins.input', side_effect=seq):
            r = self.env.eval(['debug', '"断点"'])
        self.assertEqual(r.to_int(), 0)
        self.assertIn('传感器', buf.getvalue())

    def test_breakpoint_eof(self):
        buf = io.StringIO()
        with redirect_stdout(buf), mock.patch('builtins.input', side_effect=EOFError):
            r = self.env.eval(['debug', '"断点"'])
        self.assertEqual(r.to_int(), 0)


class TestWaitTraceExplain(unittest.TestCase):
    """wait / trace / explain 算子。"""

    def setUp(self):
        self.env = SanyanEvaluator()

    def test_wait_ms(self):
        self.assertEqual(self.env.eval(['wait', 1]).to_int(), 0)

    def test_wait_trit_and_float(self):
        self.assertEqual(self.env.eval(['wait', ['add', 1, 0]]).to_int(), 0)  # TritValue 分支
        self.assertEqual(self.env.eval(['wait', 0.0]).to_int(), 0)  # float 分支

    def test_wait_no_arg(self):
        with self.assertRaises(SanyanSyntaxError):
            self.env.eval(['wait'])

    def test_wait_negative(self):
        with self.assertRaises(SanyanValueError):
            self.env.eval(['wait', -5])

    def test_wait_wrong_type(self):
        with self.assertRaises(SanyanTypeError):
            self.env.eval(['wait', '"abc"'])

    def test_trace(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.assertEqual(self.env.eval(['trace', ['add', 1, 1]]).to_int(), 0)

    def test_trace_no_args(self):
        self.assertEqual(self.env.eval(['trace']).to_int(), 0)

    def test_trace_low_confidence(self):
        # 必须构造新实例（带 confidence 绕过小值缓存），切勿改 TritValue(1) 共享单例
        lc = TritValue(1, confidence=0.5, source='test')
        self.env.set_var('lc', lc)
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.env.eval(['trace', 'lc'])
        self.assertIn('信度', buf.getvalue())

    def test_explain_numeric(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            r = self.env.eval(['explain', ['add', 1, 1]])
        self.assertIsNotNone(r)
        self.assertIn('置信度', buf.getvalue())

    def test_explain_low_confidence_source(self):
        lc = TritValue(1, confidence=0.3, source='sensor')
        self.env.set_var('lc', lc)
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.env.eval(['explain', 'lc'])
        out = buf.getvalue()
        self.assertIn('来源', out)
        self.assertIn('低信度', out)

    def test_explain_non_trit(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.assertEqual(self.env.eval(['explain', '"hi"']), 'hi')

    def test_explain_no_args(self):
        self.assertEqual(self.env.eval(['explain']).to_int(), 0)


if __name__ == '__main__':
    unittest.main()
