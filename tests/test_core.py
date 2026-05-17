"""Python 单测：覆盖运行时核心模块。
运行方式：python tests/test_core.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
from ternary_core import BT, TernaryALU, TritValue, ternary_sin, ternary_sqrt, ternary_exp, ternary_log
from values import (
    SanyanError, SanyanNameError, SanyanSyntaxError, SanyanTypeError,
    SanyanValueError, SanyanRuntimeError, SanyanKeyError, SanyanAttributeError,
    SanyanIOError, ReturnException, BreakException, FunctionValue, ModuleValue,
)
from runtime import SanyanRuntime
from skin import SkinManager
from preprocess import preprocess_includes, _safe_include_path


class TestTernaryCore(unittest.TestCase):
    """三进制核心运算"""

    def test_int_conversion(self):
        cases = [(0, [0]), (1, [1]), (-1, [-1]), (2, [1, -1]),
                 (3, [1, 0]), (5, [1, -1, -1]), (10, [1, 0, 1]),
                 (-5, [-1, 1, 1])]
        for dec, trits in cases:
            with self.subTest(dec=dec):
                self.assertEqual(BT.from_int(dec), trits)
                self.assertEqual(BT.to_int(trits), dec)

    def test_add(self):
        self.assertEqual(BT.to_int(TernaryALU.add(BT.from_int(2), BT.from_int(3))), 5)
        self.assertEqual(BT.to_int(TernaryALU.add(BT.from_int(10), BT.from_int(-5))), 5)
        self.assertEqual(BT.to_int(TernaryALU.add(BT.from_int(0), BT.from_int(0))), 0)

    def test_sub(self):
        self.assertEqual(BT.to_int(TernaryALU.sub(BT.from_int(10), BT.from_int(3))), 7)
        self.assertEqual(BT.to_int(TernaryALU.sub(BT.from_int(0), BT.from_int(5))), -5)

    def test_multiply(self):
        self.assertEqual(BT.to_int(TernaryALU.multiply(BT.from_int(3), BT.from_int(4))), 12)
        self.assertEqual(BT.to_int(TernaryALU.multiply(BT.from_int(7), BT.from_int(0))), 0)
        self.assertEqual(BT.to_int(TernaryALU.multiply(BT.from_int(-3), BT.from_int(5))), -15)
        # 大数乘法（快速路径）
        self.assertEqual(BT.to_int(TernaryALU.multiply(BT.from_int(12345), BT.from_int(67890))),
                         12345 * 67890)

    def test_logic(self):
        a, b = BT.from_int(1), BT.from_int(-1)
        self.assertEqual(BT.to_int(TernaryALU.tritwise_and(a, b)), -1)
        self.assertEqual(BT.to_int(TernaryALU.tritwise_or(a, b)), 1)
        self.assertEqual(BT.to_int(TernaryALU.tritwise_not(a)), -1)

    def test_trit_value_pool(self):
        a = TritValue(5)
        b = TritValue(5)
        self.assertIs(a, b)  # 对象池复用

    def test_trit_value_states(self):
        self.assertEqual(TritValue(1).to_int(), 1)
        self.assertEqual(TritValue(0).to_int(), 0)
        self.assertEqual(TritValue(-1).to_int(), -1)
        self.assertEqual(TritValue.from_string('真').to_int(), 1)
        self.assertEqual(TritValue.from_string('假').to_int(), -1)
        self.assertEqual(TritValue.from_string('可能').to_int(), 0)


class TestExceptions(unittest.TestCase):
    """异常体系"""

    def test_hierarchy(self):
        self.assertTrue(issubclass(SanyanNameError, SanyanError))
        self.assertTrue(issubclass(SanyanSyntaxError, SanyanError))
        self.assertTrue(issubclass(SanyanTypeError, SanyanError))
        self.assertTrue(issubclass(SanyanValueError, SanyanError))
        self.assertTrue(issubclass(SanyanRuntimeError, SanyanError))
        self.assertTrue(issubclass(SanyanKeyError, SanyanError))
        self.assertTrue(issubclass(SanyanAttributeError, SanyanError))
        self.assertTrue(issubclass(SanyanIOError, SanyanError))

    def test_value_error_message(self):
        e = SanyanValueError("除数不能为零")
        self.assertIn("除数不能为零", str(e))


class TestScopes(unittest.TestCase):
    """作用域栈式链"""

    def setUp(self):
        self.rt = SanyanRuntime()

    def test_initial_scope(self):
        self.assertEqual(len(self.rt._scopes), 1)
        self.assertEqual(self.rt._scopes[0], {})

    def test_push_pop(self):
        self.rt.push_scope()
        self.assertEqual(len(self.rt._scopes), 2)
        self.rt.pop_scope()
        self.assertEqual(len(self.rt._scopes), 1)

    def test_pop_global_protection(self):
        self.rt.pop_scope()
        self.rt.pop_scope()
        self.assertEqual(len(self.rt._scopes), 1)  # 全局作用域永不被弹出

    def test_set_and_get(self):
        self.rt.set_var('x', TritValue(10))
        self.assertEqual(self.rt.get_var('x').to_int(), 10)
        self.assertTrue(self.rt.has_var('x'))

    def test_cross_scope_lookup(self):
        self.rt.scope_vars['global_x'] = TritValue(100)
        self.rt.push_scope()
        self.rt.set_var('local_x', TritValue(50))
        # 可以从内层查找外层
        self.assertEqual(self.rt.get_var('global_x').to_int(), 100)
        self.assertEqual(self.rt.get_var('local_x').to_int(), 50)

    def test_inner_shadows_outer(self):
        self.rt.scope_vars['x'] = TritValue(1)
        self.rt.push_scope()
        self.rt.set_var('x', TritValue(2))
        self.assertEqual(self.rt.get_var('x').to_int(), 2)  # 内层覆盖
        self.rt.pop_scope()
        self.assertEqual(self.rt.get_var('x').to_int(), 1)  # 外层恢复

    def test_all_scoped_vars(self):
        self.rt.scope_vars['a'] = TritValue(1)
        self.rt.push_scope()
        self.rt.set_var('b', TritValue(2))
        all_vars = self.rt.all_scoped_vars()
        self.assertEqual(all_vars['a'].to_int(), 1)
        self.assertEqual(all_vars['b'].to_int(), 2)

    def test_vars_property_write(self):
        self.rt.scope_vars['x'] = TritValue(42)
        self.assertEqual(self.rt.get_var('x').to_int(), 42)
        self.rt.push_scope()
        self.rt.scope_vars['y'] = TritValue(99)
        self.assertEqual(self.rt.scope_vars['y'].to_int(), 99)
        self.rt.pop_scope()
        self.assertFalse(self.rt.has_var('y'))  # 局部变量已清理


class TestFunctionValue(unittest.TestCase):
    """函数值和闭包"""

    def test_call_args_mismatch(self):
        from evaluator import SanyanEvaluator
        fn = FunctionValue(['x'], [['print', 'x']])
        rt = SanyanEvaluator()
        with self.assertRaises(SanyanSyntaxError):
            fn.call(rt, [])

    def test_closure_capture(self):
        from evaluator import SanyanEvaluator
        rt = SanyanEvaluator()
        rt.set_var('captured', TritValue(100))
        fn = FunctionValue([], [], closure_vars={'captured': TritValue(100)})
        old_count = len(rt._scopes)
        fn.call(rt, [])
        self.assertEqual(len(rt._scopes), old_count)


class TestControlFlow(unittest.TestCase):
    """控制流异常"""

    def test_return_exception(self):
        e = ReturnException(TritValue(42))
        self.assertEqual(e.value.to_int(), 42)

    def test_break_exception(self):
        e = BreakException()
        self.assertIsInstance(e, BreakException)


class TestModuleValue(unittest.TestCase):
    """模块值"""

    def test_call_missing_func(self):
        mod = ModuleValue({}, {})
        rt = SanyanRuntime()
        with self.assertRaises(SanyanSyntaxError):
            mod.call(rt, [])

    def test_call_undefined_func(self):
        mod = ModuleValue({}, {'add': (['x', 'y'], [['add', 'x', 'y']])})
        rt = SanyanRuntime()
        with self.assertRaises(SanyanNameError):
            mod.call(rt, ['not_exist'])


class TestSkin(unittest.TestCase):
    """皮肤系统"""

    def setUp(self):
        self.skin = SkinManager('chinese')

    def test_ternary_words(self):
        self.assertEqual(self.skin.is_ternary_word('真'), 1)
        self.assertEqual(self.skin.is_ternary_word('假'), -1)
        self.assertEqual(self.skin.is_ternary_word('可能'), 0)
        self.assertIsNone(self.skin.is_ternary_word('不存在的词'))

    def test_keyword_lookup(self):
        self.assertEqual(self.skin.get_internal_keyword('设'), 'set')
        self.assertEqual(self.skin.get_internal_keyword('若'), 'if')
        self.assertEqual(self.skin.get_internal_keyword('循环'), 'loop')

    def test_switch_skin(self):
        self.skin.switch_skin('english')
        self.assertIsNotNone(self.skin.get_internal_keyword('set'))


class TestPreprocess(unittest.TestCase):
    def test_expand_include(self):
        code = '#include "test_math"\n输出(1)'
        result = preprocess_includes(code)
        self.assertIn('输出(1)', result)

    def test_reject_path_traversal(self):
        with self.assertRaises(ValueError):
            _safe_include_path('../secret')

    def test_nonexistent_file(self):
        result = preprocess_includes('#include "not_exist_file_xyz"\n输出(1)')
        self.assertIn('输出(1)', result)


class TestTernaryEdge(unittest.TestCase):
    def test_large_integer_conversion(self):
        n = 10**18 + 1
        trits = BT.from_int(n)
        self.assertEqual(BT.to_int(trits), n)

    def test_zero_has_no_sign(self):
        self.assertEqual(BT.from_int(0), [0])

    def test_fixed_point_conversion(self):
        trits = BT.from_float(1.5, precision=8)
        result = BT.to_float(trits, precision=8)
        self.assertAlmostEqual(result, 1.5, places=2)

    def test_fixed_point_negative(self):
        trits = BT.from_float(-2.25, precision=8)
        result = BT.to_float(trits, precision=8)
        self.assertAlmostEqual(result, -2.25, places=2)

    def test_trit_value_float_precision(self):
        v = TritValue(3.14)
        self.assertTrue(v.is_float())
        self.assertAlmostEqual(v.to_float(), 3.14, places=1)

    def test_ternary_sin_zero(self):
        s = ternary_sin(BT.from_float(0.0, 16), 16)
        self.assertAlmostEqual(BT.to_float(s, 16), 0.0, places=2)

    def test_ternary_sin_half_pi(self):
        s = ternary_sin(BT.from_float(1.5708, 16), 16)
        self.assertAlmostEqual(BT.to_float(s, 16), 1.0, places=1)

    def test_ternary_sqrt_four(self):
        s = ternary_sqrt(BT.from_float(4.0, 16), 16)
        self.assertAlmostEqual(BT.to_float(s, 16), 2.0, places=1)

    def test_ternary_exp_one(self):
        e = ternary_exp(BT.from_float(1.0, 16), 16)
        self.assertAlmostEqual(BT.to_float(e, 16), 2.718, places=1)

    def test_ternary_log_e(self):
        log_e = ternary_log(BT.from_float(2.71828, 16), 16)
        self.assertAlmostEqual(BT.to_float(log_e, 16), 1.0, places=1)

    def test_ternary_cos_zero(self):
        from ternary_core import ternary_cos
        c = ternary_cos(BT.from_float(0.0, 16), 16)
        self.assertAlmostEqual(BT.to_float(c, 16), 1.0, places=1)

    def test_ternary_tan_zero(self):
        from ternary_core import ternary_tan
        t = ternary_tan(BT.from_float(0.0, 16), 16)
        self.assertAlmostEqual(BT.to_float(t, 16), 0.0, places=1)

    def test_ternary_log10_100(self):
        from ternary_core import ternary_log10
        l10 = ternary_log10(BT.from_float(100.0, 16), 16)
        self.assertAlmostEqual(BT.to_float(l10, 16), 2.0, places=1)

    def test_negative_multiplication(self):
        self.assertEqual(BT.to_int(TernaryALU.multiply(BT.from_int(-1), BT.from_int(-1))), 1)
        self.assertEqual(BT.to_int(TernaryALU.multiply(BT.from_int(-1), BT.from_int(0))), 0)

    def test_pool_lru_eviction(self):
        for i in range(10001):
            TritValue(i)
        a = TritValue(5)
        b = TritValue(5)
        self.assertIs(a, b)


class TestParsePairs(unittest.TestCase):
    def test_dot_format(self):
        r = SanyanRuntime()
        result = r._parse_pairs(['灯.亮', '风扇.关'])
        self.assertEqual(result, [('灯', '亮'), ('风扇', '关')])

    def test_alternating_dot_format(self):
        r = SanyanRuntime()
        result = r._parse_pairs(['灯', '.', '亮', '风扇', '.', '关'])
        self.assertEqual(result, [('灯', '亮'), ('风扇', '关')])

    def test_mixed_formats(self):
        r = SanyanRuntime()
        result = r._parse_pairs(['灯.亮', '风扇', '.', '关'])
        self.assertEqual(result, [('灯', '亮'), ('风扇', '关')])

    def test_empty_list_returns_empty(self):
        r = SanyanRuntime()
        result = r._parse_pairs([])
        self.assertEqual(result, [])

    def test_single_pair_dot(self):
        r = SanyanRuntime()
        result = r._parse_pairs(['灯.亮'])
        self.assertEqual(result, [('灯', '亮')])

    def test_single_pair_alternating(self):
        r = SanyanRuntime()
        result = r._parse_pairs(['灯', '.', '亮'])
        self.assertEqual(result, [('灯', '亮')])

    def test_invalid_format_raises(self):
        r = SanyanRuntime()
        with self.assertRaises(SanyanSyntaxError):
            r._parse_pairs(['灯'])

    def test_non_string_raises(self):
        r = SanyanRuntime()
        with self.assertRaises(SanyanSyntaxError):
            r._parse_pairs([42, '.', '亮'])


if __name__ == '__main__':
    unittest.main()
