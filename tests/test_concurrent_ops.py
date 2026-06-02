"""并发操作模块测试 — 覆盖 concurrent_run、delayed_run、mutex 操作"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import unittest
import threading
from evaluator import SanyanEvaluator
from ternary_core import TritValue, ArrayValue
from values import SanyanSyntaxError, SanyanRuntimeError


class TestConcurrentRun(unittest.TestCase):
    """并发执行测试"""

    def setUp(self):
        self.env = SanyanEvaluator()

    def test_concurrent_no_args(self):
        result = self.env.eval(['并发'])
        self.assertEqual(result.to_int(), 0)

    def test_concurrent_single_task(self):
        self.env.eval(['set', 'x', 0])
        result = self.env.eval(['并发', ['set', 'x', 42]])
        self.assertIsInstance(result, ArrayValue)
        self.assertEqual(result.get(0).to_int() if isinstance(result.get(0), TritValue) else result.get(0), 42)

    def test_concurrent_multiple_tasks(self):
        result = self.env.eval(['并发', ['add', 1, 2], ['mul', 3, 4], ['sub', 10, 5]])
        self.assertIsInstance(result, ArrayValue)
        self.assertEqual(len(result.data), 3)
        self.assertEqual(result.get(0).to_int(), 3)
        self.assertEqual(result.get(1).to_int(), 12)
        self.assertEqual(result.get(2).to_int(), 5)

    def test_concurrent_with_side_effects(self):
        result = self.env.eval(['并发', ['add', 1, 2], ['add', 3, 4], ['add', 5, 6]])
        self.assertIsInstance(result, ArrayValue)
        nums = [result.get(i).to_int() for i in range(3)]
        self.assertIn(3, nums)
        self.assertIn(7, nums)
        self.assertIn(11, nums)


class TestDelayedRun(unittest.TestCase):
    """延迟执行测试"""

    def setUp(self):
        self.env = SanyanEvaluator()

    def test_delay_missing_args(self):
        with self.assertRaises(SanyanSyntaxError):
            self.env.eval(['延迟', 100])

    def test_delay_simple(self):
        import time

        self.env.eval(['set', 'x', 0])
        t0 = time.time()
        result = self.env.eval(['延迟', 50, ['set', 'x', 99]])
        dt = time.time() - t0
        self.assertGreaterEqual(dt, 0.04)
        self.assertEqual(result.to_int(), 99)
        self.assertEqual(self.env.get_var('x').to_int(), 99)

    def test_delay_expression(self):
        import time

        self.env.eval(['set', 'y', 100])
        t0 = time.time()
        result = self.env.eval(['延迟', 30, ['add', 'y', 1]])
        dt = time.time() - t0
        self.assertGreaterEqual(dt, 0.025)
        self.assertEqual(result.to_int(), 101)


class TestMutexOps(unittest.TestCase):
    """互斥锁操作测试"""

    def setUp(self):
        self.env = SanyanEvaluator()

    def test_lock_create(self):
        result = self.env.eval(['锁', '"my_lock"'])
        self.assertEqual(result, '"my_lock"')

    def test_lock_no_name(self):
        with self.assertRaises(SanyanSyntaxError):
            self.env.eval(['锁'])

    def test_lock_acquire_release(self):
        self.env.eval(['锁', '"A"'])
        result = self.env.eval(['锁住', '"A"'])
        self.assertEqual(result.to_int(), 1)
        result = self.env.eval(['开锁', '"A"'])
        self.assertEqual(result.to_int(), 0)

    def test_lock_acquire_no_name(self):
        with self.assertRaises(SanyanSyntaxError):
            self.env.eval(['锁住'])

    def test_lock_release_no_name(self):
        with self.assertRaises(SanyanSyntaxError):
            self.env.eval(['开锁'])

    def test_lock_undefined(self):
        with self.assertRaises(SanyanRuntimeError):
            self.env.eval(['锁住', '"nonexistent"'])

    def test_lock_release_released(self):
        self.env.eval(['锁', '"B"'])
        self.env.eval(['锁住', '"B"'])
        self.env.eval(['开锁', '"B"'])
        result = self.env.eval(['开锁', '"B"'])
        self.assertEqual(result.to_int(), 0)

    def test_lock_multiple_names(self):
        self.env.eval(['锁', '"L1"'])
        self.env.eval(['锁', '"L2"'])
        self.assertNotEqual(self.env.eval(['锁', '"L1"']), self.env.eval(['锁', '"L2"']))

    def test_lock_variable_name(self):
        self.env.eval(['set', 'name', '"dynamic_lock"'])
        self.env.eval(['锁', 'name'])
        result = self.env.eval(['锁住', 'name'])
        self.assertEqual(result.to_int(), 1)

    def test_lock_thread_safety(self):
        self.env.eval(['锁', '"shared"'])
        results = []
        errors = []

        def worker():
            try:
                e = SanyanEvaluator()
                e.eval(['锁住', '"shared"'])
                results.append(1)
                e.eval(['开锁', '"shared"'])
            except Exception as ex:
                errors.append(ex)

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(len(results), 5)
        self.assertEqual(len(errors), 0)


class TestConcurrentAliases(unittest.TestCase):
    """别名测试"""

    def setUp(self):
        self.env = SanyanEvaluator()

    def test_concurrent_alias(self):
        result = self.env.eval(['concurrent', ['add', 1, 1]])
        self.assertIsInstance(result, ArrayValue)

    def test_delay_alias(self):
        import time

        t0 = time.time()
        result = self.env.eval(['delay', 30, ['add', 5, 5]])
        dt = time.time() - t0
        self.assertGreaterEqual(dt, 0.025)
        self.assertEqual(result.to_int(), 10)

    def test_lock_aliases(self):
        self.env.eval(['lock', '"X"'])
        result = self.env.eval(['lock_acquire', '"X"'])
        self.assertEqual(result.to_int(), 1)
        result = self.env.eval(['lock_release', '"X"'])
        self.assertEqual(result.to_int(), 0)


if __name__ == '__main__':
    unittest.main()
