"""覆盖补全第六轮：针对剩余未覆盖行的精确测试"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.evaluator import SanyanEvaluator


def ev(expr):
    e = SanyanEvaluator()
    return e.eval(expr)


# ═══════════════════════════════════════════════════════════
# evaluator.py: _is_numeric_string 边界情况
# ═══════════════════════════════════════════════════════════


class TestIsNumericString(unittest.TestCase):
    """evaluator._is_numeric_string 边界测试"""

    def test_empty_string(self):
        e = SanyanEvaluator()
        self.assertFalse(e._is_numeric_string(''))

    def test_hex_0x(self):
        e = SanyanEvaluator()
        self.assertTrue(e._is_numeric_string('0xFF'))

    def test_hex_negative(self):
        e = SanyanEvaluator()
        self.assertTrue(e._is_numeric_string('-0xFF'))

    def test_hex_empty_after_0x(self):
        e = SanyanEvaluator()
        self.assertFalse(e._is_numeric_string('0x'))

    def test_negative_only(self):
        e = SanyanEvaluator()
        self.assertFalse(e._is_numeric_string('-'))

    def test_float(self):
        e = SanyanEvaluator()
        self.assertTrue(e._is_numeric_string('3.14'))

    def test_invalid_float(self):
        e = SanyanEvaluator()
        self.assertFalse(e._is_numeric_string('3.'))

    def test_integer(self):
        e = SanyanEvaluator()
        self.assertTrue(e._is_numeric_string('42'))

    def test_non_numeric(self):
        e = SanyanEvaluator()
        self.assertFalse(e._is_numeric_string('abc'))


# ═══════════════════════════════════════════════════════════
# evaluator.py: _eval_list 各分支
# ═══════════════════════════════════════════════════════════


class TestEvalListBranches(unittest.TestCase):
    def setUp(self):
        self.e = SanyanEvaluator()

    def test_eval_list_empty(self):
        r = self.e.eval([])
        self.assertEqual(r, [])

    def test_eval_list_single_float_string(self):
        r = self.e.eval(['3.14'])
        self.assertEqual(r, ['3.14'])

    def test_eval_list_function_value(self):
        from core.values import FunctionValue

        fv = FunctionValue(['x'], ['set', 'y', ['add', 'x', 1]], None, {}, {})
        self.e.set_var('f', fv)
        r = self.e.eval(['f', 5])
        self.assertEqual(r.to_int(), 6)

    def test_eval_list_module_value(self):
        from core.values import ModuleValue

        mv = ModuleValue({}, {'func': (['x'], ['set', 'y', ['add', 'x', 1]], None, {}, {})}, set(['func']))
        self.e.set_var('m', mv)
        r = self.e.eval(['m', 'func', 5])
        self.assertEqual(r.to_int(), 6)

    def test_eval_list_numeric_string(self):
        r = self.e.eval(['123'])
        self.assertEqual(r, ['123'])

    def test_eval_list_float_string(self):
        r = self.e.eval(['3.14'])
        self.assertEqual(r, ['3.14'])


# ═══════════════════════════════════════════════════════════
# evaluator.py: _pos 方法
# ═══════════════════════════════════════════════════════════


class TestPosMethod(unittest.TestCase):
    def test_pos_with_line_col(self):
        from core.values import SrcNode

        e = SanyanEvaluator()
        node = SrcNode(['add', 1, 2], line=10, col=5)
        r = e._pos(node)
        self.assertIn('10', r)
        self.assertIn('5', r)

    def test_pos_without_line(self):
        from core.values import SrcNode

        e = SanyanEvaluator()
        node = SrcNode(['add', 1, 2])
        r = e._pos(node)
        self.assertEqual(r, '')

    def test_pos_non_srcnode(self):
        e = SanyanEvaluator()
        r = e._pos(42)
        self.assertEqual(r, '')


# ═══════════════════════════════════════════════════════════
# evaluator.py: profiling
# ═══════════════════════════════════════════════════════════


class TestProfiling(unittest.TestCase):
    def test_profile_start_stop(self):
        e = SanyanEvaluator()
        e.profile_start()
        self.assertTrue(e._profiling)
        e.eval(['add', 1, 2])
        report = e.profile_stop()
        self.assertFalse(e._profiling)
        self.assertIn('add', report)

    def test_profile_report(self):
        e = SanyanEvaluator()
        e.profile_start()
        e.eval(['add', 1, 2])
        e.eval(['add', 3, 4])
        report = e.profile_report()
        self.assertIn('add', report)


# ═══════════════════════════════════════════════════════════
# evaluator.py: _is_valid_identifier
# ═══════════════════════════════════════════════════════════


class TestIsValidIdentifier(unittest.TestCase):
    def test_valid(self):
        e = SanyanEvaluator()
        self.assertTrue(e._is_valid_identifier('foo'))

    def test_invalid(self):
        e = SanyanEvaluator()
        self.assertFalse(e._is_valid_identifier(''))


# ═══════════════════════════════════════════════════════════
# values.py: check_type 边界情况
# ═══════════════════════════════════════════════════════════


class TestCheckTypeEdgeCases(unittest.TestCase):
    def test_check_type_int_pass(self):
        from core.values import check_type

        self.assertIsNone(check_type(42, 'int'))

    def test_check_type_int_fail(self):
        from core.values import check_type
        from core.values import SanyanTypeError

        with self.assertRaises(SanyanTypeError):
            check_type('hello', 'int')

    def test_check_type_float_pass(self):
        from core.values import check_type

        self.assertIsNone(check_type(3.14, 'float'))

    def test_check_type_float_fail(self):
        from core.values import check_type
        from core.values import SanyanTypeError

        with self.assertRaises(SanyanTypeError):
            check_type('hello', 'float')

    def test_check_type_str_pass(self):
        from core.values import check_type

        self.assertIsNone(check_type('hello', 'str'))

    def test_check_type_str_fail(self):
        from core.values import check_type
        from core.values import SanyanTypeError

        with self.assertRaises(SanyanTypeError):
            check_type(42, 'str')

    def test_check_type_list_pass(self):
        from core.values import check_type

        self.assertIsNone(check_type([1, 2], 'list'))

    def test_check_type_list_fail(self):
        from core.values import check_type
        from core.values import SanyanTypeError

        with self.assertRaises(SanyanTypeError):
            check_type(42, 'list')

    def test_check_type_dict_pass(self):
        from core.values import check_type

        self.assertIsNone(check_type({'a': 1}, 'dict'))

    def test_check_type_dict_fail(self):
        from core.values import check_type
        from core.values import SanyanTypeError

        with self.assertRaises(SanyanTypeError):
            check_type(42, 'dict')

    def test_check_type_num(self):
        from core.values import check_type

        self.assertIsNone(check_type(42, 'num'))

    def test_check_type_any(self):
        from core.values import check_type

        self.assertIsNone(check_type(42, 'any'))
        self.assertIsNone(check_type('hello', 'any'))

    def test_check_type_none(self):
        from core.values import check_type

        self.assertIsNone(check_type(None, 'any'))


# ═══════════════════════════════════════════════════════════
# ternary_queue_ops.py: 错误处理分支
# ═══════════════════════════════════════════════════════════


class TestQueueOpsErrors(unittest.TestCase):
    def test_enqueue_wrong_type(self):
        e = SanyanEvaluator()
        e.set_var('x', 42)
        with self.assertRaises(Exception):
            e.eval(['三态入队', 'x', 'a'])

    def test_dequeue_wrong_type(self):
        e = SanyanEvaluator()
        e.set_var('x', 42)
        with self.assertRaises(Exception):
            e.eval(['三态出队', 'x'])

    def test_peek_wrong_type(self):
        e = SanyanEvaluator()
        e.set_var('x', 42)
        with self.assertRaises(Exception):
            e.eval(['三态查看队', 'x'])

    def test_size_wrong_type(self):
        e = SanyanEvaluator()
        e.set_var('x', 42)
        with self.assertRaises(Exception):
            e.eval(['三态队长', 'x'])

    def test_enqueue_wrong_args(self):
        with self.assertRaises(Exception):
            ev(['三态入队'])

    def test_dequeue_wrong_args(self):
        with self.assertRaises(Exception):
            ev(['三态出队', 'a', 'b'])

    def test_push_wrong_type(self):
        e = SanyanEvaluator()
        e.set_var('x', 42)
        with self.assertRaises(Exception):
            e.eval(['三态压栈', 'x', 'a'])

    def test_pop_wrong_type(self):
        e = SanyanEvaluator()
        e.set_var('x', 42)
        with self.assertRaises(Exception):
            e.eval(['三态弹栈', 'x'])

    def test_stack_peek_wrong_type(self):
        e = SanyanEvaluator()
        e.set_var('x', 42)
        with self.assertRaises(Exception):
            e.eval(['三态查看栈', 'x'])

    def test_stack_size_wrong_type(self):
        e = SanyanEvaluator()
        e.set_var('x', 42)
        with self.assertRaises(Exception):
            e.eval(['三态栈长', 'x'])

    def test_push_wrong_args(self):
        with self.assertRaises(Exception):
            ev(['三态压栈'])

    def test_pop_wrong_args(self):
        with self.assertRaises(Exception):
            ev(['三态弹栈', 'a', 'b'])


# ═══════════════════════════════════════════════════════════
# ternary_set_ops.py: 错误处理分支
# ═══════════════════════════════════════════════════════════


class TestSetOpsErrors(unittest.TestCase):
    def test_add_wrong_type(self):
        e = SanyanEvaluator()
        e.set_var('x', 42)
        with self.assertRaises(Exception):
            e.eval(['三态集加', 'x', 1])

    def test_remove_wrong_type(self):
        e = SanyanEvaluator()
        e.set_var('x', 42)
        with self.assertRaises(Exception):
            e.eval(['三态集删', 'x', 1])

    def test_contains_wrong_type(self):
        e = SanyanEvaluator()
        e.set_var('x', 42)
        with self.assertRaises(Exception):
            e.eval(['三态集含', 'x', 1])

    def test_size_wrong_type(self):
        e = SanyanEvaluator()
        e.set_var('x', 42)
        with self.assertRaises(Exception):
            e.eval(['三态集长', 'x'])

    def test_union_wrong_type(self):
        e = SanyanEvaluator()
        e.set_var('x', 42)
        with self.assertRaises(Exception):
            e.eval(['三态集并', 'x', 'x'])

    def test_intersection_wrong_type(self):
        e = SanyanEvaluator()
        e.set_var('x', 42)
        with self.assertRaises(Exception):
            e.eval(['三态集交', 'x', 'x'])

    def test_difference_wrong_type(self):
        e = SanyanEvaluator()
        e.set_var('x', 42)
        with self.assertRaises(Exception):
            e.eval(['三态集差', 'x', 'x'])

    def test_to_list_wrong_type(self):
        e = SanyanEvaluator()
        e.set_var('x', 42)
        with self.assertRaises(Exception):
            e.eval(['三态集列', 'x'])

    def test_conf_sum_wrong_type(self):
        e = SanyanEvaluator()
        e.set_var('x', 42)
        with self.assertRaises(Exception):
            e.eval(['三态集信度和', 'x'])

    def test_add_wrong_args(self):
        with self.assertRaises(Exception):
            ev(['三态集加'])

    def test_remove_wrong_args(self):
        with self.assertRaises(Exception):
            ev(['三态集删'])

    def test_contains_wrong_args(self):
        with self.assertRaises(Exception):
            ev(['三态集含'])

    def test_size_wrong_args(self):
        with self.assertRaises(Exception):
            ev(['三态集长', 'a', 'b'])

    def test_union_wrong_args(self):
        with self.assertRaises(Exception):
            ev(['三态集并'])

    def test_intersection_wrong_args(self):
        with self.assertRaises(Exception):
            ev(['三态集交'])

    def test_difference_wrong_args(self):
        with self.assertRaises(Exception):
            ev(['三态集差'])

    def test_to_list_wrong_args(self):
        with self.assertRaises(Exception):
            ev(['三态集列', 'a', 'b'])

    def test_conf_sum_wrong_args(self):
        with self.assertRaises(Exception):
            ev(['三态集信度和', 'a', 'b'])


# ═══════════════════════════════════════════════════════════
# ternary_source_ops.py: 错误处理分支
# ═══════════════════════════════════════════════════════════


class TestSourceOpsErrors(unittest.TestCase):
    def test_source_wrong_args(self):
        with self.assertRaises(Exception):
            ev(['source'])

    def test_source_chain_wrong_args(self):
        r = ev(['source_chain'])
        self.assertEqual(r.to_payload(), '')

    def test_detect_conflict_wrong_args(self):
        with self.assertRaises(Exception):
            ev(['detect_conflict'])

    def test_conflict_merge_wrong_args(self):
        with self.assertRaises(Exception):
            ev(['conflict_merge'])

    def test_bayes_update_wrong_args(self):
        with self.assertRaises(Exception):
            ev(['bayes_update'])

    def test_fuse_wrong_args(self):
        r = ev(['fuse'])
        self.assertEqual(r.to_int(), 0)

    def test_fuse_wrong_type(self):
        e = SanyanEvaluator()
        e.set_var('x', 42)
        with self.assertRaises(Exception):
            e.eval(['fuse', 'x'])

    def test_consensus_wrong_args(self):
        with self.assertRaises(Exception):
            ev(['consensus'])

    def test_assert_confidence_wrong_args(self):
        with self.assertRaises(Exception):
            ev(['assert_confidence'])

    def test_quantize_wrong_args(self):
        with self.assertRaises(Exception):
            ev(['quantize'])

    def test_dequantize_wrong_args(self):
        with self.assertRaises(Exception):
            ev(['dequantize'])

    def test_majority_vote_wrong_args(self):
        r = ev(['majority_vote'])
        self.assertEqual(r.to_int(), 0)

    def test_source_wrong_type(self):
        e = SanyanEvaluator()
        e.set_var('x', 42)
        r = e.eval(['source', 'x'])
        self.assertEqual(r.to_payload(), '')

    def test_detect_conflict_wrong_type(self):
        e = SanyanEvaluator()
        e.set_var('x', 42)
        e.set_var('y', 'hello')
        r = e.eval(['detect_conflict', 'x', 'y'])
        self.assertEqual(r['冲突'], 0)

    def test_bayes_update_wrong_type(self):
        e = SanyanEvaluator()
        e.set_var('x', 42)
        r = e.eval(['bayes_update', 'x', 'x'])
        self.assertEqual(r.to_int(), 42)

    def test_assert_confidence_wrong_type(self):
        e = SanyanEvaluator()
        e.set_var('x', 42)
        r = e.eval(['assert_confidence', 'x', 0.5])
        self.assertEqual(r, 42)

    def test_quantize_wrong_type(self):
        e = SanyanEvaluator()
        e.set_var('x', 42)
        r = e.eval(['quantize', 'x'])
        self.assertEqual(r.to_int(), 0)

    def test_dequantize_wrong_type(self):
        e = SanyanEvaluator()
        e.set_var('x', 'hello')
        with self.assertRaises(Exception):
            e.eval(['dequantize', 'x'])


if __name__ == '__main__':
    unittest.main()
