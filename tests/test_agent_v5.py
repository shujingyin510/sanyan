"""Agent V5 全量测试：Phase 0/1/2 所有模块，目标覆盖率 ≥95%"""

import os
import sys
import json
import tempfile
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ═══════════════════════════════════════════════════════════
# Phase 0: agent_tool_graph.py
# ═══════════════════════════════════════════════════════════


class TestToolDependencyGraph(unittest.TestCase):
    def setUp(self):
        from agent_system.agent_tool_graph import ToolDependencyGraph

        self.g = ToolDependencyGraph()

    def test_validate_chain_ok(self):
        ok, msg = self.g.validate_chain(['read_file', 'replace_in_file'])
        self.assertTrue(ok)
        self.assertEqual(msg, '')

    def test_validate_chain_empty(self):
        ok, msg = self.g.validate_chain([])
        self.assertTrue(ok)

    def test_validate_chain_missing_prereq(self):
        ok, msg = self.g.validate_chain(['replace_in_file'])
        self.assertFalse(ok)
        self.assertIn('read_file', msg)

    def test_validate_chain_conflict(self):
        ok, msg = self.g.validate_chain(['read_file', 'write_file', 'dry_run'])
        self.assertFalse(ok)
        self.assertIn('冲突', msg)

    def test_filter_valid(self):
        chains = [['read_file', 'replace_in_file'], ['replace_in_file']]
        result = self.g.filter_valid(chains)
        self.assertEqual(len(result), 1)

    def test_filter_valid_all_valid(self):
        chains = [['read_file'], ['read_file', 'analyze']]
        result = self.g.filter_valid(chains)
        self.assertEqual(len(result), 2)

    def test_get_prerequisites(self):
        self.assertIn('read_file', self.g.get_prerequisites('replace_in_file'))
        self.assertEqual(self.g.get_prerequisites('read_file'), [])

    def test_would_conflict_true(self):
        self.assertTrue(self.g.would_conflict({'write_file'}, 'dry_run'))

    def test_would_conflict_false(self):
        self.assertFalse(self.g.would_conflict({'read_file'}, 'dry_run'))

    def test_would_conflict_reverse(self):
        self.assertTrue(self.g.would_conflict({'dry_run'}, 'write_file'))


class TestToolCapabilityRegistry(unittest.TestCase):
    def setUp(self):
        from agent_system.agent_tool_graph import ToolCapabilityRegistry

        self.r = ToolCapabilityRegistry()

    def test_get_capabilities(self):
        self.assertIn('code_analysis', self.r.get_capabilities('analyze'))
        self.assertIn('file_read', self.r.get_capabilities('read_file'))
        self.assertEqual(self.r.get_capabilities('unknown'), [])

    def test_is_suitable_true(self):
        self.assertTrue(self.r.is_suitable('replace_in_file', ['code_modify']))

    def test_is_suitable_false(self):
        self.assertFalse(self.r.is_suitable('read_file', ['code_modify']))

    def test_find_tools_for_caps(self):
        tools = self.r.find_tools_for_caps(['code_modify'])
        self.assertIn('replace_in_file', tools)
        self.assertIn('write_file', tools)

    def test_find_tools_for_empty(self):
        tools = self.r.find_tools_for_caps([])
        self.assertEqual(tools, [])


class TestTaskCapabilityExtractor(unittest.TestCase):
    def setUp(self):
        from agent_system.agent_tool_graph import TaskCapabilityExtractor

        self.e = TaskCapabilityExtractor()

    def test_extract_modify(self):
        self.assertIn('code_modify', self.e.extract('修改 foo.py 中的函数'))

    def test_extract_search(self):
        self.assertIn('symbol_search', self.e.extract('查找所有引用'))

    def test_extract_analysis(self):
        self.assertIn('code_analysis', self.e.extract('分析代码结构'))

    def test_extract_testing(self):
        self.assertIn('testing', self.e.extract('跑测试'))

    def test_extract_version_control(self):
        self.assertIn('version_control', self.e.extract('查看 git diff'))

    def test_extract_batch(self):
        self.assertIn('batch_modify', self.e.extract('批量替换所有文件'))

    def test_extract_default(self):
        self.assertEqual(self.e.extract('随便什么'), ['file_read'])

    def test_validate_chain_ok(self):
        self.assertTrue(self.e.validate_chain('修改文件', ['read_file', 'replace_in_file']))

    def test_validate_chain_fail(self):
        self.assertFalse(self.e.validate_chain('修改代码', ['read_file']))

    def test_suggest_tools(self):
        tools = self.e.suggest_tools('修改 foo.py')
        self.assertTrue(len(tools) > 0)


# ═══════════════════════════════════════════════════════════
# Phase 0: agent_decompose.py
# ═══════════════════════════════════════════════════════════


class TestComplexityClassifier(unittest.TestCase):
    def setUp(self):
        from agent_system.agent_decompose import ComplexityClassifier

        self.c = ComplexityClassifier()

    def test_simple(self):
        for p in ['读取', '告诉我', '列出来', '查看', '是什么', '读', '列出']:
            self.assertEqual(self.c.classify(f'{p} config.py'), 'simple')

    def test_complex(self):
        for p in ['重构', '多个文件', '全部替换', '生成测试', '新建模块', '批量', '全局']:
            self.assertEqual(self.c.classify(f'{p} 认证模块'), 'complex')

    def test_medium(self):
        for p in ['修改', '替换', '修复', '增加', '删除', '改', '更新']:
            self.assertEqual(self.c.classify(f'{p} foo.py'), 'medium')

    def test_unknown_medium(self):
        self.assertEqual(self.c.classify('随便什么任务'), 'medium')

    def test_should_decompose(self):
        self.assertFalse(self.c.should_decompose('读取 config.py'))
        self.assertTrue(self.c.should_decompose('修改 foo.py'))
        self.assertTrue(self.c.should_decompose('重构认证模块'))


class TestTaskNode(unittest.TestCase):
    def setUp(self):
        from agent_system.agent_decompose import TaskNode

        self.root = TaskNode('root', '根任务')

    def test_add_child(self):
        from agent_system.agent_decompose import TaskNode

        child = TaskNode('root.0', '子任务')
        self.root.add_child(child)
        self.assertEqual(len(self.root.children), 1)
        self.assertEqual(child.parent, self.root)

    def test_is_leaf(self):
        self.assertTrue(self.root.is_leaf())
        from agent_system.agent_decompose import TaskNode

        self.root.add_child(TaskNode('root.0', '子'))
        self.assertFalse(self.root.is_leaf())

    def test_to_dict(self):
        d = self.root.to_dict()
        self.assertEqual(d['id'], 'root')
        self.assertEqual(d['description'], '根任务')
        self.assertEqual(d['status'], 'pending')
        self.assertEqual(d['children'], [])

    def test_to_dict_with_children(self):
        from agent_system.agent_decompose import TaskNode

        child = TaskNode('root.0', '子任务')
        child.result_summary = '子结果'
        self.root.add_child(child)
        d = self.root.to_dict()
        self.assertEqual(len(d['children']), 1)
        self.assertEqual(d['children'][0]['result'], '子结果')

    def test_context_budget_default(self):
        self.assertEqual(self.root.context_budget, 2000)

    def test_created_at(self):
        self.assertGreater(self.root.created_at, 0)


class TestBoundedContext(unittest.TestCase):
    def setUp(self):
        from agent_system.agent_decompose import BoundedContext

        self.ctx = BoundedContext(budget=100)

    def test_build_basic(self):
        self.ctx.set_task('测试任务')
        result = self.ctx.build()
        self.assertIn('任务: 测试任务', result)

    def test_build_with_extras(self):
        self.ctx.set_task('任务')
        self.ctx.add_extra('额外信息')
        result = self.ctx.build()
        self.assertIn('额外信息', result)

    def test_build_with_tool_results(self):
        self.ctx.set_task('任务')
        self.ctx.add_tool_result('结果1')
        self.ctx.add_tool_result('结果2')
        result = self.ctx.build()
        self.assertIn('工具结果:', result)
        self.assertIn('结果2', result)

    def test_build_tool_results_limit(self):
        self.ctx.set_task('任务')
        for i in range(10):
            self.ctx.add_tool_result(f'结果{i}')
        result = self.ctx.build()
        self.assertIn('结果9', result)
        self.assertNotIn('结果0', result)

    def test_build_truncation(self):
        self.ctx.set_task('x' * 5000)
        result = self.ctx.build()
        self.assertIn('截断', result)

    def test_token_count(self):
        self.ctx.set_task('hello world')
        count = self.ctx.token_count()
        self.assertGreater(count, 0)
        self.assertEqual(count, len(self.ctx.build()) // 2)


class TestDecompositionEngine(unittest.TestCase):
    def setUp(self):
        from agent_system.agent_decompose import DecompositionEngine

        self.mock_agent = MagicMock()
        self.mock_agent._run_single_task.return_value = '执行结果'
        self.de = DecompositionEngine(MagicMock(return_value='子任务1\n子任务2'), self.mock_agent)

    def test_run_simple_task(self):
        from agent_system.agent_decompose import DecompositionEngine

        de = DecompositionEngine(MagicMock(return_value=''), self.mock_agent)
        de.run('读取 config.py')
        self.mock_agent._run_single_task.assert_called()

    def test_run_complex_task(self):
        from agent_system.agent_decompose import DecompositionEngine

        mock_agent = MagicMock()
        mock_agent._run_single_task.return_value = '执行结果'
        de = DecompositionEngine(MagicMock(return_value='子任务1\n子任务2'), mock_agent)
        # Task must be > 200 chars to trigger decomposition
        long_task = '重构认证模块的多个文件，包括修改和测试' * 20
        result = de.run(long_task)
        self.assertIn('[', result)

    def test_decompose(self):
        from agent_system.agent_decompose import TaskNode

        node = TaskNode('root', '重构认证模块的多个文件，包括修改和测试')
        subtasks = self.de._decompose(node)
        self.assertEqual(len(subtasks), 2)

    def test_decompose_error(self):
        from agent_system.agent_decompose import DecompositionEngine, TaskNode

        de = DecompositionEngine(MagicMock(side_effect=Exception('LLM错误')), self.mock_agent)
        node = TaskNode('root', '重构认证模块的多个文件')
        subtasks = de._decompose(node)
        self.assertEqual(subtasks, [])

    def test_execute_leaf_success(self):
        from agent_system.agent_decompose import TaskNode

        node = TaskNode('root', '读取配置')
        self.de._execute_leaf(node)
        self.assertEqual(node.status, 'done')

    def test_execute_leaf_failure(self):
        from agent_system.agent_decompose import DecompositionEngine, TaskNode

        mock_agent = MagicMock()
        mock_agent._run_single_task.side_effect = Exception('执行错误')
        de = DecompositionEngine(MagicMock(), mock_agent)
        node = TaskNode('root', '任务')
        de._execute_leaf(node)
        self.assertEqual(node.status, 'failed')
        self.assertIn('执行失败', node.result_summary)

    def test_merge_children(self):
        from agent_system.agent_decompose import TaskNode

        root = TaskNode('root', '任务')
        c1 = TaskNode('root.0', '子1')
        c1.result_summary = '结果1'
        c2 = TaskNode('root.1', '子2')
        c2.result_summary = '结果2'
        root.add_child(c1)
        root.add_child(c2)
        self.de._merge_children(root)
        self.assertIn('结果1', root.result_summary)
        self.assertIn('结果2', root.result_summary)
        self.assertEqual(root.status, 'done')

    def test_merge_children_empty(self):
        from agent_system.agent_decompose import TaskNode

        root = TaskNode('root', '任务')
        self.de._merge_children(root)
        self.assertEqual(root.result_summary, '')

    def test_max_depth(self):
        from agent_system.agent_decompose import DecompositionEngine, TaskNode

        de = DecompositionEngine(MagicMock(return_value='子任务\n子任务2'), self.mock_agent)
        node = TaskNode('root', 'x' * 300)
        de._process(node, depth=3)
        self.mock_agent._run_single_task.assert_called()


# ═══════════════════════════════════════════════════════════
# Phase 1: agent_hypothesis.py
# ═══════════════════════════════════════════════════════════


class TestFailureMode(unittest.TestCase):
    def test_enum_values(self):
        from agent_system.agent_hypothesis import FailureMode

        self.assertEqual(FailureMode.SUCCESS.value, 'ok')
        self.assertEqual(FailureMode.EMPTY_RESULT.value, 'empty')
        self.assertEqual(FailureMode.TOOL_MISSING.value, 'missing')
        self.assertEqual(FailureMode.SCHEMA_ERROR.value, 'schema')
        self.assertEqual(FailureMode.TIMEOUT.value, 'timeout')
        self.assertEqual(FailureMode.LOGIC_ERROR.value, 'logic')
        self.assertEqual(FailureMode.LOGIC_LOOP.value, 'loop')
        self.assertEqual(FailureMode.UNKNOWN.value, 'unknown')

    def test_retry_strategy_keys(self):
        from agent_system.agent_hypothesis import RETRY_STRATEGY, FailureMode

        for mode in FailureMode:
            if mode != FailureMode.SUCCESS:
                self.assertIn(mode, RETRY_STRATEGY)


class TestFailureClassifier(unittest.TestCase):
    def setUp(self):
        from agent_system.agent_hypothesis import FailureClassifier

        self.fc = FailureClassifier()

    def test_success(self):
        from agent_system.agent_hypothesis import FailureMode

        self.assertEqual(self.fc.classify('analyze', {}, '函数列表...'), FailureMode.SUCCESS)

    def test_empty_none(self):
        from agent_system.agent_hypothesis import FailureMode

        self.assertEqual(self.fc.classify('x', {}, None), FailureMode.EMPTY_RESULT)

    def test_empty_string(self):
        from agent_system.agent_hypothesis import FailureMode

        self.assertEqual(self.fc.classify('x', {}, ''), FailureMode.EMPTY_RESULT)

    def test_not_found_en(self):
        from agent_system.agent_hypothesis import FailureMode

        self.assertEqual(self.fc.classify('x', {}, 'not found'), FailureMode.TOOL_MISSING)

    def test_not_found_cn(self):
        from agent_system.agent_hypothesis import FailureMode

        self.assertEqual(self.fc.classify('x', {}, '未找到目标'), FailureMode.TOOL_MISSING)

    def test_schema_error(self):
        from agent_system.agent_hypothesis import FailureMode

        self.assertEqual(self.fc.classify('x', {}, 'missing argument'), FailureMode.SCHEMA_ERROR)
        self.assertEqual(self.fc.classify('x', {}, '格式错误'), FailureMode.SCHEMA_ERROR)
        self.assertEqual(self.fc.classify('x', {}, '参数不对'), FailureMode.SCHEMA_ERROR)

    def test_timeout(self):
        from agent_system.agent_hypothesis import FailureMode

        self.assertEqual(self.fc.classify('x', {}, 'timeout'), FailureMode.TIMEOUT)
        self.assertEqual(self.fc.classify('x', {}, '请求超时'), FailureMode.TIMEOUT)

    def test_logic_error_test_fail(self):
        from agent_system.agent_hypothesis import FailureMode

        self.assertEqual(self.fc.classify('run_test', {}, 'FAIL test_foo'), FailureMode.LOGIC_ERROR)

    def test_logic_error_replace_not_found(self):
        from agent_system.agent_hypothesis import FailureMode

        # replace_in_file with '未找到' is TOOL_MISSING (checked first)
        self.assertEqual(self.fc.classify('replace_in_file', {}, '未找到'), FailureMode.TOOL_MISSING)

    def test_logic_error_analyze(self):
        from agent_system.agent_hypothesis import FailureMode

        self.assertEqual(self.fc.classify('analyze', {}, '分析错误'), FailureMode.LOGIC_ERROR)

    def test_logic_error_keyword(self):
        from agent_system.agent_hypothesis import FailureMode

        self.assertEqual(self.fc.classify('x', {}, 'error occurred'), FailureMode.LOGIC_ERROR)
        self.assertEqual(self.fc.classify('x', {}, '执行错误'), FailureMode.LOGIC_ERROR)
        self.assertEqual(self.fc.classify('x', {}, '操作失败'), FailureMode.LOGIC_ERROR)

    def test_loop_detection(self):
        from agent_system.agent_hypothesis import FailureMode

        for _ in range(3):
            mode = self.fc.classify('foo', {}, 'same result')
        self.assertEqual(mode, FailureMode.LOGIC_LOOP)

    def test_no_loop_different_results(self):
        from agent_system.agent_hypothesis import FailureMode

        self.fc.classify('foo', {}, 'result1')
        self.fc.classify('foo', {}, 'result2')
        self.fc.classify('foo', {}, 'result3')
        # 不同结果不触发循环
        self.assertNotEqual(self.fc.classify('foo', {}, 'result4'), FailureMode.LOGIC_LOOP)

    def test_looks_logically_wrong_analyze_error(self):
        self.assertTrue(self.fc._looks_logically_wrong('analyze', '分析错误'))
        self.assertFalse(self.fc._looks_logically_wrong('analyze', '分析完成'))


class TestDiversityController(unittest.TestCase):
    def setUp(self):
        from agent_system.agent_hypothesis import DiversityController, Hypothesis

        self.dc = DiversityController()
        self.H = Hypothesis

    def test_empty(self):
        self.assertEqual(self.dc.filter([]), [])

    def test_single(self):
        h = self.H(0, '方案A')
        self.assertEqual(self.dc.filter([h]), [h])

    def test_identical_keeps_highest(self):
        h1 = self.H(0, 'read config file')
        h2 = self.H(1, 'read config file')
        h1.confidence = 0.9
        h2.confidence = 0.5
        result = self.dc.filter([h1, h2])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].id, 0)

    def test_diverse_keeps_all(self):
        h1 = self.H(0, '修改 foo 函数')
        h2 = self.H(1, '运行 测试 验证')
        self.assertEqual(len(self.dc.filter([h1, h2])), 2)

    def test_three_two_similar(self):
        h1 = self.H(0, 'read config file port')
        h2 = self.H(1, 'read config file port')
        h3 = self.H(2, 'run test suite')
        h1.confidence = 0.9
        h2.confidence = 0.5
        result = self.dc.filter([h1, h2, h3])
        self.assertEqual(len(result), 2)


class TestThresholdTuner(unittest.TestCase):
    def setUp(self):
        from agent_system.agent_hypothesis import ThresholdTuner

        self.tt = ThresholdTuner()

    def test_default_thresholds(self):
        t = self.tt.fit()
        self.assertEqual(t['confidence_gap'], 0.3)
        self.assertEqual(t['step_gap'], 2)
        self.assertEqual(t['collapse_threshold'], 0.8)

    def test_record_round(self):
        self.tt.record_round({'method': 'rule'})
        self.assertEqual(len(self.tt.history), 1)

    def test_fit_with_enough_history(self):
        for i in range(25):
            self.tt.record_round({'method': 'llm', 'rule_wrong': True, 'a_conf': 0.8, 'b_conf': 0.3})
        t = self.tt.fit()
        self.assertIn('confidence_gap', t)
        self.assertIn('collapse_threshold', t)

    def test_fit_no_disagreements(self):
        for i in range(25):
            self.tt.record_round({'method': 'rule', 'rule_wrong': False})
        t = self.tt.fit()
        self.assertEqual(t['confidence_gap'], 0.3)


class TestHypothesis(unittest.TestCase):
    def setUp(self):
        from agent_system.agent_hypothesis import Hypothesis, FailureMode

        self.h = Hypothesis(0, '方案A', estimated_cost=3)
        self.FM = FailureMode

    def test_init(self):
        self.assertEqual(self.h.id, 0)
        self.assertEqual(self.h.confidence, 0.5)
        self.assertEqual(self.h.trit, 0)
        self.assertEqual(self.h.status, 'pending')
        self.assertEqual(self.h.estimated_cost, 3)
        self.assertEqual(self.h.tools_used, [])
        self.assertEqual(self.h.evidence, [])

    def test_update_success(self):
        self.h.update('tool1', 'ok', 1, 0.9, self.FM.SUCCESS)
        self.assertEqual(self.h.trit, 1)
        self.assertEqual(self.h.tools_used, ['tool1'])
        self.assertEqual(len(self.h.evidence), 1)

    def test_update_failure(self):
        self.h.update('tool1', 'fail', -1, 0.8, self.FM.LOGIC_ERROR)
        self.assertEqual(self.h.trit, -1)

    def test_update_uncertain(self):
        self.h.update('tool1', '?', 0, 0.4, self.FM.UNKNOWN)
        self.assertEqual(self.h.trit, 0)

    def test_collapse_score_empty(self):
        self.assertEqual(self.h.collapse_score(), 0.0)

    def test_collapse_score_all_positive(self):
        self.h.update('a', 'ok', 1, 0.9)
        self.h.update('b', 'ok', 1, 0.9)
        score = self.h.collapse_score()
        self.assertGreater(score, 0)

    def test_collapse_score_mixed(self):
        self.h.update('a', 'ok', 1, 0.9)
        self.h.update('b', 'fail', -1, 0.8)
        score = self.h.collapse_score()
        self.assertGreater(score, 0)

    def test_is_dead_low_confidence(self):
        self.h.confidence = 0.1
        self.assertTrue(self.h.is_dead())

    def test_is_dead_consecutive_fail(self):
        for _ in range(3):
            self.h.update('x', 'fail', -1, 0.5)
        self.assertTrue(self.h.is_dead())

    def test_not_dead(self):
        self.h.update('a', 'ok', 1, 0.9)
        self.h.update('b', 'ok', 1, 0.9)
        self.assertFalse(self.h.is_dead())

    def test_to_dict(self):
        d = self.h.to_dict()
        self.assertEqual(d['id'], 0)
        self.assertEqual(d['description'], '方案A')
        self.assertEqual(d['status'], 'pending')
        self.assertEqual(d['cost'], 3)


class TestHypothesisGenerator(unittest.TestCase):
    def setUp(self):
        from agent_system.agent_hypothesis import HypothesisGenerator

        self.hg = HypothesisGenerator()

    def test_generate_mock_llm(self):
        mock_llm = MagicMock(return_value='方案A | read_file\n方案B | search_code')
        hyps = self.hg.generate(mock_llm, '读取配置', None)
        self.assertGreater(len(hyps), 0)

    def test_generate_empty_llm(self):
        mock_llm = MagicMock(return_value='')
        hyps = self.hg.generate(mock_llm, '任务', None)
        self.assertEqual(len(hyps), 0)

    def test_generate_error_llm(self):
        mock_llm = MagicMock(side_effect=Exception('LLM错误'))
        hyps = self.hg.generate(mock_llm, '任务', None)
        self.assertGreaterEqual(len(hyps), 1)

    def test_build_hypothesis(self):
        h = self.hg._build_hypothesis({'description': '测试', 'tools': ['a', 'b']})
        self.assertEqual(h.description, '测试')
        self.assertEqual(h.estimated_cost, 2)

    def test_filter_by_dependency(self):
        plans = [{'description': 'A', 'tools': ['read_file', 'replace_in_file']}]
        result = self.hg._filter_by_dependency(plans)
        self.assertEqual(len(result), 1)

    def test_filter_by_dependency_invalid(self):
        plans = [{'description': 'A', 'tools': ['replace_in_file']}]
        result = self.hg._filter_by_dependency(plans)
        self.assertEqual(len(result), 1)  # fallback to original

    def test_filter_by_capability(self):
        plans = [{'description': '修改文件', 'tools': ['read_file', 'replace_in_file']}]
        result = self.hg._filter_by_capability('修改文件', plans)
        self.assertEqual(len(result), 1)


class TestTournament(unittest.TestCase):
    def setUp(self):
        from agent_system.agent_hypothesis import Tournament, Hypothesis

        self.T = Tournament
        self.H = Hypothesis

    def test_empty(self):
        self.assertIsNone(self.T().run([], '任务', None))

    def test_single(self):
        h = self.H(0, '方案')
        self.assertEqual(self.T().run([h], '任务', None).id, 0)

    def test_two_confidence_gap(self):
        h1 = self.H(0, 'A')
        h1.confidence = 0.9
        h2 = self.H(1, 'B')
        h2.confidence = 0.1
        result = self.T().run([h1, h2], '任务', None)
        self.assertEqual(result.id, 0)

    def test_two_cost_gap(self):
        h1 = self.H(0, 'A', estimated_cost=5)
        h1.confidence = 0.6
        h2 = self.H(1, 'B', estimated_cost=1)
        h2.confidence = 0.6
        result = self.T().run([h1, h2], '任务', None)
        self.assertEqual(result.id, 1)

    def test_llm_compare(self):
        mock_llm = MagicMock(return_value='A')
        h1 = self.H(0, 'A')
        h1.confidence = 0.5
        h1.estimated_cost = 2
        h2 = self.H(1, 'B')
        h2.confidence = 0.5
        h2.estimated_cost = 2
        t = self.T(llm_fn=mock_llm)
        result = t.run([h1, h2], '任务', None)
        self.assertEqual(result.id, 0)

    def test_llm_compare_b(self):
        mock_llm = MagicMock(return_value='B is better')
        h1 = self.H(0, 'A')
        h1.confidence = 0.5
        h1.estimated_cost = 2
        h2 = self.H(1, 'B')
        h2.confidence = 0.5
        h2.estimated_cost = 2
        t = self.T(llm_fn=mock_llm)
        result = t.run([h1, h2], '任务', None)
        self.assertEqual(result.id, 1)

    def test_llm_compare_error(self):
        mock_llm = MagicMock(side_effect=Exception('err'))
        h1 = self.H(0, 'A')
        h1.confidence = 0.5
        h1.estimated_cost = 2
        h2 = self.H(1, 'B')
        h2.confidence = 0.5
        h2.estimated_cost = 2
        t = self.T(llm_fn=mock_llm)
        result = t.run([h1, h2], '任务', None)
        self.assertIsNotNone(result)

    def test_fallback_equal(self):
        h1 = self.H(0, 'A')
        h1.confidence = 0.5
        h1.estimated_cost = 2
        h2 = self.H(1, 'B')
        h2.confidence = 0.5
        h2.estimated_cost = 2
        result = self.T().run([h1, h2], '任务', None)
        self.assertEqual(result.id, 0)

    def test_with_metrics(self):
        from agent_system.agent_resource import MetricsCollector

        m = MetricsCollector()
        h1 = self.H(0, 'A')
        h1.confidence = 0.9
        h2 = self.H(1, 'B')
        h2.confidence = 0.1
        t = self.T(metrics=m)
        t.run([h1, h2], '任务', None)
        self.assertGreater(m.total_compares, 0)

    def test_parallel_phase(self):
        mock_exec = MagicMock()
        h1 = self.H(0, 'A')
        h1.confidence = 0.9
        h2 = self.H(1, 'B')
        h2.confidence = 0.9
        mock_exec.advance.return_value = h1
        t = self.T()
        result = t._parallel_phase([h1, h2], mock_exec, None)
        self.assertEqual(len(result), 2)

    def test_parallel_phase_early_death(self):
        mock_exec = MagicMock()
        h = self.H(0, 'A')
        h.confidence = 0.05
        mock_exec.advance.return_value = h
        from agent_system.agent_resource import MetricsCollector

        m = MetricsCollector()
        t = self.T(metrics=m)
        # When all die, returns original candidates (survivors or candidates)
        result = t._parallel_phase([h], mock_exec, None)
        self.assertEqual(len(result), 1)
        self.assertEqual(h.status, 'discarded_early')
        self.assertEqual(m.early_deaths, 1)


class TestHypothesisExecutor(unittest.TestCase):
    def setUp(self):
        from agent_system.agent_hypothesis import HypothesisExecutor, FailureClassifier

        self.tools = {'read_file': MagicMock(return_value='内容'), 'analyze': MagicMock(return_value='分析')}
        self.exec = HypothesisExecutor(self.tools, FailureClassifier())

    def test_advance_success(self):
        from agent_system.agent_hypothesis import Hypothesis

        h = Hypothesis(0, 'read_file,analyze')
        from agent_system.agent_decompose import BoundedContext

        ctx = BoundedContext()
        ctx.set_task('test')
        self.exec.advance(h, ctx)
        self.assertEqual(len(h.tools_used), 1)

    def test_advance_no_tool(self):
        from agent_system.agent_hypothesis import Hypothesis

        h = Hypothesis(0, 'unknown_tool')
        from agent_system.agent_decompose import BoundedContext

        ctx = BoundedContext()
        ctx.set_task('test')
        self.exec.advance(h, ctx)
        self.assertLess(h.confidence, 0.5)

    def test_advance_error(self):
        from agent_system.agent_hypothesis import Hypothesis, HypothesisExecutor, FailureClassifier

        bad_tools = {'fail': MagicMock(side_effect=Exception('错误'))}
        exec = HypothesisExecutor(bad_tools, FailureClassifier())
        h = Hypothesis(0, 'fail')
        from agent_system.agent_decompose import BoundedContext

        ctx = BoundedContext()
        ctx.set_task('test')
        exec.advance(h, ctx)
        # When tool not found in tools dict, confidence is reduced
        self.assertLess(h.confidence, 0.5)

    def test_infer_tools(self):
        tools = self.exec._infer_tools('修改 foo.py')
        self.assertIsInstance(tools, list)


# ═══════════════════════════════════════════════════════════
# Phase 2: agent_resource.py
# ═══════════════════════════════════════════════════════════


class TestMetricsCollector(unittest.TestCase):
    def setUp(self):
        from agent_system.agent_resource import MetricsCollector

        self.m = MetricsCollector()

    def test_record_compare_rule(self):
        self.m.record_compare('rule')
        self.assertEqual(self.m.total_compares, 1)
        self.assertEqual(self.m.llm_compare_calls, 0)

    def test_record_compare_llm(self):
        self.m.record_compare('llm')
        self.assertEqual(self.m.llm_compare_calls, 1)

    def test_record_early_death(self):
        self.m.record_early_death()
        self.assertEqual(self.m.early_deaths, 1)

    def test_record_cache_hit(self):
        self.m.record_cache_hit()
        self.assertEqual(self.m.cache_hits, 1)

    def test_record_failure(self):
        self.m.record_failure('logic')
        self.m.record_failure('logic')
        self.assertEqual(self.m.failure_mode_counts['logic'], 2)

    def test_record_cost(self):
        self.m.record_cost(5.0, 7)
        self.assertEqual(self.m.predicted_cost, [5])
        self.assertEqual(self.m.actual_cost, [7])
        self.assertEqual(self.m.prediction_errors, [2.0])

    def test_report_basic(self):
        r = self.m.report()
        self.assertIn('假设总数', r)
        self.assertIn('早停数', r)

    def test_report_with_costs(self):
        self.m.record_cost(3.0, 5)
        r = self.m.report()
        self.assertIn('成本预测MAE', r)

    def test_report_with_failures(self):
        self.m.record_failure('logic')
        r = self.m.report()
        self.assertIn('失败分布', r)

    def test_save(self):
        self.m.record_cost(1.0, 2)
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            path = f.name
        try:
            self.m.log_path = path
            self.m.save()
            with open(path) as f:
                data = json.load(f)
            self.assertEqual(data['predicted_cost'], [1])
        finally:
            os.remove(path)


class TestSemanticCache(unittest.TestCase):
    def setUp(self):
        from agent_system.agent_resource import SemanticCache

        self.sc = SemanticCache()

    def test_store_and_lookup_exact(self):
        self.sc.store('read config file', 'port 8080')
        self.assertEqual(self.sc.lookup('read config file'), 'port 8080')

    def test_lookup_miss(self):
        self.assertIsNone(self.sc.lookup('completely different task'))

    def test_lookup_similar(self):
        self.sc.store('read config file to check port', '8080')
        self.assertIsNotNone(self.sc.lookup('read config file to check port'))

    def test_keyword_overlap(self):
        self.assertAlmostEqual(self.sc._keyword_overlap('a b c', 'a b c'), 1.0)
        self.assertAlmostEqual(self.sc._keyword_overlap('a b', 'c d'), 0.0)
        self.assertAlmostEqual(self.sc._keyword_overlap('', 'a'), 0.0)

    def test_store_overflow(self):
        from agent_system.agent_resource import SemanticCache

        sc = SemanticCache()
        sc.MAX_SIZE = 3
        for i in range(5):
            sc.store(f'task {i}', f'result {i}')
        self.assertEqual(len(sc._cache), 3)


class TestCostPredictor(unittest.TestCase):
    def setUp(self):
        from agent_system.agent_resource import CostPredictor

        self.cp = CostPredictor()

    def test_predict_no_history(self):
        self.assertEqual(self.cp.predict('任务', ['read_file']), 1)

    def test_predict_with_history(self):
        self.cp.record('读取 config', ['read_file'], 2)
        self.cp.record('读取 config', ['read_file'], 4)
        p = self.cp.predict('读取 config.py', ['read_file'])
        self.assertEqual(p, 3.0)

    def test_predict_no_similar(self):
        self.cp.record('short', ['a'], 1)
        # task_len=5 vs 120 → diff=115 > 50, so no similar
        p = self.cp.predict('a' * 120, ['a', 'b'])
        self.assertEqual(p, 2)

    def test_train(self):
        self.cp.train()  # no-op, just ensure no crash


class TestActionLog(unittest.TestCase):
    def test_add_action(self):
        from agent_system.agent_resource import ActionLog

        log = ActionLog('run1', '任务')
        log.add_action(0, 'read_file', 'foo.py', '内容', 0.9)
        self.assertEqual(len(log.actions), 1)
        self.assertEqual(log.actions[0]['tool'], 'read_file')

    def test_to_dict(self):
        from agent_system.agent_resource import ActionLog

        log = ActionLog('run1', '任务')
        d = log.to_dict()
        self.assertEqual(d['run_id'], 'run1')
        self.assertEqual(d['task'], '任务')
        self.assertEqual(d['actions'], [])


class TestReplayEngine(unittest.TestCase):
    def setUp(self):
        from agent_system.agent_resource import ReplayEngine

        self.re = ReplayEngine()

    def test_create_run(self):
        run_id = self.re.create_run('任务')
        self.assertIn(run_id, self.re.logs)

    def test_record_action_auto_create(self):
        self.re.record_action('new_run', 0, 'tool', 'args', 'result', 0.9)
        self.assertIn('new_run', self.re.logs)

    def test_replay_existing(self):
        run_id = self.re.create_run('任务')
        log = self.re.replay(run_id)
        self.assertIsNotNone(log)

    def test_replay_missing(self):
        self.assertIsNone(self.re.replay('nonexistent'))

    def test_diff_replay_same(self):
        id_a = self.re.create_run('A')
        self.re.record_action(id_a, 0, 'read_file', '', '', 0.9)
        id_b = self.re.create_run('B')
        self.re.record_action(id_b, 0, 'read_file', '', '', 0.9)
        self.assertEqual(self.re.diff_replay(id_a, id_b), '无差异')

    def test_diff_replay_different(self):
        id_a = self.re.create_run('A')
        self.re.record_action(id_a, 0, 'read_file', '', '', 0.9)
        id_b = self.re.create_run('B')
        self.re.record_action(id_b, 0, 'search_code', '', '', 0.8)
        diff = self.re.diff_replay(id_a, id_b)
        self.assertIn('read_file', diff)
        self.assertIn('search_code', diff)

    def test_diff_replay_missing(self):
        self.assertEqual(self.re.diff_replay('a', 'b'), '找不到运行记录')

    def test_diff_replay_length_mismatch(self):
        id_a = self.re.create_run('A')
        self.re.record_action(id_a, 0, 'a', '', '', 0.9)
        self.re.record_action(id_a, 1, 'b', '', '', 0.9)
        id_b = self.re.create_run('B')
        self.re.record_action(id_b, 0, 'a', '', '', 0.9)
        diff = self.re.diff_replay(id_a, id_b)
        self.assertIn('b', diff)


class TestResourceManager(unittest.TestCase):
    def setUp(self):
        from agent_system.agent_resource import ResourceManager

        self.rm = ResourceManager()

    def test_record_tool_use_success(self):
        self.rm.record_tool_use('read_file', True, 'config.py', 'ok')
        self.assertEqual(self.rm.tool_stats['read_file']['success'], 1)

    def test_record_tool_use_fail(self):
        self.rm.record_tool_use('read_file', False, 'config.py', 'logic')
        self.assertEqual(self.rm.tool_stats['read_file']['fail'], 1)

    def test_record_tool_use_module(self):
        self.rm.record_tool_use('x', False, 'mod1')
        self.assertEqual(self.rm.module_stats['mod1']['error_count'], 1)
        self.assertEqual(self.rm.module_stats['mod1']['total_count'], 1)

    def test_tool_reliability_unknown(self):
        self.assertEqual(self.rm.tool_reliability('unknown'), 0.7)

    def test_tool_reliability_known(self):
        self.rm.record_tool_use('x', True)
        rel = self.rm.tool_reliability('x')
        self.assertGreater(rel, 0)

    def test_get_unreliable_tools(self):
        for _ in range(5):
            self.rm.record_tool_use('bad', False)
        self.assertIn('bad', self.rm.get_unreliable_tools(0.5))

    def test_check_tokens_ok(self):
        self.assertTrue(self.rm.check_tokens(100))

    def test_check_tokens_overflow(self):
        self.rm.spend_tokens(6900)
        self.assertFalse(self.rm.check_tokens(200))

    def test_spend_tokens(self):
        self.rm.spend_tokens(100)
        self.assertEqual(self.rm.total_tokens, 100)
        self.assertEqual(self.rm.call_count, 1)

    def test_get_experience_context_tool(self):
        self.rm.record_tool_use('read_file', True)
        ctx = self.rm.get_experience_context(tool='read_file')
        self.assertIn('read_file', ctx)

    def test_get_experience_context_empty(self):
        self.assertEqual(self.rm.get_experience_context(), '')

    def test_save_load(self):
        self.rm.record_tool_use('test_tool', True)
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            path = f.name
        try:
            self.rm.save(path)
            rm2 = type(self.rm)()
            rm2.load(path)
            self.assertIn('test_tool', rm2.tool_stats)
        finally:
            os.remove(path)

    def test_save_error(self):
        self.rm.save('/nonexistent/path/file.json')

    def test_load_error(self):
        self.rm.load('/nonexistent/path/file.json')


# ═══════════════════════════════════════════════════════════
# 集成测试
# ═══════════════════════════════════════════════════════════


class TestAgentRuntimeV5Integration(unittest.TestCase):
    def setUp(self):
        from agent_system.agent_runtime import AgentRuntime
        from evaluator import SanyanEvaluator

        ev = SanyanEvaluator()
        self.runtime = AgentRuntime(ev, None)
        self.runtime.register('analyze', lambda p, d: f'{p}: 100行')
        self.runtime.register('read_file', lambda p, d: '内容')
        self.runtime.register('search_code', lambda p, d: '搜索')
        self.runtime.register('replace_in_file', lambda p, d: '已替换')
        self.runtime.register('run_test', lambda p, d: '通过')

    def test_all_components_exist(self):
        self.assertIsNotNone(self.runtime.resource)
        self.assertIsNotNone(self.runtime.tool_graph)
        self.assertIsNotNone(self.runtime.hypothesis_generator)
        self.assertIsNotNone(self.runtime.tournament)
        self.assertIsNotNone(self.runtime.failure_classifier)
        self.assertIsNotNone(self.runtime.decomposition_engine)

    def test_force_tool_analyze(self):
        result = self.runtime._force_tool('读取 run_agent.py 的函数')
        self.assertIsNotNone(result)
        self.assertEqual(result[0], 'analyze')

    def test_force_tool_find_symbol(self):
        result = self.runtime._force_tool('查找 main 在哪里被引用')
        self.assertIsNotNone(result)
        self.assertEqual(result[0], 'find_symbol')

    def test_force_tool_none(self):
        result = self.runtime._force_tool('随便什么')
        self.assertIsNone(result)

    def test_extract_module(self):
        self.assertEqual(self.runtime._extract_module('foo.py|old|new'), 'foo')
        self.assertEqual(self.runtime._extract_module(''), '')

    def test_fail_closed(self):
        self.assertTrue(self.runtime._fail_closed('write_file', 'rm -rf /', False))
        self.assertFalse(self.runtime._fail_closed('read_file', 'foo.py', False))


if __name__ == '__main__':
    unittest.main()
