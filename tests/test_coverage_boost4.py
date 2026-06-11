"""覆盖补全第四轮：evaluator/runtime/values/ternary_core 边界情况"""

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


class TestEvaluatorFinal(unittest.TestCase):
    def setUp(self):
        self.e = SanyanEvaluator()

    def test_eval_empty_list(self):
        r = self.e.eval([])
        self.assertEqual(r, [])

    def test_eval_list_with_non_string_first(self):
        r = self.e.eval([1, 2, 3])
        self.assertEqual(len(r), 3)

    def test_eval_list_with_numeric_first(self):
        r = self.e.eval(['123'])
        self.assertEqual(r, ['123'])

    def test_eval_list_with_float_first(self):
        r = self.e.eval(['3.14'])
        self.assertEqual(r, ['3.14'])

    def test_eval_tritvalue(self):
        v = TritValue(42, confidence=0.9)
        r = self.e.eval(v)
        self.assertEqual(r.to_int(), 42)
        self.assertAlmostEqual(r.confidence, 0.9, delta=0.01)

    def test_eval_dict(self):
        d = {'a': 1, 'b': 2}
        r = self.e.eval(d)
        self.assertEqual(r, d)

    def test_eval_function_value(self):
        from values import FunctionValue

        fv = FunctionValue(['x'], ['set', 'y', ['add', 'x', 1]], None, {}, {})
        r = self.e.eval(fv)
        self.assertEqual(r, fv)

    def test_eval_module_value(self):
        from values import ModuleValue

        mv = ModuleValue({}, {}, set())
        r = self.e.eval(mv)
        self.assertEqual(r, mv)

    def test_eval_array_value(self):
        from ternary_core import ArrayValue

        arr = ArrayValue(3, TritValue(0))
        r = self.e.eval(arr)
        self.assertEqual(r, arr)

    def test_eval_other(self):
        r = self.e.eval(None)
        self.assertIsNone(r)

    def test_eval_list_single_string_literal(self):
        r = self.e.eval(['"hello"'])
        self.assertEqual(r, 'hello')

    def test_eval_list_single_numeric(self):
        r = self.e.eval(['42'])
        self.assertEqual(r, ['42'])

    def test_eval_list_single_float(self):
        r = self.e.eval(['3.14'])
        self.assertEqual(r, ['3.14'])

    def test_eval_list_function_call(self):
        self.e.eval(['定义', 'add', ['a', 'b'], ['add', 'a', 'b']])
        r = self.e.eval(['add', 1, 2])
        self.assertEqual(r.to_int(), 3)

    def test_eval_list_module_call(self):
        from values import ModuleValue

        mv = ModuleValue({}, {'func': (['x'], ['set', 'y', ['add', 'x', 1]], None, {}, {})}, set(['func']))
        self.e.set_var('m', mv)
        r = self.e.eval(['m', 'func', 5])
        self.assertEqual(r.to_int(), 6)

    def test_eval_string_variable(self):
        self.e.set_var('x', TritValue(42))
        r = self.e.eval('x')
        self.assertEqual(r.to_int(), 42)

    def test_eval_string_keyword(self):
        r = self.e.eval('真')
        self.assertEqual(r.to_int(), 1)

    def test_eval_string_digit(self):
        r = self.e.eval('42')
        self.assertEqual(r.to_int(), 42)


# ═══════════════════════════════════════════════════════════
# runtime.py (78% → 90%+)
# ═══════════════════════════════════════════════════════════


class TestRuntimeFinal(unittest.TestCase):
    def test_scope_set_var_existing(self):
        from runtime import ScopeManager

        sm = ScopeManager()
        sm.set_var('x', 1)
        sm.set_var('x', 2)
        self.assertEqual(sm.get_var('x'), 2)

    def test_scope_push_pop_multiple(self):
        from runtime import ScopeManager

        sm = ScopeManager()
        sm.set_var('a', 1)
        sm.push_scope()
        sm.set_var('b', 2)
        sm.push_scope()
        sm.set_var('c', 3)
        self.assertEqual(sm.get_var('a'), 1)
        self.assertEqual(sm.get_var('b'), 2)
        self.assertEqual(sm.get_var('c'), 3)
        sm.pop_scope()
        sm.pop_scope()
        self.assertEqual(sm.get_var('a'), 1)

    def test_scope_has_var_after_pop(self):
        from runtime import ScopeManager

        sm = ScopeManager()
        sm.set_var('x', 1)
        sm.push_scope()
        sm.set_var('y', 2)
        sm.pop_scope()
        self.assertTrue(sm.has_var('x'))
        self.assertFalse(sm.has_var('y'))

    def test_scope_all_vars_multiple(self):
        from runtime import ScopeManager

        sm = ScopeManager()
        sm.set_var('a', 1)
        sm.push_scope()
        sm.set_var('b', 2)
        sm.push_scope()
        sm.set_var('c', 3)
        vars = sm.all_scoped_vars()
        self.assertEqual(len(vars), 3)

    def test_scope_depth_multiple(self):
        from runtime import ScopeManager

        sm = ScopeManager()
        self.assertEqual(sm.depth(), 1)
        sm.push_scope()
        self.assertEqual(sm.depth(), 2)
        sm.push_scope()
        self.assertEqual(sm.depth(), 3)
        sm.pop_scope()
        self.assertEqual(sm.depth(), 2)
        sm.pop_scope()
        self.assertEqual(sm.depth(), 1)


# ═══════════════════════════════════════════════════════════
# values.py (86% → 90%+)
# ═══════════════════════════════════════════════════════════


class TestValuesFinal(unittest.TestCase):
    def test_function_value_str(self):
        from values import FunctionValue

        fv = FunctionValue(['x'], ['add', 'x', 1], None, {}, {})
        self.assertIn('λ', str(fv))

    def test_module_value_get_attr(self):
        from values import ModuleValue

        mv = ModuleValue({}, {'func': (['x'], ['add', 'x', 1], None, {}, {})}, set(['func']))
        self.assertTrue(mv.is_exported('func'))
        self.assertFalse(mv.is_exported('missing'))

    def test_module_value_get_attr_missing(self):
        from values import ModuleValue

        mv = ModuleValue({}, {}, set())
        with self.assertRaises(Exception):
            mv.get_attr('missing')

    def test_src_node_str(self):
        from values import SrcNode

        sn = SrcNode(['do', 1, 2], line=10, col=5)
        self.assertIn('do', str(sn))

    def test_to_num_empty_string(self):
        from values import to_num

        self.assertEqual(to_num(''), '')

    def test_to_num_bool(self):
        from values import to_num

        self.assertEqual(to_num(True), True)
        self.assertEqual(to_num(False), False)

    def test_check_type_num(self):
        from values import check_type

        self.assertIsNone(check_type(42, 'num'))
        self.assertIsNone(check_type(3.14, 'num'))

    def test_check_type_none(self):
        from values import check_type

        self.assertIsNone(check_type(None, 'any'))


# ═══════════════════════════════════════════════════════════
# ternary_core.py (89% → 90%+)
# ═══════════════════════════════════════════════════════════


class TestTernaryCoreFinal(unittest.TestCase):
    def test_bt_from_int_zero(self):
        trits = BT.from_int(0)
        self.assertEqual(trits, [0])

    def test_bt_to_int_empty(self):
        self.assertEqual(BT.to_int([]), 0)

    def test_bt_to_str_empty(self):
        self.assertEqual(BT.to_str([]), '')

    def test_bt_from_str_empty(self):
        self.assertEqual(BT.from_str(''), [0])

    def test_ternary_alu_add_zero(self):
        result = TernaryALU.add([0], [0])
        self.assertEqual(BT.to_int(result), 0)

    def test_ternary_alu_mul_zero(self):
        result = TernaryALU.multiply([0], [1])
        self.assertEqual(BT.to_int(result), 0)

    def test_tritvalue_state_map(self):
        self.assertEqual(TritValue.STATE_MAP['真'], 1)
        self.assertEqual(TritValue.STATE_MAP['假'], -1)
        self.assertEqual(TritValue.STATE_MAP['可能'], 0)

    def test_tritvalue_small_cache(self):
        v1 = TritValue(42)
        v2 = TritValue(42)
        self.assertIs(v1, v2)


# ═══════════════════════════════════════════════════════════
# ternary_container_ops.py (88% → 90%+)
# ═══════════════════════════════════════════════════════════


class TestTernaryContainerFinal(unittest.TestCase):
    def test_trit_list_wrong_args(self):
        r = ev(['trit_list'])
        self.assertEqual(len(r), 0)

    def test_trit_get_wrong_args(self):
        with self.assertRaises(Exception):
            ev(['trit_get', [1, 2]])

    def test_trit_set_wrong_args(self):
        with self.assertRaises(Exception):
            ev(['trit_set', [1, 2], 0])

    def test_trit_list_len_wrong_args(self):
        with self.assertRaises(Exception):
            ev(['trit_list_len'])

    def test_trit_list_map_wrong_args(self):
        with self.assertRaises(Exception):
            ev(['trit_list_map', [1, 2]])

    def test_trit_dict_wrong_args(self):
        with self.assertRaises(Exception):
            ev(['trit_dict', '"a"'])

    def test_trit_key_get_wrong_args(self):
        with self.assertRaises(Exception):
            ev(['trit_key_get', {'a': 1}])

    def test_trit_key_set_wrong_args(self):
        with self.assertRaises(Exception):
            ev(['trit_key_set', {'a': 1}, '"b"'])

    def test_chain_all_false(self):
        e = SanyanEvaluator()
        e.set_var('a', TritValue(-1, confidence=0.9))
        e.set_var('b', TritValue(-1, confidence=0.8))
        r = e.eval(['链', 'a', 'b'])
        self.assertEqual(r.to_int(), -1)

    def test_chain_or_break_maybe(self):
        e = SanyanEvaluator()
        e.set_var('a', TritValue(0, confidence=0.5))
        r = e.eval(['链断', 'a'])
        self.assertEqual(r.to_int(), 1)

    def test_unwrap_or_maybe(self):
        e = SanyanEvaluator()
        e.set_var('x', TritValue(0, confidence=0.3))
        r = e.eval(['或解', 'x', 42])
        self.assertEqual(r.to_int(), 42)

    def test_try_chain_single(self):
        e = SanyanEvaluator()
        e.set_var('a', TritValue(1, confidence=0.9))
        r = e.eval(['尝试链', 'a'])
        self.assertEqual(r.to_int(), 1)


if __name__ == '__main__':
    unittest.main()
