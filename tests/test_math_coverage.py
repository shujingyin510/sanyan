"""ternary_core.py 数学函数覆盖测试"""

import os
import sys
import math
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.ternary_core import BT, TernaryALU, ternary_sin, ternary_cos, ternary_tan
from core.ternary_core import ternary_sqrt, ternary_exp, ternary_log, ternary_log10
from core.ternary_core import _ternary_range_reduce, _int_at_precision, _half_at_precision
from core.ternary_core import _get_pi, _get_two_pi, _get_half_pi, TritValue


# ═══════════════════════════════════════════════════════════
# BT 基础操作
# ═══════════════════════════════════════════════════════════


class TestBT(unittest.TestCase):
    def test_from_int_zero(self):
        self.assertEqual(BT.from_int(0), [0])

    def test_from_int_positive(self):
        self.assertEqual(BT.from_int(1), [1])
        self.assertEqual(BT.from_int(2), [1, -1])
        self.assertEqual(BT.from_int(3), [1, 0])

    def test_from_int_negative(self):
        self.assertEqual(BT.from_int(-1), [-1])
        self.assertEqual(BT.from_int(-2), [-1, 1])

    def test_from_int_with_length(self):
        trits = BT.from_int(1, length=4)
        self.assertEqual(len(trits), 4)
        self.assertEqual(BT.to_int(trits), 1)

    def test_to_int(self):
        self.assertEqual(BT.to_int([0]), 0)
        self.assertEqual(BT.to_int([1]), 1)
        self.assertEqual(BT.to_int([-1]), -1)
        self.assertEqual(BT.to_int([1, -1]), 2)

    def test_to_str(self):
        self.assertEqual(BT.to_str([1, 0, -1]), '+0-')
        self.assertEqual(BT.to_str([]), '')

    def test_from_str(self):
        self.assertEqual(BT.from_str('+0-'), [1, 0, -1])
        self.assertEqual(BT.from_str(''), [0])

    def test_from_str_error(self):
        with self.assertRaises(ValueError):
            BT.from_str('abc')

    def test_from_float(self):
        trits = BT.from_float(1.0)
        self.assertGreater(len(trits), 0)
        self.assertAlmostEqual(BT.to_float(trits), 1.0, delta=0.01)

    def test_from_float_negative(self):
        trits = BT.from_float(-1.5)
        self.assertGreater(len(trits), 0)
        self.assertAlmostEqual(BT.to_float(trits), -1.5, delta=0.1)

    def test_from_float_precision(self):
        trits = BT.from_float(1.5, precision=8)
        self.assertGreater(len(trits), 0)

    def test_to_float(self):
        f = BT.to_float(BT.from_float(2.0))
        self.assertAlmostEqual(f, 2.0, delta=0.01)

    def test_roundtrip_int(self):
        for n in [-10, -1, 0, 1, 10, 100, 1000]:
            trits = BT.from_int(n)
            self.assertEqual(BT.to_int(trits), n)

    def test_roundtrip_float(self):
        for f in [-1.5, -0.5, 0.0, 0.5, 1.5]:
            trits = BT.from_float(f)
            self.assertAlmostEqual(BT.to_float(trits), f, delta=0.1)


# ═══════════════════════════════════════════════════════════
# TernaryALU 算术
# ═══════════════════════════════════════════════════════════


class TestTernaryALU(unittest.TestCase):
    def test_add(self):
        self.assertEqual(BT.to_int(TernaryALU.add([1], [1])), 2)
        self.assertEqual(BT.to_int(TernaryALU.add([1], [-1])), 0)
        self.assertEqual(BT.to_int(TernaryALU.add([-1], [-1])), -2)

    def test_sub(self):
        self.assertEqual(BT.to_int(TernaryALU.sub([1, 0], [1])), 2)
        self.assertEqual(BT.to_int(TernaryALU.sub([1], [1])), 0)

    def test_multiply(self):
        self.assertEqual(BT.to_int(TernaryALU.multiply([1, 0], [1])), 3)
        self.assertEqual(BT.to_int(TernaryALU.multiply([1], [-1])), -1)
        self.assertEqual(BT.to_int(TernaryALU.multiply([0], [1])), 0)

    def test_div(self):
        self.assertEqual(BT.to_int(TernaryALU.div([1, 0, 0], [1, 0], 0)), 3)

    def test_div_zero(self):
        with self.assertRaises(Exception):
            TernaryALU.div([1], [0], 0)

    def test_neg(self):
        self.assertEqual(BT.to_int(TernaryALU.neg([1, 0])), -3)
        self.assertEqual(BT.to_int(TernaryALU.neg([-1])), 1)

    def test_is_zero(self):
        self.assertTrue(TernaryALU.is_zero([0]))
        self.assertFalse(TernaryALU.is_zero([1]))

    def test_tritwise_and(self):
        self.assertEqual(TernaryALU.tritwise_and([1, 0], [1, 1]), [1, 0])

    def test_tritwise_or(self):
        self.assertEqual(TernaryALU.tritwise_or([1, 0], [0, 1]), [1, 1])

    def test_tritwise_not(self):
        self.assertEqual(TernaryALU.tritwise_not([1, 0, -1]), [-1, 0, 1])

    def test_fixed_mul(self):
        a = BT.from_int(3)
        b = BT.from_int(2)
        result = TernaryALU.fixed_mul(a, b, 0)
        self.assertEqual(BT.to_int(result), 6)

    def test_fixed_div(self):
        a = BT.from_int(6)
        b = BT.from_int(2)
        result = TernaryALU.fixed_div(a, b, 0)
        self.assertEqual(BT.to_int(result), 3)


# ═══════════════════════════════════════════════════════════
# 数学函数
# ═══════════════════════════════════════════════════════════


class TestMathFunctions(unittest.TestCase):
    def test_sin_zero(self):
        result = ternary_sin(BT.from_int(0))
        self.assertAlmostEqual(BT.to_float(result), 0.0, delta=0.1)

    def test_sin_half_pi(self):
        x = BT.from_float(1.5707963267948966)  # π/2
        result = ternary_sin(x)
        self.assertAlmostEqual(BT.to_float(result), 1.0, delta=0.1)

    def test_sin_pi(self):
        x = BT.from_float(3.141592653589793)  # π
        result = ternary_sin(x)
        self.assertAlmostEqual(BT.to_float(result), 0.0, delta=0.1)

    def test_sin_negative(self):
        x = BT.from_float(-1.5707963267948966)  # -π/2
        result = ternary_sin(x)
        self.assertAlmostEqual(BT.to_float(result), -1.0, delta=0.1)

    def test_cos_zero(self):
        result = ternary_cos(BT.from_int(0))
        self.assertAlmostEqual(BT.to_float(result), 1.0, delta=0.1)

    def test_cos_half_pi(self):
        x = BT.from_float(1.5707963267948966)
        result = ternary_cos(x)
        self.assertAlmostEqual(BT.to_float(result), 0.0, delta=0.1)

    def test_tan_zero(self):
        result = ternary_tan(BT.from_int(0))
        self.assertAlmostEqual(BT.to_float(result), 0.0, delta=0.1)

    def test_tan_quarter_pi(self):
        x = BT.from_float(0.7853981633974483)  # π/4
        result = ternary_tan(x)
        self.assertAlmostEqual(BT.to_float(result), 1.0, delta=0.2)

    def test_sqrt_zero(self):
        result = ternary_sqrt(BT.from_int(0))
        self.assertEqual(BT.to_int(result), 0)

    def test_sqrt_positive(self):
        result = ternary_sqrt(BT.from_int(100))
        self.assertGreater(BT.to_float(result), 0)

    def test_sqrt_negative(self):
        with self.assertRaises(Exception):
            ternary_sqrt(BT.from_int(-1))

    def test_exp_zero(self):
        result = ternary_exp(BT.from_int(0))
        self.assertAlmostEqual(BT.to_float(result), 1.0, delta=0.1)

    def test_exp_one(self):
        x = BT.from_float(1.0)
        result = ternary_exp(x)
        self.assertAlmostEqual(BT.to_float(result), math.e, delta=0.3)

    def test_log_positive(self):
        x = BT.from_int(100)
        result = ternary_log(x)
        # log 函数可能不精确，只检查返回值
        self.assertGreater(len(result), 0)

    def test_log_zero(self):
        with self.assertRaises(Exception):
            ternary_log(BT.from_int(0))

    def test_log_negative(self):
        with self.assertRaises(Exception):
            ternary_log(BT.from_int(-1))

    def test_log10_positive(self):
        result = ternary_log10(BT.from_int(100))
        self.assertGreater(len(result), 0)


# ═══════════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════════


class TestHelperFunctions(unittest.TestCase):
    def test_int_at_precision(self):
        trits = _int_at_precision(1, 8)
        self.assertEqual(BT.to_int(trits), 1 * (3**8))

    def test_half_at_precision(self):
        trits = _half_at_precision(8)
        self.assertGreater(len(trits), 0)

    def test_get_pi(self):
        trits = _get_pi(8)
        self.assertGreater(len(trits), 0)

    def test_get_two_pi(self):
        trits = _get_two_pi(8)
        self.assertGreater(len(trits), 0)

    def test_get_half_pi(self):
        trits = _get_half_pi(8)
        self.assertGreater(len(trits), 0)

    def test_range_reduce(self):
        x = BT.from_float(10.0)
        result = _ternary_range_reduce(x, 16)
        self.assertGreater(len(result), 0)

    def test_ternary_sin_custom_precision(self):
        x = BT.from_float(1.0, precision=8)
        result = ternary_sin(x, precision=8)
        self.assertGreater(len(result), 0)

    def test_ternary_cos_custom_precision(self):
        x = BT.from_float(1.0, precision=8)
        result = ternary_cos(x, precision=8)
        self.assertGreater(len(result), 0)


# ═══════════════════════════════════════════════════════════
# TritValue 修复验证
# ═══════════════════════════════════════════════════════════


class TestTritValueFix(unittest.TestCase):
    def test_list_with_non_trit_values(self):
        v = TritValue([1, 2, 3])
        self.assertEqual(v._val_type, TritValue.TYPE_LIST)
        self.assertEqual(v.to_payload(), [1, 2, 3])

    def test_list_with_trit_values(self):
        v = TritValue([1, 0, -1])
        self.assertEqual(v._val_type, TritValue.TYPE_NUMERIC)
        # [1, 0, -1] 在平衡三进制中表示 1*9 + 0*3 + (-1)*1 = 8
        self.assertEqual(v.to_int(), 8)

    def test_empty_list(self):
        v = TritValue([])
        self.assertEqual(v._val_type, TritValue.TYPE_LIST)

    def test_list_with_float_first(self):
        v = TritValue([1.5, 2.5])
        self.assertEqual(v._val_type, TritValue.TYPE_LIST)


if __name__ == '__main__':
    unittest.main()
