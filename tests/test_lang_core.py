"""编程语言核心全量测试：覆盖 ternary_util_ops / ternary_generic_ops / data_pipeline_ops / ternary_source_ops"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.evaluator import SanyanEvaluator
from core.ternary_core import TritValue


def ev(expr):
    """快捷求值"""
    e = SanyanEvaluator()
    return e.eval(expr)


def ev_with(var_name, var_val, expr):
    """带变量求值"""
    e = SanyanEvaluator()
    e.set_var(var_name, var_val)
    return e.eval(expr)


# ═══════════════════════════════════════════════════════════
# ternary_util_ops.py (20% → 目标 90%+)
# ═══════════════════════════════════════════════════════════


class TestTritShift(unittest.TestCase):
    """三态移位"""

    def test_shift_zero(self):
        r = ev(['trit_shift', 5, 0])
        self.assertEqual(r.to_int(), 5)

    def test_shift_one(self):
        r = ev(['trit_shift', 2, 1])
        self.assertEqual(r.to_int(), 6)

    def test_shift_two(self):
        r = ev(['trit_shift', 1, 2])
        self.assertEqual(r.to_int(), 9)

    def test_shift_negative(self):
        r = ev(['trit_shift', 1, -1])
        self.assertEqual(r.to_int(), 0)

    def test_shift_negative_value(self):
        r = ev(['trit_shift', -3, 1])
        self.assertEqual(r.to_int(), -9)

    def test_shift_preserves_confidence(self):
        e = SanyanEvaluator()
        e.set_var('x', TritValue(5, confidence=0.8))
        r = e.eval(['trit_shift', 'x', 1])
        self.assertAlmostEqual(r.confidence, 0.8, places=2)

    def test_shift_wrong_args(self):
        with self.assertRaises(Exception):
            ev(['trit_shift', 5])


class TestTritFlip(unittest.TestCase):
    """三态翻转"""

    def test_flip_positive(self):
        r = ev(['trit_flip', 1])
        self.assertEqual(r.to_int(), -1)

    def test_flip_negative(self):
        r = ev(['trit_flip', -3])
        self.assertEqual(r.to_int(), 3)

    def test_flip_zero(self):
        r = ev(['trit_flip', 0])
        self.assertEqual(r.to_int(), 0)

    def test_flip_preserves_confidence(self):
        e = SanyanEvaluator()
        e.set_var('x', TritValue(5, confidence=0.7))
        r = e.eval(['trit_flip', 'x'])
        self.assertAlmostEqual(r.confidence, 0.7, places=2)

    def test_flip_wrong_args(self):
        with self.assertRaises(Exception):
            ev(['trit_flip', 1, 2])


class TestTritCompress(unittest.TestCase):
    """三态压缩"""

    def test_compress_empty(self):
        r = ev(['trit_compress'])
        self.assertEqual(r, [])

    def test_compress_single(self):
        r = ev(['trit_compress', 1])
        self.assertEqual(len(r), 1)

    def test_compress_three(self):
        r = ev(['trit_compress', 1, -1, 0])
        self.assertEqual(len(r), 1)

    def test_compress_six(self):
        r = ev(['trit_compress', 1, -1, 0, 1, -1, 0])
        self.assertEqual(len(r), 2)

    def test_compress_padded(self):
        r = ev(['trit_compress', 1, 0])
        self.assertEqual(len(r), 1)

    def test_compress_clamp(self):
        r = ev(['trit_compress', 5, -5])
        self.assertEqual(len(r), 1)


class TestTritDecompress(unittest.TestCase):
    """三态解压"""

    def test_decompress_single(self):
        r = ev(['trit_decompress', 13])
        self.assertEqual(len(r), 3)

    def test_decompress_roundtrip(self):
        original = [1, -1, 0, 1, 0, -1]
        compressed = ev(['trit_compress'] + original)
        decompressed = ev(['trit_decompress'] + compressed)
        for orig, dec in zip(original, decompressed):
            self.assertEqual(orig, dec.to_int())


class TestParseHex(unittest.TestCase):
    """解析十六进制"""

    def test_parse_hex_ff(self):
        r = ev(['parse_hex', '"FF"'])
        self.assertEqual(r.to_int(), 255)

    def test_parse_hex_0x(self):
        r = ev(['parse_hex', '"0xFF"'])
        self.assertEqual(r.to_int(), 255)

    def test_parse_hex_zero(self):
        r = ev(['parse_hex', '"0"'])
        self.assertEqual(r.to_int(), 0)

    def test_parse_hex_10(self):
        r = ev(['parse_hex', '"0x10"'])
        self.assertEqual(r.to_int(), 16)

    def test_parse_hex_tritvalue(self):
        e = SanyanEvaluator()
        e.set_var('h', TritValue('FF'))
        r = e.eval(['parse_hex', 'h'])
        self.assertEqual(r.to_int(), 255)


class TestParseBin(unittest.TestCase):
    """解析二进制"""

    def test_parse_bin_1010(self):
        r = ev(['parse_bin', '"1010"'])
        self.assertEqual(r.to_int(), 10)

    def test_parse_bin_0b(self):
        r = ev(['parse_bin', '"0b1010"'])
        self.assertEqual(r.to_int(), 10)

    def test_parse_bin_0B(self):
        r = ev(['parse_bin', '"0B1010"'])
        self.assertEqual(r.to_int(), 10)

    def test_parse_bin_one(self):
        r = ev(['parse_bin', '"1"'])
        self.assertEqual(r.to_int(), 1)


class TestEnumOp(unittest.TestCase):
    """枚举"""

    def test_enum_simple(self):
        r = ev(['enum', '"红=1"', '"绿=2"', '"蓝=3"'])
        self.assertEqual(r, {'红': 1, '绿': 2, '蓝': 3})

    def test_enum_string_value(self):
        r = ev(['enum', '"name=hello"'])
        self.assertEqual(r, {'name': 'hello'})

    def test_enum_negative(self):
        r = ev(['enum', '"x=-5"'])
        self.assertEqual(r, {'x': -5})

    def test_enum_empty(self):
        r = ev(['enum'])
        self.assertEqual(r, {})


class TestStructOp(unittest.TestCase):
    """结构体"""

    def test_struct_simple(self):
        r = ev(['struct', '"x=1"', '"y=2"'])
        self.assertEqual(r, {'x': 1, 'y': 2})

    def test_struct_string(self):
        r = ev(['struct', '"name=老王"'])
        self.assertEqual(r, {'name': '老王'})


class TestBeliefOp(unittest.TestCase):
    """信念"""

    def test_belief_minimal(self):
        r = ev(['belief', '"今天下雨"'])
        self.assertEqual(r['命题'], '今天下雨')
        self.assertEqual(r['值'].to_int(), 1)
        self.assertEqual(r['信度'], 1.0)
        self.assertEqual(r['来源'], '')

    def test_belief_with_confidence(self):
        e = SanyanEvaluator()
        e.set_var('conf', TritValue(0.8, confidence=0.8))
        r = e.eval(['belief', '"今天下雨"', 'conf'])
        self.assertEqual(r['信度'], 0.8)

    def test_belief_with_source(self):
        r = ev(['belief', '"今天下雨"', 0.8, '"天气预报"'])
        self.assertEqual(r['来源'], '天气预报')

    def test_belief_with_time(self):
        r = ev(['belief', '"今天下雨"', 0.8, '"天气预报"', 1000.0])
        self.assertEqual(r['时间'], 1000.0)

    def test_belief_tritvalue_confidence(self):
        e = SanyanEvaluator()
        e.set_var('c', TritValue(1, confidence=0.9))
        r = e.eval(['belief', '"测试"', 'c'])
        self.assertEqual(r['信度'], 0.9)

    def test_belief_set(self):
        r = ev(['belief_set', '1', '2', '3'])
        self.assertEqual(len(r), 3)


# ═══════════════════════════════════════════════════════════
# ternary_generic_ops.py (44% → 目标 90%+)
# ═══════════════════════════════════════════════════════════


class TestTernarySet(unittest.TestCase):
    """三态集"""

    def test_create(self):
        r = ev(['三态集', 1, 2, 3])
        self.assertEqual(r.size(), 3)

    def test_add(self):
        e = SanyanEvaluator()
        s = e.eval(['三态集'])
        e.set_var('s', s)
        e.eval(['三态集加', 's', 5])
        self.assertEqual(s.size(), 1)

    def test_add_duplicate(self):
        e = SanyanEvaluator()
        s = e.eval(['三态集', 1, 2])
        e.set_var('s', s)
        e.eval(['三态集加', 's', 1])
        self.assertEqual(s.size(), 2)

    def test_remove(self):
        e = SanyanEvaluator()
        s = e.eval(['三态集', 1, 2, 3])
        e.set_var('s', s)
        e.eval(['三态集删', 's', 2])
        self.assertEqual(s.size(), 2)

    def test_contains(self):
        e = SanyanEvaluator()
        s = e.eval(['三态集', 1, 2, 3])
        e.set_var('s', s)
        r = e.eval(['三态集含', 's', 2])
        self.assertTrue(r.to_int() == 1)

    def test_not_contains(self):
        e = SanyanEvaluator()
        s = e.eval(['三态集', 1, 2, 3])
        e.set_var('s', s)
        r = e.eval(['三态集含', 's', 5])
        self.assertTrue(r.to_int() == -1)

    def test_size(self):
        r = ev(['三态集长', ['三态集', 1, 2, 3]])
        self.assertEqual(r.to_int(), 3)

    def test_union(self):
        r = ev(['三态集并', ['三态集', 1, 2], ['三态集', 2, 3]])
        self.assertEqual(r.size(), 3)

    def test_intersection(self):
        r = ev(['三态集交', ['三态集', 1, 2, 3], ['三态集', 2, 3, 4]])
        self.assertEqual(r.size(), 2)

    def test_difference(self):
        r = ev(['三态集差', ['三态集', 1, 2, 3], ['三态集', 2, 3, 4]])
        self.assertEqual(r.size(), 1)

    def test_to_list(self):
        r = ev(['三态集列', ['三态集', 1, 2, 3]])
        self.assertEqual(len(r), 3)

    def test_confidence_sum(self):
        e = SanyanEvaluator()
        s = e.eval(['三态集'])
        e.set_var('s', s)
        e.eval(['三态集加', 's', 1, 0.9])
        e.eval(['三态集加', 's', 2, 0.8])
        r = e.eval(['三态集信度和', 's'])
        # confidence_sum returns float, to_int rounds
        self.assertAlmostEqual(float(str(r)), 1.7, delta=0.1)


class TestTernaryGraph(unittest.TestCase):
    """三态图"""

    def test_create(self):
        r = ev(['三态图'])
        self.assertIsNotNone(r)

    def test_add_node(self):
        e = SanyanEvaluator()
        g = e.eval(['三态图'])
        e.set_var('g', g)
        e.eval(['三态图加节点', 'g', '"A"'])
        self.assertEqual(len(g._nodes), 1)

    def test_add_edge(self):
        e = SanyanEvaluator()
        g = e.eval(['三态图'])
        e.set_var('g', g)
        e.eval(['三态图加边', 'g', '"A"', '"B"', 0.9])
        self.assertEqual(len(g._edges['A']), 1)

    def test_neighbors(self):
        e = SanyanEvaluator()
        g = e.eval(['三态图'])
        e.set_var('g', g)
        e.eval(['三态图加边', 'g', '"A"', '"B"', 0.9])
        e.eval(['三态图加边', 'g', '"A"', '"C"', 0.7])
        r = e.eval(['三态图邻居', 'g', '"A"'])
        self.assertEqual(len(r), 2)

    def test_shortest_path(self):
        e = SanyanEvaluator()
        g = e.eval(['三态图'])
        e.set_var('g', g)
        e.eval(['三态图加边', 'g', '"A"', '"B"', 0.9])
        e.eval(['三态图加边', 'g', '"B"', '"C"', 0.8])
        r = e.eval(['三态图最短路', 'g', '"A"', '"C"'])
        self.assertEqual(r[0], ['A', 'B', 'C'])

    def test_components(self):
        e = SanyanEvaluator()
        g = e.eval(['三态图'])
        e.set_var('g', g)
        e.eval(['三态图加边', 'g', '"A"', '"B"', 0.9])
        e.eval(['三态图加边', 'g', '"C"', '"D"', 0.8])
        r = e.eval(['三态图连通', 'g'])
        self.assertEqual(len(r), 2)

    def test_to_dict(self):
        e = SanyanEvaluator()
        g = e.eval(['三态图'])
        e.set_var('g', g)
        e.eval(['三态图加边', 'g', '"A"', '"B"', 0.9])
        r = e.eval(['三态图字典', 'g'])
        self.assertIn('nodes', r)
        self.assertIn('edges', r)


class TestTernaryQueue(unittest.TestCase):
    """三态队列"""

    def test_create(self):
        r = ev(['三态队列'])
        self.assertIsNotNone(r)

    def test_enqueue_dequeue(self):
        e = SanyanEvaluator()
        q = e.eval(['三态队列'])
        e.set_var('q', q)
        e.eval(['三态入队', 'q', '"任务1"', 0.9])
        e.eval(['三态入队', 'q', '"任务2"', 0.8])
        r = e.eval(['三态出队', 'q'])
        self.assertEqual(r, '任务1')

    def test_peek(self):
        e = SanyanEvaluator()
        q = e.eval(['三态队列'])
        e.set_var('q', q)
        e.eval(['三态入队', 'q', '"任务1"'])
        r = e.eval(['三态查看队', 'q'])
        self.assertEqual(r, '任务1')
        self.assertEqual(q.size(), 1)

    def test_size(self):
        e = SanyanEvaluator()
        q = e.eval(['三态队列'])
        e.set_var('q', q)
        e.eval(['三态入队', 'q', '"a"'])
        e.eval(['三态入队', 'q', '"b"'])
        r = e.eval(['三态队长', 'q'])
        self.assertEqual(r.to_int(), 2)


class TestTernaryStack(unittest.TestCase):
    """三态栈"""

    def test_create(self):
        r = ev(['三态栈'])
        self.assertIsNotNone(r)

    def test_push_pop(self):
        e = SanyanEvaluator()
        s = e.eval(['三态栈'])
        e.set_var('s', s)
        e.eval(['三态压栈', 's', '"数据1"', 0.9])
        e.eval(['三态压栈', 's', '"数据2"', 0.8])
        r = e.eval(['三态弹栈', 's'])
        self.assertEqual(r, '数据2')

    def test_peek(self):
        e = SanyanEvaluator()
        s = e.eval(['三态栈'])
        e.set_var('s', s)
        e.eval(['三态压栈', 's', '"数据1"'])
        r = e.eval(['三态查看栈', 's'])
        self.assertEqual(r, '数据1')
        self.assertEqual(s.size(), 1)

    def test_size(self):
        e = SanyanEvaluator()
        s = e.eval(['三态栈'])
        e.set_var('s', s)
        e.eval(['三态压栈', 's', '"a"'])
        e.eval(['三态压栈', 's', '"b"'])
        r = e.eval(['三态栈长', 's'])
        self.assertEqual(r.to_int(), 2)


# ═══════════════════════════════════════════════════════════
# data_pipeline_ops.py (52% → 目标 85%+)
# ═══════════════════════════════════════════════════════════


class TestTernaryData(unittest.TestCase):
    """三态数据"""

    def test_create(self):
        r = ev(['三态数据', 100, 0.9, '"传感器"'])
        # r.value is a TritValue, compare by to_int()
        self.assertEqual(trit_to_int(r.value), 100)
        self.assertAlmostEqual(r.confidence, 0.9, places=2)
        self.assertEqual(r.source, '传感器')

    def test_create_minimal(self):
        r = ev(['三态数据', 42])
        self.assertEqual(trit_to_int(r.value), 42)
        self.assertAlmostEqual(r.confidence, 1.0, places=2)

    def test_valid(self):
        from ops.data_pipeline_ops import TernaryData

        d = TernaryData(42, 0.9)
        self.assertTrue(d.is_valid(0.5))
        d2 = TernaryData(42, 0.3)
        self.assertFalse(d2.is_valid(0.5))

    def test_str(self):
        from ops.data_pipeline_ops import TernaryData

        d = TernaryData(42, 0.9)
        self.assertEqual(str(d), '42')


class TestTernaryClean(unittest.TestCase):
    """三态清洗"""

    def test_clean_remove_null(self):
        from ops.data_pipeline_ops import TernaryData

        d = TernaryData(None, 0.5)
        r = ev(['三态清洗', d, '"去空"'])
        self.assertAlmostEqual(r.confidence, 0.0, places=2)

    def test_clean_normalize(self):
        from ops.data_pipeline_ops import TernaryData

        d = TernaryData(42, 0.5)
        r = ev(['三态清洗', d, '"归一化"'])
        self.assertTrue(0.0 <= r.confidence <= 1.0)


class TestTernaryAggregate(unittest.TestCase):
    """三态聚合"""

    def test_average(self):
        from ops.data_pipeline_ops import TernaryData

        data = [TernaryData(10, 0.9), TernaryData(20, 0.8)]
        r = ev(['三态聚合', data, '"平均"'])
        self.assertAlmostEqual(float(str(r.value)), 14.71, delta=1)

    def test_sum(self):
        from ops.data_pipeline_ops import TernaryData

        data = [TernaryData(10, 0.9), TernaryData(20, 0.8)]
        r = ev(['三态聚合', data, '"求和"'])
        self.assertEqual(float(str(r.value)), 30.0)

    def test_count(self):
        from ops.data_pipeline_ops import TernaryData

        data = [TernaryData(10, 0.9), TernaryData(0, 0.3), TernaryData(20, 0.8)]
        r = ev(['三态聚合', data, '"计数"'])
        self.assertEqual(float(str(r.value)), 2.0)


class TestTernaryPipeline(unittest.TestCase):
    """三态管线"""

    def test_create(self):
        r = ev(['三态管线', '"测试"'])
        self.assertEqual(r.name, '测试')

    def test_add_stage(self):
        e = SanyanEvaluator()
        p = e.eval(['三态管线', '"测试"'])
        e.set_var('p', p)
        e.eval(['三态管线加阶段', 'p', '"阶段1"', '函数(x) { x }'])
        self.assertEqual(len(p.stages), 1)


# ═══════════════════════════════════════════════════════════
# ternary_source_ops.py (58% → 目标 85%+)
# ═══════════════════════════════════════════════════════════


class TestSourceOps(unittest.TestCase):
    """来源操作"""

    def test_source(self):
        e = SanyanEvaluator()
        e.set_var('x', TritValue(42, source='传感器'))
        r = e.eval(['source', 'x'])
        self.assertEqual(r.to_payload(), '传感器')

    def test_source_empty(self):
        r = ev(['source', 42])
        self.assertEqual(r.to_payload(), '')

    def test_source_chain(self):
        e = SanyanEvaluator()
        e.set_var('a', TritValue(1, source='来源A'))
        e.set_var('b', TritValue(2, source='来源B'))
        r = e.eval(['source_chain', 'a', 'b'])
        self.assertIn('来源A', r.to_payload())
        self.assertIn('来源B', r.to_payload())


class TestConflictOps(unittest.TestCase):
    """冲突操作"""

    def test_detect_conflict_no(self):
        r = ev(['detect_conflict', 1, 1])
        self.assertEqual(r['冲突'], 0)

    def test_detect_conflict_yes(self):
        e = SanyanEvaluator()
        e.set_var('a', TritValue(1, confidence=0.9))
        e.set_var('b', TritValue(-1, confidence=0.8))
        r = e.eval(['detect_conflict', 'a', 'b'])
        self.assertEqual(r['冲突'], 1)

    def test_conflict_merge_conservative(self):
        e = SanyanEvaluator()
        e.set_var('a', TritValue(1, confidence=0.9))
        e.set_var('b', TritValue(-1, confidence=0.8))
        r = e.eval(['conflict_merge', 'a', 'b', '"保守"'])
        self.assertEqual(r.to_int(), 0)

    def test_conflict_merge_vote(self):
        e = SanyanEvaluator()
        e.set_var('a', TritValue(1, confidence=0.9))
        e.set_var('b', TritValue(-1, confidence=0.3))
        r = e.eval(['conflict_merge', 'a', 'b', '"投票"'])
        self.assertEqual(r.to_int(), 1)


class TestBayesOps(unittest.TestCase):
    """贝叶斯操作"""

    def test_bayes_confirm(self):
        e = SanyanEvaluator()
        e.set_var('prior', TritValue(1, confidence=0.6))
        e.set_var('evidence', TritValue(1, confidence=0.8))
        r = e.eval(['bayes_update', 'prior', 'evidence'])
        self.assertEqual(r.to_int(), 1)
        self.assertGreater(r.confidence, 0.6)

    def test_bayes_contradict(self):
        e = SanyanEvaluator()
        e.set_var('prior', TritValue(1, confidence=0.6))
        e.set_var('evidence', TritValue(-1, confidence=0.9))
        r = e.eval(['bayes_update', 'prior', 'evidence'])
        self.assertEqual(r.to_int(), -1)


class TestFuseOps(unittest.TestCase):
    """融合操作"""

    def test_fuse_list(self):
        e = SanyanEvaluator()
        e.set_var('items', [TritValue(1, confidence=0.9), TritValue(1, confidence=0.7)])
        r = e.eval(['fuse', 'items'])
        self.assertEqual(r.to_int(), 1)

    def test_fuse_multi(self):
        r = ev(['fuse', 1, 1, 1])
        self.assertEqual(r.to_int(), 1)

    def test_fuse_mixed(self):
        r = ev(['fuse', 1, -1, 0])
        self.assertEqual(r.to_int(), 0)


class TestConsensusOps(unittest.TestCase):
    """共识操作"""

    def test_consensus_all_true(self):
        e = SanyanEvaluator()
        e.set_var('a', TritValue(1, confidence=0.9))
        e.set_var('b', TritValue(1, confidence=0.8))
        r = e.eval(['consensus', 'a', 'b'])
        self.assertEqual(r.to_int(), 1)
        self.assertGreater(r.confidence, 0.7)

    def test_consensus_one_false(self):
        e = SanyanEvaluator()
        e.set_var('a', TritValue(1, confidence=0.9))
        e.set_var('b', TritValue(-1, confidence=0.8))
        r = e.eval(['consensus', 'a', 'b'])
        self.assertEqual(r.to_int(), -1)


class TestAssertConfidenceOps(unittest.TestCase):
    """断言信度"""

    def test_assert_pass(self):
        e = SanyanEvaluator()
        e.set_var('x', TritValue(1, confidence=0.9))
        r = e.eval(['assert_confidence', 'x', 0.5])
        self.assertEqual(r.to_int(), 1)

    def test_assert_fail(self):
        e = SanyanEvaluator()
        e.set_var('x', TritValue(1, confidence=0.3))
        with self.assertRaises(Exception):
            e.eval(['assert_confidence', 'x', 0.5])


class TestQuantizeOps(unittest.TestCase):
    """量化/反量化"""

    def test_quantize_dequantize_roundtrip(self):
        e = SanyanEvaluator()
        e.set_var('x', TritValue(1, confidence=0.8))
        q = e.eval(['量化', 'x'])
        d = e.eval(['反量化', q])
        self.assertEqual(d.to_int(), 1)


# ═══════════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════════


def trit_to_int(v):
    if isinstance(v, TritValue):
        return v.to_int()
    return v


if __name__ == '__main__':
    unittest.main()
