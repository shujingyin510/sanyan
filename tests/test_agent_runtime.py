"""AgentRuntime V3 单元测试 — SymbolTable/MemoryStore/ProjectGraph/AgentRuntime"""

import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_system.agent_runtime import SymbolTable, MemoryStore, ProjectGraph, AgentRuntime


class TestSymbolTable(unittest.TestCase):
    def test_lookup_function(self):
        st = SymbolTable()
        result = st.lookup('main')
        self.assertIn('def', result)
        self.assertIn('ref', result)

    def test_lookup_unknown(self):
        st = SymbolTable()
        result = st.lookup('xyznonexistent123')
        self.assertEqual(len(result['def']), 0)

    def test_build_all(self):
        st = SymbolTable()
        st.build_all()
        result = st.lookup('main')
        self.assertGreaterEqual(len(result['def']), 1)

    def test_cache_hit(self):
        st = SymbolTable()
        st.lookup('main')
        self.assertIn('main', st._cache)


class TestMemoryStore(unittest.TestCase):
    def setUp(self):
        self.ms = MemoryStore()

    def test_add_and_context(self):
        self.ms.add('analyze', 'run_agent.py', '37函数, ⚠ >50行: main')
        ctx = self.ms.context('分析')
        self.assertIn('analyze', ctx)
        self.assertIn('⚠', ctx)

    def test_context_empty(self):
        ctx = self.ms.context('nothing')
        self.assertEqual(ctx, '')

    def test_keyword_relevance(self):
        self.ms.add('read_file', 'x.py', 'def main(): pass')
        self.ms.add('replace_in_file', 'y.py', '已替换 1 处')
        ctx = self.ms.context('main 函数', 2)
        self.assertIn('read_file', ctx)
        # replace_in_file 应该分更低，可能不在结果中
        ctx2 = self.ms.context('替换')
        self.assertIn('replace_in_file', ctx2)


class TestProjectGraph(unittest.TestCase):
    def test_build(self):
        pg = ProjectGraph()
        pg.build()
        deps = pg.depends_on('run_agent.py')
        self.assertIsInstance(deps, list)

    def test_idempotent_build(self):
        pg = ProjectGraph()
        pg.build()
        first = len(pg.deps)
        pg.build()
        self.assertEqual(len(pg.deps), first)


class TestAgentRuntime(unittest.TestCase):
    def setUp(self):
        # Mock evaluator
        class MockEval:
            def get_var(self, name):
                return {'模型名': 'deepseek-v4-pro', '模型URL': 'https://api.example.com', 'API密钥': 'sk-test'}.get(
                    name, ''
                )

            def has_var(self, name):
                return name in ('模型名', '模型URL', 'API密钥')

        self.ev = MockEval()
        self.rt = AgentRuntime(self.ev, None)
        self.rt.register('analyze', lambda p, d: '37函数, ⚠ >50行: main, init')
        self.rt.register('find_symbol', lambda p, d: '符号 main (23处):\nDEF run_agent.py:899')
        self.rt.register('read_file', lambda p, d: 'def main():...')
        self.rt.register('search_code', lambda p, d: 'run_agent.py:899: def main()')
        self.rt.register('replace_in_file', lambda p, d: '已替换 1 处')
        self.rt.register('replace_all', lambda p, d: '共替换 3 个文件')
        self.rt.register('run_test', lambda p, d: '通过 rc=0')
        self.rt.register('done', lambda p, d: p if p else '完成')
        self.rt.register('git_diff', lambda p, d: '(无修改)')
        self.rt.register('git_status', lambda p, d: '(干净)')
        # Mock LLM 调用：避免 CI 无网络时失败，模拟工具调用+done流程
        self._mock_llm_round = 0

        def mock_llm(prompt, override=None):
            self._mock_llm_round += 1
            if self._mock_llm_round == 1:
                if '超过50行' in str(prompt) or '哪些函数' in str(prompt):
                    return 'analyze|run_agent.py'
                if 'main' in str(prompt) and ('调用' in str(prompt) or '在哪' in str(prompt)):
                    return 'find_symbol|main'
            # 第2轮及以后：done，带第一轮工具结果
            if self.rt.memory.get('history'):
                last = self.rt.memory['history'][-1]
                return f'done|结果: {last.get("result", "完成")}'
            return 'done|任务已完成'

        self.rt._llm_call = mock_llm

    def test_force_tool_analyze(self):
        tool, params = self.rt._force_tool('这个文件有哪些函数')
        self.assertEqual(tool, 'analyze')

    def test_force_tool_find_symbol(self):
        tool, params = self.rt._force_tool('main在哪里被调用')
        self.assertEqual(tool, 'find_symbol')

    def test_force_tool_none(self):
        result = self.rt._force_tool('你好')
        self.assertIsNone(result)

    def test_parse_tool(self):
        tool, params = self.rt._parse_tool('analyze|run_agent.py')
        self.assertEqual(tool, 'analyze')
        self.assertEqual(params, 'run_agent.py')

    def test_parse_tool_done(self):
        tool, params = self.rt._parse_tool('done|任务完成')
        self.assertEqual(tool, 'done')

    def test_parse_tool_garbage(self):
        tool, params = self.rt._parse_tool('random noise')
        self.assertEqual(tool, 'random noise')

    def test_constraint_violation(self):
        self.rt.memory = {'same_tool_count': {}, 'modified': [], 'history': []}
        for i in range(5):
            self.rt._constraint_violation('read_file')
        result = self.rt._constraint_violation('read_file')  # 第6次触发
        self.assertTrue(result)

    def test_constraint_ok(self):
        self.rt.memory = {'same_tool_count': {}, 'modified': [], 'history': []}
        result = self.rt._constraint_violation('read_file')  # 第6次触发
        self.assertFalse(result)

    def test_build_context_init(self):
        ctx = self.rt._build_context('分析run_agent.py', 'init')
        self.assertIn('任务:', ctx)

    def test_build_context_result(self):
        self.rt.mem.add('analyze', 'run_agent.py', '37函数')
        ctx = self.rt._build_context('分析', 'analyze', '37函数')
        self.assertIn('analyze', ctx)

    def test_extract_key_warning(self):
        result = self.rt._extract_key('代码:\n⚠ >50行: main, init\ndef main...')
        self.assertIn('⚠', result)
        self.assertIn('main', result)

    def test_extract_key_replace(self):
        result = self.rt._extract_key('已替换 3 处 v0.3→v0.4')
        self.assertIn('已替换', result)

    def test_needs_plan(self):
        self.assertTrue(self.rt._needs_plan('把 run_agent.py 修改一下'))
        self.assertFalse(self.rt._needs_plan('你好'))

    def test_token_exceeded(self):
        self.assertFalse(self.rt._token_exceeded('short'))
        self.assertTrue(self.rt._token_exceeded('x' * 8000))

    def test_compress_ctx(self):
        long_ctx = '任务: 测试\n' + ('data line\n' * 500)
        result = self.rt._compress_ctx(long_ctx)
        self.assertLess(len(result), len(long_ctx))

    def test_fail_closed(self):
        self.assertTrue(self.rt._fail_closed('write_file', 'rm -rf /', False))
        self.assertFalse(self.rt._fail_closed('write_file', 'hello.txt|content', False))
        self.assertTrue(self.rt._fail_closed('write_file', 'rm -rf /', True))  # 干跑也拦截

    def test_run_analyze_auto(self):
        """完整 run() 流程：analyze 任务自动完成"""
        self._mock_llm_round = 0
        result = self.rt.run('run_agent.py哪些函数超过50行', max_rounds=2)
        self.assertIn('answer', result)
        self.assertIn('⚠', result['answer'])

    def test_run_find_symbol_auto(self):
        """find_symbol 任务自动完成"""
        self._mock_llm_round = 0
        result = self.rt.run('main在哪里被调用', max_rounds=2)
        self.assertIn('answer', result)
        self.assertIn('符号', result['answer'])


class TestAgentTools(unittest.TestCase):
    """agent_tools.py 独立单测"""

    def test_resolve_path_exists(self):
        from agent_system.agent_tools import _resolve_path_simple

        self.assertEqual(_resolve_path_simple('run_agent.py'), 'run_agent.py')

    def test_resolve_path_search(self):
        from agent_system.agent_tools import _resolve_path_simple

        resolved = _resolve_path_simple('agent_tools.py')
        self.assertTrue(resolved.endswith('agent_tools.py'))

    def test_analyze_file(self):
        from agent_system.agent_tools import _analyze_file_direct

        r = _analyze_file_direct('run_agent.py')
        self.assertIn('⚠ >50行:', r)
        self.assertIn('main()', r)

    def test_find_symbol(self):
        from agent_system.agent_tools import _find_symbol_direct

        r = _find_symbol_direct('main')
        self.assertIn('DEF', r)

    def test_read_file(self):
        from agent_system.agent_tools import _read_file_direct_simple

        r = _read_file_direct_simple('run_agent.py|1|3')
        self.assertIn('三言 Agent', r)

    def test_read_file_no_range(self):
        from agent_system.agent_tools import _read_file_direct_simple

        r = _read_file_direct_simple('run_agent.py')
        self.assertTrue(len(r) > 100)

    def test_search_code(self):
        from agent_system.agent_tools import _search_code_direct

        r = _search_code_direct('def main')
        self.assertIn('run_agent.py', r)

    def test_replace_in_file_dry(self):
        from agent_system.agent_tools import _replace_in_file_direct

        r = _replace_in_file_direct('run_agent.py|# 三言|# 三言|# Sanyan', dry_run=True)
        self.assertIn('[干跑]', r)

    def test_list_files(self):
        from agent_system.agent_tools import _list_files_direct_simple

        r = _list_files_direct_simple('*.py')
        self.assertIn('.py', r.lower())

    def test_git_diff(self):
        from agent_system.agent_tools import _git_diff_direct

        r = _git_diff_direct()
        self.assertIsInstance(r, str)

    def test_git_status(self):
        from agent_system.agent_tools import _git_status_direct

        r = _git_status_direct()
        self.assertIsInstance(r, str)

    def test_sandbox_path(self):
        from agent_system.agent_tools import _resolve_path_simple

        r = _resolve_path_simple('../../etc/passwd')
        self.assertNotIn('..', r)


if __name__ == '__main__':
    unittest.main()
