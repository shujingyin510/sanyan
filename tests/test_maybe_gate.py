"""若(可能) 关卡（D8）：可能作为确定性条件 → 收集诊断，运行时不变。

D8：这道关卡是给「可能」发通行证的检查站——`允许(x)` 未来在此豁免。
本刀只立关卡（收集 + `诊断()` 可见），**不改运行时**（可能仍按假 fall-through）。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.evaluator import SanyanEvaluator
from core.ternary_core import TritValue


def _run(ast):
    e = SanyanEvaluator()
    r = e.eval(ast)
    return e, r


class TestMaybeGate(unittest.TestCase):
    def _diag(self, e):
        return e.eval(['诊断'])

    # ── 收集 ──

    def test_maybe_condition_collects(self):
        e, _ = _run(['若', TritValue(0), '"真分支"', '"假分支"'])
        self.assertEqual(len(self._diag(e)), 1)
        self.assertIn('可能', self._diag(e)[0])

    def test_true_condition_no_warning(self):
        e, _ = _run(['若', TritValue(1), '"a"', '"b"'])
        self.assertEqual(self._diag(e), [])

    def test_false_condition_no_warning(self):
        e, _ = _run(['若', TritValue(-1), '"a"', '"b"'])
        self.assertEqual(self._diag(e), [])

    def test_multiple_maybe_accumulate(self):
        e, _ = _run(['做', ['若', TritValue(0), '"x"'], ['若', TritValue(0), '"y"']])
        self.assertEqual(len(self._diag(e)), 2)

    def test_float_zero_not_flagged(self):
        # 浮点 0.0 不是 trit「可能」——is_float 守卫应排除，不误报
        e, _ = _run(['若', TritValue(0.0), '"a"', '"b"'])
        self.assertEqual(self._diag(e), [])

    # ── 运行时不变（关键：这一刀不改行为）──

    def test_runtime_unchanged_maybe_falls_through(self):
        _, r = _run(['若', TritValue(0), '"真分支"', '"假分支"'])
        self.assertEqual(r, '假分支')  # 可能 → 假分支，与改动前一致

    def test_runtime_unchanged_true_takes_true(self):
        _, r = _run(['若', TritValue(1), '"真分支"', '"假分支"'])
        self.assertEqual(r, '真分支')

    def test_no_else_maybe_returns_zero(self):
        e, r = _run(['若', TritValue(0), '"仅真分支"'])
        self.assertEqual(r.to_int(), 0)
        self.assertEqual(len(self._diag(e)), 1)

    # ── 诊断算子 ──

    def test_diagnostics_returns_list(self):
        e, _ = _run(['若', TritValue(1), '"a"', '"b"'])
        self.assertIsInstance(self._diag(e), list)


if __name__ == '__main__':
    unittest.main(verbosity=2)
