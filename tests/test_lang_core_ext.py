"""编程语言补充测试：覆盖低覆盖率模块"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.evaluator import SanyanEvaluator
from core.ternary_core import TritValue


def ev(expr):
    e = SanyanEvaluator()
    return e.eval(expr)


def ev_set(var_name, var_val, expr):
    e = SanyanEvaluator()
    e.set_var(var_name, var_val)
    return e.eval(expr)


# ═══════════════════════════════════════════════════════════
# ternary_source_ops.py 补充 (69% → 目标 90%+)
# ═══════════════════════════════════════════════════════════


class TestSourceOpsExtended(unittest.TestCase):
    """来源操作补充"""

    def test_source_chain_empty(self):
        r = ev(['source_chain'])
        self.assertEqual(r.to_payload(), '')

    def test_source_chain_string(self):
        r = ev(['source_chain', '"来源A"', '"来源B"'])
        self.assertIn('来源A', r.to_payload())
        self.assertIn('来源B', r.to_payload())

    def test_detect_conflict_three_args(self):
        e = SanyanEvaluator()
        e.set_var('a', TritValue(1, confidence=0.9))
        e.set_var('b', TritValue(-1, confidence=0.8))
        e.set_var('c', TritValue(1, confidence=0.7))
        r = e.eval(['detect_conflict', 'a', 'b', 'c'])
        self.assertEqual(r['冲突'], 1)

    def test_conflict_merge_priority(self):
        e = SanyanEvaluator()
        e.set_var('a', TritValue(1, confidence=0.9))
        e.set_var('b', TritValue(-1, confidence=0.8))
        r = e.eval(['conflict_merge', 'a', 'b', '"优先级"'])
        self.assertEqual(r.to_int(), 1)

    def test_conflict_merge_default(self):
        e = SanyanEvaluator()
        e.set_var('a', TritValue(1, confidence=0.5))
        e.set_var('b', TritValue(-1, confidence=0.5))
        r = e.eval(['conflict_merge', 'a', 'b', '"未知策略"'])
        self.assertEqual(r.to_int(), 0)

    def test_bayes_update_same_value(self):
        e = SanyanEvaluator()
        e.set_var('prior', TritValue(1, confidence=0.5))
        e.set_var('evidence', TritValue(1, confidence=0.5))
        r = e.eval(['bayes_update', 'prior', 'evidence'])
        self.assertEqual(r.to_int(), 1)
        self.assertGreater(r.confidence, 0.5)

    def test_bayes_update_different_value(self):
        e = SanyanEvaluator()
        e.set_var('prior', TritValue(1, confidence=0.3))
        e.set_var('evidence', TritValue(-1, confidence=0.9))
        r = e.eval(['bayes_update', 'prior', 'evidence'])
        self.assertEqual(r.to_int(), -1)

    def test_fuse_empty(self):
        r = ev(['fuse', []])
        self.assertEqual(r.to_int(), 0)

    def test_fuse_all_true(self):
        e = SanyanEvaluator()
        e.set_var('items', [TritValue(1, confidence=0.9), TritValue(1, confidence=0.8)])
        r = e.eval(['fuse', 'items'])
        self.assertEqual(r.to_int(), 1)

    def test_fuse_all_false(self):
        e = SanyanEvaluator()
        e.set_var('items', [TritValue(-1, confidence=0.9), TritValue(-1, confidence=0.8)])
        r = e.eval(['fuse', 'items'])
        self.assertEqual(r.to_int(), -1)

    def test_consensus_one_false(self):
        e = SanyanEvaluator()
        e.set_var('a', TritValue(1, confidence=0.9))
        e.set_var('b', TritValue(1, confidence=0.8))
        e.set_var('c', TritValue(-1, confidence=0.7))
        r = e.eval(['consensus', 'a', 'b', 'c'])
        self.assertEqual(r.to_int(), -1)

    def test_consensus_one_maybe(self):
        e = SanyanEvaluator()
        e.set_var('a', TritValue(1, confidence=0.9))
        e.set_var('b', TritValue(0, confidence=0.5))
        r = e.eval(['consensus', 'a', 'b'])
        self.assertEqual(r.to_int(), 0)

    def test_assert_confidence_high(self):
        e = SanyanEvaluator()
        e.set_var('x', TritValue(1, confidence=0.95))
        r = e.eval(['assert_confidence', 'x', 0.9])
        self.assertEqual(r.to_int(), 1)

    def test_majority_vote(self):
        r = ev(['majority_vote', 1, 1, -1])
        self.assertEqual(r.to_int(), 1)

    def test_majority_vote_tie(self):
        r = ev(['majority_vote', 1, -1, 0])
        self.assertEqual(r.to_int(), 1)

    def test_quantize_dequantize(self):
        e = SanyanEvaluator()
        e.set_var('x', TritValue(-1, confidence=0.75))
        q = e.eval(['量化', 'x'])
        d = e.eval(['反量化', q])
        self.assertEqual(d.to_int(), -1)
        self.assertAlmostEqual(d.confidence, 0.75, delta=0.1)

    def test_detect_conflict_no_conflict(self):
        e = SanyanEvaluator()
        e.set_var('a', TritValue(1, confidence=0.5))
        e.set_var('b', TritValue(-1, confidence=0.5))
        r = e.eval(['detect_conflict', 'a', 'b'])
        self.assertEqual(r['冲突'], 0)

    def test_source_chain_non_tritvalue(self):
        r = ev(['source_chain', '"来源A"', '"来源B"'])
        self.assertIn('来源A', r.to_payload())
        self.assertIn('来源B', r.to_payload())


# ═══════════════════════════════════════════════════════════
# ternary_graph_ops.py 补充 (81% → 目标 95%+)
# ═══════════════════════════════════════════════════════════


class TestTernaryGraphExtended(unittest.TestCase):
    """三态图补充"""

    def test_add_node_existing(self):
        e = SanyanEvaluator()
        g = e.eval(['三态图'])
        e.set_var('g', g)
        e.eval(['三态图加节点', 'g', '"A"', 0.9])
        e.eval(['三态图加节点', 'g', '"A"', 0.7])
        self.assertEqual(len(g._nodes), 1)
        self.assertAlmostEqual(g._nodes['A'].confidence, 0.9, places=2)

    def test_add_edge_creates_nodes(self):
        e = SanyanEvaluator()
        g = e.eval(['三态图'])
        e.set_var('g', g)
        e.eval(['三态图加边', 'g', '"X"', '"Y"', 0.8])
        self.assertIn('X', g._nodes)
        self.assertIn('Y', g._nodes)

    def test_add_edge_bidirectional(self):
        e = SanyanEvaluator()
        g = e.eval(['三态图'])
        e.set_var('g', g)
        e.eval(['三态图加边', 'g', '"A"', '"B"', 0.9, 1])
        self.assertEqual(len(g._edges['A']), 1)
        self.assertEqual(len(g._edges['B']), 1)

    def test_edge_confidence(self):
        e = SanyanEvaluator()
        g = e.eval(['三态图'])
        e.set_var('g', g)
        e.eval(['三态图加边', 'g', '"A"', '"B"', 0.85])
        conf = g.edge_confidence('A', 'B')
        self.assertAlmostEqual(conf, 0.85, delta=0.01)

    def test_edge_confidence_missing(self):
        e = SanyanEvaluator()
        g = e.eval(['三态图'])
        e.set_var('g', g)
        conf = g.edge_confidence('A', 'B')
        self.assertEqual(conf, 0.0)

    def test_shortest_path_no_path(self):
        e = SanyanEvaluator()
        g = e.eval(['三态图'])
        e.set_var('g', g)
        e.eval(['三态图加边', 'g', '"A"', '"B"', 0.9])
        path, conf = g.shortest_path('A', 'Z')
        self.assertIsNone(path)

    def test_shortest_path_same_node(self):
        e = SanyanEvaluator()
        g = e.eval(['三态图'])
        e.set_var('g', g)
        e.eval(['三态图加节点', 'g', '"A"'])
        path, conf = g.shortest_path('A', 'A')
        self.assertEqual(path, ['A'])
        self.assertEqual(conf, 1.0)

    def test_components_single(self):
        e = SanyanEvaluator()
        g = e.eval(['三态图'])
        e.set_var('g', g)
        e.eval(['三态图加边', 'g', '"A"', '"B"', 0.9])
        r = e.eval(['三态图连通', 'g'])
        self.assertEqual(len(r), 1)

    def test_to_dict_empty(self):
        e = SanyanEvaluator()
        g = e.eval(['三态图'])
        e.set_var('g', g)
        r = e.eval(['三态图字典', 'g'])
        self.assertEqual(r['nodes'], {})
        self.assertEqual(r['edges'], {})

    def test_repr(self):
        from ops.ternary_graph_ops import TernaryGraph

        g = TernaryGraph()
        g.add_node('A')
        g.add_node('B')
        g.add_edge('A', 'B', 0.9)
        self.assertIn('2', repr(g))


# ═══════════════════════════════════════════════════════════
# ternary_queue_ops.py 补充 (84% → 目标 95%+)
# ═══════════════════════════════════════════════════════════


class TestTernaryQueueExtended(unittest.TestCase):
    """三态队列补充"""

    def test_empty_dequeue(self):
        e = SanyanEvaluator()
        q = e.eval(['三态队列'])
        e.set_var('q', q)
        r = e.eval(['三态出队', 'q'])
        self.assertEqual(r.to_int(), -1)

    def test_empty_peek(self):
        e = SanyanEvaluator()
        q = e.eval(['三态队列'])
        e.set_var('q', q)
        r = e.eval(['三态查看队', 'q'])
        self.assertEqual(r.to_int(), -1)

    def test_is_empty(self):
        from ops.ternary_queue_ops import TernaryQueue

        q = TernaryQueue()
        self.assertTrue(q.is_empty())
        q.enqueue('a')
        self.assertFalse(q.is_empty())

    def test_to_list(self):
        from ops.ternary_queue_ops import TernaryQueue

        q = TernaryQueue()
        q.enqueue('a', 0.9)
        q.enqueue('b', 0.8)
        items = q.to_list()
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0][0], 'a')

    def test_repr(self):
        from ops.ternary_queue_ops import TernaryQueue

        q = TernaryQueue()
        q.enqueue('a')
        self.assertIn('1', repr(q))


class TestTernaryStackExtended(unittest.TestCase):
    """三态栈补充"""

    def test_empty_pop(self):
        e = SanyanEvaluator()
        s = e.eval(['三态栈'])
        e.set_var('s', s)
        r = e.eval(['三态弹栈', 's'])
        self.assertEqual(r.to_int(), -1)

    def test_empty_peek(self):
        e = SanyanEvaluator()
        s = e.eval(['三态栈'])
        e.set_var('s', s)
        r = e.eval(['三态查看栈', 's'])
        self.assertEqual(r.to_int(), -1)

    def test_is_empty(self):
        from ops.ternary_queue_ops import TernaryStack

        s = TernaryStack()
        self.assertTrue(s.is_empty())
        s.push('a')
        self.assertFalse(s.is_empty())

    def test_to_list(self):
        from ops.ternary_queue_ops import TernaryStack

        s = TernaryStack()
        s.push('a', 0.9)
        s.push('b', 0.8)
        items = s.to_list()
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0][0], 'b')

    def test_repr(self):
        from ops.ternary_queue_ops import TernaryStack

        s = TernaryStack()
        s.push('a')
        self.assertIn('1', repr(s))


# ═══════════════════════════════════════════════════════════
# ternary_set_ops.py 补充 (86% → 目标 95%+)
# ═══════════════════════════════════════════════════════════


class TestTernarySetExtended(unittest.TestCase):
    """三态集补充"""

    def test_add_duplicate_higher_conf(self):
        e = SanyanEvaluator()
        s = e.eval(['三态集'])
        e.set_var('s', s)
        e.eval(['三态集加', 's', 1, 0.9])
        e.eval(['三态集加', 's', 1, 0.7])
        self.assertEqual(s.size(), 1)
        self.assertAlmostEqual(s.contains(1), 0.9, places=2)

    def test_confidence_sum(self):
        e = SanyanEvaluator()
        s = e.eval(['三态集'])
        e.set_var('s', s)
        e.eval(['三态集加', 's', 1, 0.9])
        e.eval(['三态集加', 's', 2, 0.8])
        e.eval(['三态集加', 's', 3, 0.7])
        r = e.eval(['三态集信度和', 's'])
        self.assertAlmostEqual(float(str(r)), 2.4, delta=0.1)

    def test_to_list(self):
        e = SanyanEvaluator()
        s = e.eval(['三态集', 1, 2, 3])
        e.set_var('s', s)
        r = e.eval(['三态集列', 's'])
        self.assertEqual(len(r), 3)
        self.assertIn('1', r)
        self.assertIn('2', r)
        self.assertIn('3', r)

    def test_repr(self):
        from ops.ternary_set_ops import TernarySet

        s = TernarySet()
        s.add(1, 0.9)
        self.assertIn('1', repr(s))
        self.assertIn('0.90', repr(s))

    def test_contains_missing(self):
        from ops.ternary_set_ops import TernarySet

        s = TernarySet()
        s.add(1)
        self.assertEqual(s.contains(2), 0.0)

    def test_union_preserves_confidence(self):
        e = SanyanEvaluator()
        s1 = e.eval(['三态集'])
        s2 = e.eval(['三态集'])
        e.set_var('s1', s1)
        e.set_var('s2', s2)
        e.eval(['三态集加', 's1', 1, 0.9])
        e.eval(['三态集加', 's2', 1, 0.7])
        r = e.eval(['三态集并', 's1', 's2'])
        self.assertAlmostEqual(r.contains(1), 0.9, places=2)

    def test_intersection_confidence(self):
        e = SanyanEvaluator()
        s1 = e.eval(['三态集'])
        s2 = e.eval(['三态集'])
        e.set_var('s1', s1)
        e.set_var('s2', s2)
        e.eval(['三态集加', 's1', 1, 0.9])
        e.eval(['三态集加', 's2', 1, 0.7])
        r = e.eval(['三态集交', 's1', 's2'])
        self.assertAlmostEqual(r.contains(1), 0.7, places=2)


# ═══════════════════════════════════════════════════════════
# data_pipeline_ops.py 补充 (53% → 目标 80%+)
# ═══════════════════════════════════════════════════════════


class TestTernaryDataExtended(unittest.TestCase):
    """三态数据补充"""

    def test_to_trit(self):
        from ops.data_pipeline_ops import TernaryData

        d = TernaryData(42, 0.9)
        trit = d.to_trit()
        self.assertEqual(trit.to_int(), 1)

    def test_to_trit_zero(self):
        from ops.data_pipeline_ops import TernaryData

        d = TernaryData(0, 0.5)
        trit = d.to_trit()
        self.assertEqual(trit.to_int(), 0)

    def test_to_trit_string(self):
        from ops.data_pipeline_ops import TernaryData

        d = TernaryData('hello', 0.9)
        trit = d.to_trit()
        self.assertEqual(trit.to_int(), 1)

    def test_metadata(self):
        from ops.data_pipeline_ops import TernaryData

        d = TernaryData(42, 0.9)
        d.metadata['tag'] = 'test'
        self.assertEqual(d.metadata['tag'], 'test')

    def test_timestamp(self):
        from ops.data_pipeline_ops import TernaryData
        import time

        before = time.time()
        d = TernaryData(42, 0.9)
        after = time.time()
        self.assertGreaterEqual(d.timestamp, before)
        self.assertLessEqual(d.timestamp, after)


class TestTernaryPipelineExtended(unittest.TestCase):
    """三态管线补充"""

    def test_add_stage(self):
        e = SanyanEvaluator()
        p = e.eval(['三态管线', '"测试"'])
        e.set_var('p', p)
        e.eval(['三态管线加阶段', 'p', '"清洗"', '函数(x) { x }'])
        self.assertEqual(len(p.stages), 1)
        self.assertEqual(p.stages[0][0], '清洗')

    def test_stats(self):
        from ops.data_pipeline_ops import TernaryPipeline, TernaryData

        p = TernaryPipeline('测试')
        p.add_stage('步骤1', lambda d: TernaryData(d.value * 2, d.confidence))
        p.process(TernaryData(5, 0.9))
        stats = p.get_stats()
        self.assertEqual(stats['total'], 1)
        self.assertEqual(stats['valid'], 1)

    def test_reset_stats(self):
        from ops.data_pipeline_ops import TernaryPipeline, TernaryData

        p = TernaryPipeline('测试')
        p.process(TernaryData(5, 0.9))
        p.reset_stats()
        self.assertEqual(p.get_stats()['total'], 0)


class TestTernaryCleanExtended(unittest.TestCase):
    """三态清洗补充"""

    def test_clean_unknown_rule(self):
        from ops.data_pipeline_ops import TernaryData

        d = TernaryData(42, 0.5)
        r = ev(['三态清洗', d, '"未知规则"'])
        self.assertEqual(r.value, 42)


class TestTernaryAggregateExtended(unittest.TestCase):
    """三态聚合补充"""

    def test_aggregate_empty(self):

        r = ev(['三态聚合', [], '"平均"'])
        self.assertEqual(float(str(r.value)), 0.0)

    def test_aggregate_fusion(self):
        from ops.data_pipeline_ops import TernaryData

        data = [TernaryData(1, 0.9), TernaryData(1, 0.8)]
        r = ev(['三态聚合', data, '"融合"'])
        self.assertEqual(float(str(r.value)), 1.0)


class TestTernaryValidateExtended(unittest.TestCase):
    """三态验证补充"""

    def test_validate_non_dict(self):
        r = ev(['三态验证', 42, '"简单规则"'])
        self.assertAlmostEqual(r.confidence, 1.0, places=2)


if __name__ == '__main__':
    unittest.main()
