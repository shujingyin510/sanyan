"""学习存储读写往返 + LearningHandler 单一写入路径测试。

阶段 4（学习/记忆存储合并）的前置守护：在把 AgentRuntime 里重复的 _save_experience /
_learn_from_task 收敛到 LearningHandler 之前，先锁住 ExperienceStore 的读路径与
LearningHandler 的写行为，确保收敛是行为保持的。
"""

import os

from agent_system.agent_learning import AdaptiveToolSelector, ExperienceStore
from agent_system.agent_learning_handler import LearningHandler


def _store(tmp_path):
    return ExperienceStore(db_path=os.path.join(str(tmp_path), 'exp.db'))


def test_tool_reliability_roundtrip(tmp_path):
    store = _store(tmp_path)
    store.record_tool_use('read_file', True, 0.1)
    store.record_tool_use('read_file', True, 0.1)
    store.record_tool_use('read_file', False, 0.2)
    # 2 成功 / 3 总 ≈ 0.667
    assert abs(store.get_tool_reliability('read_file') - 2 / 3) < 1e-6


def test_failure_pattern_roundtrip(tmp_path):
    store = _store(tmp_path)
    store.record_failure_pattern('replace_in_file', '未找到目标文本', 'logic_error')
    store.record_failure_pattern('replace_in_file', '未找到目标文本', 'logic_error')
    fps = store.get_failure_patterns('replace_in_file')
    assert fps and fps[0]['tool'] == 'replace_in_file'
    assert fps[0]['count'] >= 2  # 同一 (tool, error) 累加而非重复行


def test_similar_tasks_roundtrip(tmp_path):
    store = _store(tmp_path)
    store.record_task('修复登录bug', ['read_file', 'replace_in_file'], True, 1.0)
    sims = store.get_similar_tasks('修复登录bug')
    assert any('修复登录bug' == s['task'] for s in sims)


def test_handler_save_experience_uses_passed_memory(tmp_path):
    # LearningHandler 不再于构造时捕获 memory；按次传入的 memory 必须真正落库
    store = _store(tmp_path)
    handler = LearningHandler(experience_store=store, git_batch_learner=None, llm_call=lambda p: '')
    memory = {
        'history': [
            {'tool': 'read_file', 'trit': 1, 'duration': 0.1},
            {'tool': 'replace_in_file', 'trit': -1, 'duration': 0.2, 'result': '未找到'},
        ],
        'modified': ['x.py'],
    }
    handler.save_experience('修复bug', memory)
    # 写入可读回：read_file 可靠度记录在案
    assert store.get_tool_reliability('read_file') == 1.0
    # 失败模式落库
    assert store.get_failure_patterns('replace_in_file')


def test_record_outcome_does_not_count_tool_use(tmp_path):
    # 单一记录源：record_outcome 只更新推荐，不再累计 tool_use（避免与 save_experience 双记）
    store = _store(tmp_path)
    selector = AdaptiveToolSelector(store)
    # 调两次：满足 get_recommendations 的 usage_count>=2 过滤
    selector.record_outcome('fix bug', 'read_file', True, 0.1)
    selector.record_outcome('fix bug', 'read_file', True, 0.1)
    # tool_stats 未被写入 → 可靠度仍是默认 0.7（证明没记 tool_use）
    assert store.get_tool_reliability('read_file') == 0.7
    # 但推荐表确实更新了（kw 取自 task.lower().split()[:3]）
    recs = dict(store.get_recommendations('fix'))
    assert 'read_file' in recs


def test_save_experience_is_single_tool_use_source(tmp_path):
    # 端到端：同一次执行经 record_outcome + save_experience，tool_use 只应记一次
    store = _store(tmp_path)
    selector = AdaptiveToolSelector(store)
    handler = LearningHandler(experience_store=store, git_batch_learner=None, llm_call=lambda p: '')
    memory = {'history': [{'tool': 'write_file', 'trit': 1, 'duration': 0.1}], 'modified': ['x.py']}
    # 模拟主循环每步回调 + 收尾保存
    selector.record_outcome('写模块', 'write_file', True, 0.1)
    handler.save_experience('写模块', memory)
    # 仅 save_experience 记了 1 次成功 → 可靠度为 1.0（若双记仍是 1.0，故再查计数语义）
    assert store.get_tool_reliability('write_file') == 1.0
    # 关键：tool_stats 里 write_file 的 success 计数恰为 1（双记会是 2）
    import sqlite3

    conn = sqlite3.connect(store.db_path)
    success, fail = conn.execute('SELECT success, fail FROM tool_stats WHERE tool=?', ('write_file',)).fetchone()
    conn.close()
    assert (success, fail) == (1, 0)


def test_handler_lookup_style_no_file_is_safe(tmp_path):
    handler = LearningHandler(experience_store=_store(tmp_path), git_batch_learner=None, llm_call=lambda p: '')
    # 任务无匹配/无文件时返回空串，不抛
    assert isinstance(handler.lookup_style('随便什么任务'), str)
