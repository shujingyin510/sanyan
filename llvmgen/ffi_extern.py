"""FFI 层 B 编译后端（M4-LLVM，RFC docs/ffi_plan.md §4.6）——manifest 驱动 extern 直呼。

同一份 c_bind_gen manifest 喂两个后端：解释器路径走 ctypes（ops/c_ffi_ops.py 的
c载入/c调，经生成桩），编译路径在此把 manifest 函数发射为 `declare` 外部原型 +
直接调用——用户程序写 `(add 2 3)`，名字先查 sanyan 函数、查不到再查 FFI extern 表
（ops_gen 的调用分派末端挂钩），最后才报"未定义"。链接由 `build(link_libs=…)` 把
库文件交给 CC。

阶段 1 类型面：**整数族 only**（int8..64 / uint8..64 / long / ulong）——tagged i64
拆箱 → trunc 到 C ABI 宽度 → 调用 → sext/zext 回 i64 → RawValue。void 返回映射为
真（与解释器信封"无返回值的成功调用给真"对齐）。f32/f64/cstr/ptr/struct 的编译
路径暂不支持（解释器路径全支持——两后端能力面不对称已在 RFC §1 矩阵显式声明）；
变参编译期拒，与运行时同口径。
"""

from __future__ import annotations

import ctypes
import json
from typing import Sequence

from llvmlite import ir

from llvmgen.type_mapping import RawValue

_I64 = ir.IntType(64)
_LONG_BITS = ctypes.sizeof(ctypes.c_long) * 8  # 'long' 平台宽度（与 c_ffi_ops 同约定）
_INT_TOKENS = {
    'int8': (8, True),
    'uint8': (8, False),
    'int16': (16, True),
    'uint16': (16, False),
    'int32': (32, True),
    'uint32': (32, False),
    'int64': (64, True),
    'uint64': (64, False),
    'long': (_LONG_BITS, True),
    'ulong': (_LONG_BITS, False),
}


def load_ffi_manifests(paths: Sequence[str]) -> dict:
    """manifest 文件列表 → {函数名: 条目}。类型/变参检查延迟到调用点（报错带函数名）。"""
    externs: dict = {}
    for p in paths or ():
        with open(p, encoding='utf-8') as f:
            manifest = json.load(f)
        for fn in manifest.get('functions', []):
            externs[fn['name']] = fn
    return externs


def _ir_int(token: str) -> tuple:
    bits, signed = _INT_TOKENS[token]
    return ir.IntType(bits), signed


def emit_ffi_call(cg, entry: dict, args: list, compile_node) -> RawValue:
    """在当前 builder 位置发射一次 extern 调用；返回装回 tagged 语义的 RawValue。"""
    name = entry['name']
    if entry.get('variadic'):
        raise NameError(f'编译错误: FFI 函数 {name} 是变参函数（阶段1拒，与运行时同口径）')
    for t in [entry['ret'], *entry['args']]:
        if t != 'void' and t not in _INT_TOKENS:
            raise NameError(f'编译错误: FFI 函数 {name} 的类型 {t} 编译路径暂不支持（解释器路径可用）')
    if len(args) != len(entry['args']):
        raise NameError(f'编译错误: FFI 函数 {name} 需要 {len(entry["args"])} 个参数，得到 {len(args)}')

    ret_ty = ir.VoidType() if entry['ret'] == 'void' else _ir_int(entry['ret'])[0]
    fnty = ir.FunctionType(ret_ty, [_ir_int(t)[0] for t in entry['args']])
    fn = cg.module.globals.get(name)
    if fn is None:
        fn = ir.Function(cg.module, fnty, name=name)

    call_vals = []
    for node, token in zip(args, entry['args']):
        raw = cg._to_raw(compile_node(node, cg)).ll_val  # tagged/boxed → i64
        ty, _ = _ir_int(token)
        if ty.width < 64:
            raw = cg.builder.trunc(raw, ty, name=f'ffi_arg_{token}')
        call_vals.append(raw)

    res = cg.builder.call(fn, call_vals, name=f'ffi_{name}')
    if entry['ret'] == 'void':
        return RawValue(ir.Constant(_I64, 1))  # void 成功 → 真（对齐解释器信封语义）
    ty, signed = _ir_int(entry['ret'])
    if ty.width < 64:
        res = cg.builder.sext(res, _I64) if signed else cg.builder.zext(res, _I64)
    return RawValue(res)
