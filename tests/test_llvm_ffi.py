"""FFI 层 B 编译后端（M4-LLVM）守护——manifest 驱动 extern 声明/直呼/类型面/native 活体。

IR 文本层断言不依赖工具链（llvmlite 发射即可验）；native 活体走 build() 三级回退
（llc → clang → llvmlite binding 吐对象）+ gcc 链接，gcc 缺席 skip。
差分角落（RFC §4.6）：同一 manifest 双后端（ctypes 解释器 vs 原生编译）产出一致
——FFI 里唯一可差分的角落。
"""

import json
import os
import shutil
import subprocess
import sys
import types

import pytest

pytest.importorskip('llvmlite', reason='llvmgen 依赖 llvmlite')

from llvmgen.compiler import compile_source  # noqa: E402

_GCC = shutil.which('gcc')
# 注意命名：内置算子（如 add/加）在分派序上遮蔽 FFI extern——manifest 函数与
# 内置同名时编译路径不可达（已记 RFC 已知限制）。测试与示例一律用带前缀名。
_ADD = {'name': 'mini_add', 'ret': 'int32', 'args': ['int32', 'int32'], 'err': None}


def _mf(tmp_path, functions, name='t'):
    p = tmp_path / f'{name}.ffi.json'
    p.write_text(
        json.dumps({'lib': name, 'functions': functions, 'structs': {}, 'enums': {}}, ensure_ascii=False),
        encoding='utf-8',
    )
    return str(p)


def test_ir_declare_and_direct_call(tmp_path):
    ir_text, _ = compile_source('(输出 (mini_add 2 3))', 'm', ffi_manifests=(_mf(tmp_path, [_ADD]),))
    decl = [ln for ln in ir_text.splitlines() if ln.startswith('declare') and 'mini_add' in ln]
    assert decl and 'i32' in decl[0]  # declare i32 @"add"(i32, i32)
    assert 'ffi_mini_add' in ir_text  # 调用点落在 builder 命名里


def test_ir_int64_passthrough_and_void(tmp_path):
    fns = [
        {'name': 'big', 'ret': 'uint64', 'args': ['uint64'], 'err': None},
        {'name': 'ping', 'ret': 'void', 'args': [], 'err': None},
    ]
    mf = _mf(tmp_path, fns)
    ir1, _ = compile_source('(设 x (big 7))', 'm1', ffi_manifests=(mf,))
    assert any(ln.startswith('declare i64') and 'big' in ln for ln in ir1.splitlines())
    ir2, _ = compile_source('(ping)', 'm2', ffi_manifests=(mf,))
    assert any(ln.startswith('declare void') and 'ping' in ln for ln in ir2.splitlines())


def test_unsupported_type_rejected_compiletime(tmp_path):
    mf = _mf(tmp_path, [{'name': 'echo', 'ret': 'cstr', 'args': ['cstr'], 'err': None}])
    with pytest.raises(NameError, match='暂不支持'):
        compile_source('(echo "x")', 'm', ffi_manifests=(mf,))


def test_variadic_rejected_compiletime(tmp_path):
    mf = _mf(tmp_path, [{'name': 'logf', 'ret': 'int32', 'args': ['int32'], 'err': None, 'variadic': True}])
    with pytest.raises(NameError, match='变参'):
        compile_source('(logf 1)', 'm', ffi_manifests=(mf,))


def test_wrong_argc_rejected_compiletime(tmp_path):
    with pytest.raises(NameError, match='需要 2 个参数'):
        compile_source('(mini_add 1)', 'm', ffi_manifests=(_mf(tmp_path, [_ADD]),))


def test_unlisted_name_still_undefined(tmp_path):
    with pytest.raises(NameError, match='未定义的操作或函数'):
        compile_source('(nosuch 1)', 'm', ffi_manifests=(_mf(tmp_path, [_ADD]),))


@pytest.mark.skipif(_GCC is None, reason='gcc 缺席（编库+链接需要）')
def test_native_end_to_end_and_differential_corner(tmp_path):
    # 编一个只有 add 的共享库
    (tmp_path / 'add.c').write_text('int mini_add(int a, int b) { return a + b; }', encoding='utf-8')
    dll = tmp_path / ('add.dll' if sys.platform.startswith('win') else 'libadd.so')
    r = subprocess.run(
        [_GCC, '-shared', '-o', str(dll), str(tmp_path / 'add.c')]
        + ([] if sys.platform.startswith('win') else ['-fPIC']),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert r.returncode == 0, r.stderr

    mf = _mf(tmp_path, [_ADD], 'add')
    src = tmp_path / 'p.san'
    src.write_text('(输出 (mini_add 2 3))', encoding='utf-8')
    from llvmgen.build import build

    exe = str(tmp_path / ('p.exe' if sys.platform.startswith('win') else 'p'))
    try:
        build(str(src), exe, ffi_manifests=(mf,), link_libs=(str(dll),))
    except (RuntimeError, subprocess.CalledProcessError) as e:
        pytest.skip(f'本机无法完成 IR→对象→链接: {e}')
    out = subprocess.run([exe], capture_output=True, text=True, cwd=str(tmp_path), timeout=30)
    assert out.returncode == 0, out.stderr
    native_val = out.stdout.strip()

    # 差分角落：同一 manifest，解释器 ctypes 路径给出同一答案
    import ops.c_ffi_ops as cf

    os.environ['SANYAN_FFI'] = '1'
    cf._reset_for_tests()
    manifest = json.loads(open(mf, encoding='utf-8').read())
    manifest['binary'] = {'win32': dll.name, 'linux': dll.name, 'darwin': dll.name}
    mf2 = tmp_path / 'add2.ffi.json'
    mf2.write_text(json.dumps(manifest), encoding='utf-8')
    ev = types.SimpleNamespace(eval=lambda a: a)
    h = cf._c_load(ev, [str(mf2)])['值']
    interp_val = cf._c_call(ev, [h, 'mini_add', 2, 3])['值']
    assert str(interp_val) == native_val == '5'
