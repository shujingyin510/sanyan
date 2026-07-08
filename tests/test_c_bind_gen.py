"""FFI 层 B 离线半（c_bind_gen，M3）守护——声明导入产物形状。

pycparser 仅生成器需要（可选开发依赖）：缺席时整文件 skip；
测试走 --no-preprocess 路径（夹具无 include），不依赖 gcc。
"""

import json
import os
import shutil
import subprocess
import sys

import pytest

pytest.importorskip('pycparser', reason='c_bind_gen 依赖 pycparser（可选开发依赖）')

from scripts.c_bind_gen import build_manifest, build_stub, parse_header  # noqa: E402

_FIX = os.path.join(os.path.dirname(__file__), 'fixtures', 'mini.h')


@pytest.fixture(scope='module')
def manifest():
    with open(_FIX, encoding='utf-8') as f:
        return build_manifest(parse_header(f.read(), 'mini.h'), 'mini')


def _fn(manifest, name):
    return next(f for f in manifest['functions'] if f['name'] == name)


def test_manifest_shape_and_type_mapping(manifest):
    assert manifest['lib'] == 'mini' and manifest['binary']['win32'] == 'mini.dll'
    assert _fn(manifest, 'add') == {'name': 'add', 'err': None, 'ret': 'int32', 'args': ['int32', 'int32']}
    assert _fn(manifest, 'echo')['ret'] == 'cstr' and _fn(manifest, 'echo')['args'] == ['cstr']
    assert _fn(manifest, 'openf')['ret'] == 'ptr'  # void* → 不透明句柄
    assert _fn(manifest, 'scale')['args'] == ['f64', 'f32']
    assert _fn(manifest, 'big')['ret'] == 'uint64'
    assert _fn(manifest, 'ping') == {'name': 'ping', 'err': None, 'ret': 'void', 'args': []}


def test_typedef_resolved(manifest):
    assert _fn(manifest, 'twice') == {'name': 'twice', 'err': None, 'ret': 'int32', 'args': ['int32']}


def test_struct_and_enum(manifest):
    assert manifest['structs']['Point'] == [['x', 'int32'], ['y', 'int32']]
    assert manifest['enums'] == {'OK': 0, 'FAIL': 1, 'RETRY': 2}  # 自动递增


def test_variadic_flagged_funcptr_skipped(manifest):
    assert _fn(manifest, 'logf_style').get('variadic') is True  # 进 manifest、运行时拒
    assert all(f['name'] != 'apply' for f in manifest['functions'])  # 函数指针 → skipped
    sk = {s['name']: s for s in manifest['skipped']}
    assert 'apply' in sk and '函数指针' in sk['apply']['reason']


def test_err_defaults_null_for_human_review(manifest):
    # RFC §4.4：生成器不推断错误惯例——默认 null，人审补注（生成物入库人审的主要审点）
    assert all(f['err'] is None for f in manifest['functions'])


def test_stub_shape_and_parses(manifest):
    from sugar.parser import parse_code

    stub = build_stub(manifest, 'mini.h')
    assert '人工审阅后使用' in stub and '解包(c载入("mini.ffi.json"))' in stub
    assert '定义 add (a1, a2) {' in stub and '解包(c调(__库, "add", a1, a2));' in stub
    assert '定义 ping () {' in stub and '解包(c调(__库, "ping"));' in stub
    assert 'logf_style: 变参函数' in stub and '定义 logf_style' not in stub  # 变参不生成桩
    assert '导出 add' in stub
    ast, errors = parse_code(stub)
    assert ast and not [e for e in errors if isinstance(e, str) and '行' in e]  # 桩语法可解析


def test_cli_writes_artifacts(tmp_path):
    r = subprocess.run(
        [
            sys.executable,
            '-X',
            'utf8',
            'scripts/c_bind_gen.py',
            _FIX,
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
    mf = json.loads((tmp_path / 'mini.ffi.json').read_text(encoding='utf-8'))
    assert mf['generator'].startswith('c_bind_gen') and mf['functions']
    assert (tmp_path / 'mini.san').read_text(encoding='utf-8').startswith('// 由 c_bind_gen')
    assert '跳过' in r.stdout and 'err 惯例默认 null' in r.stdout  # skipped 可见 + 人审提醒


@pytest.mark.skipif(shutil.which('gcc') is None, reason='gcc 缺席（预处理路径需要）')
def test_preprocess_path_with_gcc(tmp_path):
    r = subprocess.run(
        [sys.executable, '-X', 'utf8', 'scripts/c_bind_gen.py', _FIX, '--lib', 'mini2', '-o', str(tmp_path)],
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace',
        timeout=120,
    )
    assert r.returncode == 0, r.stderr
    mf = json.loads((tmp_path / 'mini2.ffi.json').read_text(encoding='utf-8'))
    assert any(f['name'] == 'add' for f in mf['functions'])  # линemarker 路径同样可解析
