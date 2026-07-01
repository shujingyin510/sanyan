"""全模块覆盖补全测试：目标所有模块 ≥90%"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.evaluator import SanyanEvaluator
from core.ternary_core import TritValue, BT, TernaryALU


def ev(expr):
    e = SanyanEvaluator()
    return e.eval(expr)


def ev_set(name, val, expr):
    e = SanyanEvaluator()
    e.set_var(name, val)
    return e.eval(expr)


# ═══════════════════════════════════════════════════════════
# ternary_time_ops.py (16% → 90%+)
# ═══════════════════════════════════════════════════════════


class TestDecayOp(unittest.TestCase):
    def test_decay_with_elapsed(self):
        r = ev(['decay', ['ternary_value', 1, 0.9, '"test"'], 0.1, 86400])
        self.assertAlmostEqual(r.confidence, 0.81, delta=0.01)

    def test_decay_auto_elapsed(self):
        e = SanyanEvaluator()
        e.set_var('x', TritValue(1, confidence=0.9))
        r = e.eval(['decay', 'x', 0.0])
        self.assertAlmostEqual(r.confidence, 0.9, delta=0.01)

    def test_decay_non_tritvalue(self):
        e = SanyanEvaluator()
        e.set_var('x', 42)
        r = e.eval(['decay', 'x', 0.1])
        self.assertEqual(r, 42)

    def test_decay_zero_rate(self):
        r = ev(['decay', ['ternary_value', 1, 0.9, '"x"'], 0.0, 100])
        self.assertAlmostEqual(r.confidence, 0.9, delta=0.01)

    def test_decay_full_rate(self):
        r = ev(['decay', ['ternary_value', 1, 0.9, '"x"'], 1.0, 86400])
        self.assertAlmostEqual(r.confidence, 0.0, delta=0.01)

    def test_decay_min_args(self):
        with self.assertRaises(Exception):
            ev(['decay', 1])


class TestDecayExpOp(unittest.TestCase):
    def test_decay_exp(self):
        r = ev(['decay_exp', ['ternary_value', 1, 0.9, '"x"'], 86400, 86400])
        self.assertAlmostEqual(r.confidence, 0.45, delta=0.01)

    def test_decay_exp_zero_elapsed(self):
        r = ev(['decay_exp', ['ternary_value', 1, 0.9, '"x"'], 86400, 0])
        self.assertAlmostEqual(r.confidence, 0.9, delta=0.01)

    def test_decay_exp_non_tritvalue(self):
        e = SanyanEvaluator()
        e.set_var('x', 42)
        r = e.eval(['decay_exp', 'x', 86400, 86400])
        self.assertEqual(r, 42)

    def test_decay_exp_min_args(self):
        with self.assertRaises(Exception):
            ev(['decay_exp', 1, 100])


class TestSerializeOp(unittest.TestCase):
    def test_serialize_true(self):
        r = ev(['serialize', ['ternary_value', 1, 0.9, '"sensor"']])
        self.assertTrue(r.startswith('+'))

    def test_serialize_false(self):
        r = ev(['serialize', ['ternary_value', -1, 0.8, '"sensor"']])
        self.assertTrue(r.startswith('-'))

    def test_serialize_maybe(self):
        r = ev(['serialize', ['ternary_value', 0, 0.5, '"sensor"']])
        self.assertTrue(r.startswith('0'))

    def test_serialize_string(self):
        r = ev(['serialize', ['ternary_value', '"hello"', 0.8]])
        self.assertIn('"hello"', r)
        self.assertIn('@0.800', r)

    def test_serialize_non_tritvalue(self):
        r = ev(['serialize', '"hello"'])
        self.assertIn('hello', r)

    def test_serialize_min_args(self):
        with self.assertRaises(Exception):
            ev(['serialize'])


class TestDeserializeOp(unittest.TestCase):
    def test_deserialize_true(self):
        r = ev(['deserialize', '"+0.900+sensor"'])
        self.assertEqual(r.to_int(), 1)
        self.assertAlmostEqual(r.confidence, 0.9, delta=0.01)

    def test_deserialize_false(self):
        r = ev(['deserialize', '"-"'])
        self.assertEqual(r.to_int(), -1)

    def test_deserialize_maybe(self):
        r = ev(['deserialize', '"0"'])
        self.assertEqual(r.to_int(), 0)

    def test_deserialize_string(self):
        r = ev(['deserialize', '"\\"hello\\"@0.800"'])
        self.assertEqual(r.to_payload(), 'hello')
        self.assertAlmostEqual(r.confidence, 0.8, delta=0.01)

    def test_deserialize_min_args(self):
        with self.assertRaises(Exception):
            ev(['deserialize'])


# ═══════════════════════════════════════════════════════════
# ternary_math_ops.py (49% → 90%+)
# ═══════════════════════════════════════════════════════════


class TestTritDist(unittest.TestCase):
    def test_dist_true_dominant(self):
        r = ev(['trit_dist', 0.7, 0.2, 0.1])
        self.assertEqual(r.to_int(), 1)
        self.assertAlmostEqual(r.confidence, 0.7, delta=0.01)

    def test_dist_false_dominant(self):
        r = ev(['trit_dist', 0.1, 0.7, 0.2])
        self.assertEqual(r.to_int(), -1)
        self.assertAlmostEqual(r.confidence, 0.7, delta=0.01)

    def test_dist_maybe_dominant(self):
        r = ev(['trit_dist', 0.2, 0.2, 0.6])
        self.assertEqual(r.to_int(), 0)
        self.assertAlmostEqual(r.confidence, 0.6, delta=0.01)

    def test_dist_zero_total(self):
        r = ev(['trit_dist', 0, 0, 0])
        self.assertEqual(r.confidence, 0)

    def test_dist_min_args(self):
        with self.assertRaises(Exception):
            ev(['trit_dist', 0.5, 0.5])


class TestEntropy(unittest.TestCase):
    def test_entropy_certain(self):
        r = ev(['entropy', ['ternary_value', 1, 1.0]])
        self.assertLess(r.to_float(), 0.1)

    def test_entropy_uncertain(self):
        r = ev(['entropy', ['ternary_value', 0, 0.5]])
        self.assertGreater(r.to_float(), 0.9)

    def test_entropy_non_tritvalue(self):
        r = ev(['entropy', 42])
        self.assertLess(r.to_float(), 0.1)

    def test_entropy_min_args(self):
        with self.assertRaises(Exception):
            ev(['entropy'])


class TestCrossEntropy(unittest.TestCase):
    def test_cross_entropy_same(self):
        r = ev(['cross_entropy', ['ternary_value', 1, 0.8], ['ternary_value', 1, 0.8]])
        self.assertGreater(r.to_float(), 0)

    def test_cross_entropy_different(self):
        r = ev(['cross_entropy', ['ternary_value', 1, 0.9], ['ternary_value', -1, 0.1]])
        self.assertGreater(r.to_float(), 0)

    def test_cross_entropy_min_args(self):
        with self.assertRaises(Exception):
            ev(['cross_entropy', 1])


class TestCalibrate(unittest.TestCase):
    def test_calibrate(self):
        r = ev(['calibrate', [TritValue(1, 0.8), TritValue(1, 0.7)], [TritValue(1), TritValue(1)]])
        self.assertGreater(r.to_float(), 0)

    def test_calibrate_empty(self):
        r = ev(['calibrate', [], []])
        self.assertEqual(r.to_float(), 1.0)

    def test_calibrate_mismatch(self):
        with self.assertRaises(Exception):
            ev(['calibrate', [1, 2], [1]])

    def test_calibrate_non_list(self):
        with self.assertRaises(Exception):
            ev(['calibrate', 1, 2])

    def test_calibrate_min_args(self):
        with self.assertRaises(Exception):
            ev(['calibrate', 1])


class TestObserve(unittest.TestCase):
    def test_observe_correct(self):
        r = ev(['observe', ['ternary_value', 1, 0.8], 1])
        self.assertGreater(r.confidence, 0.8)

    def test_observe_wrong(self):
        r = ev(['observe', ['ternary_value', 1, 0.8], -1])
        self.assertLess(r.confidence, 0.8)

    def test_observe_non_tritvalue(self):
        r = ev(['observe', 1, 1])
        self.assertGreater(r.confidence, 0)

    def test_observe_min_args(self):
        with self.assertRaises(Exception):
            ev(['observe', 1])


# ═══════════════════════════════════════════════════════════
# ternary_container_ops.py (63% → 90%+)
# ═══════════════════════════════════════════════════════════


class TestChain(unittest.TestCase):
    def test_chain_empty(self):
        r = ev(['链'])
        self.assertEqual(r.to_int(), 0)

    def test_chain_all_true(self):
        e = SanyanEvaluator()
        e.set_var('a', TritValue(1, confidence=0.9))
        e.set_var('b', TritValue(1, confidence=0.8))
        r = e.eval(['链', 'a', 'b'])
        self.assertEqual(r.to_int(), 1)
        self.assertAlmostEqual(r.confidence, 0.72, delta=0.01)

    def test_chain_with_false(self):
        e = SanyanEvaluator()
        e.set_var('a', TritValue(1, confidence=0.9))
        e.set_var('b', TritValue(-1, confidence=0.8))
        r = e.eval(['链', 'a', 'b'])
        self.assertEqual(r.to_int(), -1)

    def test_chain_with_maybe(self):
        e = SanyanEvaluator()
        e.set_var('a', TritValue(0, confidence=0.5))
        e.set_var('b', TritValue(1, confidence=0.9))
        r = e.eval(['链', 'a', 'b'])
        self.assertEqual(r.to_int(), 1)
        self.assertLess(r.confidence, 0.5)

    def test_chain_non_tritvalue(self):
        r = ev(['链', 42, 100])
        self.assertEqual(r.to_int(), 100)


class TestChainOrBreak(unittest.TestCase):
    def test_chain_break_on_false(self):
        e = SanyanEvaluator()
        e.set_var('a', TritValue(1, confidence=0.9))
        e.set_var('b', TritValue(-1, confidence=0.8))
        with self.assertRaises(Exception):
            e.eval(['链断', 'a', 'b'])

    def test_chain_break_all_true(self):
        e = SanyanEvaluator()
        e.set_var('a', TritValue(1, confidence=0.9))
        r = e.eval(['链断', 'a'])
        self.assertEqual(r.to_int(), 1)


class TestUnwrap(unittest.TestCase):
    def test_unwrap_true(self):
        e = SanyanEvaluator()
        e.set_var('x', TritValue(1, confidence=0.9))
        r = e.eval(['解包', 'x'])
        self.assertEqual(r.to_int(), 1)

    def test_unwrap_false_raises(self):
        e = SanyanEvaluator()
        e.set_var('x', TritValue(-1, confidence=0.5))
        with self.assertRaises(Exception):
            e.eval(['解包', 'x'])

    def test_unwrap_maybe_default(self):
        e = SanyanEvaluator()
        e.set_var('x', TritValue(0, confidence=0.3))
        r = e.eval(['解包', 'x', 42])
        self.assertEqual(r.to_int(), 42)

    def test_unwrap_maybe_no_default(self):
        e = SanyanEvaluator()
        e.set_var('x', TritValue(0, confidence=0.3))
        with self.assertRaises(Exception):
            e.eval(['解包', 'x'])

    def test_unwrap_non_tritvalue(self):
        e = SanyanEvaluator()
        e.set_var('x', 42)
        r = e.eval(['解包', 'x'])
        self.assertEqual(r, 42)


class TestUnwrapOr(unittest.TestCase):
    def test_unwrap_or_true(self):
        e = SanyanEvaluator()
        e.set_var('x', TritValue(1, confidence=0.9))
        r = e.eval(['或解', 'x', 42])
        self.assertEqual(r.to_int(), 1)

    def test_unwrap_or_false(self):
        e = SanyanEvaluator()
        e.set_var('x', TritValue(-1, confidence=0.5))
        r = e.eval(['或解', 'x', 42])
        self.assertEqual(r.to_int(), 42)


class TestTryChain(unittest.TestCase):
    def test_try_chain_success(self):
        e = SanyanEvaluator()
        e.set_var('a', TritValue(1, confidence=0.9))
        r = e.eval(['尝试链', 'a'])
        self.assertEqual(r.to_int(), 1)

    def test_try_chain_with_default(self):
        e = SanyanEvaluator()
        e.set_var('a', TritValue(-1, confidence=0.5))
        r = e.eval(['尝试链', 'a', ['默认', 42]])
        self.assertEqual(r.to_int(), 42)


class TestConfidenceGuard(unittest.TestCase):
    def test_guard_high(self):
        e = SanyanEvaluator()
        e.set_var('x', TritValue(1, confidence=0.9))
        r = e.eval(['信度守卫', 'x', 0.7, '高', 100, '低', 0])
        self.assertEqual(r.to_int(), 100)

    def test_guard_low(self):
        e = SanyanEvaluator()
        e.set_var('x', TritValue(1, confidence=0.3))
        r = e.eval(['信度守卫', 'x', 0.7, '高', 100, '低', 0])
        self.assertEqual(r.to_int(), 0)


# ═══════════════════════════════════════════════════════════
# ternary_engine.py (28% → 90%+)
# ═══════════════════════════════════════════════════════════


class TestTernaryEngine(unittest.TestCase):
    def setUp(self):
        from core.ternary_engine import TernaryEngine

        self.engine = TernaryEngine()

    def test_classify_affirm(self):
        self.assertEqual(self.engine.classify('analyze', '函数列表...'), 'AFFIRM')

    def test_classify_negate(self):
        self.assertEqual(self.engine.classify('read_file', '未找到文件'), 'UNCERT')  # 文件不存在是可恢复的
        self.assertEqual(self.engine.classify('run_test', 'FAIL test_foo'), 'NEGATE')

    def test_classify_uncert(self):
        self.assertEqual(self.engine.classify('replace_in_file', '已替换'), 'AFFIRM')
        self.assertEqual(self.engine.classify('replace_in_file', '操作完成'), 'UNCERT')

    def test_classify_fail(self):
        self.assertEqual(self.engine.classify('run_test', 'traceback error'), 'NEGATE')

    def test_classify_default(self):
        self.assertEqual(self.engine.classify('unknown', 'result'), 'UNCERT')  # 默认不确定

    def test_map_trit(self):
        self.assertEqual(self.engine.map_trit('AFFIRM'), 1)
        self.assertEqual(self.engine.map_trit('NEGATE'), -1)
        self.assertEqual(self.engine.map_trit('UNCERT'), 0)
        self.assertEqual(self.engine.map_trit('UNKNOWN'), 0)

    def test_propagate(self):
        self.assertEqual(self.engine.propagate(1, 1), 1)
        self.assertEqual(self.engine.propagate(1, -1), -1)
        self.assertEqual(self.engine.propagate(1, 0), 0)
        self.assertEqual(self.engine.propagate(0, 1), 0)
        self.assertEqual(self.engine.propagate(-1, 1), -1)

    def test_confidence(self):
        self.assertGreater(self.engine.confidence('AFFIRM', 'analyze'), 0)
        self.assertGreater(self.engine.confidence('NEGATE', 'read_file'), 0)
        self.assertGreater(self.engine.confidence('UNCERT'), 0)

    def test_propagate_confidence(self):
        r = self.engine.propagate_confidence(0.9, 0.8)
        self.assertAlmostEqual(r, 0.72, delta=0.01)

    def test_protect_high_risk(self):
        gate = self.engine.protect('高', -1, 0.5, [])
        self.assertEqual(gate['action'], 'block')

    def test_protect_hesitation(self):
        self.engine.hesitation = 5
        gate = self.engine.protect('低', 0, 0.9, [(1, 0.8)])  # trit=0 才触发犹豫
        self.assertEqual(gate['action'], 'block')

    def test_protect_low_gain(self):
        self.engine.history = [(1, 0.81), (1, 0.82), (1, 0.83)]
        self.engine.hesitation = 0
        gate = self.engine.protect('低', 0, 0.815, self.engine.history)
        self.assertIn('不确定', gate['reason'])  # trit=0 → UNCERT

    def test_protect_continue(self):
        gate = self.engine.protect('低', 1, 0.9, [])
        self.assertEqual(gate['action'], 'continue')

    def test_step(self):
        trit, conf, gate, cog = self.engine.step('analyze', '函数列表')
        self.assertEqual(trit, 1)
        self.assertEqual(cog, 'AFFIRM')
        self.assertEqual(gate['action'], 'continue')

    def test_step_uncert(self):
        trit, conf, gate, cog = self.engine.step('replace_in_file', '操作完成')
        self.assertEqual(trit, 0)
        self.assertEqual(cog, 'UNCERT')
        self.assertEqual(self.engine.hesitation, 1)

    def test_majority(self):
        self.assertEqual(self.engine._majority([(1, 0.9), (1, 0.8), (-1, 0.7)]), 1)
        self.assertEqual(self.engine._majority([(-1, 0.9), (-1, 0.8), (1, 0.7)]), -1)
        self.assertEqual(self.engine._majority([(1, 0.9), (-1, 0.8)]), 0)

    def test_summary_empty(self):
        self.assertEqual(self.engine.summary(), '无记录')

    def test_summary_with_history(self):
        self.engine.history.append((1, 0.85))
        self.assertIn('真', self.engine.summary())

    def test_trit_display(self):
        self.assertIn('●●●', self.engine.trit_display(1, 0.9))
        self.assertIn('○○○', self.engine.trit_display(-1, 0.8))
        self.assertIn('◐◐◐', self.engine.trit_display(0, 0.5))


# ═══════════════════════════════════════════════════════════
# runtime.py (77% → 90%+)
# ═══════════════════════════════════════════════════════════


class TestScopeManager(unittest.TestCase):
    def setUp(self):
        from core.runtime import ScopeManager

        self.sm = ScopeManager()

    def test_get_var(self):
        self.sm._scopes[0]['x'] = 42
        self.assertEqual(self.sm.get_var('x'), 42)

    def test_get_var_undefined(self):
        with self.assertRaises(Exception):
            self.sm.get_var('undefined')

    def test_has_var(self):
        self.sm._scopes[0]['x'] = 42
        self.assertTrue(self.sm.has_var('x'))
        self.assertFalse(self.sm.has_var('y'))

    def test_set_var(self):
        self.sm.set_var('x', 42)
        self.assertEqual(self.sm.scope_vars['x'], 42)

    def test_push_pop_scope(self):
        self.sm.set_var('x', 1)
        self.sm.push_scope()
        self.sm.set_var('y', 2)
        self.assertEqual(self.sm.get_var('y'), 2)
        self.sm.pop_scope()
        self.assertEqual(self.sm.get_var('x'), 1)

    def test_pop_global_scope(self):
        self.sm.pop_scope()
        self.assertEqual(len(self.sm._scopes), 1)

    def test_all_scoped_vars(self):
        self.sm.set_var('x', 1)
        self.sm.push_scope()
        self.sm.set_var('y', 2)
        vars = self.sm.all_scoped_vars()
        self.assertEqual(vars['x'], 1)
        self.assertEqual(vars['y'], 2)

    def test_depth(self):
        self.assertEqual(self.sm.depth(), 1)
        self.sm.push_scope()
        self.assertEqual(self.sm.depth(), 2)


# ═══════════════════════════════════════════════════════════
# values.py (74% → 90%+)
# ═══════════════════════════════════════════════════════════


class TestExceptions(unittest.TestCase):
    def test_hierarchy(self):
        from core.values import (
            SanyanError,
            SanyanSyntaxError,
            SanyanTypeError,
            SanyanValueError,
            SanyanRuntimeError,
            SanyanNameError,
            SanyanKeyError,
            SanyanAttributeError,
            SanyanIOError,
        )

        self.assertTrue(issubclass(SanyanSyntaxError, SanyanError))
        self.assertTrue(issubclass(SanyanTypeError, SanyanError))
        self.assertTrue(issubclass(SanyanValueError, SanyanError))
        self.assertTrue(issubclass(SanyanRuntimeError, SanyanError))
        self.assertTrue(issubclass(SanyanNameError, SanyanError))
        self.assertTrue(issubclass(SanyanKeyError, SanyanError))
        self.assertTrue(issubclass(SanyanAttributeError, SanyanError))
        self.assertTrue(issubclass(SanyanIOError, SanyanError))


class TestFunctionValue(unittest.TestCase):
    def test_create(self):
        from core.values import FunctionValue

        fv = FunctionValue(['x'], ['add', 'x', 1], None, {}, {})
        self.assertEqual(fv.params, ['x'])
        self.assertEqual(fv.body, ['add', 'x', 1])

    def test_repr(self):
        from core.values import FunctionValue

        fv = FunctionValue(['x'], ['add', 'x', 1], None, {}, {})
        self.assertIn('x', repr(fv))


class TestModuleValue(unittest.TestCase):
    def test_create(self):
        from core.values import ModuleValue

        mv = ModuleValue({}, {}, set(['func1']))
        self.assertTrue(mv.is_exported('func1'))
        self.assertFalse(mv.is_exported('func2'))


class TestSrcNode(unittest.TestCase):
    def test_create(self):
        from core.values import SrcNode

        sn = SrcNode(['do', 1, 2], line=10, col=5)
        self.assertEqual(sn.line, 10)
        self.assertEqual(sn.col, 5)


class TestToNum(unittest.TestCase):
    def test_to_num_tritvalue(self):
        from core.values import to_num

        self.assertEqual(to_num(TritValue(42)), 42)

    def test_to_num_int(self):
        from core.values import to_num

        self.assertEqual(to_num(42), 42)

    def test_to_num_float(self):
        from core.values import to_num

        self.assertEqual(to_num(3.14), 3.14)

    def test_to_num_string(self):
        from core.values import to_num

        self.assertEqual(to_num('42'), 42)

    def test_to_num_invalid(self):
        from core.values import to_num

        self.assertEqual(to_num('abc'), 'abc')


# ═══════════════════════════════════════════════════════════
# ternary_core.py (83% → 90%+)
# ═══════════════════════════════════════════════════════════


class TestBT(unittest.TestCase):
    def test_from_int(self):
        self.assertEqual(BT.from_int(0), [0])
        self.assertEqual(BT.from_int(1), [1])
        self.assertEqual(BT.from_int(-1), [-1])
        self.assertEqual(BT.from_int(2), [1, -1])
        self.assertEqual(BT.from_int(3), [1, 0])

    def test_to_int(self):
        self.assertEqual(BT.to_int([0]), 0)
        self.assertEqual(BT.to_int([1]), 1)
        self.assertEqual(BT.to_int([-1]), -1)
        self.assertEqual(BT.to_int([1, -1]), 2)

    def test_to_str(self):
        self.assertEqual(BT.to_str([1, 0, -1]), '+0-')

    def test_from_str(self):
        self.assertEqual(BT.from_str('+0-'), [1, 0, -1])

    def test_from_float(self):
        trits = BT.from_float(1.5)
        self.assertIsInstance(trits, list)

    def test_to_float(self):
        trits = BT.from_float(1.0)
        f = BT.to_float(trits)
        self.assertAlmostEqual(f, 1.0, delta=0.01)

    def test_from_int_with_length(self):
        trits = BT.from_int(1, length=4)
        self.assertEqual(len(trits), 4)


class TestTernaryALU(unittest.TestCase):
    def test_add(self):
        result = TernaryALU.add([1], [1])
        self.assertEqual(BT.to_int(result), 2)

    def test_sub(self):
        result = TernaryALU.sub([1, 0], [1])
        self.assertEqual(BT.to_int(result), 2)

    def test_multiply(self):
        result = TernaryALU.multiply([1, 0], [1])
        self.assertEqual(BT.to_int(result), 3)

    def test_div(self):
        result = TernaryALU.div([1, 0, 0], [1, 0], 0)
        self.assertEqual(BT.to_int(result), 3)

    def test_div_zero(self):
        with self.assertRaises(Exception):
            TernaryALU.div([1], [0], 0)

    def test_neg(self):
        result = TernaryALU.neg([1, 0])
        self.assertEqual(BT.to_int(result), -3)

    def test_is_zero(self):
        self.assertTrue(TernaryALU.is_zero([0]))
        self.assertFalse(TernaryALU.is_zero([1]))

    def test_tritwise_and(self):
        result = TernaryALU.tritwise_and([1, 0], [1, 1])
        self.assertEqual(result, [1, 0])

    def test_tritwise_or(self):
        result = TernaryALU.tritwise_or([1, 0], [0, 1])
        self.assertEqual(result, [1, 1])

    def test_tritwise_not(self):
        result = TernaryALU.tritwise_not([1, 0, -1])
        self.assertEqual(result, [-1, 0, 1])


class TestTritValueExtended(unittest.TestCase):
    def test_with_confidence(self):
        v = TritValue(1, confidence=0.8)
        v2 = v.with_confidence(0.9)
        self.assertAlmostEqual(v2.confidence, 0.9, delta=0.01)

    def test_confidence_str(self):
        v = TritValue(1, confidence=0.9)
        self.assertIn('0.90', v.confidence_str())

    def test_confidence_str_high(self):
        v = TritValue(1, confidence=1.0)
        self.assertNotIn('1.00', v.confidence_str())

    def test_is_float(self):
        v = TritValue(3.14)
        self.assertTrue(v.is_float())

    def test_is_string(self):
        v = TritValue('hello')
        self.assertTrue(v.is_string())

    def test_is_numeric(self):
        v = TritValue(42)
        self.assertTrue(v.is_numeric())

    def test_to_payload(self):
        v = TritValue('hello')
        self.assertEqual(v.to_payload(), 'hello')

    def test_array_value(self):
        from core.ternary_core import ArrayValue

        arr = ArrayValue(3, TritValue(0))
        self.assertEqual(arr.length, 3)
        arr.set(1, TritValue(5))
        self.assertEqual(arr.get(1).to_int(), 5)

    def test_array_value_out_of_bounds(self):
        from core.ternary_core import ArrayValue

        arr = ArrayValue(3, TritValue(0))
        with self.assertRaises(Exception):
            arr.get(5)


# ═══════════════════════════════════════════════════════════
# evaluator.py (80% → 90%+)
# ═══════════════════════════════════════════════════════════


class TestEvaluatorExtended(unittest.TestCase):
    def setUp(self):
        self.e = SanyanEvaluator()

    def test_eval_int(self):
        r = self.e.eval(42)
        self.assertEqual(r.to_int(), 42)

    def test_eval_string(self):
        r = self.e.eval('"hello"')
        self.assertEqual(r, 'hello')

    def test_eval_list_add(self):
        r = self.e.eval(['add', 1, 2])
        self.assertEqual(r.to_int(), 3)

    def test_eval_list_set(self):
        self.e.eval(['set', 'x', 10])
        self.assertEqual(self.e.get_var('x').to_int(), 10)

    def test_eval_list_if(self):
        r = self.e.eval(['if', 1, 'yes', 'no'])
        self.assertEqual(r, 'yes')

    def test_eval_list_do(self):
        self.e.eval(['do', ['set', 'x', 1], ['set', 'y', 2]])
        self.assertEqual(self.e.get_var('y').to_int(), 2)

    def test_eval_list_return(self):
        from core.values import ReturnException

        with self.assertRaises(ReturnException):
            self.e.eval(['return', 42])

    def test_eval_list_break(self):
        from core.values import BreakException

        with self.assertRaises(BreakException):
            self.e.eval(['break'])

    def test_eval_list_continue(self):
        from core.values import ContinueException

        with self.assertRaises(ContinueException):
            self.e.eval(['continue'])

    def test_eval_ternary_true(self):
        r = self.e.eval(TritValue(1))
        self.assertEqual(r.to_int(), 1)

    def test_eval_ternary_false(self):
        r = self.e.eval(TritValue(-1))
        self.assertEqual(r.to_int(), -1)

    def test_eval_ternary_maybe(self):
        r = self.e.eval(TritValue(0))
        self.assertEqual(r.to_int(), 0)


# ═══════════════════════════════════════════════════════════
# data_pipeline_ops.py (53% → 90%+)
# ═══════════════════════════════════════════════════════════


class TestDataPipelineExtended(unittest.TestCase):
    def test_ternary_data_create(self):
        from ops.data_pipeline_ops import TernaryData

        d = TernaryData(42, 0.9, 'sensor')
        self.assertEqual(d.value, 42)
        self.assertEqual(d.source, 'sensor')

    def test_ternary_data_is_valid(self):
        from ops.data_pipeline_ops import TernaryData

        d = TernaryData(42, 0.9)
        self.assertTrue(d.is_valid(0.5))
        d2 = TernaryData(42, 0.3)
        self.assertFalse(d2.is_valid(0.5))

    def test_ternary_data_to_trit(self):
        from ops.data_pipeline_ops import TernaryData

        d = TernaryData(42, 0.9)
        t = d.to_trit()
        self.assertEqual(t.to_int(), 1)

    def test_ternary_data_str(self):
        from ops.data_pipeline_ops import TernaryData

        d = TernaryData(42, 0.9)
        self.assertEqual(str(d), '42')

    def test_pipeline_process(self):
        from ops.data_pipeline_ops import TernaryPipeline, TernaryData

        p = TernaryPipeline('test')
        p.add_stage('double', lambda d: TernaryData(d.value * 2, d.confidence))
        result = p.process(TernaryData(5, 0.9))
        self.assertEqual(result.value, 10)

    def test_pipeline_stats(self):
        from ops.data_pipeline_ops import TernaryPipeline, TernaryData

        p = TernaryPipeline('test')
        p.process(TernaryData(5, 0.9))
        stats = p.get_stats()
        self.assertEqual(stats['total'], 1)
        self.assertEqual(stats['valid'], 1)

    def test_pipeline_reset(self):
        from ops.data_pipeline_ops import TernaryPipeline, TernaryData

        p = TernaryPipeline('test')
        p.process(TernaryData(5, 0.9))
        p.reset_stats()
        self.assertEqual(p.get_stats()['total'], 0)

    def test_clean_remove_null(self):
        from ops.data_pipeline_ops import TernaryData

        d = TernaryData(None, 0.5)
        r = ev(['三态清洗', d, '"去空"'])
        self.assertEqual(r.confidence, 0.0)

    def test_clean_normalize(self):
        from ops.data_pipeline_ops import TernaryData

        d = TernaryData(42, 0.5)
        r = ev(['三态清洗', d, '"归一化"'])
        self.assertTrue(0.0 <= r.confidence <= 1.0)

    def test_aggregate_average(self):
        from ops.data_pipeline_ops import TernaryData

        data = [TernaryData(10, 0.9), TernaryData(20, 0.8)]
        r = ev(['三态聚合', data, '"平均"'])
        self.assertGreater(float(str(r.value)), 0)

    def test_aggregate_sum(self):
        from ops.data_pipeline_ops import TernaryData

        data = [TernaryData(10, 0.9), TernaryData(20, 0.8)]
        r = ev(['三态聚合', data, '"求和"'])
        self.assertEqual(float(str(r.value)), 30.0)

    def test_aggregate_count(self):
        from ops.data_pipeline_ops import TernaryData

        data = [TernaryData(10, 0.9), TernaryData(0, 0.3)]
        r = ev(['三态聚合', data, '"计数"'])
        self.assertEqual(float(str(r.value)), 1.0)

    def test_aggregate_fusion(self):
        from ops.data_pipeline_ops import TernaryData

        data = [TernaryData(1, 0.9), TernaryData(1, 0.8)]
        r = ev(['三态聚合', data, '"融合"'])
        self.assertEqual(float(str(r.value)), 1.0)

    def test_validate(self):

        data = {'name': 'test', 'age': 25}
        schema = {'name': {'type': 'str', 'required': True}, 'age': {'type': 'int'}}
        r = ev(['三态验证', data, schema])
        self.assertEqual(r.confidence, 1.0)

    def test_validate_fail(self):

        data = {'name': 'test'}
        schema = {'name': {'type': 'str', 'required': True}, 'age': {'type': 'int', 'required': True}}
        r = ev(['三态验证', data, schema])
        self.assertEqual(r.confidence, 0.0)


# ═══════════════════════════════════════════════════════════
# ternary_source_ops.py (88% → 95%+)
# ═══════════════════════════════════════════════════════════


class TestSourceOpsFull(unittest.TestCase):
    def test_source_with_tritvalue(self):
        e = SanyanEvaluator()
        e.set_var('x', TritValue(42, source='sensor'))
        r = e.eval(['source', 'x'])
        self.assertEqual(r.to_payload(), 'sensor')

    def test_detect_conflict_high_confidence(self):
        e = SanyanEvaluator()
        e.set_var('a', TritValue(1, confidence=0.95))
        e.set_var('b', TritValue(-1, confidence=0.95))
        r = e.eval(['detect_conflict', 'a', 'b'])
        self.assertEqual(r['冲突'], 1)

    def test_detect_conflict_low_confidence(self):
        e = SanyanEvaluator()
        e.set_var('a', TritValue(1, confidence=0.3))
        e.set_var('b', TritValue(-1, confidence=0.3))
        r = e.eval(['detect_conflict', 'a', 'b'])
        self.assertEqual(r['冲突'], 0)

    def test_bayes_update_exact_same(self):
        e = SanyanEvaluator()
        e.set_var('prior', TritValue(1, confidence=0.5))
        e.set_var('evidence', TritValue(1, confidence=0.5))
        r = e.eval(['bayes_update', 'prior', 'evidence'])
        self.assertEqual(r.to_int(), 1)
        self.assertGreater(r.confidence, 0.5)

    def test_consensus_three_true(self):
        e = SanyanEvaluator()
        e.set_var('a', TritValue(1, confidence=0.9))
        e.set_var('b', TritValue(1, confidence=0.8))
        e.set_var('c', TritValue(1, confidence=0.7))
        r = e.eval(['consensus', 'a', 'b', 'c'])
        self.assertEqual(r.to_int(), 1)
        self.assertEqual(r.confidence, 0.9)

    def test_majority_vote_all_same(self):
        r = ev(['majority_vote', 1, 1, 1])
        self.assertEqual(r.to_int(), 1)

    def test_quantize_zero(self):
        e = SanyanEvaluator()
        e.set_var('x', TritValue(0, confidence=0.5))
        q = e.eval(['量化', 'x'])
        d = e.eval(['反量化', q])
        self.assertEqual(d.to_int(), 0)

    def test_assert_confidence_exact(self):
        e = SanyanEvaluator()
        e.set_var('x', TritValue(1, confidence=0.5))
        r = e.eval(['assert_confidence', 'x', 0.5])
        self.assertEqual(r.to_int(), 1)


# ═══════════════════════════════════════════════════════════
# ternary_set/graph/queue (88% → 95%+)
# ═══════════════════════════════════════════════════════════


class TestTernarySetFull(unittest.TestCase):
    def test_add_no_confidence(self):
        e = SanyanEvaluator()
        s = e.eval(['三态集'])
        e.set_var('s', s)
        e.eval(['三态集加', 's', 1])
        self.assertEqual(s.size(), 1)

    def test_union_three(self):
        r = ev(['三态集并', ['三态集', 1, 2], ['三态集', 3, 4]])
        self.assertEqual(r.size(), 4)

    def test_intersection_disjoint(self):
        r = ev(['三态集交', ['三态集', 1, 2], ['三态集', 3, 4]])
        self.assertEqual(r.size(), 0)

    def test_difference_empty(self):
        r = ev(['三态集差', ['三态集', 1, 2], ['三态集', 1, 2]])
        self.assertEqual(r.size(), 0)


class TestTernaryGraphFull(unittest.TestCase):
    def test_node_confidence(self):
        from ops.ternary_graph_ops import TernaryGraph

        g = TernaryGraph()
        g.add_node('A', 0.9)
        self.assertAlmostEqual(g.node_confidence('A'), 0.9, delta=0.01)

    def test_node_confidence_missing(self):
        from ops.ternary_graph_ops import TernaryGraph

        g = TernaryGraph()
        self.assertEqual(g.node_confidence('X'), 0.0)

    def test_shortest_path_direct(self):
        from ops.ternary_graph_ops import TernaryGraph

        g = TernaryGraph()
        g.add_edge('A', 'B', 0.9)
        path, conf = g.shortest_path('A', 'B')
        self.assertEqual(path, ['A', 'B'])

    def test_repr(self):
        from ops.ternary_graph_ops import TernaryGraph

        g = TernaryGraph()
        g.add_node('A')
        g.add_node('B')
        g.add_edge('A', 'B', 0.9)
        self.assertIn('2', repr(g))


class TestTernaryQueueFull(unittest.TestCase):
    def test_enqueue_confidence(self):
        from ops.ternary_queue_ops import TernaryQueue

        q = TernaryQueue()
        q.enqueue('a', 0.9)
        item, conf = q.peek()
        self.assertEqual(item, 'a')
        self.assertAlmostEqual(conf, 0.9, delta=0.01)

    def test_dequeue_multiple(self):
        from ops.ternary_queue_ops import TernaryQueue

        q = TernaryQueue()
        q.enqueue('a')
        q.enqueue('b')
        q.enqueue('c')
        self.assertEqual(q.dequeue()[0], 'a')
        self.assertEqual(q.dequeue()[0], 'b')
        self.assertEqual(q.dequeue()[0], 'c')


class TestTernaryStackFull(unittest.TestCase):
    def test_push_confidence(self):
        from ops.ternary_queue_ops import TernaryStack

        s = TernaryStack()
        s.push('a', 0.9)
        item, conf = s.peek()
        self.assertEqual(item, 'a')
        self.assertAlmostEqual(conf, 0.9, delta=0.01)

    def test_pop_multiple(self):
        from ops.ternary_queue_ops import TernaryStack

        s = TernaryStack()
        s.push('a')
        s.push('b')
        s.push('c')
        self.assertEqual(s.pop()[0], 'c')
        self.assertEqual(s.pop()[0], 'b')
        self.assertEqual(s.pop()[0], 'a')


if __name__ == '__main__':
    unittest.main()
