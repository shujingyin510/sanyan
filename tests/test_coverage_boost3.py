"""覆盖补全第三轮：重点补 evaluator/values/runtime/ternary_container"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from evaluator import SanyanEvaluator
from ternary_core import TritValue, BT, TernaryALU


def ev(expr):
    e = SanyanEvaluator()
    return e.eval(expr)


# ═══════════════════════════════════════════════════════════
# evaluator.py (80% → 90%+)
# ═══════════════════════════════════════════════════════════


class TestEvaluatorEdgeCases(unittest.TestCase):
    def setUp(self):
        self.e = SanyanEvaluator()

    def test_eval_string_chinese(self):
        r = self.e.eval('"你好世界"')
        self.assertEqual(r, '你好世界')

    def test_eval_negative_int(self):
        r = self.e.eval('-5')
        self.assertEqual(r.to_int(), -5)

    def test_eval_hex(self):
        r = self.e.eval('0xFF')
        self.assertEqual(r.to_int(), 255)

    def test_eval_bin(self):
        r = self.e.eval('0b1010')
        self.assertEqual(r, '0b1010')

    def test_eval_list_do_empty(self):
        r = self.e.eval(['do'])
        self.assertEqual(r.to_int(), 0)

    def test_eval_list_if_no_else(self):
        r = self.e.eval(['if', 0, 'yes'])
        self.assertEqual(r.to_int(), 0)

    def test_eval_list_loop_zero_iterations(self):
        self.e.eval(['set', 'i', 10])
        self.e.eval(['loop', ['lt', 'i', 5], ['set', 'i', ['add', 'i', 1]]])
        self.assertEqual(self.e.get_var('i').to_int(), 10)

    def test_eval_list_forin_list(self):
        self.e.eval(['set', 'sum', 0])
        self.e.eval(['forin', 'i', [1, 2, 3], ['set', 'sum', ['add', 'sum', 'i']]])
        self.assertEqual(self.e.get_var('sum').to_int(), 6)

    def test_eval_list_try_catch(self):
        r = self.e.eval(['try', ['add', 1, 2], ['catch', 'e', 0]])
        self.assertEqual(r.to_int(), 3)

    def test_eval_list_try_catch_error(self):
        r = self.e.eval(['try', ['throw', 'error'], ['catch', 'e', 42]])
        self.assertEqual(r.to_int(), 42)

    def test_eval_list_define(self):
        self.e.eval(['定义', 'double', ['x'], ['mul', 'x', 2]])
        r = self.e.eval(['double', 5])
        self.assertEqual(r.to_int(), 10)

    def test_eval_list_lambda(self):
        self.e.eval(['set', 'f', ['函数', ['x'], ['mul', 'x', 2]]])
        r = self.e.eval(['f', 5])
        self.assertEqual(r.to_int(), 10)

    def test_eval_list_list(self):
        r = self.e.eval(['list', 1, 2, 3])
        self.assertEqual(len(r), 3)

    def test_eval_list_dict(self):
        r = self.e.eval(['dict', '"a"', 1, '"b"', 2])
        self.assertEqual(r['a'].to_int(), 1)

    def test_eval_list_length(self):
        r = self.e.eval(['length', [1, 2, 3]])
        self.assertEqual(r.to_int(), 3)

    def test_eval_list_concat(self):
        r = self.e.eval(['列表合', [1, 2], [3, 4]])
        self.assertEqual(len(r), 4)

    def test_eval_list_sort(self):
        r = self.e.eval(['sort', [3, 1, 2]])
        self.assertEqual(r, [1, 2, 3])

    def test_eval_list_reverse(self):
        r = self.e.eval(['reverse', [1, 2, 3]])
        self.assertEqual(r, [3, 2, 1])

    def test_eval_list_unique(self):
        r = self.e.eval(['unique', [1, 2, 2, 3]])
        self.assertEqual(len(r), 3)

    def test_eval_list_contains(self):
        r = self.e.eval(['contains', [1, 2, 3], 2])
        self.assertEqual(r.to_int(), 1)

    def test_eval_list_not_contains(self):
        r = self.e.eval(['contains', [1, 2, 3], 5])
        self.assertEqual(r.to_int(), -1)

    def test_eval_list_slice(self):
        r = self.e.eval(['slice', [1, 2, 3, 4, 5], 1, 3])
        self.assertEqual(r, [2, 3])

    def test_eval_list_map(self):
        self.e.eval(['定义', 'double', ['x'], ['mul', 'x', 2]])
        r = self.e.eval(['映射', 'double', [1, 2, 3]])
        self.assertEqual(len(r), 3)

    def test_eval_list_filter(self):
        self.e.eval(['定义', 'is_even', ['x'], ['eq', ['mod', 'x', 2], 0]])
        r = self.e.eval(['过滤', 'is_even', [1, 2, 3, 4]])
        self.assertEqual(len(r), 2)

    def test_eval_list_reduce(self):
        self.e.eval(['定义', 'add', ['a', 'b'], ['add', 'a', 'b']])
        r = self.e.eval(['归并', 'add', [1, 2, 3], 0])
        self.assertEqual(r.to_int(), 6)


# ═══════════════════════════════════════════════════════════
# values.py (80% → 90%+)
# ═══════════════════════════════════════════════════════════


class TestValuesEdgeCases(unittest.TestCase):
    def test_function_value_params(self):
        from values import FunctionValue

        fv = FunctionValue(['x', 'y'], ['add', 'x', 'y'], None, {}, {})
        self.assertEqual(fv.params, ['x', 'y'])

    def test_function_value_closure(self):
        from values import FunctionValue

        fv = FunctionValue(['x'], ['add', 'x', 1], None, {'y': 10}, {})
        self.assertEqual(fv.closure_vars['y'], 10)

    def test_function_value_param_types(self):
        from values import FunctionValue

        fv = FunctionValue(['x'], ['add', 'x', 1], None, {}, {'x': 'int'})
        self.assertEqual(fv.param_types['x'], 'int')

    def test_module_value_exports(self):
        from values import ModuleValue

        mv = ModuleValue({}, {}, set(['a', 'b', 'c']))
        self.assertTrue(mv.is_exported('a'))
        self.assertTrue(mv.is_exported('b'))
        self.assertFalse(mv.is_exported('d'))

    def test_src_node_list(self):
        from values import SrcNode

        sn = SrcNode(['do', 1, 2, 3], line=10, col=5)
        self.assertEqual(len(sn), 4)
        self.assertEqual(sn[1], 1)

    def test_to_num_tritvalue_float(self):
        from values import to_num

        v = TritValue(3.14)
        self.assertAlmostEqual(to_num(v), 3.14, delta=0.01)

    def test_to_num_list(self):
        from values import to_num

        self.assertEqual(to_num([1, 2, 3]), [1, 2, 3])

    def test_to_num_dict(self):
        from values import to_num

        self.assertEqual(to_num({'a': 1}), {'a': 1})

    def test_to_num_none(self):
        from values import to_num

        self.assertIsNone(to_num(None))

    def test_check_type_int(self):
        from values import check_type

        self.assertIsNone(check_type(42, 'int'))
        with self.assertRaises(Exception):
            check_type('hello', 'int')

    def test_check_type_float(self):
        from values import check_type

        self.assertIsNone(check_type(3.14, 'float'))
        with self.assertRaises(Exception):
            check_type('hello', 'float')

    def test_check_type_str(self):
        from values import check_type

        self.assertIsNone(check_type('hello', 'str'))
        with self.assertRaises(Exception):
            check_type(42, 'str')

    def test_check_type_list(self):
        from values import check_type

        self.assertIsNone(check_type([1, 2], 'list'))
        with self.assertRaises(Exception):
            check_type(42, 'list')

    def test_check_type_dict(self):
        from values import check_type

        self.assertIsNone(check_type({'a': 1}, 'dict'))
        with self.assertRaises(Exception):
            check_type(42, 'dict')

    def test_check_type_any(self):
        from values import check_type

        self.assertIsNone(check_type(42, 'any'))
        self.assertIsNone(check_type('hello', 'any'))


# ═══════════════════════════════════════════════════════════
# runtime.py (78% → 90%+)
# ═══════════════════════════════════════════════════════════


class TestRuntimeEdgeCases(unittest.TestCase):
    def test_scope_nested(self):
        from runtime import ScopeManager

        sm = ScopeManager()
        sm.set_var('x', 1)
        sm.push_scope()
        sm.set_var('x', 2)
        sm.push_scope()
        sm.set_var('x', 3)
        self.assertEqual(sm.get_var('x'), 3)
        sm.pop_scope()
        self.assertEqual(sm.get_var('x'), 2)
        sm.pop_scope()
        self.assertEqual(sm.get_var('x'), 1)

    def test_scope_shadow(self):
        from runtime import ScopeManager

        sm = ScopeManager()
        sm.set_var('x', 1)
        sm.push_scope()
        sm.set_var('x', 2)
        self.assertEqual(sm.get_var('x'), 2)
        sm.pop_scope()
        self.assertEqual(sm.get_var('x'), 1)

    def test_scope_has_var_nested(self):
        from runtime import ScopeManager

        sm = ScopeManager()
        sm.set_var('x', 1)
        sm.push_scope()
        self.assertTrue(sm.has_var('x'))
        self.assertFalse(sm.has_var('y'))

    def test_scope_all_vars_nested(self):
        from runtime import ScopeManager

        sm = ScopeManager()
        sm.set_var('x', 1)
        sm.push_scope()
        sm.set_var('y', 2)
        sm.push_scope()
        sm.set_var('z', 3)
        vars = sm.all_scoped_vars()
        self.assertEqual(len(vars), 3)

    def test_scope_pop_preserves_global(self):
        from runtime import ScopeManager

        sm = ScopeManager()
        sm.set_var('x', 1)
        sm.pop_scope()
        self.assertEqual(sm.depth(), 1)
        self.assertEqual(sm.get_var('x'), 1)


# ═══════════════════════════════════════════════════════════
# ternary_container_ops.py (84% → 90%+)
# ═══════════════════════════════════════════════════════════


class TestTernaryContainerEdgeCases(unittest.TestCase):
    def test_trit_list_with_tritvalues(self):
        r = ev(['trit_list', ['ternary_value', 1, 0.9], ['ternary_value', 2, 0.8]])
        self.assertEqual(len(r), 2)

    def test_trit_get_wrong_type(self):
        e = SanyanEvaluator()
        e.set_var('x', 42)
        with self.assertRaises(Exception):
            e.eval(['trit_get', 'x', 0])

    def test_trit_set_wrong_type(self):
        e = SanyanEvaluator()
        e.set_var('x', 42)
        with self.assertRaises(Exception):
            e.eval(['trit_set', 'x', 0, 99])

    def test_trit_list_len_wrong_type(self):
        e = SanyanEvaluator()
        e.set_var('x', 42)
        with self.assertRaises(Exception):
            e.eval(['trit_list_len', 'x'])

    def test_trit_list_map_wrong_type(self):
        e = SanyanEvaluator()
        e.set_var('x', 42)
        with self.assertRaises(Exception):
            e.eval(['trit_list_map', 'x', 'double'])

    def test_trit_dict_wrong_args(self):
        with self.assertRaises(Exception):
            ev(['trit_dict', '"a"'])

    def test_trit_key_get_wrong_type(self):
        e = SanyanEvaluator()
        e.set_var('x', 42)
        with self.assertRaises(Exception):
            e.eval(['trit_key_get', 'x', '"a"'])

    def test_trit_key_set_wrong_type(self):
        e = SanyanEvaluator()
        e.set_var('x', 42)
        with self.assertRaises(Exception):
            e.eval(['trit_key_set', 'x', '"a"', 1])

    def test_chain_confidence_maybe(self):
        e = SanyanEvaluator()
        e.set_var('a', TritValue(0, confidence=0.5))
        r = e.eval(['链', 'a'])
        self.assertEqual(r.to_int(), 0)
        self.assertAlmostEqual(r.confidence, 0.4, delta=0.01)

    def test_chain_or_break_empty(self):
        r = ev(['链断'])
        self.assertEqual(r.to_int(), 0)

    def test_unwrap_maybe_no_default(self):
        e = SanyanEvaluator()
        e.set_var('x', TritValue(0, confidence=0.3))
        with self.assertRaises(Exception):
            e.eval(['解包', 'x'])

    def test_try_chain_empty(self):
        with self.assertRaises(Exception):
            ev(['尝试链'])

    def test_try_chain_no_default(self):
        e = SanyanEvaluator()
        e.eval(['定义', 'fail', [], ['raise_error', '"fail"']])
        r = e.eval(['尝试链', ['fail']])
        self.assertEqual(r.to_int(), 0)


# ═══════════════════════════════════════════════════════════
# ternary_core.py (89% → 90%+)
# ═══════════════════════════════════════════════════════════


class TestTernaryCoreEdgeCases(unittest.TestCase):
    def test_bt_from_int_negative(self):
        trits = BT.from_int(-5)
        self.assertEqual(BT.to_int(trits), -5)

    def test_bt_from_int_large(self):
        trits = BT.from_int(1000)
        self.assertEqual(BT.to_int(trits), 1000)

    def test_bt_to_str_empty(self):
        self.assertEqual(BT.to_str([]), '')

    def test_bt_to_float_negative(self):
        trits = BT.from_float(-1.5)
        f = BT.to_float(trits)
        self.assertAlmostEqual(f, -1.5, delta=0.1)

    def test_ternary_alu_add_negative(self):
        result = TernaryALU.add([-1], [-1])
        self.assertEqual(BT.to_int(result), -2)

    def test_ternary_alu_sub_negative(self):
        result = TernaryALU.sub([-1, 0], [-1])
        self.assertEqual(BT.to_int(result), -2)

    def test_ternary_alu_multiply_negative(self):
        result = TernaryALU.multiply([-1], [1])
        self.assertEqual(BT.to_int(result), -1)

    def test_ternary_alu_neg_negative(self):
        result = TernaryALU.neg([-1, 0])
        self.assertEqual(BT.to_int(result), 3)

    def test_tritvalue_from_string_true(self):
        v = TritValue.from_string('真')
        self.assertEqual(v.to_int(), 1)

    def test_tritvalue_from_string_false(self):
        v = TritValue.from_string('假')
        self.assertEqual(v.to_int(), -1)

    def test_tritvalue_from_string_maybe(self):
        v = TritValue.from_string('可能')
        self.assertEqual(v.to_int(), 0)

    def test_array_value_get_set(self):
        from ternary_core import ArrayValue

        arr = ArrayValue(5, TritValue(0))
        arr.set(0, TritValue(10))
        arr.set(4, TritValue(50))
        self.assertEqual(arr.get(0).to_int(), 10)
        self.assertEqual(arr.get(4).to_int(), 50)


if __name__ == '__main__':
    unittest.main()
