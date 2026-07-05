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


def test_calls_undefined_helper_rejected(tmp_path):
    # 2026-07-04 尝试 2 回归钉：抽取的辅助函数被调用却从没定义——目标函数确实变短、
    # 过了 span 检查，旧实现放行、靠 pytest 花 ~1 分钟才报 NameError。现在秒毙。
    wd = _write(tmp_path, 'def big(x):\n    return _ternary_match_branch_loop(x)\n')
    v = make_shrink_oracle('mod.py', 'big', 10)(wd)
    assert not v.ok and '_ternary_match_branch_loop' in v.reason
    assert v.report.get('unresolved') == ['_ternary_match_branch_loop']


def test_calls_module_level_helper_passes(tmp_path):
    # 抽取正确落地：辅助函数在模块级定义并被调用——放行（真变短 + 引用可解析）。
    body = 'def _helper(x):\n    return x + 1\n\n\ndef big(x):\n    return _helper(x)\n'
    wd = _write(tmp_path, body)
    v = make_shrink_oracle('mod.py', 'big', 10)(wd)
    assert v.ok and '10 → 2' in v.reason


def test_calls_builtin_not_flagged(tmp_path):
    # 防误杀：调用 builtins 不算未解析。
    wd = _write(tmp_path, 'def big(xs):\n    return len(list(xs))\n')
    assert make_shrink_oracle('mod.py', 'big', 10)(wd).ok


def test_calls_local_binding_not_flagged(tmp_path):
    # 防误杀：函数内绑定的名字（Store）可解析。
    wd = _write(tmp_path, 'def big(x):\n    helper = abs\n    return helper(x)\n')
    assert make_shrink_oracle('mod.py', 'big', 10)(wd).ok


def test_star_import_skips_resolvability(tmp_path):
    # 防误杀：from x import * 无法静态推断绑定，跳过引用检查（仍走变短判定）。
    body = 'from os.path import *\n\n\ndef big(p):\n    return mystery_fn(p)\n'
    wd = _write(tmp_path, body)
    assert make_shrink_oracle('mod.py', 'big', 10)(wd).ok


def test_class_method_helper_called_as_bare_name_rejected(tmp_path):
    # 0705 第二轮实跑回归钉：agent 把辅助函数定义成类方法、又在目标方法里裸名调用——
    # 类体绑定对方法内裸名不可见（LEGB 无类作用域），必然 NameError。旧实现把全树
    # FunctionDef 名一律计入可解析而放行，靠 pytest 才炸；现在毫秒毙。
    body = (
        'class C:\n'
        '    @staticmethod\n'
        '    def _impl(x):\n'
        '        return x\n'
        '\n'
        '    @staticmethod\n'
        '    def big(x):\n'
        '        return _impl(x)\n'
    )
    wd = _write(tmp_path, body)
    v = make_shrink_oracle('mod.py', 'big', 10)(wd)
    assert not v.ok and '_impl' in v.reason


def test_class_method_helper_called_via_class_passes(tmp_path):
    # 防误杀：同样的类方法辅助函数，走 C._impl(x)（Attribute 调用）是正确写法——放行。
    body = (
        'class C:\n'
        '    @staticmethod\n'
        '    def _impl(x):\n'
        '        return x\n'
        '\n'
        '    @staticmethod\n'
        '    def big(x):\n'
        '        return C._impl(x)\n'
    )
    wd = _write(tmp_path, body)
    assert make_shrink_oracle('mod.py', 'big', 10)(wd).ok


def test_module_level_class_and_assign_resolve(tmp_path):
    # 防误杀：类名/模块级赋值名都是模块层绑定，方法内裸名调用可解析。
    body = (
        'handler = len\n\n\nclass Helper:\n    pass\n\n\ndef big(xs):\n    return Helper() if handler(xs) else None\n'
    )
    wd = _write(tmp_path, body)
    assert make_shrink_oracle('mod.py', 'big', 10)(wd).ok


def test_nested_function_sees_enclosing_locals(tmp_path):
    # 防误杀：目标函数嵌套在外层函数里时，外层局部（含外层定义的辅助函数）经闭包可见。
    body = 'def outer():\n    def helper(x):\n        return x\n\n    def big(x):\n        return helper(x)\n\n    return big\n'
    wd = _write(tmp_path, body)
    assert make_shrink_oracle('mod.py', 'big', 10)(wd).ok


def test_pick_task_by_substring():
    tasks = [
        MinedTask('long_function', 'a/x.py', 1, 'huge_fn', detail='100 行'),
        MinedTask('long_function', 'ops/control_ops.py', 308, 'ternary_match', detail='94 行'),
    ]
    assert pick_task(tasks, 'ternary').title == 'ternary_match'
    assert pick_task(tasks, 'a/x').title == 'huge_fn'
    assert pick_task(tasks, '不存在') is None
