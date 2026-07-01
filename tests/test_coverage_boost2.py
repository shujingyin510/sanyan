"""覆盖补全第二轮：目标所有模块 ≥90%"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.evaluator import SanyanEvaluator
from core.ternary_core import TritValue, BT, TernaryALU


def ev(expr):
    e = SanyanEvaluator()
    return e.eval(expr)


# ═══════════════════════════════════════════════════════════
# ternary_container_ops.py (74% → 90%+)
# ═══════════════════════════════════════════════════════════


class TestTernaryContainerOpsFull(unittest.TestCase):
    """三态容器操作全覆盖"""

    def test_trit_list(self):
        r = ev(['trit_list', 1, 2, 3])
        self.assertEqual(len(r), 3)

    def test_trit_list_empty(self):
        r = ev(['trit_list'])
        self.assertEqual(len(r), 0)

    def test_trit_get(self):
        e = SanyanEvaluator()
        e.set_var('lst', [TritValue(10), TritValue(20)])
        r = e.eval(['trit_get', 'lst', 0])
        self.assertEqual(r.to_int(), 10)

    def test_trit_get_out_of_bounds(self):
        e = SanyanEvaluator()
        e.set_var('lst', [TritValue(10)])
        with self.assertRaises(Exception):
            e.eval(['trit_get', 'lst', 5])

    def test_trit_set(self):
        e = SanyanEvaluator()
        e.set_var('lst', [TritValue(10), TritValue(20)])
        e.eval(['trit_set', 'lst', 0, 99])
        self.assertEqual(e.get_var('lst')[0].to_int(), 99)

    def test_trit_set_out_of_bounds(self):
        e = SanyanEvaluator()
        e.set_var('lst', [TritValue(10)])
        with self.assertRaises(Exception):
            e.eval(['trit_set', 'lst', 5, 99])

    def test_trit_list_len(self):
        e = SanyanEvaluator()
        e.set_var('lst', [TritValue(10), TritValue(20)])
        r = e.eval(['trit_list_len', 'lst'])
        self.assertEqual(r.to_int(), 2)

    def test_trit_list_map(self):
        e = SanyanEvaluator()
        e.set_var('lst', [TritValue(10), TritValue(20)])
        e.eval(['定义', 'double', ['x'], ['mul', 'x', 2]])
        r = e.eval(['trit_list_map', 'lst', 'double'])
        self.assertEqual(len(r), 2)

    def test_trit_dict(self):
        r = ev(['trit_dict', '"a"', 1, '"b"', 2])
        self.assertIsInstance(r, dict)

    def test_trit_dict_empty(self):
        r = ev(['trit_dict'])
        self.assertEqual(len(r), 0)

    def test_trit_key_get(self):
        e = SanyanEvaluator()
        e.set_var('d', {'a': TritValue(10)})
        r = e.eval(['trit_key_get', 'd', '"a"'])
        self.assertEqual(r.to_int(), 10)

    def test_trit_key_get_missing(self):
        e = SanyanEvaluator()
        e.set_var('d', {'a': TritValue(10)})
        r = e.eval(['trit_key_get', 'd', '"b"'])
        self.assertEqual(r.to_int(), 0)

    def test_trit_key_set(self):
        e = SanyanEvaluator()
        e.set_var('d', {'a': TritValue(10)})
        e.eval(['trit_key_set', 'd', '"a"', 99])
        self.assertEqual(e.get_var('d')['a'].to_int(), 99)

    def test_chain_multiple_steps(self):
        e = SanyanEvaluator()
        e.set_var('a', TritValue(1, confidence=0.9))
        e.set_var('b', TritValue(1, confidence=0.8))
        e.set_var('c', TritValue(1, confidence=0.7))
        r = e.eval(['链', 'a', 'b', 'c'])
        self.assertEqual(r.to_int(), 1)
        self.assertAlmostEqual(r.confidence, 0.504, delta=0.01)

    def test_chain_or_break_success(self):
        e = SanyanEvaluator()
        e.set_var('a', TritValue(1, confidence=0.9))
        r = e.eval(['链断', 'a'])
        self.assertEqual(r.to_int(), 1)

    def test_chain_or_break_with_maybe(self):
        e = SanyanEvaluator()
        e.set_var('a', TritValue(0, confidence=0.5))
        e.set_var('b', TritValue(1, confidence=0.9))
        r = e.eval(['链断', 'a', 'b'])
        self.assertEqual(r.to_int(), 1)

    def test_unwrap_or_true(self):
        e = SanyanEvaluator()
        e.set_var('x', TritValue(1, confidence=0.9))
        r = e.eval(['或解', 'x', 42])
        self.assertEqual(r.to_int(), 1)

    def test_unwrap_or_maybe(self):
        e = SanyanEvaluator()
        e.set_var('x', TritValue(0, confidence=0.3))
        r = e.eval(['或解', 'x', 42])
        self.assertEqual(r.to_int(), 42)

    def test_try_chain_all_fail(self):
        e = SanyanEvaluator()
        e.eval(['定义', 'fail', [], ['raise_error', '"fail"']])
        r = e.eval(['尝试链', ['fail'], ['默认', 99]])
        self.assertEqual(r.to_int(), 99)

    def test_confidence_guard_mid(self):
        e = SanyanEvaluator()
        e.set_var('x', TritValue(1, confidence=0.5))
        r = e.eval(['信度守卫', 'x', 0.7, '高', 100, '低', 0])
        self.assertEqual(r.to_int(), 0)

    def test_confidence_guard_no_match(self):
        e = SanyanEvaluator()
        e.set_var('x', TritValue(1, confidence=0.5))
        r = e.eval(['信度守卫', 'x', 0.7, '高', 100])
        self.assertEqual(r.to_int(), 0)


# ═══════════════════════════════════════════════════════════
# ternary_core.py (87% → 90%+)
# ═══════════════════════════════════════════════════════════


class TestTernaryCoreFull(unittest.TestCase):
    def test_bt_from_str(self):
        self.assertEqual(BT.from_str('+'), [1])
        self.assertEqual(BT.from_str('-'), [-1])
        self.assertEqual(BT.from_str('0'), [0])
        self.assertEqual(BT.from_str('+0-'), [1, 0, -1])

    def test_bt_from_str_error(self):
        with self.assertRaises(Exception):
            BT.from_str('abc')

    def test_bt_from_float_precision(self):
        trits = BT.from_float(1.5, precision=8)
        self.assertGreater(len(trits), 0)

    def test_bt_to_float_precision(self):
        trits = BT.from_float(1.5, precision=8)
        f = BT.to_float(trits, precision=8)
        self.assertAlmostEqual(f, 1.5, delta=0.1)

    def test_ternary_alu_fixed_mul(self):
        a = BT.from_int(3)
        b = BT.from_int(2)
        result = TernaryALU.fixed_mul(a, b, 0)
        self.assertEqual(BT.to_int(result), 6)

    def test_ternary_alu_fixed_div(self):
        a = BT.from_int(6)
        b = BT.from_int(2)
        result = TernaryALU.fixed_div(a, b, 0)
        self.assertEqual(BT.to_int(result), 3)

    def test_tritvalue_repr_string(self):
        v = TritValue('hello')
        self.assertEqual(repr(v), 'hello')

    def test_tritvalue_repr_int(self):
        v = TritValue(42)
        self.assertEqual(repr(v), '42')

    def test_tritvalue_repr_float(self):
        v = TritValue(3.14)
        self.assertIn('3.14', repr(v))

    def test_tritvalue_from_string(self):
        v = TritValue.from_string('真')
        self.assertEqual(v.to_int(), 1)

    def test_tritvalue_from_string_unknown(self):
        v = TritValue.from_string('未知')
        self.assertEqual(v.to_int(), 0)

    def test_array_value_len(self):
        from core.ternary_core import ArrayValue

        arr = ArrayValue(5, TritValue(0))
        self.assertEqual(len(arr), 5)

    def test_array_value_iter(self):
        from core.ternary_core import ArrayValue

        arr = ArrayValue(3, TritValue(5))
        items = list(arr)
        self.assertEqual(len(items), 3)

    def test_array_value_to_list(self):
        from core.ternary_core import ArrayValue

        arr = ArrayValue(3, TritValue(5))
        lst = arr.to_list()
        self.assertEqual(len(lst), 3)

    def test_array_value_setitem(self):
        from core.ternary_core import ArrayValue

        arr = ArrayValue(3, TritValue(0))
        arr[1] = TritValue(5)
        self.assertEqual(arr[1].to_int(), 5)

    def test_array_value_repr(self):
        from core.ternary_core import ArrayValue

        arr = ArrayValue(3, TritValue(5))
        self.assertIn('5', repr(arr))


# ═══════════════════════════════════════════════════════════
# ternary_set_ops.py (88% → 90%+)
# ═══════════════════════════════════════════════════════════


class TestTernarySetOpsFull(unittest.TestCase):
    def test_set_add_with_tritvalue(self):
        e = SanyanEvaluator()
        s = e.eval(['三态集'])
        e.set_var('s', s)
        e.eval(['三态集加', 's', ['ternary_value', 42, 0.8]])
        self.assertEqual(s.size(), 1)

    def test_set_remove_missing(self):
        e = SanyanEvaluator()
        s = e.eval(['三态集', 1, 2])
        e.set_var('s', s)
        e.eval(['三态集删', 's', 99])
        self.assertEqual(s.size(), 2)

    def test_set_contains_tritvalue(self):
        e = SanyanEvaluator()
        s = e.eval(['三态集', 1, 2])
        e.set_var('s', s)
        r = e.eval(['三态集含', 's', ['ternary_value', 1, 0.9]])
        self.assertTrue(r.to_int() == 1)

    def test_set_to_list_empty(self):
        r = ev(['三态集列', ['三态集']])
        self.assertEqual(len(r), 0)

    def test_set_confidence_sum_empty(self):
        r = ev(['三态集信度和', ['三态集']])
        self.assertEqual(float(str(r)), 0.0)


# ═══════════════════════════════════════════════════════════
# ternary_queue_ops.py (88% → 90%+)
# ═══════════════════════════════════════════════════════════


class TestTernaryQueueOpsFull(unittest.TestCase):
    def test_queue_enqueue_tritvalue(self):
        e = SanyanEvaluator()
        q = e.eval(['三态队列'])
        e.set_var('q', q)
        e.eval(['三态入队', 'q', ['ternary_value', 'task', 0.9]])
        self.assertEqual(q.size(), 1)

    def test_queue_size_empty(self):
        r = ev(['三态队长', ['三态队列']])
        self.assertEqual(r.to_int(), 0)

    def test_stack_push_tritvalue(self):
        e = SanyanEvaluator()
        s = e.eval(['三态栈'])
        e.set_var('s', s)
        e.eval(['三态压栈', 's', ['ternary_value', 'data', 0.9]])
        self.assertEqual(s.size(), 1)

    def test_stack_size_empty(self):
        r = ev(['三态栈长', ['三态栈']])
        self.assertEqual(r.to_int(), 0)


# ═══════════════════════════════════════════════════════════
# ternary_source_ops.py (89% → 90%+)
# ═══════════════════════════════════════════════════════════


class TestTernarySourceOpsFull(unittest.TestCase):
    def test_source_tritvalue_no_source(self):
        e = SanyanEvaluator()
        e.set_var('x', TritValue(42))
        r = e.eval(['source', 'x'])
        self.assertEqual(r.to_payload(), '')

    def test_detect_conflict_three_values(self):
        e = SanyanEvaluator()
        e.set_var('a', TritValue(1, confidence=0.9))
        e.set_var('b', TritValue(-1, confidence=0.8))
        e.set_var('c', TritValue(1, confidence=0.7))
        r = e.eval(['detect_conflict', 'a', 'b', 'c'])
        self.assertEqual(r['冲突'], 1)

    def test_conflict_merge_priority_tritvalue(self):
        e = SanyanEvaluator()
        e.set_var('a', TritValue(1, confidence=0.9))
        e.set_var('b', TritValue(-1, confidence=0.8))
        r = e.eval(['conflict_merge', 'a', 'b', ['ternary_value', '"优先级"', 1.0]])
        self.assertEqual(r.to_int(), 1)

    def test_consensus_all_maybe(self):
        e = SanyanEvaluator()
        e.set_var('a', TritValue(0, confidence=0.5))
        e.set_var('b', TritValue(0, confidence=0.5))
        r = e.eval(['consensus', 'a', 'b'])
        self.assertEqual(r.to_int(), 0)

    def test_assert_confidence_fail(self):
        e = SanyanEvaluator()
        e.set_var('x', TritValue(1, confidence=0.3))
        with self.assertRaises(Exception):
            e.eval(['assert_confidence', 'x', 0.5, '"too low"'])


# ═══════════════════════════════════════════════════════════
# values.py (77% → 90%+)
# ═══════════════════════════════════════════════════════════


class TestValuesFull(unittest.TestCase):
    def test_function_value_repr(self):
        from core.values import FunctionValue

        fv = FunctionValue(['x', 'y'], ['add', 'x', 'y'], None, {}, {'x': 'int'})
        self.assertIn('x', repr(fv))

    def test_function_value_call(self):
        from core.values import FunctionValue
        from core.evaluator import SanyanEvaluator

        fv = FunctionValue(['x'], ['set', 'y', ['add', 'x', 1]], None, {}, {})
        e = SanyanEvaluator()
        result = fv.call(e, [5])
        self.assertEqual(result.to_int(), 6)

    def test_module_value_is_exported(self):
        from core.values import ModuleValue

        mv = ModuleValue({}, {}, set(['a', 'b']))
        self.assertTrue(mv.is_exported('a'))
        self.assertFalse(mv.is_exported('c'))

    def test_src_node(self):
        from core.values import SrcNode

        sn = SrcNode(['do', 1, 2], line=10, col=5)
        self.assertEqual(sn.line, 10)
        self.assertEqual(sn.col, 5)
        self.assertEqual(sn[0], 'do')

    def test_check_type(self):
        from core.values import check_type

        self.assertIsNone(check_type(42, 'int'))
        self.assertIsNone(check_type('hello', 'str'))
        self.assertIsNone(check_type(3.14, 'float'))
        self.assertIsNone(check_type([1, 2], 'list'))
        self.assertIsNone(check_type({'a': 1}, 'dict'))
        self.assertIsNone(check_type(42, 'num'))
        self.assertIsNone(check_type(42, 'any'))


# ═══════════════════════════════════════════════════════════
# evaluator.py (80% → 90%+)
# ═══════════════════════════════════════════════════════════


class TestEvaluatorFull(unittest.TestCase):
    def setUp(self):
        self.e = SanyanEvaluator()

    def test_eval_string_literal(self):
        r = self.e.eval('"hello world"')
        self.assertEqual(r, 'hello world')

    def test_eval_numeric_literal(self):
        r = self.e.eval('42')
        self.assertEqual(r.to_int(), 42)

    def test_eval_float_literal(self):
        r = self.e.eval('3.14')
        self.assertTrue(r.is_float())

    def test_eval_hex_literal(self):
        r = self.e.eval('0xFF')
        self.assertEqual(r.to_int(), 255)

    def test_eval_list_do(self):
        r = self.e.eval(['do', 1, 2, 3])
        self.assertEqual(r.to_int(), 3)

    def test_eval_list_if_true(self):
        r = self.e.eval(['if', 1, 'yes'])
        self.assertEqual(r, 'yes')

    def test_eval_list_if_false(self):
        r = self.e.eval(['if', 0, 'yes', 'no'])
        self.assertEqual(r, 'no')

    def test_eval_list_set(self):
        self.e.eval(['set', 'x', 10])
        self.assertEqual(self.e.get_var('x').to_int(), 10)

    def test_eval_list_loop(self):
        self.e.eval(['set', 'i', 0])
        self.e.eval(['loop', ['lt', 'i', 3], ['set', 'i', ['add', 'i', 1]]])
        self.assertEqual(self.e.get_var('i').to_int(), 3)

    def test_eval_list_for(self):
        self.e.eval(['set', 'sum', 0])
        self.e.eval(['for', 'i', 1, 5, ['set', 'sum', ['add', 'sum', 'i']]])
        self.assertEqual(self.e.get_var('sum').to_int(), 15)

    def test_eval_list_return(self):
        from core.values import ReturnException

        with self.assertRaises(ReturnException) as ctx:
            self.e.eval(['return', 42])
        self.assertEqual(ctx.exception.value.to_int(), 42)

    def test_eval_list_break(self):
        from core.values import BreakException

        with self.assertRaises(BreakException):
            self.e.eval(['break'])

    def test_eval_list_continue(self):
        from core.values import ContinueException

        with self.assertRaises(ContinueException):
            self.e.eval(['continue'])


# ═══════════════════════════════════════════════════════════
# runtime.py (78% → 90%+)
# ═══════════════════════════════════════════════════════════


class TestRuntimeFull(unittest.TestCase):
    def test_scope_manager_depth(self):
        from core.runtime import ScopeManager

        sm = ScopeManager()
        self.assertEqual(sm.depth(), 1)
        sm.push_scope()
        self.assertEqual(sm.depth(), 2)
        sm.pop_scope()
        self.assertEqual(sm.depth(), 1)

    def test_scope_manager_set_var(self):
        from core.runtime import ScopeManager

        sm = ScopeManager()
        sm.set_var('x', 42)
        self.assertEqual(sm.get_var('x'), 42)

    def test_scope_manager_has_var(self):
        from core.runtime import ScopeManager

        sm = ScopeManager()
        sm.set_var('x', 42)
        self.assertTrue(sm.has_var('x'))
        self.assertFalse(sm.has_var('y'))

    def test_scope_manager_all_vars(self):
        from core.runtime import ScopeManager

        sm = ScopeManager()
        sm.set_var('x', 1)
        sm.push_scope()
        sm.set_var('y', 2)
        vars = sm.all_scoped_vars()
        self.assertEqual(len(vars), 2)

    def test_scope_manager_pop_global(self):
        from core.runtime import ScopeManager

        sm = ScopeManager()
        sm.pop_scope()
        self.assertEqual(sm.depth(), 1)


# ═══════════════════════════════════════════════════════════
# ternary_engine.py (97% → 97%+)
# ═══════════════════════════════════════════════════════════


class TestTernaryEngineFull(unittest.TestCase):
    def setUp(self):
        from core.ternary_engine import TernaryEngine

        self.engine = TernaryEngine()

    def test_classify_with_risk(self):
        self.assertEqual(self.engine.classify('analyze', 'ok', '高'), 'AFFIRM')

    def test_step_multiple(self):
        self.engine.step('analyze', 'ok')
        self.engine.step('run_test', '通过')
        self.assertEqual(len(self.engine.history), 2)

    def test_trit_display_all(self):
        self.assertIn('●●●', self.engine.trit_display(1, 0.9))
        self.assertIn('○○○', self.engine.trit_display(-1, 0.8))
        self.assertIn('◐◐◐', self.engine.trit_display(0, 0.5))


if __name__ == '__main__':
    unittest.main()
