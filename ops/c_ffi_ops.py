"""C FFI 运行时（层 B 在线半，RFC docs/ffi_plan.md §4 / M4-ctypes）——解释器路径 only。

三算子：`c载入(manifest路径) → 信封`、`c调(库句柄, 函数名, 参数…) → 信封`、
`c释(C句柄) → 真`。manifest（c_bind_gen 产物，入库人审后使用）是唯一事实源：
argtypes/restype/err 惯例全部由它驱动，运行时绝不猜签名。

错误惯例（RFC §4.4，manifest 每函数的 `err` 字段）：
  null       恒判真（默认——生成器不推断，人审补注）
  null_ret   返回 NULL → 判假
  neg_ret    返回 < 0 → 判假（置信度 0.9，`值` 仍附原始返回）
  errno      调用后 errno ≠ 0 → 判假带 strerror

内存与诚实声明（RFC §4.5）：谁分配谁释放，本层不自动 free；**段错误不可捕获**
——C 库崩溃 = 三言进程崩溃（不受信 C 库勿开 FFI，子进程隔离列 RFC 开放问题 #5）。

门控与 Python 桥同口径：`SANYAN_FFI` ≠ '1' 时能力面算子（c载入/c调）信封报假；
`沙箱()` 经 registry 自动可禁；agent 自更新环境恒不设 SANYAN_FFI。
"""

from __future__ import annotations

import ctypes
import json
import os
import sys
from typing import Any, Optional

from core.ternary_core import TritValue
from core.values import SanyanSyntaxError
from ops.capability import register_self_guarded
from ops.py_bridge_ops import _envelope, _fail, _gate, _to_python
from ops.registry import register

# manifest 类型记号 → ctypes（'long'/'ulong' 按平台宽度，与生成器约定一致）
_CTYPES_MAP = {
    'int8': ctypes.c_int8,
    'uint8': ctypes.c_uint8,
    'int16': ctypes.c_int16,
    'uint16': ctypes.c_uint16,
    'int32': ctypes.c_int32,
    'uint32': ctypes.c_uint32,
    'int64': ctypes.c_int64,
    'uint64': ctypes.c_uint64,
    'long': ctypes.c_long,
    'ulong': ctypes.c_ulong,
    'f32': ctypes.c_float,
    'f64': ctypes.c_double,
    'cstr': ctypes.c_char_p,
    'ptr': ctypes.c_void_p,
}

_MAX_LIBS = 64
_libs: dict[int, tuple] = {}  # id → (CDLL, manifest, struct_types)
_c_handles: dict[int, int] = {}  # C 指针句柄注册表（不透明地址值；py 句柄机制的独立版）
_next_id = 1


def _reset_for_tests() -> None:
    global _next_id
    _libs.clear()
    _c_handles.clear()
    _next_id = 1


def _platform_key() -> str:
    if sys.platform.startswith('win'):
        return 'win32'
    if sys.platform == 'darwin':
        return 'darwin'
    return 'linux'


def _build_struct_types(manifest: dict) -> dict:
    """manifest structs → ctypes.Structure 子类（按值传参/返回 + 字典往返）。"""
    out: dict = {}
    for name, fields in (manifest.get('structs') or {}).items():
        ct_fields = []
        for fname, ftype in fields:
            ct = _CTYPES_MAP.get(ftype)
            if ct is None:
                break  # 含不支持字段的结构体不建类型——用到它的调用会按未知类型拒
            ct_fields.append((fname, ct))
        else:
            out[name] = type(f'C_{name}', (ctypes.Structure,), {'_fields_': ct_fields})
    return out


def _resolve_ct(token: str, struct_types: dict):
    if token == 'void':
        return None
    if token.startswith('struct:'):
        st = struct_types.get(token.split(':', 1)[1])
        if st is None:
            raise SanyanSyntaxError(f'结构体类型未建模: {token}')
        return st
    ct = _CTYPES_MAP.get(token)
    if ct is None:
        raise SanyanSyntaxError(f'未知类型记号: {token}')
    return ct


def _c_load(evaluator: Any, args: list) -> dict:
    """c载入(manifest路径) → 信封。二进制查找序：manifest 同目录 → 原名交给系统装载器。"""
    denied = _gate(evaluator)
    if denied:
        return denied
    if len(args) != 1:
        raise SanyanSyntaxError('c载入 需要一个参数（manifest 路径）')
    global _next_id
    path = _to_python(evaluator.eval(args[0]))
    # 相对路径解析序：CWD → 当前模块目录（import_module 设 _module_dir）——
    # 生成桩里的 `c载入("mini.ffi.json")` 从任意处 导入 都能找到与桩同目录的 manifest
    if isinstance(path, str) and not os.path.isabs(path) and not os.path.exists(path):
        mod_dir = getattr(evaluator, '_module_dir', '')
        if mod_dir and os.path.exists(os.path.join(mod_dir, path)):
            path = os.path.join(mod_dir, path)
    try:
        with open(path, encoding='utf-8') as f:
            manifest = json.load(f)
        binary = (manifest.get('binary') or {}).get(_platform_key(), '')
        if not binary:
            return _fail(f'manifest 未给 {_platform_key()} 平台的二进制名')
        local = os.path.join(os.path.dirname(os.path.abspath(path)), binary)
        cdll = ctypes.CDLL(local if os.path.exists(local) else binary, use_errno=True)
    except Exception as e:
        return _fail(f'{type(e).__name__}: {str(e)[:200]}')
    if len(_libs) >= _MAX_LIBS:
        return _fail(f'库句柄超上限 {_MAX_LIBS}')
    hid = _next_id
    _next_id += 1
    _libs[hid] = (cdll, manifest, _build_struct_types(manifest))
    return _envelope(1, value={'__c_lib__': hid, 'lib': manifest.get('lib', '')})


def _judge_result(raw: Any, err: Optional[str], ret_token: str) -> dict:
    """按 manifest err 惯例把原始返回裁成信封（纯函数，四类惯例各有单测）。"""
    if err == 'null_ret' and (raw is None or raw == 0) and (ret_token in ('ptr', 'cstr')):
        return _envelope(-1, value=_marshal_out(raw, ret_token), err='NULL 返回（null_ret 惯例）')
    if err == 'neg_ret' and isinstance(raw, (int, float)) and raw < 0:
        return _envelope(-1, value=_marshal_out(raw, ret_token), err=f'负返回 {raw}（neg_ret 惯例）', conf=0.9)
    if err == 'errno':
        eno = ctypes.get_errno()
        if eno != 0:
            ctypes.set_errno(0)
            return _envelope(-1, value=_marshal_out(raw, ret_token), err=f'errno={eno}: {os.strerror(eno)}')
    return _envelope(1, value=_marshal_out(raw, ret_token))


def _marshal_out(raw: Any, ret_token: str) -> Any:
    """C 返回值 → 三言（cstr 已由 ctypes 给 bytes；ptr 进句柄注册表）。"""
    global _next_id
    if ret_token == 'void':
        return TritValue(1)  # 无返回值的成功调用给真
    if ret_token == 'cstr':
        return raw.decode('utf-8', errors='replace') if isinstance(raw, bytes) else ('' if raw is None else str(raw))
    if ret_token == 'ptr':
        addr = 0 if raw is None else int(raw)
        hid = _next_id
        _next_id += 1
        _c_handles[hid] = addr
        return {'__c_ptr__': hid, 'addr': addr}
    if isinstance(raw, ctypes.Structure):
        # _fields_ 类型桩允许 (名, 类型, 位宽) 三元组——按下标取名（位域在生成器侧已拒）
        return {f[0]: getattr(raw, f[0]) for f in raw._fields_}
    return raw


def _marshal_in(v: Any, token: str, struct_types: dict) -> Any:
    """三言实参 → ctypes 实参（fail-closed：形态不符抛 SanyanSyntaxError 进信封）。"""
    val = _to_python(v)
    if token == 'cstr':
        if isinstance(val, str):
            return val.encode('utf-8')
        if isinstance(val, bytes) or val is None:
            return val
        raise SanyanSyntaxError(f'cstr 参数需要字符串，得到 {type(val).__name__}')
    if token == 'ptr':
        if isinstance(val, dict) and '__c_ptr__' in val:
            hid = val['__c_ptr__']
            if hid not in _c_handles:
                raise SanyanSyntaxError(f'C句柄 {hid} 不存在或已被 c释')
            return ctypes.c_void_p(_c_handles[hid])
        if val in (0, None):
            return ctypes.c_void_p(0)
        raise SanyanSyntaxError('ptr 参数需要 C句柄（或 0 表示 NULL）')
    if token.startswith('struct:'):
        st = struct_types.get(token.split(':', 1)[1])
        if st is None or not isinstance(val, dict):
            raise SanyanSyntaxError(f'{token} 参数需要字段字典')
        return st(**{f[0]: val[f[0]] for f in st._fields_})  # 缺字段 → KeyError → 外层进假信封
    if token in ('f32', 'f64'):
        return float(val)
    return int(val)


def _c_call(evaluator: Any, args: list) -> dict:
    """c调(库句柄, 函数名, 参数…) → 信封。签名/err 全由 manifest 驱动，不猜。"""
    denied = _gate(evaluator)
    if denied:
        return denied
    if len(args) < 2:
        raise SanyanSyntaxError('c调 需要至少两个参数（库句柄, 函数名）')
    try:
        lib_h = _to_python(evaluator.eval(args[0]))
        fname = _to_python(evaluator.eval(args[1]))
        if not (isinstance(lib_h, dict) and lib_h.get('__c_lib__') in _libs):
            return _fail('第一个参数不是有效的库句柄（c载入 的信封须先解包）')
        cdll, manifest, struct_types = _libs[lib_h['__c_lib__']]
        entry = next((f for f in manifest.get('functions', []) if f['name'] == fname), None)
        if entry is None:
            return _fail(f'manifest 里没有函数 {fname}（只有入册函数可调）')
        if entry.get('variadic'):
            return _fail(f'{fname} 是变参函数（阶段1拒，RFC §4.2）')
        call_vals = [evaluator.eval(a) for a in args[2:]]
        if len(call_vals) != len(entry['args']):
            return _fail(f'{fname} 需要 {len(entry["args"])} 个参数，得到 {len(call_vals)}')
        fn = getattr(cdll, fname)
        fn.argtypes = [_resolve_ct(t, struct_types) for t in entry['args']]
        fn.restype = _resolve_ct(entry['ret'], struct_types)
        c_args = [_marshal_in(v, t, struct_types) for v, t in zip(call_vals, entry['args'])]
        ctypes.set_errno(0)
        raw = fn(*c_args)
        return _judge_result(raw, entry.get('err'), entry['ret'])
    except Exception as e:
        return _fail(f'{type(e).__name__}: {str(e)[:200]}')


def _c_release(evaluator: Any, args: list) -> TritValue:
    """c释(C句柄) → 真。移除注册表条目（幂等）；不 free——谁分配谁释放（RFC §4.5）。"""
    if len(args) != 1:
        raise SanyanSyntaxError('c释 需要一个参数（C句柄）')
    v = evaluator.eval(args[0])
    if isinstance(v, dict) and '__c_ptr__' in v:
        _c_handles.pop(v['__c_ptr__'], None)
    return TritValue(1)


register('c载入', _c_load)
register('c调', _c_call)
register('c释', _c_release)

# 能力面（c载入/c调）信封式：约束块内未 `许 外链` → 判假·因=约束（_gate 自理），分派处不抛。
# c释 是清理算子（不设门、未标外链类），不登记。
register_self_guarded('c载入')
register_self_guarded('c调')
