"""任务感知 oracle（P3 第一块）：long_function 重构必须真的变短 + --pick 选任务。

P2 首跑产物的直接教训回归钉：行为不变+测试全绿的半成品重构（辅助函数嵌套定义
且未被调用、目标函数 94→125 行反而变长）被通用 oracle 放行——通用 oracle 只判
"不退化"，判不了"有改进"。
"""

from agent_system.run_self_update import pick_task
from agent_system.self_update import make_shrink_oracle
from agent_system.task_mining import MinedTask


def _write(tmp_path, body):
    (tmp_path / 'mod.py').write_text(body, encoding='utf-8')
    return str(tmp_path)


def test_shrunk_function_passes(tmp_path):
    wd = _write(tmp_path, 'def big():\n    a = 1\n    return a\n')
    v = make_shrink_oracle('mod.py', 'big', 10)(wd)
    assert v.ok and '10 → 3' in v.reason


def test_not_shrunk_rejected(tmp_path):
    # P2 首跑半成品回归钉：行数没降（等长/变长）必须拒绝
    body = 'def big():\n' + '\n'.join(f'    x{i} = {i}' for i in range(11)) + '\n    return 0\n'
    wd = _write(tmp_path, body)
    v = make_shrink_oracle('mod.py', 'big', 10)(wd)
    assert not v.ok and '未变短' in v.reason


def test_missing_function_rejected_fail_closed(tmp_path):
    wd = _write(tmp_path, 'def other():\n    pass\n')
    v = make_shrink_oracle('mod.py', 'big', 10)(wd)
    assert not v.ok and '消失' in v.reason


def test_broken_file_rejected_fail_closed(tmp_path):
    wd = _write(tmp_path, 'def big(:\n')
    v = make_shrink_oracle('mod.py', 'big', 10)(wd)
    assert not v.ok and '不可解析' in v.reason


def test_pick_task_by_substring():
    tasks = [
        MinedTask('long_function', 'a/x.py', 1, 'huge_fn', detail='100 行'),
        MinedTask('long_function', 'ops/control_ops.py', 308, 'ternary_match', detail='94 行'),
    ]
    assert pick_task(tasks, 'ternary').title == 'ternary_match'
    assert pick_task(tasks, 'a/x').title == 'huge_fn'
    assert pick_task(tasks, '不存在') is None
