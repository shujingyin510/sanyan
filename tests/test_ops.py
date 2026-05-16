"""ops 模块单元测试：覆盖所有内置操作"""
import sys
import os
import contextlib
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
from ternary_core import TritValue, ArrayValue
from evaluator import SanyanEvaluator
from values import SanyanValueError, SanyanTypeError, SanyanSyntaxError, SanyanNameError


class TestArithmetic(unittest.TestCase):
    def setUp(self):
        self.env = SanyanEvaluator()

    def test_add(self):
        self.assertEqual(self.env.eval(['add', 3, 4]).to_int(), 7)
        self.assertEqual(self.env.eval(['add', -1, 1]).to_int(), 0)
        self.assertEqual(self.env.eval(['add', 0, 0]).to_int(), 0)

    def test_sub(self):
        self.assertEqual(self.env.eval(['sub', 10, 3]).to_int(), 7)
        self.assertEqual(self.env.eval(['sub', 0, 5]).to_int(), -5)

    def test_mul(self):
        self.assertEqual(self.env.eval(['mul', 3, 4]).to_int(), 12)
        self.assertEqual(self.env.eval(['mul', -2, 5]).to_int(), -10)
        self.assertEqual(self.env.eval(['mul', 7, 0]).to_int(), 0)

    def test_div(self):
        self.assertEqual(self.env.eval(['div', 10, 2]).to_int(), 5)
        with self.assertRaises(Exception):
            self.env.eval(['div', 1, 0])

    def test_mod(self):
        self.assertEqual(self.env.eval(['mod', 10, 3]).to_int(), 1)
        self.assertEqual(self.env.eval(['mod', 7, 4]).to_int(), 3)

    def test_pow(self):
        self.assertEqual(self.env.eval(['pow', 2, 3]).to_int(), 8)
        self.assertEqual(self.env.eval(['pow', 5, 0]).to_int(), 1)

    def test_float_arithmetic(self):
        result = self.env.eval(['add', 3.14, 2.0])
        self.assertAlmostEqual(result.to_float(), 5.14, places=2)
        result = self.env.eval(['sub', 3.14, 2.0])
        self.assertAlmostEqual(result.to_float(), 1.14, places=2)
        result = self.env.eval(['mul', 3.14, 2.0])
        self.assertAlmostEqual(result.to_float(), 6.28, places=2)
        result = self.env.eval(['div', 3.14, 2.0])
        self.assertAlmostEqual(result.to_float(), 1.57, places=2)

    def test_digit(self):
        self.assertEqual(self.env.eval(['digit', 1234, 2]).to_int(), 2)
        self.assertEqual(self.env.eval(['digit', 1234, 0]).to_int(), 4)


class TestComparison(unittest.TestCase):
    def setUp(self):
        self.env = SanyanEvaluator()

    def _v(self, ast):
        return self.env.eval(ast).to_int()

    def test_eq(self):
        self.assertEqual(self._v(['eq', 5, 5]), 1)
        self.assertEqual(self._v(['eq', 5, 6]), -1)

    def test_gt(self):
        self.assertEqual(self._v(['gt', 5, 3]), 1)
        self.assertEqual(self._v(['gt', 3, 5]), -1)

    def test_lt(self):
        self.assertEqual(self._v(['lt', 3, 5]), 1)
        self.assertEqual(self._v(['lt', 5, 3]), -1)

    def test_ne(self):
        self.assertEqual(self._v(['ne', 5, 6]), 1)
        self.assertEqual(self._v(['ne', 5, 5]), -1)

    def test_gte(self):
        self.assertEqual(self._v(['gte', 5, 5]), 1)
        self.assertEqual(self._v(['gte', 5, 3]), 1)
        self.assertEqual(self._v(['gte', 3, 5]), -1)

    def test_lte(self):
        self.assertEqual(self._v(['lte', 3, 5]), 1)
        self.assertEqual(self._v(['lte', 5, 5]), 1)
        self.assertEqual(self._v(['lte', 6, 5]), -1)

    def test_ngt(self):
        self.assertEqual(self._v(['ngt', 3, 5]), 1)
        self.assertEqual(self._v(['ngt', 5, 5]), 1)

    def test_nlt(self):
        self.assertEqual(self._v(['nlt', 5, 3]), 1)
        self.assertEqual(self._v(['nlt', 5, 5]), 1)


class TestLogic(unittest.TestCase):
    def setUp(self):
        self.env = SanyanEvaluator()

    def _v(self, ast):
        return self.env.eval(ast).to_int()

    def test_and(self):
        self.assertEqual(self._v(['and', 1, 1]), 1)
        self.assertEqual(self._v(['and', 1, -1]), -1)
        self.assertEqual(self._v(['and', 1, 0]), 0)

    def test_or(self):
        self.assertEqual(self._v(['or', 1, -1]), 1)
        self.assertEqual(self._v(['or', -1, 0]), 0)
        self.assertEqual(self._v(['or', -1, -1]), -1)

    def test_not(self):
        self.assertEqual(self._v(['not', 1]), -1)
        self.assertEqual(self._v(['not', -1]), 1)
        self.assertEqual(self._v(['not', 0]), 0)


class TestMathFunctions(unittest.TestCase):
    def setUp(self):
        self.env = SanyanEvaluator()

    def test_abs(self):
        self.assertEqual(self.env.eval(['abs', -5]).to_int(), 5)
        self.assertEqual(self.env.eval(['abs', 3]).to_int(), 3)

    def test_max_min(self):
        self.assertEqual(self.env.eval(['max', 3, 7, 5]).to_int(), 7)
        self.assertEqual(self.env.eval(['min', 3, 7, 5]).to_int(), 3)

    def test_sqrt(self):
        self.assertAlmostEqual(self.env.eval(['sqrt', 4.0]).to_float(), 2.0, places=1)

    def test_sin(self):
        val = self.env.eval(['sin', 0.0])
        self.assertAlmostEqual(val.to_float(), 0.0, places=2)

    def test_cos(self):
        val = self.env.eval(['cos', 0.0])
        self.assertAlmostEqual(val.to_float(), 1.0, places=2)

    def test_floor_ceil_round(self):
        self.assertEqual(self.env.eval(['floor', 3.7]).to_int(), 3)
        self.assertEqual(self.env.eval(['ceil', 3.2]).to_int(), 4)
        self.assertEqual(self.env.eval(['round', 3.5]).to_int(), 4)

    def test_ternary_parse(self):
        result = self.env.eval(['ternary', '+-0'])
        self.assertEqual(result.to_int(), 6)


class TestStringOps(unittest.TestCase):
    def setUp(self):
        self.env = SanyanEvaluator()

    def test_concat(self):
        result = self.env.eval(['concat', '"hello"', '" "', '"world"'])
        self.assertEqual(result, 'hello world')

    def test_length(self):
        result = self.env.eval(['length', '"hello"'])
        self.assertEqual(result.to_int(), 5)

    def test_substring(self):
        result = self.env.eval(['substring', '"hello"', 1, 3])
        self.assertEqual(result, 'ell')

    def test_replace(self):
        result = self.env.eval(['replace', '"hello world"', '"world"', '"there"'])
        self.assertEqual(result, 'hello there')

    def test_split(self):
        result = self.env.eval(['split', '"a,b,c"', '","'])
        self.assertEqual(result, ['a', 'b', 'c'])

    def test_find(self):
        result = self.env.eval(['find', '"hello"', '"ell"'])
        self.assertEqual(result.to_int(), 1)
        result = self.env.eval(['find', '"hello"', '"xyz"'])
        self.assertEqual(result.to_int(), -1)

    def test_trim(self):
        result = self.env.eval(['trim', '"  hello  "'])
        self.assertEqual(result, 'hello')

    def test_upper_lower(self):
        result = self.env.eval(['upper', '"Hello"'])
        self.assertEqual(result, 'HELLO')
        result = self.env.eval(['lower', '"Hello"'])
        self.assertEqual(result, 'hello')

    def test_startswith_endswith(self):
        result = self.env.eval(['startswith', '"hello"', '"he"'])
        self.assertEqual(result.to_int(), 1)
        result = self.env.eval(['startswith', '"hello"', '"xyz"'])
        self.assertEqual(result.to_int(), -1)
        result = self.env.eval(['endswith', '"hello"', '"lo"'])
        self.assertEqual(result.to_int(), 1)


class TestContainerOps(unittest.TestCase):
    def setUp(self):
        self.env = SanyanEvaluator()

    def test_list_new(self):
        result = self.env.eval(['list', 1, 2, 3])
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0].to_int(), 1)

    def test_list_len(self):
        self.env.eval(['set', 'lst', ['list', 1, 2, 3]])
        result = self.env.eval(['list_len', 'lst'])
        self.assertEqual(result.to_int(), 3)

    def test_array_new(self):
        result = self.env.eval(['array', 5, 0])
        self.assertIsInstance(result, ArrayValue)
        self.assertEqual(result.length, 5)

    def test_dict_new(self):
        result = self.env.eval(['dict', '"a"', 1, '"b"', 2])
        self.assertEqual(result, {'a': TritValue(1), 'b': TritValue(2)})

    def test_get_key(self):
        self.env.eval(['set', 'd', ['dict', '"a"', 1]])
        result = self.env.eval(['get_key', 'd', '"a"'])
        self.assertEqual(result.to_int(), 1)

    def test_set_key(self):
        self.env.eval(['set', 'd', ['dict', '"a"', 1]])
        self.env.eval(['set_key', 'd', '"b"', 2])
        result = self.env.eval(['get_key', 'd', '"b"'])
        self.assertEqual(result.to_int(), 2)

    def test_get_element(self):
        self.env.eval(['set', 'lst', ['list', 10, 20, 30]])
        result = self.env.eval(['get', 'lst', 2])
        self.assertEqual(result.to_int(), 30)

    def test_contains(self):
        self.env.eval(['set', 'lst', ['list', 1, 2, 3]])
        result = self.env.eval(['contains', 'lst', 2])
        self.assertEqual(result.to_int(), 1)
        result = self.env.eval(['contains', 'lst', 99])
        self.assertEqual(result.to_int(), -1)

    def test_sort_reverse(self):
        self.env.eval(['set', 'lst', ['list', 3, 1, 2]])
        result = self.env.eval(['sort', 'lst'])
        self.assertEqual([x.to_int() for x in result], [1, 2, 3])
        result = self.env.eval(['reverse', 'lst'])
        self.assertEqual([x.to_int() for x in result], [2, 1, 3])

    def test_slice(self):
        self.env.eval(['set', 'lst', ['list', 1, 2, 3, 4, 5]])
        result = self.env.eval(['slice', 'lst', 1, 4])
        self.assertEqual([x.to_int() for x in result], [2, 3, 4])

    def test_sum(self):
        self.env.eval(['set', 'lst', ['list', 1, 2, 3]])
        result = self.env.eval(['sum', 'lst'])
        self.assertEqual(result.to_int(), 6)

    def test_join(self):
        self.env.eval(['set', 'lst', ['list', 1, 2, 3]])
        result = self.env.eval(['join', 'lst', '","'])
        self.assertEqual(result, '1,2,3')

    def test_count(self):
        self.env.eval(['set', 'lst', ['list', 1, 2, 2, 3, 2]])
        result = self.env.eval(['count', 'lst', 2])
        self.assertEqual(result.to_int(), 3)

    def test_unique(self):
        self.env.eval(['set', 'lst', ['list', 1, 2, 2, 3]])
        result = self.env.eval(['unique', 'lst'])
        self.assertEqual([x.to_int() for x in result], [1, 2, 3])


class TestJsonOps(unittest.TestCase):
    def setUp(self):
        self.env = SanyanEvaluator()

    def test_to_json(self):
        self.env.eval(['set', 'd', ['dict', '"name"', '"Alice"', '"score"', 95]])
        result = self.env.eval(['to_json', 'd'])
        self.assertIn('"name"', result)
        self.assertIn('"Alice"', result)
        self.assertIn('95', result)

    def test_from_json(self):
        result = self.env.eval(['from_json', '{"name": "Bob", "age": 30}'])
        self.assertIsInstance(result, dict)
        self.assertEqual(result['name'], 'Bob')
        self.assertEqual(result['age'].to_int(), 30)


class TestTypeOps(unittest.TestCase):
    def setUp(self):
        self.env = SanyanEvaluator()

    def test_is_number(self):
        self.assertEqual(self.env.eval(['is_number', 42]).to_int(), 1)
        self.assertEqual(self.env.eval(['is_number', '"str"']).to_int(), -1)

    def test_is_string(self):
        self.assertEqual(self.env.eval(['is_string', '"hello"']).to_int(), 1)
        self.assertEqual(self.env.eval(['is_string', 123]).to_int(), -1)


class TestControlFlow(unittest.TestCase):
    def setUp(self):
        self.env = SanyanEvaluator()

    def test_if_true(self):
        self.env.eval(['if', 1, ['do', ['set', 'x', 42]], ['do', ['set', 'x', 0]]])
        self.assertEqual(self.env.get_var('x').to_int(), 42)

    def test_if_false(self):
        self.env.eval(['if', -1, ['do', ['set', 'x', 42]], ['do', ['set', 'x', 0]]])
        self.assertEqual(self.env.get_var('x').to_int(), 0)

    def test_if_maybe(self):
        self.env.eval(['if', 0, ['do', ['set', 'x', 42]], ['do', ['set', 'x', 99]]])
        self.assertEqual(self.env.get_var('x').to_int(), 99)

    def test_do(self):
        self.env.eval(['do', ['set', 'a', 10], ['set', 'b', 20]])
        self.assertEqual(self.env.get_var('a').to_int(), 10)
        self.assertEqual(self.env.get_var('b').to_int(), 20)

    def test_loop(self):
        self.env.eval(['set', 'i', 0])
        self.env.eval(['loop', ['lt', 'i', 5], ['set', 'i', ['add', 'i', 1]]])
        self.assertEqual(self.env.get_var('i').to_int(), 5)

    def test_for(self):
        self.env.eval(['for', 'i', 1, 3, ['do', ['set', 'x', 'i']]])
        self.assertEqual(self.env.get_var('x').to_int(), 3)

    def test_judge(self):
        self.env.eval(['judge', 1, ['do', ['set', 'v', 100]], ['do', ['set', 'v', 0]], ['do', ['set', 'v', -1]]])
        self.assertEqual(self.env.get_var('v').to_int(), 100)
        self.env.eval(['judge', 0, ['do', ['set', 'v', 100]], ['do', ['set', 'v', 0]], ['do', ['set', 'v', -1]]])
        self.assertEqual(self.env.get_var('v').to_int(), 0)
        self.env.eval(['judge', -1, ['do', ['set', 'v', 100]], ['do', ['set', 'v', 0]], ['do', ['set', 'v', -1]]])
        self.assertEqual(self.env.get_var('v').to_int(), -1)

    def test_try_catch(self):
        self.env.eval(['try', ['div', 1, 0], ['catch', 'e', ['set', 'caught', 1]]])
        self.assertEqual(self.env.get_var('caught').to_int(), 1)


class TestLambda(unittest.TestCase):
    def setUp(self):
        self.env = SanyanEvaluator()

    def test_lambda_call(self):
        self.env.eval(['set', 'double', ['lambda', ['x'], ['mul', 'x', 2]]])
        result = self.env.eval(['double', 5])
        self.assertEqual(result.to_int(), 10)

    def test_map(self):
        self.env.eval(['set', 'double', ['lambda', ['x'], ['mul', 'x', 2]]])
        self.env.eval(['set', 'lst', ['list', 1, 2, 3]])
        result = self.env.eval(['map', 'double', 'lst'])
        self.assertEqual([x.to_int() for x in result], [2, 4, 6])

    def test_filter(self):
        self.env.eval(['set', 'gt2', ['lambda', ['x'], ['gt', 'x', 2]]])
        self.env.eval(['set', 'lst', ['list', 1, 2, 3, 4]])
        result = self.env.eval(['filter', 'gt2', 'lst'])
        self.assertEqual([x.to_int() for x in result], [3, 4])

    def test_reduce(self):
        self.env.eval(['set', 'add', ['lambda', ['a', 'b'], ['add', 'a', 'b']]])
        self.env.eval(['set', 'lst', ['list', 1, 2, 3]])
        result = self.env.eval(['reduce', 'add', 'lst', 0])
        self.assertEqual(result.to_int(), 6)


class TestFileOps(unittest.TestCase):
    def setUp(self):
        self.env = SanyanEvaluator()
        self.tmp_path = '_test_tmp.txt'

    def tearDown(self):
        if os.path.exists(self.tmp_path):
            os.remove(self.tmp_path)

    def test_write_read_file(self):
        self.env.eval(['write_file', '"_test_tmp.txt"', '"hello world"'])
        result = self.env.eval(['read_file', '"_test_tmp.txt"'])
        self.assertEqual(result, 'hello world')


class TestNegativeCases(unittest.TestCase):
    """负面测试：错误路径和边界条件"""
    def setUp(self):
        self.env = SanyanEvaluator()

    def test_div_by_zero(self):
        with self.assertRaises(SanyanValueError):
            self.env.eval(['div', 1, 0])

    def test_type_error_list(self):
        with self.assertRaises(SanyanTypeError):
            self.env.eval(['list_len', '"not_a_list"'])

    def test_syntax_error_wrong_arg_count(self):
        with self.assertRaises(SanyanSyntaxError):
            self.env.eval(['sub'])

    def test_name_error(self):
        with contextlib.redirect_stdout(None):
            with self.assertRaises(SanyanNameError):
                self.env.eval(['undefined_symbol'])

    def test_empty_list_concat(self):
        result = self.env.eval(['list_concat', ['list'], ['list']])
        self.assertEqual(result, [])

    def test_string_find_not_found(self):
        result = self.env.eval(['find', '"hello"', '"xyz"'])
        self.assertEqual(result.to_int(), -1)

    def test_string_startswith_false(self):
        result = self.env.eval(['startswith', '"hello"', '"xyz"'])
        self.assertEqual(result.to_int(), -1)

    def test_contains_negative(self):
        self.env.eval(['set', 'lst', ['list', 1, 2, 3]])
        result = self.env.eval(['contains', 'lst', 99])
        self.assertEqual(result.to_int(), -1)

    def test_mixed_type_contains(self):
        self.env.eval(['set', 'lst', ['list', 1, '"hello"', 3]])
        result = self.env.eval(['contains', 'lst', '"hello"'])
        self.assertEqual(result.to_int(), 1)

    def test_get_out_of_range(self):
        self.env.eval(['set', 'lst', ['list', 1, 2]])
        with self.assertRaises(SanyanValueError):
            self.env.eval(['get', 'lst', 99])

    def test_dict_contains_missing(self):
        self.env.eval(['set', 'd', ['dict', '"a"', 1]])
        result = self.env.eval(['dict_contains', 'd', '"b"'])
        self.assertEqual(result.to_int(), -1)

    def test_abs_negative(self):
        result = self.env.eval(['abs', -5])
        self.assertEqual(result.to_int(), 5)


if __name__ == '__main__':
    unittest.main()
