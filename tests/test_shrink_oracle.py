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


_BASELINE = (
    'class C:\n'
    '    @staticmethod\n'
    '    def big(evaluator, args):\n'
    '        """老文档。"""\n'
    '        # 注释行\n'
    '        if len(args) < 2:\n'
    "            raise SanyanSyntaxError('需要值和至少一个分支')\n"
    '        val = evaluator.eval(args[0])\n'
    '        for i in range(0, len(val), 2):\n'
    '            result = evaluator.eval(val[i])\n'
    '        return result\n'
)


def test_rewrite_not_move_rejected(tmp_path):
    # 0705 第二轮真候选回归钉：变短、引用可解析，但把校验条件/异常类型改写了——
    # 守恒检查点名消失的原始行，毫秒毙，不再烧 pytest 才发现"重写而非搬运"。
    new = (
        'def _impl(evaluator, args):\n'
        '    if len(args) % 2 != 0:\n'
        "        raise ValueError('even required')\n"
        '    val = evaluator.eval(args[0])\n'
        '    for i in range(0, len(val), 2):\n'
        '        result = evaluator.eval(val[i])\n'
        '    return result\n'
        '\n'
        '\n'
        'class C:\n'
        '    @staticmethod\n'
        '    def big(evaluator, args):\n'
        '        return _impl(evaluator, args)\n'
    )
    wd = _write(tmp_path, new)
    v = make_shrink_oracle('mod.py', 'big', 10, baseline_source=_BASELINE)(wd)
    assert not v.ok and '重写而非搬运' in v.reason and 'SanyanSyntaxError' in v.reason
    assert any('len(args) < 2' in ln for ln in v.report['missing_lines'])


def test_true_move_passes_conservation(tmp_path):
    # 纯搬运：原函数体每一行原样存活（缩进变了不算），docstring/注释重写不追责——放行。
    new = (
        'def _impl(evaluator, args):\n'
        '    """新文档随便写。"""\n'
        '    if len(args) < 2:\n'
        "        raise SanyanSyntaxError('需要值和至少一个分支')\n"
        '    val = evaluator.eval(args[0])\n'
        '    for i in range(0, len(val), 2):\n'
        '        result = evaluator.eval(val[i])\n'
        '    return result\n'
        '\n'
        '\n'
        'class C:\n'
        '    @staticmethod\n'
        '    def big(evaluator, args):\n'
        '        return _impl(evaluator, args)\n'
    )
    wd = _write(tmp_path, new)
    v = make_shrink_oracle('mod.py', 'big', 10, baseline_source=_BASELINE)(wd)
    assert v.ok, v.reason


def test_no_baseline_source_skips_conservation(tmp_path):
    # 不传基线源码 → 守恒静默跳过（宽松方向），变短+可解析即放行。
    wd = _write(tmp_path, 'def big(x):\n    return x\n')
    assert make_shrink_oracle('mod.py', 'big', 10)(wd).ok


_DUP_BASELINE = (
    'class C:\n'
    '    @staticmethod\n'
    '    def big(evaluator, args):\n'
    '        matched = False\n'
    '        for a in args:\n'
    '            if evaluator.check(a):\n'
    '                matched = True\n'
    '            else:\n'
    '                matched = False\n'
    '        val = evaluator.eval(args[0])\n'
    '        return matched and val\n'
)


def test_deleted_duplicate_line_rejected(tmp_path):
    # 0707 第十三轮回归钉：守恒曾用集合成员判定——重复行留一份副本即有"不在场证明"
    # （ternary_match 内 matched = False ×3，压缩改写静态全过打进 pytest）。
    # 按整文件行计数后：删掉任何一份重复立即出现亏空，毫秒拒。
    new = (
        'def _impl(evaluator, args):\n'
        '    matched = False\n'
        '    for a in args:\n'
        '        if evaluator.check(a):\n'
        '            matched = True\n'
        '    val = evaluator.eval(args[0])\n'
        '    return matched and val\n'
        '\n'
        '\n'
        'class C:\n'
        '    @staticmethod\n'
        '    def big(evaluator, args):\n'
        '        return _impl(evaluator, args)\n'
    )
    wd = _write(tmp_path, new)
    v = make_shrink_oracle('mod.py', 'big', 10, baseline_source=_DUP_BASELINE)(wd)
    assert not v.ok and '重写而非搬运' in v.reason
    assert 'matched = False' in v.reason  # 亏空的正是被压缩掉的那份重复行


def test_true_move_with_duplicates_passes(tmp_path):
    # 两份重复原样搬进辅助函数 → 整文件计数不变，守恒放行
    new = (
        'def _impl(evaluator, args):\n'
        '    matched = False\n'
        '    for a in args:\n'
        '        if evaluator.check(a):\n'
        '            matched = True\n'
        '        else:\n'
        '            matched = False\n'
        '    val = evaluator.eval(args[0])\n'
        '    return matched and val\n'
        '\n'
        '\n'
        'class C:\n'
        '    @staticmethod\n'
        '    def big(evaluator, args):\n'
        '        return _impl(evaluator, args)\n'
    )
    wd = _write(tmp_path, new)
    v = make_shrink_oracle('mod.py', 'big', 10, baseline_source=_DUP_BASELINE)(wd)
    assert v.ok, v.reason


_PLAIN_BASELINE = 'def big(x):\n    y = x + 1\n    z = y * 2\n    return z\n'


def test_nested_def_diagnosed_when_not_shrunk(tmp_path):
    # 0706 第五轮尝试 1 回归钉：两步都做了，但辅助函数嵌套在原函数体内 → 反而变长。
    # 拒绝理由点名病灶（基线无嵌套时才提示），纠偏才有的放矢。
    new = (
        'def big(x):\n'
        '    def _helper(x):\n'
        '        y = x + 1\n'
        '        z = y * 2\n'
        '        return z\n'
        '\n'
        '    return _helper(x)\n'
    )
    wd = _write(tmp_path, new)
    v = make_shrink_oracle('mod.py', 'big', 4, baseline_source=_PLAIN_BASELINE)(wd)
    assert not v.ok and '未变短' in v.reason and '嵌套在目标函数内部' in v.reason


def test_nested_def_hint_suppressed_without_baseline(tmp_path):
    # 无基线（不知道原本有没有嵌套）→ 只报未变短，不给可能失真的病灶提示
    new = 'def big(x):\n    def _h():\n        return 1\n\n    return _h() + x\n'
    wd = _write(tmp_path, new)
    v = make_shrink_oracle('mod.py', 'big', 4)(wd)
    assert not v.ok and '未变短' in v.reason and '嵌套' not in v.reason


def test_paste_dump_diagnosed(tmp_path):
    # 0706 第七轮尝试 3 回归钉：+390/-0 整段重复粘贴——文件净增超过目标函数整体体量时
    # 点名"疑似整段重复粘贴"，纠偏不再开"两步都做完"的错药。
    dup = _PLAIN_BASELINE + '\n\n' + _PLAIN_BASELINE.replace('def big', 'def big_copy') * 3
    wd = _write(tmp_path, dup)
    v = make_shrink_oracle('mod.py', 'big', 4, baseline_source=_PLAIN_BASELINE)(wd)
    assert not v.ok and '疑似整段重复粘贴' in v.reason


def test_small_growth_not_flagged_as_paste(tmp_path):
    # 正常插入一个辅助函数（净增 < 函数体量）不误报大粘贴——只报未变短走两步纠偏
    new = 'def _h(x):\n    return x\n\n\n' + _PLAIN_BASELINE
    wd = _write(tmp_path, new)
    v = make_shrink_oracle('mod.py', 'big', 4, baseline_source=_PLAIN_BASELINE)(wd)
    assert not v.ok and '未变短' in v.reason and '粘贴' not in v.reason


def test_nested_def_hint_suppressed_when_baseline_had_nested(tmp_path):
    # 基线本就有嵌套 def → 不把既有结构误报成本次病灶
    baseline = 'def big(x):\n    def _old():\n        return 1\n\n    return _old() + x\n'
    wd = _write(tmp_path, baseline)  # 新版原样（等长 → 未变短）
    v = make_shrink_oracle('mod.py', 'big', 5, baseline_source=baseline)(wd)
    assert not v.ok and '未变短' in v.reason and '嵌套' not in v.reason


def test_pick_task_by_substring():
    tasks = [
        MinedTask('long_function', 'a/x.py', 1, 'huge_fn', detail='100 行'),
        MinedTask('long_function', 'ops/control_ops.py', 308, 'ternary_match', detail='94 行'),
    ]
    assert pick_task(tasks, 'ternary').title == 'ternary_match'
    assert pick_task(tasks, 'a/x').title == 'huge_fn'
    assert pick_task(tasks, '不存在') is None
