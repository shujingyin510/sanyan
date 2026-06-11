"""覆盖补全第五轮：runtime/debug/profile/IoT"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from evaluator import SanyanEvaluator
from ternary_core import TritValue


# ═══════════════════════════════════════════════════════════
# runtime.py (78% → 90%+)
# ═══════════════════════════════════════════════════════════


class TestDebugManager(unittest.TestCase):
    def test_break_add(self):
        from runtime import DebugManager

        dm = DebugManager()
        dm.break_add('add')
        self.assertTrue(dm.debug_mode)
        self.assertIn('add', dm._break_ops)

    def test_break_remove(self):
        from runtime import DebugManager

        dm = DebugManager()
        dm.break_add('add')
        dm.break_remove('add')
        self.assertNotIn('add', dm._break_ops)

    def test_watch_add(self):
        from runtime import DebugManager

        dm = DebugManager()
        dm.watch_add('x')
        self.assertIn('x', dm._watched_vars)

    def test_watch_remove(self):
        from runtime import DebugManager

        dm = DebugManager()
        dm.watch_add('x')
        dm.watch_remove('x')
        self.assertNotIn('x', dm._watched_vars)

    def test_should_break(self):
        from runtime import DebugManager

        dm = DebugManager()
        dm.break_add('add')
        self.assertTrue(dm.should_break('add', 'add'))
        self.assertFalse(dm.should_break('sub', 'sub'))

    def test_should_break_all(self):
        from runtime import DebugManager

        dm = DebugManager()
        dm.debug_mode = True
        dm._break_all = True
        self.assertTrue(dm.should_break('anything', 'anything'))


class TestProfileManager(unittest.TestCase):
    def test_start_stop(self):
        from runtime import ProfileManager

        pm = ProfileManager()
        pm.start()
        self.assertTrue(pm._profiling)
        result = pm.stop()
        self.assertFalse(pm._profiling)
        self.assertIsInstance(result, dict)

    def test_record(self):
        from runtime import ProfileManager

        pm = ProfileManager()
        pm.start()
        pm.record('add', 0.001)
        pm.record('add', 0.002)
        self.assertEqual(pm._profile['add']['count'], 2)
        self.assertAlmostEqual(pm._profile['add']['time'], 0.003, delta=0.001)

    def test_report(self):
        from runtime import ProfileManager

        pm = ProfileManager()
        pm.start()
        pm.record('add', 0.001)
        report = pm.report()
        self.assertIn('add', report)

    def test_report_empty(self):
        from runtime import ProfileManager

        pm = ProfileManager()
        report = pm.report()
        self.assertIn('无性能数据', report)


class TestIoTManager(unittest.TestCase):
    def test_create(self):
        from runtime import IoTManager

        iot = IoTManager()
        self.assertIn('人体', iot.sensors)
        self.assertIn('灯', iot.actuators)


class TestSanyanRuntime(unittest.TestCase):
    def test_create(self):
        from runtime import SanyanRuntime

        sr = SanyanRuntime()
        self.assertIsNotNone(sr._scope_mgr)
        self.assertIsNotNone(sr._iot_mgr)
        self.assertIsNotNone(sr._debug_mgr)
        self.assertIsNotNone(sr._profile_mgr)

    def test_scope_access(self):
        from runtime import SanyanRuntime

        sr = SanyanRuntime()
        sr.set_var('x', 42)
        self.assertEqual(sr.get_var('x'), 42)

    def test_iot_access(self):
        from runtime import SanyanRuntime

        sr = SanyanRuntime()
        self.assertIn('人体', sr.sensors)
        self.assertIn('灯', sr.actuators)


# ═══════════════════════════════════════════════════════════
# values.py (89% → 90%+)
# ═══════════════════════════════════════════════════════════


class TestValuesFinal2(unittest.TestCase):
    def test_function_value_repr(self):
        from values import FunctionValue

        fv = FunctionValue(['x'], ['add', 'x', 1], None, {}, {})
        self.assertIn('λ', repr(fv))

    def test_module_value_repr(self):
        from values import ModuleValue

        mv = ModuleValue({}, {}, set())
        self.assertIn('ModuleValue', repr(mv))

    def test_src_node_repr(self):
        from values import SrcNode

        sn = SrcNode(['do', 1, 2], line=10, col=5)
        self.assertIn('do', repr(sn))

    def test_to_num_none(self):
        from values import to_num

        self.assertIsNone(to_num(None))

    def test_to_num_complex(self):
        from values import to_num

        self.assertEqual(to_num(42j), 42j)


# ═══════════════════════════════════════════════════════════
# evaluator.py (82% → 90%+)
# ═══════════════════════════════════════════════════════════


class TestEvaluatorFinal2(unittest.TestCase):
    def setUp(self):
        self.e = SanyanEvaluator()

    def test_eval_string_empty(self):
        r = self.e.eval('""')
        self.assertEqual(r, '')

    def test_eval_string_single_char(self):
        r = self.e.eval('"a"')
        self.assertEqual(r, 'a')

    def test_eval_string_unicode(self):
        r = self.e.eval('"你好"')
        self.assertEqual(r, '你好')

    def test_eval_numeric_zero(self):
        r = self.e.eval('0')
        self.assertEqual(r.to_int(), 0)

    def test_eval_numeric_negative(self):
        r = self.e.eval('-1')
        self.assertEqual(r.to_int(), -1)

    def test_eval_float(self):
        r = self.e.eval('3.14')
        self.assertTrue(r.is_float())

    def test_eval_hex(self):
        r = self.e.eval('0xFF')
        self.assertEqual(r.to_int(), 255)

    def test_eval_list_single_element(self):
        r = self.e.eval(['42'])
        self.assertEqual(r, ['42'])

    def test_eval_list_multiple_elements(self):
        r = self.e.eval([1, 2, 3])
        self.assertEqual(len(r), 3)

    def test_eval_dict(self):
        d = {'a': 1, 'b': 2}
        r = self.e.eval(d)
        self.assertEqual(r, d)

    def test_eval_tritvalue(self):
        v = TritValue(42, confidence=0.9)
        r = self.e.eval(v)
        self.assertEqual(r.to_int(), 42)

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
# ternary_container_ops.py (90% → 90%+)
# ═══════════════════════════════════════════════════════════


class TestTernaryContainerFinal2(unittest.TestCase):
    def setUp(self):
        self.e = SanyanEvaluator()

    def test_trit_list_with_tritvalues(self):
        r = self.e.eval(['trit_list', ['ternary_value', 1, 0.9], ['ternary_value', 2, 0.8]])
        self.assertEqual(len(r), 2)

    def test_trit_get_wrong_args(self):
        with self.assertRaises(Exception):
            self.e.eval(['trit_get', [1, 2]])

    def test_trit_set_wrong_args(self):
        with self.assertRaises(Exception):
            self.e.eval(['trit_set', [1, 2], 0])

    def test_trit_list_len_wrong_args(self):
        with self.assertRaises(Exception):
            self.e.eval(['trit_list_len'])

    def test_trit_list_map_wrong_args(self):
        with self.assertRaises(Exception):
            self.e.eval(['trit_list_map', [1, 2]])

    def test_trit_dict_wrong_args(self):
        with self.assertRaises(Exception):
            self.e.eval(['trit_dict', '"a"'])

    def test_trit_key_get_wrong_args(self):
        with self.assertRaises(Exception):
            self.e.eval(['trit_key_get', {'a': 1}])

    def test_trit_key_set_wrong_args(self):
        with self.assertRaises(Exception):
            self.e.eval(['trit_key_set', {'a': 1}, '"b"'])

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
