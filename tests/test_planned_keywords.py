"""规划关键字测试 — 置信度/清空/克隆/掩码/约束桩/别名"""

import unittest
from core.evaluator import SanyanEvaluator
from core.ternary_core import TritValue


class TestPlannedKeywords(unittest.TestCase):
    def setUp(self):
        self.e = SanyanEvaluator()

    def eval(self, code):
        return self.e.eval(['do'] + code if isinstance(code, list) else code)

    # ═══════════════════════════════════════════
    # 置信度 / 信度传播
    # ═══════════════════════════════════════════

    def test_confidence_trit(self):
        r = self.e.eval(['置信度', TritValue(1, confidence=0.85)])
        self.assertEqual(r, 0.85)

    def test_confidence_normal_value(self):
        r = self.e.eval(['置信度', 42])
        self.assertEqual(r, 1.0)

    def test_propagate_confidence(self):
        """信度传播(上游, 当前): 0.9 × 0.8 = 0.72"""
        up = TritValue(1, confidence=0.9)
        cur = TritValue(-1, confidence=0.8)
        r = self.e.eval(['信度传播', up, cur])
        self.assertIsInstance(r, TritValue)
        self.assertAlmostEqual(r.confidence, 0.72, places=5)

    def test_propagate_confidence_chain(self):
        """信度传播 链式调用"""
        up = TritValue(1, confidence=1.0)
        cur = TritValue(0, confidence=0.5)
        r = self.e.eval(['信度传播', up, cur])
        self.assertAlmostEqual(r.confidence, 0.5, places=5)

    # ═══════════════════════════════════════════
    # 清空
    # ═══════════════════════════════════════════

    def test_clear_list(self):
        lst = [1, 2, 3]
        self.e.eval(['清空', lst])
        self.assertEqual(len(lst), 0)

    def test_clear_dict(self):
        d = {'a': 1, 'b': 2}
        self.e.eval(['清空', d])
        self.assertEqual(len(d), 0)

    # ═══════════════════════════════════════════
    # 克隆
    # ═══════════════════════════════════════════

    def test_clone_trit(self):
        t = TritValue(42, confidence=0.7)
        r = self.e.eval(['克隆', t])
        self.assertIsInstance(r, TritValue)
        self.assertEqual(r.to_int(), 42)
        self.assertEqual(r.confidence, 0.7)
        # TritValue 有小整数缓存，小整数克隆可能返回同一实例

    def test_clone_list(self):
        lst = [1, 2, 3]
        r = self.e.eval(['克隆', lst])
        self.assertEqual(r, lst)
        self.assertIsNot(r, lst)

    def test_clone_dict(self):
        d = {'a': 1}
        r = self.e.eval(['克隆', d])
        self.assertEqual(r, d)
        self.assertIsNot(r, d)

    # ═══════════════════════════════════════════
    # 掩码
    # ═══════════════════════════════════════════

    def test_mask(self):
        r = self.e.eval(['掩码', 0xFF, 0x0F])
        self.assertEqual(r.to_int(), 0x0F)

    def test_mask_zero(self):
        r = self.e.eval(['掩码', 42, 0])
        self.assertEqual(r.to_int(), 0)

    # ═══════════════════════════════════════════
    # 别名：压入/弹出/休眠/竞速
    # ═══════════════════════════════════════════

    def test_push_alias(self):
        """压入 = ternary_stack_push"""
        self.e.eval(['设', 's', ['三态栈']])
        self.e.eval(['压入', 's', TritValue(1)])
        # peek should show 1
        r = self.e.eval(['三态查看栈', 's'])
        self.assertEqual(r.to_int(), 1)

    def test_pop_alias(self):
        """弹出 = ternary_stack_pop"""
        self.e.eval(['设', 's', ['三态栈']])
        self.e.eval(['压入', 's', TritValue(1)])
        self.e.eval(['压入', 's', TritValue(-1)])
        r = self.e.eval(['弹出', 's'])
        self.assertEqual(r.to_int(), -1)

    def test_race_alias(self):
        """竞速 = concurrent_race 别名"""
        # 只验证不抛异常
        self.e.eval(['竞速', 50, ['输出', 'hello']])

    # ═══════════════════════════════════════════
    # 约束/权限 桩
    # ═══════════════════════════════════════════

    def test_grant_always_true(self):
        r = self.e.eval(['许', 1])
        self.assertEqual(r.to_int(), 1)

    def test_allow_passthrough(self):
        """允许 是修饰子：透传 x 的实际判，不再把真/假压成可能（去有损语义）。"""
        self.assertEqual(self.e.eval(['允许', TritValue(1)]).to_int(), 1)
        self.assertEqual(self.e.eval(['允许', TritValue(-1)]).to_int(), -1)
        self.assertEqual(self.e.eval(['允许', TritValue(0)]).to_int(), 0)

    def test_deny_always_false(self):
        r = self.e.eval(['禁', 1])
        self.assertEqual(r.to_int(), -1)

    def test_restrict_in_whitelist(self):
        r = self.e.eval(['只许', 1, 1, 2, 3])
        self.assertEqual(r.to_int(), 1)

    def test_restrict_not_in_whitelist(self):
        r = self.e.eval(['只许', 4, 1, 2, 3])
        self.assertEqual(r.to_int(), -1)

    # ═══════════════════════════════════════════
    # 嵌入式 / 结构 桩（期望抛异常）
    # ═══════════════════════════════════════════

    def test_interrupt_stub(self):
        with self.assertRaises(Exception):
            self.e.eval(['中断', 'PA0', '上升', '占位'])

    def test_bind_stub(self):
        with self.assertRaises(Exception):
            self.e.eval(['绑定', 'PA0', '传感器状态'])

    def test_struct_stub(self):
        with self.assertRaises(Exception):
            self.e.eval(['结构', '传感器', ['值', '三态']])

    def test_instance_stub(self):
        with self.assertRaises(Exception):
            self.e.eval(['实例', '传感器', 0, 12345])

    def test_trait_stub(self):
        with self.assertRaises(Exception):
            self.e.eval(['特征', '可序列化'])

    # ═══════════════════════════════════════════
    # 读取 / 写入 / 行号
    # ═══════════════════════════════════════════

    def test_read_stream(self):
        r = self.e.eval(['read_stream', TritValue(1)])
        self.assertIsInstance(r, TritValue)
        self.assertEqual(r.confidence, 0.9)

    def test_line_number_stub(self):
        r = self.e.eval(['行号'])
        self.assertEqual(r.to_int(), -1)


if __name__ == '__main__':
    unittest.main()
