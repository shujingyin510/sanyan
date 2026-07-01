"""阶段三收尾：消灭 runtime 残存的文本嗅探 —— run_test 判定改读结构化 meta['passed']。

修掉的脆弱性（与 search_code('失败') 同一类）：成功结果的文本里恰好含 '失败'/'FAIL'
二字（搜索命中、日志回显、断言用例名）会被旧逻辑误判为测试失败 → 假重试 / 假降置信。
现由工具**自报** meta['passed'] 决定；旧式裸字符串仍回退文本嗅探（兼容规则/模板路径）。
"""

from agent_system.contracts import ToolResult, ToolStatus


def test_run_test_reports_passed_in_meta(tmp_path):
    from agent_system.agent_tools import _run_test_direct

    t = tmp_path / 'test_ok_case.py'
    t.write_text('def test_ok():\n    assert 1 == 1\n', encoding='utf-8')
    r = _run_test_direct({'test_file': str(t)})
    assert r.meta.get('passed') is True and r.ok

    t2 = tmp_path / 'test_bad_case.py'
    t2.write_text('def test_bad():\n    assert 1 == 2\n', encoding='utf-8')
    r2 = _run_test_direct({'test_file': str(t2)})
    assert r2.meta.get('passed') is False and r2.failed


def test_test_failed_reads_meta_not_text():
    from agent_system.agent_runtime import AgentRuntime

    # 关键保证：成功结果、但 data 文本里含 '失败' 二字 —— 绝不能判成失败
    ok_text_has_fail = ToolResult(ToolStatus.OK, data='搜索到 3 处 "失败" 关键字', meta={'passed': True})
    assert AgentRuntime._test_failed(ok_text_has_fail) is False

    failed = ToolResult(ToolStatus.ERROR, error='FAIL rc=1', meta={'passed': False})
    assert AgentRuntime._test_failed(failed) is True


def test_test_failed_status_fallback_when_no_meta():
    from agent_system.agent_runtime import AgentRuntime

    # 无 meta['passed']（如测试框架异常）→ 读结构化 status
    assert AgentRuntime._test_failed(ToolResult(ToolStatus.ERROR, error='测试错误: boom')) is True
    assert AgentRuntime._test_failed(ToolResult(ToolStatus.OK, data='通过 rc=0')) is False


def test_test_failed_legacy_string():
    from agent_system.agent_runtime import AgentRuntime

    # 旧式裸字符串仍回退文本嗅探
    assert AgentRuntime._test_failed('FAIL rc=1') is True
    assert AgentRuntime._test_failed('通过 rc=0') is False


def test_looks_logically_wrong_reads_meta():
    from agent_system.agent_hypothesis import FailureClassifier

    fc = FailureClassifier()
    ok = ToolResult(ToolStatus.OK, data='断言 "失败" 场景已覆盖', meta={'passed': True})
    assert fc._looks_logically_wrong('run_test', ok) is False
    bad = ToolResult(ToolStatus.ERROR, error='FAIL', meta={'passed': False})
    assert fc._looks_logically_wrong('run_test', bad) is True


def test_confidence_delta_direct_answer_shortcut():
    from agent_system.agent_runtime import AgentRuntime

    d = AgentRuntime._confidence_delta
    assert d({'ternary': '直接回答', 'answer': 'x' * 25}, {}) == 0.03  # 长答案 → 正
    assert d({'ternary': '直接回答', 'answer': 'x'}, {}) == -0.05  # 短答案 → 负


def test_confidence_delta_reads_structured_memory():
    """主循环无 'ternary' 键，改由结构化 memory（trit/modified/failures）驱动，不再恒 0 no-op。"""
    from agent_system.agent_runtime import AgentRuntime

    d = AgentRuntime._confidence_delta
    # 有文件产出、零失败 → 强正
    assert d({}, {'history': [{'trit': 1}], 'modified': ['a.py'], 'failures': 0}) == 0.05
    # 失败居多 → 负
    assert d({}, {'history': [{'trit': -1}, {'trit': -1}, {'trit': 1}], 'failures': 0}) == -0.10
    # 失败累计≥3 → 负
    assert d({}, {'history': [{'trit': 1}], 'failures': 3}) == -0.10
    # 偏正 / 模糊
    assert d({}, {'history': [{'trit': 1}, {'trit': 1}, {'trit': 0}]}) == 0.03
    assert d({}, {'history': [{'trit': 0}]}) == -0.02
    # 空历史 / 空 memory → 0（不再无脑动）
    assert d({}, {'history': []}) == 0.0
    assert d({}, {}) == 0.0
