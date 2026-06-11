"""覆盖补全第七轮：values.py 最后1%"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from evaluator import SanyanEvaluator
from ternary_core import TritValue, BT


def ev(expr):
    e = SanyanEvaluator()
    return e.eval(expr)


# ═══════════════════════════════════════════════════════════
# values.py (89% → 90%+)
# ═══════════════════════════════════════════════════════════


class TestValuesFinal3(unittest.TestCase):
    def test_src_node_repr_with_items(self):
        from values import SrcNode

        sn = SrcNode(['do', 1, 2, 3], line=10, col=5)
        r = repr(sn)
        self.assertIn('SrcNode', r)

    def test_check_type_int(self):
        from values import check_type

        self.assertIsNone(check_type(42, 'int'))
        self.assertIsNone(check_type(TritValue(42), 'int'))

    def test_check_type_float(self):
        from values import check_type

        self.assertIsNone(check_type(3.14, 'float'))
        self.assertIsNone(check_type(TritValue(3.14), 'float'))

    def test_check_type_str(self):
        from values import check_type

        self.assertIsNone(check_type('hello', 'str'))

    def test_check_type_list(self):
        from values import check_type

        self.assertIsNone(check_type([1, 2], 'list'))

    def test_check_type_dict(self):
        from values import check_type

        self.assertIsNone(check_type({'a': 1}, 'dict'))

    def test_function_value_call_with_type_check(self):
        from values import FunctionValue

        fv = FunctionValue(['x'], ['set', 'y', ['add', 'x', 1]], None, {}, {'x': 'int'})
        e = SanyanEvaluator()
        result = fv.call(e, [5])
        self.assertEqual(result.to_int(), 6)

    def test_function_value_call_return_type(self):
        from values import FunctionValue

        fv = FunctionValue(['x'], ['set', 'y', ['add', 'x', 1]], None, {}, {'x': 'int', '__return__': 'int'})
        e = SanyanEvaluator()
        result = fv.call(e, [5])
        self.assertEqual(result.to_int(), 6)

    def test_function_value_call_with_closure(self):
        from values import FunctionValue

        fv = FunctionValue(['x'], ['set', 'y', ['add', 'x', 1]], None, {'y': 10}, {})
        e = SanyanEvaluator()
        result = fv.call(e, [5])
        self.assertEqual(result.to_int(), 6)

    def test_module_value_init_with_vars(self):
        from values import ModuleValue

        mv = ModuleValue({'x': 42}, {}, set())
        self.assertEqual(mv.vars['x'], 42)

    def test_module_value_is_exported_true(self):
        from values import ModuleValue

        mv = ModuleValue({}, {}, set(['func']))
        self.assertTrue(mv.is_exported('func'))

    def test_module_value_is_exported_false(self):
        from values import ModuleValue

        mv = ModuleValue({}, {}, set(['func']))
        self.assertFalse(mv.is_exported('missing'))


# ═══════════════════════════════════════════════════════════
# ternary_container_ops.py: 最后补充
# ═══════════════════════════════════════════════════════════


class TestContainerOpsFinal(unittest.TestCase):
    def setUp(self):
        self.e = SanyanEvaluator()

    def test_trit_list_tritvalue_elements(self):
        r = self.e.eval(['trit_list', ['ternary_value', 1, 0.9], ['ternary_value', 2, 0.8]])
        self.assertEqual(len(r), 2)

    def test_trit_list_int_elements(self):
        r = self.e.eval(['trit_list', 1, 2, 3])
        self.assertEqual(len(r), 3)

    def test_trit_list_string_elements(self):
        r = self.e.eval(['trit_list', '"a"', '"b"'])
        self.assertEqual(len(r), 2)

    def test_trit_list_empty(self):
        r = self.e.eval(['trit_list'])
        self.assertEqual(len(r), 0)

    def test_trit_get_with_tritvalue_index(self):
        e = SanyanEvaluator()
        e.set_var('lst', [TritValue(10), TritValue(20)])
        r = e.eval(['trit_get', 'lst', ['ternary_value', 0, 1.0]])
        self.assertEqual(r.to_int(), 10)

    def test_trit_set_with_tritvalue(self):
        e = SanyanEvaluator()
        e.set_var('lst', [TritValue(10), TritValue(20)])
        e.eval(['trit_set', 'lst', 0, ['ternary_value', 99, 1.0]])
        self.assertEqual(e.get_var('lst')[0].to_int(), 99)

    def test_trit_dict_with_tritvalues(self):
        r = self.e.eval(['trit_dict', ['ternary_value', '"a"', 1.0], 1])
        self.assertIsInstance(r, dict)

    def test_trit_key_get_with_tritvalue_key(self):
        e = SanyanEvaluator()
        e.set_var('d', {'a': TritValue(10)})
        r = e.eval(['trit_key_get', 'd', ['ternary_value', '"a"', 1.0]])
        self.assertEqual(r.to_int(), 10)

    def test_trit_key_set_with_tritvalue_key(self):
        e = SanyanEvaluator()
        e.set_var('d', {'a': TritValue(10)})
        e.eval(['trit_key_set', 'd', ['ternary_value', '"a"', 1.0], 99])
        self.assertEqual(e.get_var('d')['a'].to_int(), 99)


# ═══════════════════════════════════════════════════════════
# ternary_source_ops.py: 最后补充
# ═══════════════════════════════════════════════════════════


class TestSourceOpsFinal(unittest.TestCase):
    def test_source_with_integer(self):
        e = SanyanEvaluator()
        e.set_var('x', 42)
        r = e.eval(['source', 'x'])
        self.assertEqual(r.to_payload(), '')

    def test_detect_conflict_with_mixed_types(self):
        e = SanyanEvaluator()
        e.set_var('a', 42)
        e.set_var('b', 'hello')
        r = e.eval(['detect_conflict', 'a', 'b'])
        self.assertEqual(r['冲突'], 0)

    def test_conflict_merge_with_unknown_strategy(self):
        e = SanyanEvaluator()
        e.set_var('a', TritValue(1, confidence=0.9))
        e.set_var('b', TritValue(-1, confidence=0.8))
        r = e.eval(['conflict_merge', 'a', 'b', ['ternary_value', '"unknown"', 1.0]])
        self.assertEqual(r.to_int(), 0)

    def test_bayes_update_with_integers(self):
        e = SanyanEvaluator()
        e.set_var('x', 42)
        r = e.eval(['bayes_update', 'x', 'x'])
        self.assertEqual(r.to_int(), 42)

    def test_assert_confidence_with_integer(self):
        e = SanyanEvaluator()
        e.set_var('x', 42)
        r = e.eval(['assert_confidence', 'x', 0.5])
        self.assertEqual(r, 42)

    def test_quantize_with_integer(self):
        e = SanyanEvaluator()
        e.set_var('x', 42)
        r = e.eval(['quantize', 'x'])
        self.assertEqual(r.to_int(), 0)

    def test_fuse_empty(self):
        r = ev(['fuse', []])
        self.assertEqual(r.to_int(), 0)

    def test_consensus_two_maybe(self):
        e = SanyanEvaluator()
        e.set_var('a', TritValue(0, confidence=0.5))
        e.set_var('b', TritValue(0, confidence=0.5))
        r = e.eval(['consensus', 'a', 'b'])
        self.assertEqual(r.to_int(), 0)

    def test_majority_vote_all_same(self):
        r = ev(['majority_vote', 1, 1, 1])
        self.assertEqual(r.to_int(), 1)


# ═══════════════════════════════════════════════════════════
# ternary_core.py: 最后补充
# ═══════════════════════════════════════════════════════════


class TestTernaryCoreFinal(unittest.TestCase):
    def test_bt_from_int_large_negative(self):
        trits = BT.from_int(-1000)
        self.assertEqual(BT.to_int(trits), -1000)

    def test_bt_to_float_negative(self):
        trits = BT.from_float(-1.5)
        f = BT.to_float(trits)
        self.assertAlmostEqual(f, -1.5, delta=0.1)

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

    def test_array_value_repr(self):
        from ternary_core import ArrayValue

        arr = ArrayValue(3, TritValue(5))
        self.assertIn('5', repr(arr))

    def test_array_value_iter(self):
        from ternary_core import ArrayValue

        arr = ArrayValue(3, TritValue(5))
        items = list(arr)
        self.assertEqual(len(items), 3)


if __name__ == '__main__':
    unittest.main()
