"""覆盖补全第八轮：values/evaluator/ops 边界"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from evaluator import SanyanEvaluator
from lexer import tokenize
from parser import parse


def run(code):
    t = tokenize(code)
    if not t:
        return None
    a = parse(t)
    if not a:
        return None
    return SanyanEvaluator(max_loop_steps=500).eval(a)


class TestValues(unittest.TestCase):
    def test_src_node_repr(self):
        from values import SrcNode

        sn = SrcNode(['do', 1, 2], line=10, col=5)
        self.assertIn('SrcNode', repr(sn))

    def test_check_type_trit(self):
        from values import check_type
        from ternary_core import TritValue

        self.assertIsNone(check_type(TritValue(42), 'int'))
        self.assertIsNone(check_type(TritValue(3.14), 'float'))

    def test_function_value(self):
        from values import FunctionValue

        fv = FunctionValue(lambda x: x + 1, ['x'])
        self.assertEqual(fv(5), 6)

    def test_ternary_ops(self):
        from ternary_core import TritValue, BT

        t = TritValue(5, BT.TRUE)
        self.assertTrue(t.is_true)
        t2 = TritValue(0, BT.FALSE)
        self.assertFalse(t2.is_true)
        t3 = TritValue(None, BT.UNKNOWN)
        self.assertTrue(t3.is_unknown)

    def test_exception_classes(self):
        from values import SanyanSyntaxError, SanyanTypeError, SanyanValueError
        from values import SanyanRuntimeError, SanyanNameError, SanyanKeyError
        from values import SanyanAttributeError, SanyanIOError

        for c in [
            SanyanSyntaxError,
            SanyanTypeError,
            SanyanValueError,
            SanyanRuntimeError,
            SanyanNameError,
            SanyanKeyError,
            SanyanAttributeError,
            SanyanIOError,
        ]:
            self.assertIn('test', str(c('test')))


class TestTernaryCore(unittest.TestCase):
    def test_trit_math(self):
        from ternary_core import TritValue, BT

        a = TritValue(3, BT.TRUE)
        b = TritValue(2, BT.TRUE)
        c = a + b
        self.assertEqual(c.value, 5)
        d = a * b
        self.assertEqual(d.value, 6)

    def test_trit_compare(self):
        from ternary_core import TritValue, BT

        a = TritValue(3, BT.TRUE)
        b = TritValue(3, BT.TRUE)
        self.assertTrue(a.compare_eq(b))


class TestOps(unittest.TestCase):
    def test_concat(self):
        r = run('(concat "hello" " " "world")')
        self.assertEqual(r, 'hello world')

    def test_length(self):
        r = run('(length (list 1 2 3))')
        self.assertEqual(r, 3)
        r = run('(length "hello")')
        self.assertEqual(r, 5)

    def test_upper_lower(self):
        r = run('(upper "hello")')
        self.assertEqual(r, 'HELLO')
        r = run('(lower "HELLO")')
        self.assertEqual(r, 'hello')

    def test_replace(self):
        r = run('(replace "hello" "l" "x")')
        self.assertEqual(r, 'hexxo')

    def test_split(self):
        r = run('(split "a,b,c" ",")')
        self.assertEqual(r, ['a', 'b', 'c'])

    def test_trim(self):
        r = run('(trim "  hello  ")')
        self.assertEqual(r, 'hello')

    def test_starts_ends(self):
        self.assertTrue(run('(startswith "hello" "he")'))
        self.assertTrue(run('(endswith "hello" "lo")'))

    def test_substring(self):
        r = run('(substring "hello" 1 3)')
        self.assertEqual(r, 'el')

    def test_find(self):
        r = run('(find "hello" "ll")')
        self.assertEqual(r, 2)

    def test_print(self):
        run('(print "test output")')

    def test_input_mock(self):
        import io
        import sys

        old = sys.stdin
        sys.stdin = io.StringIO('mocked\n')
        try:
            r = run('(input)')
            self.assertIsNotNone(r)
        finally:
            sys.stdin = old

    def test_abs(self):
        r = run('(abs -5)')
        self.assertEqual(r, 5)

    def test_min_max(self):
        r = run('(min 3 1 2)')
        self.assertEqual(r, 1)
        r = run('(max 3 1 2)')
        self.assertEqual(r, 3)

    def test_pow(self):
        r = run('(pow 2 8)')
        self.assertEqual(r, 256)

    def test_sqrt(self):
        r = run('(sqrt 16)')
        self.assertEqual(r, 4)

    def test_round(self):
        r = run('(round 3.14159 2)')
        self.assertAlmostEqual(r, 3.14, places=2)

    def test_random(self):
        r = run('(random 1 100)')
        self.assertTrue(1 <= r <= 100)

    def test_type_predicates(self):
        self.assertTrue(run('(int? 42)'))
        self.assertTrue(run('(str? "hello")'))
        self.assertTrue(run('(list? (list 1 2))'))

    def test_and_or_not(self):
        self.assertTrue(run('(and True True)'))
        self.assertFalse(run('(and True False)'))
        self.assertTrue(run('(or False True)'))
        self.assertFalse(run('(not True)'))

    def test_comparisons(self):
        self.assertTrue(run('(lt 1 2)'))
        self.assertTrue(run('(gt 2 1)'))
        self.assertTrue(run('(eq 1 1)'))
        self.assertTrue(run('(neq 1 2)'))

    def test_arithmetic(self):
        self.assertEqual(run('(add 1 2 3)'), 6)
        self.assertEqual(run('(sub 10 3)'), 7)
        self.assertEqual(run('(mul 2 3 4)'), 24)
        self.assertEqual(run('(div 10 2)'), 5)

    def test_list_ops(self):
        r = run('(nth (list 10 20 30) 1)')
        self.assertEqual(r, 20)
        r = run('(car (list 1 2 3))')
        self.assertEqual(r, 1)
        r = run('(cdr (list 1 2 3))')
        self.assertEqual(r, [2, 3])

    def test_dict_ops(self):
        r = run('(dict "a" 1 "b" 2)')
        self.assertEqual(r, {'a': 1, 'b': 2})
        r = run('(dict-get (dict "x" 10) "x")')
        self.assertEqual(r, 10)

    def test_if_cond(self):
        r = run('(if True 1 2)')
        self.assertEqual(r, 1)
        r = run('(if False 1 2)')
        self.assertEqual(r, 2)

    def test_lambda_call(self):
        r = run('((lambda (x) (add x 1)) 5)')
        self.assertEqual(r, 6)

    def test_format(self):
        r = run('(format "hello {}" "world")')
        self.assertEqual(r, 'hello world')

    def test_repeat(self):
        r = run('(repeat "ab" 3)')
        self.assertEqual(r, 'ababab')

    def test_to_string(self):
        r = run('(to-str 42)')
        self.assertEqual(r, '42')

    def test_contains(self):
        r = run('(contains (list 1 2 3) 2)')
        self.assertTrue(r)

    def test_hash(self):
        r = run('(hash "hello")')
        self.assertIsNotNone(r)
        self.assertIsInstance(r, (int, str))

    def test_uuid(self):
        r = run('(uuid)')
        self.assertIsNotNone(r)


class TestPreprocess(unittest.TestCase):
    def test_include(self):
        from preprocess import preprocess_includes

        code = '(include "nonexistent.san")\n(print "test")'
        result = preprocess_includes(code)
        self.assertIn('test', result)


class TestEvalUtils(unittest.TestCase):
    def test_is_truthy(self):
        from eval_utils import is_truthy

        self.assertTrue(is_truthy(True))
        self.assertTrue(is_truthy(1))
        self.assertFalse(is_truthy(False))
        self.assertFalse(is_truthy(None))
        self.assertFalse(is_truthy(0))

    def test_param_constraints(self):
        from eval_utils import check_param_constraints

        check_param_constraints('test', ['a'], [{'a': 1}])


if __name__ == '__main__':
    unittest.main()
