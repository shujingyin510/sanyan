"""FFI 层 B 在线半（c载入/c调/c释，M4-ctypes）守护。

活体测试用 gcc 把 tests/fixtures/mini.c 编成临时共享库——gcc 缺席整文件 skip
（沿用既有环境 skip 口径）；err 四惯例的判定逻辑（_judge_result）是纯函数单测，
不依赖 gcc。全程不依赖网络。
"""

import json
import os
import shutil
import subprocess
import sys
import types

import pytest

pytest.importorskip('pycparser', reason='manifest 生成依赖 pycparser')

import ops.c_ffi_ops as cf
from ops.py_bridge_ops import _envelope  # noqa: F401 — 信封形状对齐层 A
from scripts.c_bind_gen import build_manifest, parse_header

_EV = types.SimpleNamespace(eval=lambda a: a)
_FIX_DIR = os.path.join(os.path.dirname(__file__), 'fixtures')
_GCC = shutil.which('gcc')


@pytest.fixture(autouse=True)
def _ffi_on(monkeypatch):
    # 只管门票不做复位——module 级 lib_handle 的注册表须跨测试存活
    monkeypatch.setenv('SANYAN_FFI', '1')
    yield


# ── err 四惯例判定（纯函数，不依赖 gcc）────────────────────────────────────


def test_judge_null_convention_always_true():
    env = cf._judge_result(-7, None, 'int32')
    assert env['判'].to_int() == 1 and env['值'] == -7  # 默认 null：恒判真


def test_judge_null_ret_convention():
    bad = cf._judge_result(None, 'null_ret', 'ptr')
    assert bad['判'].to_int() == -1 and 'null_ret' in bad['错']
    ok = cf._judge_result(0x1234, 'null_ret', 'ptr')
    assert ok['判'].to_int() == 1


def test_judge_neg_ret_keeps_raw_value():
    env = cf._judge_result(-3, 'neg_ret', 'int32')
    assert env['判'].to_int() == -1 and env['值'] == -3  # 值仍附原始返回
    assert abs(env['判'].confidence - 0.9) < 1e-9


def test_judge_errno_convention():
    import ctypes

    ctypes.set_errno(2)  # ENOENT
    env = cf._judge_result(1, 'errno', 'int32')
    assert env['判'].to_int() == -1 and 'errno=2' in env['错']
    ctypes.set_errno(0)
    assert cf._judge_result(1, 'errno', 'int32')['判'].to_int() == 1


def test_gate_off_fails_closed(monkeypatch):
    monkeypatch.delenv('SANYAN_FFI', raising=False)
    assert cf._c_load(_EV, ['x.json'])['判'].to_int() == -1
    assert cf._c_call(_EV, [{'__c_lib__': 1}, 'add'])['判'].to_int() == -1


# ── 活体：gcc 编 mini 库 → 全链路 ──────────────────────────────────────────

pytestmark_live = pytest.mark.skipif(_GCC is None, reason='gcc 缺席（编 mini 共享库需要）')


@pytest.fixture(scope='module')
def lib_handle(tmp_path_factory):
    if _GCC is None:
        pytest.skip('gcc 缺席')
    d = tmp_path_factory.mktemp('cffi')
    ext = 'dll' if sys.platform.startswith('win') else ('dylib' if sys.platform == 'darwin' else 'so')
    binary = d / f'mini.{ext}' if ext == 'dll' else d / f'libmini.{ext}'
    r = subprocess.run(
        [_GCC, '-shared', '-o', str(binary), os.path.join(_FIX_DIR, 'mini.c'), '-I', _FIX_DIR]
        + ([] if sys.platform.startswith('win') else ['-fPIC']),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert r.returncode == 0, r.stderr
    with open(os.path.join(_FIX_DIR, 'mini.h'), encoding='utf-8') as f:
        manifest = build_manifest(parse_header(f.read(), 'mini.h'), 'mini')
    # 模拟人审补注：openf 返回 NULL 属失败（null_ret 惯例）
    for fn in manifest['functions']:
        if fn['name'] == 'openf':
            fn['err'] = 'null_ret'
    mf = d / 'mini.ffi.json'
    mf.write_text(json.dumps(manifest, ensure_ascii=False), encoding='utf-8')
    os.environ['SANYAN_FFI'] = '1'  # module 级 setup 先于 function 级 monkeypatch
    cf._reset_for_tests()
    env = cf._c_load(_EV, [str(mf)])
    assert env['判'].to_int() == 1, env['错']
    return env['值']


@pytestmark_live
def test_live_int_and_float_calls(lib_handle):
    assert cf._c_call(_EV, [lib_handle, 'add', 2, 3])['值'] == 5
    out = cf._c_call(_EV, [lib_handle, 'scale', 1.5, 2.0])
    assert out['判'].to_int() == 1 and abs(out['值'] - 3.0) < 1e-6
    assert cf._c_call(_EV, [lib_handle, 'big', 2**40])['值'] == 2**40 + 1


@pytestmark_live
def test_live_cstr_roundtrip_utf8(lib_handle):
    out = cf._c_call(_EV, [lib_handle, 'echo', '三言中文'])
    assert out['判'].to_int() == 1 and out['值'] == '三言中文'


@pytestmark_live
def test_live_void_return_is_true(lib_handle):
    out = cf._c_call(_EV, [lib_handle, 'ping'])
    assert out['判'].to_int() == 1


@pytestmark_live
def test_live_null_ret_convention_fires(lib_handle):
    out = cf._c_call(_EV, [lib_handle, 'openf', '/不存在'])
    assert out['判'].to_int() == -1 and 'null_ret' in out['错']  # 人审补注后的惯例生效


@pytestmark_live
def test_live_struct_by_value_dict_roundtrip(lib_handle):
    out = cf._c_call(_EV, [lib_handle, 'mk_point', 3, 4])
    assert out['判'].to_int() == 1 and out['值'] == {'x': 3, 'y': 4}


@pytestmark_live
def test_live_variadic_and_unknown_rejected(lib_handle):
    assert '变参' in cf._c_call(_EV, [lib_handle, 'logf_style', 'x'])['错']
    assert 'manifest 里没有' in cf._c_call(_EV, [lib_handle, '不存在的函数'])['错']
    assert '需要 2 个参数' in cf._c_call(_EV, [lib_handle, 'add', 1])['错']  # 参数计数按 manifest


@pytestmark_live
def test_live_release_idempotent(lib_handle):
    h = cf._c_call(_EV, [lib_handle, 'openf', 'x'])['值']  # null_ret 判假但值仍是句柄形状
    assert cf._c_release(_EV, [h]).to_int() == 1
    assert cf._c_release(_EV, [h]).to_int() == 1  # 幂等


@pytestmark_live
def test_live_generated_stub_via_import(tmp_path):
    # 终极验收：c_bind_gen 产物（桩+manifest+库）放一个目录，真实求值器从**别处**
    # `导入` 桩后裸名直调 C——验证 _module_dir 相对路径解析（此前 manifest 只认 CWD）
    r = subprocess.run(
        [
            sys.executable,
            '-X',
            'utf8',
            'scripts/c_bind_gen.py',
            os.path.join(_FIX_DIR, 'mini.h'),
            '--lib',
            'mini',
            '--no-preprocess',
            '-o',
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace',
        timeout=60,
    )
    assert r.returncode == 0, r.stderr
    ext = 'dll' if sys.platform.startswith('win') else ('dylib' if sys.platform == 'darwin' else 'so')
    binary = tmp_path / (f'mini.{ext}' if ext == 'dll' else f'libmini.{ext}')
    rc = subprocess.run(
        [_GCC, '-shared', '-o', str(binary), os.path.join(_FIX_DIR, 'mini.c'), '-I', _FIX_DIR]
        + ([] if sys.platform.startswith('win') else ['-fPIC']),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert rc.returncode == 0, rc.stderr

    from core.evaluator import SanyanEvaluator
    from core.lexer import tokenize
    from core.parser import parse_program

    env = SanyanEvaluator()
    stub = str(tmp_path / 'mini.san').replace(chr(92), '/')
    src = f'(导入 "{stub}")\n(add 2 3)'
    result = None
    for form in parse_program(tokenize(src), src):
        result = env.eval(form)
    val = result.to_int() if hasattr(result, 'to_int') else result
    assert val == 5  # 桩→manifest(模块目录解析)→c载入→c调 全链路
