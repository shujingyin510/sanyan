"""新增功能测试：并发融合、模式匹配、泛型容器、错误处理链、Web框架、数据管线"""

import unittest
from evaluator import SanyanEvaluator
from ternary_core import TritValue
from ops.ternary_generic_ops import TernarySet, TernaryGraph, TernaryQueue, TernaryStack
from ops.web_ops import TernaryServer, TernaryRequest, TernaryResponse, TernaryRouter
from ops.data_pipeline_ops import TernaryData, TernaryPipeline, TernaryCleaner, TernaryAggregator, TernaryValidator


def trit_to_int(result):
    """将结果转为整数比较"""
    if isinstance(result, TritValue):
        return result.to_int()
    return result


class TestConcurrentFusion(unittest.TestCase):
    """并发融合操作测试"""

    def setUp(self):
        self.e = SanyanEvaluator()

    def test_concurrent_fusion_empty(self):
        """并发融合：空参数返回可能"""
        result = self.e.eval(['并发融合'])
        self.assertEqual(result.value[0], 0)

    def test_concurrent_fusion_mixed(self):
        """并发融合：混合结果返回可能"""
        result = self.e.eval(['并发融合', 1, -1])
        self.assertEqual(result.value[0], 0)

    def test_concurrent_race(self):
        """并发竞速：取最先完成的结果"""
        result = self.e.eval(['并发竞速', 1000, 1, 2, 3])
        self.assertIn(trit_to_int(result), [1, 2, 3])

    def test_concurrent_all_success(self):
        """并发全部：全部成功返回真"""
        result = self.e.eval(['并发全部', 1, 2, 3])
        self.assertEqual(result.value[0], 1)


class TestTernaryMatch(unittest.TestCase):
    """三态模式匹配测试"""

    def setUp(self):
        self.e = SanyanEvaluator()

    def test_match_true(self):
        """匹配3：真分支"""
        result = self.e.eval(['匹配3', 1, '真', 10, '可能', 20, '假', 30])
        self.assertEqual(trit_to_int(result), 10)

    def test_match_maybe(self):
        """匹配3：可能分支"""
        result = self.e.eval(['匹配3', 0, '真', 10, '可能', 20, '假', 30])
        self.assertEqual(trit_to_int(result), 20)

    def test_match_false(self):
        """匹配3：假分支"""
        result = self.e.eval(['匹配3', -1, '真', 10, '可能', 20, '假', 30])
        self.assertEqual(trit_to_int(result), 30)

    def test_match_default(self):
        """匹配3：默认分支"""
        result = self.e.eval(['匹配3', 5, '真', 10, '可能', 20, '假', 30, '默认', 99])
        self.assertEqual(trit_to_int(result), 99)

    def test_match_confidence_high(self):
        """匹配信度：高置信度"""
        self.e.set_var('val', TritValue(1, confidence=0.9))
        result = self.e.eval(['匹配信度', 'val', 0.7, '高', 100, '中', 50, '低', 0])
        self.assertEqual(trit_to_int(result), 100)

    def test_match_confidence_low(self):
        """匹配信度：低置信度"""
        self.e.set_var('val', TritValue(1, confidence=0.3))
        result = self.e.eval(['匹配信度', 'val', 0.7, '高', 100, '中', 50, '低', 0])
        self.assertEqual(trit_to_int(result), 0)


class TestGenericContainers(unittest.TestCase):
    """泛型容器测试"""

    def test_ternary_set_create(self):
        """三态集：创建"""
        s = TernarySet()
        s.add(1)
        s.add(2)
        s.add(3)
        self.assertEqual(s.size(), 3)

    def test_ternary_set_add_with_confidence(self):
        """三态集：添加带置信度"""
        s = TernarySet()
        s.add(1, 0.9)
        s.add(1, 0.7)  # 重复元素，取较高置信度
        self.assertEqual(s.size(), 1)
        self.assertAlmostEqual(s.contains(1), 0.9, places=2)

    def test_ternary_set_union(self):
        """三态集：并集"""
        s1 = TernarySet()
        s1.add(1)
        s1.add(2)
        s2 = TernarySet()
        s2.add(2)
        s2.add(3)
        result = s1.union(s2)
        self.assertEqual(result.size(), 3)

    def test_ternary_set_intersection(self):
        """三态集：交集"""
        s1 = TernarySet()
        s1.add(1, 0.9)
        s1.add(2, 0.8)
        s2 = TernarySet()
        s2.add(2, 0.7)
        s2.add(3, 0.6)
        result = s1.intersection(s2)
        self.assertEqual(result.size(), 1)
        self.assertTrue(result.contains(2) > 0)

    def test_ternary_set_difference(self):
        """三态集：差集"""
        s1 = TernarySet()
        s1.add(1, 0.9)
        s1.add(2, 0.8)
        s2 = TernarySet()
        s2.add(2, 0.7)
        s2.add(3, 0.6)
        result = s1.difference(s2)
        self.assertEqual(result.size(), 1)
        self.assertTrue(result.contains(1) > 0)

    def test_ternary_graph_create(self):
        """三态图：创建"""
        g = TernaryGraph()
        g.add_node('A')
        g.add_node('B')
        g.add_edge('A', 'B', 0.9)
        self.assertEqual(len(g._nodes), 2)
        self.assertEqual(len(g._edges['A']), 1)

    def test_ternary_graph_shortest_path(self):
        """三态图：最短路径"""
        g = TernaryGraph()
        g.add_node('A')
        g.add_node('B')
        g.add_node('C')
        g.add_edge('A', 'B', 0.9)
        g.add_edge('B', 'C', 0.8)
        path, conf = g.shortest_path('A', 'C')
        self.assertEqual(path, ['A', 'B', 'C'])
        self.assertAlmostEqual(conf, 0.8, places=2)

    def test_ternary_graph_neighbors(self):
        """三态图：邻居查询"""
        g = TernaryGraph()
        g.add_node('A')
        g.add_node('B')
        g.add_node('C')
        g.add_edge('A', 'B', 0.9)
        g.add_edge('A', 'C', 0.7)
        neighbors = g.get_neighbors('A')
        self.assertEqual(len(neighbors), 2)

    def test_ternary_queue(self):
        """三态队列：入队出队"""
        q = TernaryQueue()
        q.enqueue('a', 0.9)
        q.enqueue('b', 0.8)
        item, conf = q.dequeue()
        self.assertEqual(item, 'a')
        self.assertAlmostEqual(conf, 0.9, places=2)

    def test_ternary_stack(self):
        """三态栈：压栈弹栈"""
        s = TernaryStack()
        s.push('a', 0.9)
        s.push('b', 0.8)
        item, conf = s.pop()
        self.assertEqual(item, 'b')
        self.assertAlmostEqual(conf, 0.8, places=2)


class TestErrorHandlingChain(unittest.TestCase):
    """错误处理链测试"""

    def setUp(self):
        self.e = SanyanEvaluator()

    def test_chain_all_true(self):
        """链：全部为真"""
        self.e.set_var('a', TritValue(1, confidence=0.9))
        self.e.set_var('b', TritValue(1, confidence=0.8))
        result = self.e.eval(['链', 'a', 'b'])
        self.assertEqual(result.value[0], 1)
        self.assertAlmostEqual(result.confidence, 0.72, places=2)

    def test_chain_with_false(self):
        """链：包含假值"""
        self.e.set_var('a', TritValue(1, confidence=0.9))
        self.e.set_var('b', TritValue(-1, confidence=0.8))
        result = self.e.eval(['链', 'a', 'b'])
        self.assertEqual(result.value[0], -1)

    def test_chain_break(self):
        """链断：假值中断"""
        self.e.set_var('a', TritValue(1, confidence=0.9))
        self.e.set_var('b', TritValue(-1, confidence=0.8))
        with self.assertRaises(Exception):
            self.e.eval(['链断', 'a', 'b'])

    def test_unwrap_true(self):
        """解包：真值"""
        self.e.set_var('x', TritValue(1, confidence=0.9))
        result = self.e.eval(['解包', 'x'])
        self.assertEqual(result.value[0], 1)

    def test_unwrap_or_default(self):
        """或解：假值返回默认"""
        self.e.set_var('x', TritValue(-1, confidence=0.5))
        result = self.e.eval(['或解', 'x', 42])
        self.assertEqual(trit_to_int(result), 42)

    def test_confidence_guard_high(self):
        """信度守卫：高置信度"""
        self.e.set_var('val', TritValue(1, confidence=0.9))
        result = self.e.eval(['信度守卫', 'val', 0.7, '高', 100, '低', 0])
        self.assertEqual(trit_to_int(result), 100)

    def test_confidence_guard_low(self):
        """信度守卫：低置信度"""
        self.e.set_var('val', TritValue(1, confidence=0.3))
        result = self.e.eval(['信度守卫', 'val', 0.7, '高', 100, '低', 0])
        self.assertEqual(trit_to_int(result), 0)


class TestWebFramework(unittest.TestCase):
    """Web框架测试"""

    def test_server_create(self):
        """创建Web服务器"""
        server = TernaryServer('127.0.0.1', 8080)
        self.assertEqual(server.port, 8080)

    def test_router_add_route(self):
        """添加路由"""
        router = TernaryRouter()

        def handler(req, resp):
            resp.text('OK')

        router.get('/test', handler)
        self.assertEqual(len(router.routes), 1)

    def test_router_match(self):
        """路由匹配"""
        router = TernaryRouter()

        def handler(req, resp):
            resp.text('OK')

        router.get('/test/:id', handler)
        match = router.match('GET', '/test/123')
        self.assertIsNotNone(match)
        handler, params = match
        self.assertEqual(params['id'], '123')

    def test_request_confidence(self):
        """请求置信度"""
        req = TernaryRequest('GET', '/test', {})
        req.set_confidence(0.8)
        self.assertAlmostEqual(req.confidence, 0.8, places=2)

    def test_response_json(self):
        """JSON响应"""
        resp = TernaryResponse()
        resp.json({'key': 'value'}, 0.9)
        self.assertEqual(resp.status, 200)
        self.assertAlmostEqual(resp.confidence, 0.9, places=2)


class TestDataPipeline(unittest.TestCase):
    """数据管线测试"""

    def test_pipeline_create(self):
        """创建数据管线"""
        pipe = TernaryPipeline('测试管线')
        self.assertEqual(pipe.name, '测试管线')

    def test_pipeline_process(self):
        """管线处理"""
        pipe = TernaryPipeline('测试')
        pipe.add_stage('清洗', lambda d: TernaryData(d.value * 2, d.confidence))
        data = TernaryData(5, 0.9)
        result = pipe.process(data)
        self.assertEqual(result.value, 10)

    def test_ternary_data(self):
        """三态数据"""
        data = TernaryData(42, 0.8, '测试')
        self.assertEqual(trit_to_int(data.value) if isinstance(data.value, TritValue) else data.value, 42)
        self.assertAlmostEqual(data.confidence, 0.8, places=2)
        self.assertEqual(data.source, '测试')

    def test_ternary_data_valid(self):
        """数据有效性"""
        data = TernaryData(42, 0.9)
        self.assertTrue(data.is_valid(0.5))
        data2 = TernaryData(42, 0.3)
        self.assertFalse(data2.is_valid(0.5))

    def test_cleaner_remove_null(self):
        """清洗器：移除空值"""
        data = TernaryData(None, 0.5)
        result = TernaryCleaner.remove_null(data)
        self.assertAlmostEqual(result.confidence, 0.0, places=2)

    def test_cleaner_fill_default(self):
        """清洗器：填充默认值"""
        data = TernaryData(None, 0.5)
        result = TernaryCleaner.fill_default(data, '默认')
        self.assertEqual(result.value, '默认')

    def test_aggregator_average(self):
        """聚合器：平均值"""
        data_list = [
            TernaryData(10, 0.9),
            TernaryData(20, 0.8),
            TernaryData(30, 0.7),
        ]
        result = TernaryAggregator.average(data_list)
        # 置信度加权平均: (10*0.9 + 20*0.8 + 30*0.7) / (0.9+0.8+0.7) = 46/2.4 ≈ 19.17
        self.assertAlmostEqual(result.value, 19.17, places=1)

    def test_aggregator_sum(self):
        """聚合器：求和"""
        data_list = [
            TernaryData(10, 0.9),
            TernaryData(20, 0.8),
        ]
        result = TernaryAggregator.sum(data_list)
        self.assertEqual(result.value, 30)

    def test_aggregator_count(self):
        """聚合器：计数"""
        data_list = [
            TernaryData(10, 0.9),
            TernaryData(0, 0.3),
            TernaryData(20, 0.8),
        ]
        result = TernaryAggregator.count(data_list, threshold=0.5)
        self.assertEqual(result.value, 2)

    def test_validator_schema(self):
        """验证器：模式验证"""
        data = {'name': '张三', 'age': 25}
        schema = {
            'name': {'type': 'str', 'required': True},
            'age': {'type': 'int', 'min': 0, 'max': 150},
        }
        result = TernaryValidator.schema(data, schema)
        self.assertAlmostEqual(result.confidence, 1.0, places=2)

    def test_validator_schema_error(self):
        """验证器：模式验证失败"""
        data = {'name': '张三'}
        schema = {
            'name': {'type': 'str', 'required': True},
            'age': {'type': 'int', 'required': True},
        }
        result = TernaryValidator.schema(data, schema)
        self.assertAlmostEqual(result.confidence, 0.0, places=2)


class TestEvaluatorIntegration(unittest.TestCase):
    """求值器集成测试"""

    def setUp(self):
        self.e = SanyanEvaluator()

    def test_ternary_set_eval(self):
        """三态集求值"""
        result = self.e.eval(['三态集', 1, 2, 3])
        self.assertIsInstance(result, TernarySet)
        self.assertEqual(result.size(), 3)

    def test_ternary_graph_eval(self):
        """三态图求值"""
        result = self.e.eval(['三态图'])
        self.assertIsInstance(result, TernaryGraph)

    def test_ternary_pipeline_eval(self):
        """三态管线求值"""
        result = self.e.eval(['三态管线', '测试'])
        self.assertIsInstance(result, TernaryPipeline)
        self.assertEqual(result.name, '测试')

    def test_ternary_data_eval(self):
        """三态数据求值"""
        result = self.e.eval(['三态数据', 42, 0.9, '测试'])
        self.assertIsInstance(result, TernaryData)
        self.assertEqual(trit_to_int(result.value) if isinstance(result.value, TritValue) else result.value, 42)


if __name__ == '__main__':
    unittest.main()
