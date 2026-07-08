"""FFI 层 A（Python 进程内桥）M1 地基守护——RFC docs/ffi_plan.md §3.8 清单，全部不依赖网络。

单测直呼算子实现函数：假 evaluator 的 eval 为恒等（入参已是值）。
"""

import types

import pytest

import ops.py_bridge_ops as pb
from core.ternary_core import TritValue
from core.values import SanyanRuntimeError

_EV = types.SimpleNamespace(eval=lambda a: a)


@pytest.fixture(autouse=True)
def _ffi_on(monkeypatch):
    monkeypatch.setenv('SANYAN_FFI', '1')
    pb._reset_for_tests()
    yield
    pb._reset_for_tests()


# ── §3.8-1 封送往返 ──────────────────────────────────────────────────────────


def test_marshal_bool_none_to_trits():
    assert pb._to_sanyan(True).to_int() == 1
    assert pb._to_sanyan(False).to_int() == -1
    assert pb._to_sanyan(None).to_int() == 0


def test_marshal_scalars_passthrough():
    assert pb._to_sanyan(42) == 42
    assert pb._to_sanyan(3.5) == 3.5
    assert pb._to_sanyan('中文') == '中文'
    assert pb._to_sanyan(b'\xe4\xb8\xad') == '中'  # bytes → utf-8 串（阶段1从简）


def test_marshal_shallow_container_deep_becomes_handle():
    out = pb._to_sanyan([1, 'a', [2, 3]])
    assert out[0] == 1 and out[1] == 'a'
    assert pb._is_handle(out[2])  # 深容器 → 句柄（只转一层）
    d = pb._to_sanyan({'k': 1, 'nest': {'x': 2}})
    assert d['k'] == 1 and pb._is_handle(d['nest'])
    assert pb._is_handle(pb._to_sanyan({1: 'nonstr-key'}))  # 非 str 键字典整体句柄


def test_marshal_inbound_numeric_passthrough_and_deep():
    # 入参方向数值直通：真→1 假→-1 可能→0（语言层"真即1"，RFC 开放问题#8 记录偏差）
    assert pb._to_python(TritValue(1)) == 1
    assert pb._to_python(TritValue(-1)) == -1
    assert pb._to_python(TritValue(0)) == 0
    assert pb._to_python([TritValue(1), 'x', {'k': TritValue(-1)}]) == [1, 'x', {'k': -1}]


def test_marshal_handle_roundtrip_zero_copy():
    obj = object()
    h = pb._wrap_handle(obj)
    assert pb._to_python(h) is obj  # 句柄解回原对象——零拷贝管道


# ── §3.8-2 信封 ─────────────────────────────────────────────────────────────


def test_import_ok_envelope_and_idempotent():
    env = pb._py_import(_EV, ['json'])
    assert env['判'].to_int() == 1 and env['源'] == 'python'
    assert pb._is_handle(env['值'])
    env2 = pb._py_import(_EV, ['json'])
    assert env2['值']['__py_handle__'] == env['值']['__py_handle__']  # 幂等同句柄


def test_import_missing_module_fails_closed():
    env = pb._py_import(_EV, ['绝不存在的模块xyz'])
    assert env['判'].to_int() == -1 and 'Error' in env['错']


def test_getattr_call_pipeline():
    j = pb._py_import(_EV, ['json'])['值']
    dumps = pb._py_getattr(_EV, [j, 'dumps'])
    assert dumps['判'].to_int() == 1 and pb._is_handle(dumps['值'])
    out = pb._py_call(_EV, [dumps['值'], {'a': 1}])
    assert out['判'].to_int() == 1 and out['值'] == '{"a": 1}'


def test_call_exception_becomes_false_envelope():
    j = pb._py_import(_EV, ['json'])['值']
    loads = pb._py_getattr(_EV, [j, 'loads'])['值']
    env = pb._py_call(_EV, [loads, '不是json'])
    assert env['判'].to_int() == -1 and 'JSONDecodeError' in env['错']


def test_getitem_semantics():
    j = pb._py_import(_EV, ['json'])['值']
    loads = pb._py_getattr(_EV, [j, 'loads'])['值']
    lst = pb._py_call(_EV, [loads, '[10, 20]'])['值']
    assert lst == [10, 20]  # 浅列表直接封送，无需 py项
    env = pb._py_getitem(_EV, [pb._wrap_handle({'x': 7}), 'x'])
    assert env['判'].to_int() == 1 and env['值'] == 7


def test_python_false_return_is_payload_not_verdict():
    # 判定通道与载荷通道分离：Python 返回 False → 判=真、值=假（TritValue -1）
    j = pb._py_import(_EV, ['json'])['值']
    loads = pb._py_getattr(_EV, [j, 'loads'])['值']
    env = pb._py_call(_EV, [loads, 'false'])
    assert env['判'].to_int() == 1
    assert isinstance(env['值'], TritValue) and env['值'].to_int() == -1


# ── §3.8-2 解包互操作（含裸 TritValue 回归钉）──────────────────────────────


def test_unwrap_envelope_three_branches():
    from ops.ternary_container_ops import _unwrap

    ok = pb._envelope(1, value='载荷')
    assert _unwrap(_EV, [ok]) == '载荷'

    bad = pb._fail('ImportError: nope')
    with pytest.raises(SanyanRuntimeError, match='ImportError'):
        _unwrap(_EV, [bad])

    maybe = pb._envelope(0, err='timeout')
    assert _unwrap(_EV, [maybe, '默认']) == '默认'
    with pytest.raises(SanyanRuntimeError, match='可能'):
        _unwrap(_EV, [maybe])


def test_unwrap_bare_tritvalue_unchanged():
    from ops.ternary_container_ops import _unwrap

    v = TritValue(1, confidence=0.9)
    assert _unwrap(_EV, [v]) is v  # 裸 TritValue 行为不变（回归钉）
    with pytest.raises(SanyanRuntimeError):
        _unwrap(_EV, [TritValue(-1)])


def test_unwrap_or_envelope():
    from ops.ternary_container_ops import _unwrap_or

    assert _unwrap_or(_EV, [pb._envelope(1, value=5), 0]) == 5
    assert _unwrap_or(_EV, [pb._fail('x'), '备胎']) == '备胎'


def test_envelope_verdict_op():
    env = pb._fail('x', conf=0.9)
    j = pb._envelope_verdict(_EV, [env])
    assert isinstance(j, TritValue) and j.to_int() == -1


# ── §3.8-3 句柄 ─────────────────────────────────────────────────────────────


def test_release_idempotent_and_cache_invalidated():
    env = pb._py_import(_EV, ['json'])
    h = env['值']
    assert pb._py_release(_EV, [h]).to_int() == 1
    assert pb._py_release(_EV, [h]).to_int() == 1  # 重复释放幂等
    env2 = pb._py_import(_EV, ['json'])  # 缓存信封已失效 → 新句柄，不复活死句柄
    assert env2['值']['__py_handle__'] != h['__py_handle__']
    assert pb._py_getattr(_EV, [h, 'dumps'])['判'].to_int() == -1  # 死句柄按假拒


def test_handle_cap_reports_leak(monkeypatch):
    monkeypatch.setattr(pb, '_MAX_HANDLES', 0)
    env = pb._py_import(_EV, ['string'])
    assert env['判'].to_int() == -1 and '超上限' in env['错']


def test_list_handles_for_debugging():
    pb._py_import(_EV, ['json'])
    out = pb._py_list_handles(_EV, [])
    assert len(out) == 1 and 'json' in out[0]


# ── §3.8-4 门控 + 沙箱 ──────────────────────────────────────────────────────


def test_gate_capability_ops_fail_closed(monkeypatch):
    monkeypatch.delenv('SANYAN_FFI', raising=False)
    for fn, args in (
        (pb._py_import, ['json']),
        (pb._py_getattr, [{'__py_handle__': 1}, 'x']),
        (pb._py_call, [{'__py_handle__': 1}]),
        (pb._py_getitem, [{'__py_handle__': 1}, 0]),
    ):
        env = fn(_EV, args)
        assert env['判'].to_int() == -1 and 'FFI 未启用' in env['错']


def test_ops_registered_and_sandboxable():
    from core import sandbox
    from ops.registry import has_op

    for name in ('py导入', 'py取', 'py调', 'py项', 'py列', 'py释', '信封判'):
        assert has_op(name), name
    try:
        sandbox.restrict(ops=['py导入'])
        with pytest.raises(SanyanRuntimeError, match='沙箱'):
            sandbox.check_op('py导入')
    finally:
        sandbox.unblock()


# ── §3.8-5 回调禁止 ─────────────────────────────────────────────────────────


def test_callback_rejected_fail_closed():
    class FunctionValue:  # 与三言函数值同名——按类型名判定（避免循环导入）
        pass

    j = pb._py_import(_EV, ['json'])['值']
    dumps = pb._py_getattr(_EV, [j, 'dumps'])['值']
    env = pb._py_call(_EV, [dumps, FunctionValue()])
    assert env['判'].to_int() == -1 and '回调暂不支持' in env['错']


# ── §3.7 差分排除（跳过可见）────────────────────────────────────────────────


def test_differential_skips_ffi_cases_visibly():
    from agent_system.agent_evolution import DifferentialVerifier

    v = DifferentialVerifier()
    report = v.verify_consistency([{'input': '(输出 (py导入 "json"))', 'expected': ''}])
    assert report['total'] == 0 and report['skipped_ffi'] == 1  # 不进差分且计数可见


# ── §1 后端矩阵：编译路径显式报错（M2）──────────────────────────────────────


def test_compiler_rejects_ffi_ops_explicitly(tmp_path):
    # 字节码/LLVM 后端没有进程内 Python 运行时——编译期显式报错，绝不静默吞掉
    from compiler.compile_bytecode import compile_source
    from core.values import SanyanSyntaxError

    with pytest.raises(SanyanSyntaxError, match='仅解释器路径支持'):
        compile_source('(输出 (解包 (py导入 "json")))', str(tmp_path / 'x.bin'))


def test_compiler_allows_ffi_name_as_string_data(tmp_path):
    # 只查算子位（列表头）：字符串数据里出现 "py导入" 不误伤
    from compiler.compile_bytecode import compile_source

    ok, size, _ = compile_source('(输出 "py导入 是算子名")', str(tmp_path / 'y.bin'))
    assert (ok.to_int() if hasattr(ok, 'to_int') else ok) == 1  # 编译器返回 TritValue
    assert (size.to_int() if hasattr(size, 'to_int') else size) > 0


# ── 真实求值器全链路（注册表/分派/解包互操作，不走子进程）───────────────────


def test_real_evaluator_end_to_end_json():
    from core.evaluator import SanyanEvaluator
    from core.lexer import tokenize
    from core.parser import parse_program

    env = SanyanEvaluator()
    src = '(设 j (解包 (py导入 "json")))\n(设 d (解包 (py取 j "dumps")))\n(解包 (py调 d (字典 "a" 1)))'
    result = None
    for form in parse_program(tokenize(src), src):
        result = env.eval(form)
    assert result == '{"a": 1}'


def test_real_evaluator_gate_off_is_teachable(monkeypatch):
    # 未开 SANYAN_FFI：解包信封给出可读安全拒绝（教学一致性），不是裸 traceback
    from core.evaluator import SanyanEvaluator
    from core.lexer import tokenize
    from core.parser import parse_program
    from core.values import SanyanRuntimeError

    monkeypatch.delenv('SANYAN_FFI', raising=False)
    env = SanyanEvaluator()
    (form,) = parse_program(tokenize('(解包 (py导入 "json"))'), '')
    with pytest.raises(SanyanRuntimeError, match='FFI 未启用'):
        env.eval(form)
