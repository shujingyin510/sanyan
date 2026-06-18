"""覆盖补全第八轮：values/evaluator/ops 边界"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from evaluator import SanyanEvaluator
from eval_utils import unwrap_trit
from lexer import tokenize
from parser import parse


def run(code):
    t = tokenize(code)
    if not t:
        return None
    a = parse(t)
    if not a:
        return None
    result = SanyanEvaluator(max_loop_steps=500).eval(a)
    return unwrap_trit(result) if result is not None else None


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
        r = run('((lambda (x) (add x 1)) 5)')
        self.assertIsNotNone(r)

    def test_ternary_ops(self):
        from ternary_core import TritValue

        t = TritValue(1)
        self.assertEqual(t.symbol, '+')
        t2 = TritValue(-1)
        self.assertEqual(t2.symbol, '-')
        t3 = TritValue(0)
        self.assertEqual(t3.symbol, '0')

    def test_ternary_confidence(self):
        from ternary_core import TritValue

        t = TritValue(1, confidence=0.8)
        self.assertEqual(t.confidence, 0.8)
        self.assertEqual(t.symbol, '+')

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
    def test_trit_value(self):
        from ternary_core import TritValue

        a = TritValue(3)
        self.assertEqual(a.value, [1, 0])
        b = TritValue(2)
        self.assertEqual(b.value, [1, -1])

    def test_trit_compare(self):
        from ternary_core import TritValue

        a = TritValue(3)
        b = TritValue(3)
        self.assertTrue(a == b)
        c = TritValue(2)
        self.assertFalse(a == c)


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
        self.assertIsInstance(r, str)
        self.assertTrue(r.startswith('e'))

    def test_find(self):
        r = run('(find "hello" "ll")')
        self.assertEqual(r, 2)

    def test_print(self):
        run('(print "test output")')

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
        self.assertIsInstance(r, (int, float))

    def test_round(self):
        r = run('(round 3.14159)')
        self.assertIsInstance(r, (int, float))

    def test_random(self):
        r = run('(random 1 100)')
        self.assertTrue(1 <= r <= 100)

    def test_randint(self):
        r = run('(randint 1 100)')
        self.assertIsInstance(r, int)

    def test_type_predicates(self):
        self.assertEqual(run('(is_number 42)'), 1)
        self.assertEqual(run('(is_string "hello")'), 1)
        self.assertEqual(run('(is_list (list 1 2))'), 1)

    def test_and_or_not(self):
        self.assertEqual(run('(and 1 1)'), 1)
        self.assertEqual(run('(and 1 0)'), 0)
        self.assertEqual(run('(or 0 1)'), 1)
        self.assertEqual(run('(not 0)'), 0)

    def test_and_or_not_chinese(self):
        self.assertEqual(run('(and 真 真)'), 1)
        self.assertEqual(run('(and 真 假)'), -1)
        self.assertEqual(run('(or 假 真)'), 1)
        self.assertEqual(run('(not 假)'), 1)

    def test_comparisons(self):
        self.assertEqual(run('(lt 1 2)'), 1)
        self.assertEqual(run('(gt 2 1)'), 1)
        self.assertEqual(run('(eq 1 1)'), 1)
        self.assertEqual(run('(ne 1 2)'), 1)
        self.assertEqual(run('(gte 2 2)'), 1)
        self.assertEqual(run('(lte 1 2)'), 1)

    def test_arithmetic(self):
        self.assertEqual(run('(add 1 2 3)'), 6)
        self.assertEqual(run('(sub 10 3)'), 7)
        self.assertEqual(run('(mul 2 3 4)'), 24)
        self.assertEqual(run('(div 10 2)'), 5)

    def test_list_ops(self):
        r = run('(选取 (list 10 20 30) 1)')
        self.assertIn(r, [10, 20, 30])
        r = run('(length (list 1 2 3))')
        self.assertEqual(r, 3)

    def test_dict_ops(self):
        r = run('(dict "a" 1 "b" 2)')
        self.assertIsInstance(r, dict)
        self.assertEqual(set(r.keys()), {'a', 'b'})
        r = run('(get (dict "x" 10) "x")')
        self.assertEqual(r, 10)

    def test_if_cond(self):
        r = run('(if 真 1 2)')
        self.assertEqual(r, 1)
        r = run('(if 假 1 2)')
        self.assertEqual(r, 2)

    def test_lambda_call(self):
        r = run('((lambda (x) (add x 1)) 5)')
        self.assertIsNotNone(r)

    def test_to_string(self):
        r = run('(to_string 42)')
        self.assertEqual(r, '42')

    def test_contains(self):
        r = run('(contains (list 1 2 3) 2)')
        self.assertTrue(r)

    def test_str_contains(self):
        r = run('(str_contains "hello" "ll")')
        self.assertEqual(r, 1)

    def test_hash(self):
        r = run('(md5_hash "hello")')
        self.assertIsNotNone(r)
        self.assertIsInstance(r, str)
        r = run('(sha256_hash "hello")')
        self.assertIsNotNone(r)
        self.assertIsInstance(r, str)

    def test_format_time(self):
        r = run('(format_time)')
        self.assertIsNotNone(r)
        self.assertIsInstance(r, str)


class TestPreprocess(unittest.TestCase):
    def test_include(self):
        from preprocess import preprocess_includes

        code = '(include "nonexistent.san")\n(print "test")'
        result = preprocess_includes(code)
        self.assertIn('test', result)


if __name__ == '__main__':
    unittest.main()
