"""若(可能) 关卡（D8）：可能作为确定性条件 → 收集诊断，运行时不变。

D8：这道关卡是给「可能」发通行证的检查站——`允许(x)` 与帧级 `允许 可能` 在此豁免。
关卡 collect-only；**不改运行时**（可能仍按假 fall-through）。
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

    # ── 允许 豁免（元通道 + 帧级）──

    def test_allow_expression_skips_diagnostic(self):
        """允许(可能) 打 tolerated 标 → 若 不收集诊断，运行时仍走假分支。"""
        e, r = _run(['若', ['允许', TritValue(0)], '"真分支"', '"假分支"'])
        self.assertEqual(self._diag(e), [])
        self.assertEqual(r, '假分支')

    def test_allow_expression_keeps_truth(self):
        """允许 是 annotate：不改真假，真/假打标后仍真/假。"""
        _, r2 = _run(['允许', TritValue(1)])
        self.assertEqual(r2.to_int(), 1)
        self.assertTrue(r2.tolerated)
        _, r3 = _run(['允许', TritValue(-1)])
        self.assertEqual(r3.to_int(), -1)
        self.assertTrue(r3.tolerated)

    def test_allow_expression_sets_tolerated_flag(self):
        _, r = _run(['允许', TritValue(0)])
        self.assertTrue(r.tolerated)
        self.assertTrue(r.is_maybe())

    def test_bare_maybe_not_tolerated(self):
        _, r = _run(TritValue(0))
        # 共享单例/未打标 → tolerated 默认 False
        self.assertFalse(getattr(r, 'tolerated', False))

    def test_constraint_allow_maybe_frame_skips_diagnostic(self):
        """约束{允许 可能} 块内 若(可能) 关卡豁免。"""
        e = SanyanEvaluator()
        body = ['任务', '"t"', ['约束', ['允许', '可能']], ['若', TritValue(0), '"真"', '"假"']]
        r = e.eval(body)
        self.assertEqual(r, '假')
        self.assertEqual(e.eval(['诊断']), [])

    def test_constraint_without_allow_still_collects(self):
        e = SanyanEvaluator()
        body = ['任务', '"t"', ['约束'], ['若', TritValue(0), '"真"', '"假"']]
        e.eval(body)
        self.assertEqual(len(e.eval(['诊断'])), 1)

    def test_constraint_allow_rejects_non_maybe(self):
        from core.values import SanyanValueError

        e = SanyanEvaluator()
        with self.assertRaises(SanyanValueError):
            e.eval(['任务', '"t"', ['约束', ['允许', '网']], TritValue(1)])

    def test_nested_frame_inherits_tolerate(self):
        """父帧 允许 可能 → 子帧继承（正交轴可继承）。"""
        e = SanyanEvaluator()
        # 外层 允许 可能；内层空约束（能力收紧但容忍继承）
        inner = ['任务', '"in"', ['约束'], ['若', TritValue(0), '"真"', '"假"']]
        outer = ['任务', '"out"', ['约束', ['允许', '可能']], inner]
        r = e.eval(outer)
        self.assertEqual(r, '假')
        self.assertEqual(e.eval(['诊断']), [])

    def test_child_can_open_tolerate_without_parent(self):
        """父帧不允许可能时，子帧可自开 允许 可能。"""
        e = SanyanEvaluator()
        inner = ['任务', '"in"', ['约束', ['允许', '可能']], ['若', TritValue(0), '"真"', '"假"']]
        outer = ['任务', '"out"', ['约束'], inner]
        e.eval(outer)
        self.assertEqual(e.eval(['诊断']), [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
