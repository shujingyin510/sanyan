"""Python 进程内桥（FFI 层 A）—— RFC docs/ffi_plan.md §3 的 M1 地基。

六算子（py导入/py取/py调/py项/py列/py释）+ 三态信封 + 值封送 + 句柄注册表。
解释器路径 only（编译/VM 路径不经 ops registry，见 RFC §1 后端矩阵）。

三态信封（RFC §2）：外调一律返回 `{'判': TritValue, '值': …, '错': str, '源': 'python'}`
——判定通道与载荷通道分离：Python 返回 `False` 封送为 `值=假` 而 `判=真`；
"判=假"只表示"调用这件事失败了"。宿主异常全捕获进信封，绝无裸 traceback 穿透
（KeyboardInterrupt/SystemExit 直通——用户意志）。

封送（RFC §3.2，一处已记录的偏差）：
- Python → 三言（浅）：True/False/None → 真/假/可能；int/float/str 直通；
  list/dict 只转一层（深容器出句柄）；其余对象 → PyHandle 句柄。
- 三言 → Python（深）：**数值直通**（真→1 假→-1 可能→0）——语言层"真即 1"
  （数字字面量与三态词同为 TritValue，运行时不可区分），RFC 原案 -1→False 会造成
  Python 侧 False==0 的数值失真；此偏差已列 RFC 开放问题#8。字符串/列表/字典深转换；
  PyHandle 解回原对象（零拷贝管道）。

安全（RFC §3.6，一处已记录的偏差）：`SANYAN_FFI` ≠ '1' 时**能力面四算子**
（py导入/py取/py调/py项）调用时信封报假（不 raise——语法可解析、语义安全拒）；
py列/py释 为惰性运维算子不设门（FFI 从未开启时注册表恒空，无信息可泄，且中途关闭
后仍应允许清理句柄）。经 ops registry 注册 → `沙箱()` 机制自动可禁；agent 自更新
闭环恒不设 SANYAN_FFI（tests/test_selfupdate_cli.py 有绊线钉）。
"""

from __future__ import annotations

import importlib
import os
from typing import Any

from core.ternary_core import TritValue
from core.values import SanyanSyntaxError
from ops.capability import can, register_self_guarded
from ops.registry import register

# 句柄注册表：进程级强引用（防 GC）。上限防句柄泄漏把宿主内存拖死（RFC §3.5）。
_MAX_HANDLES = 4096
_handles: dict[int, Any] = {}
_module_cache: dict[str, dict] = {}  # 模块名 → 信封（py导入 幂等）
_next_id = 1


def _envelope(trit: int, *, value: Any = None, err: str = '', conf: float = 1.0, reason: str = '') -> dict:
    return {'判': TritValue(trit, confidence=conf), '值': value, '错': err, '源': 'python', '因': reason}


def _fail(err: str, *, conf: float = 1.0, trit: int = -1, reason: str = '') -> dict:
    return _envelope(trit, err=err[:200], conf=conf, reason=reason)


def _gate(evaluator=None) -> dict | None:
    """FFI 双闸：SANYAN_FFI 未开 → 因=门控；约束块内未 `许 外链` → 因=约束。

    均信封报假不 raise（能力面契约；分派处对这些算子已登记自守卫，见 registry 尾）。
    """
    if os.environ.get('SANYAN_FFI') != '1':
        return _fail('FFI 未启用（安全默认）：设 SANYAN_FFI=1 显式开启', reason='门控')
    if evaluator is not None and not can(evaluator, '外链'):
        return _fail('约束禁止: 外链（FFI）', reason='约束')
    return None


def _is_handle(v: Any) -> bool:
    return isinstance(v, dict) and '__py_handle__' in v


def _wrap_handle(obj: Any) -> dict | None:
    """对象进注册表换句柄；超上限返回 None（调用方发泄漏信封）。"""
    global _next_id
    if len(_handles) >= _MAX_HANDLES:
        return None
    hid = _next_id
    _next_id += 1
    _handles[hid] = obj
    return {'__py_handle__': hid}


def _to_sanyan(v: Any, depth: int = 0) -> Any:
    """Python → 三言（返回值方向，浅转换 + 句柄兜底）。

    depth=0 时容器转一层；容器内再遇容器（depth≥1）→ 句柄（RFC §3.2 表）。
    返回 ('__overflow__',) 哨元组表示句柄超上限，由调用方转信封。
    """
    if isinstance(v, bool):  # bool 是 int 子类，须先判
        return TritValue(1 if v else -1)
    if v is None:
        return TritValue(0)
    if isinstance(v, (int, float, str)):
        return v
    if isinstance(v, bytes):
        return v.decode('utf-8', errors='replace')  # 阶段 1 从简（RFC 开放问题#2）
    if isinstance(v, (list, tuple)) and depth == 0:
        return [_to_sanyan(x, depth + 1) for x in v]
    if isinstance(v, dict) and depth == 0 and all(isinstance(k, str) for k in v):
        return {k: _to_sanyan(x, depth + 1) for k, x in v.items()}
    h = _wrap_handle(v)
    return h if h is not None else ('__overflow__',)


def _contains_overflow(v: Any) -> bool:
    if v == ('__overflow__',):
        return True
    if isinstance(v, list):
        return any(_contains_overflow(x) for x in v)
    if isinstance(v, dict):
        return any(_contains_overflow(x) for x in v.values())
    return False


def _ok(raw: Any) -> dict:
    value = _to_sanyan(raw)
    if _contains_overflow(value):
        return _fail(f'句柄泄漏疑似：超上限 {_MAX_HANDLES}——用 py释 释放不再需要的句柄')
    return _envelope(1, value=value)


def _to_python(v: Any) -> Any:
    """三言 → Python（入参方向，深转换）。句柄解回原对象（零拷贝管道）。"""
    if _is_handle(v):
        hid = v['__py_handle__']
        if hid not in _handles:
            raise KeyError(f'句柄 {hid} 不存在或已被 py释')
        return _handles[hid]
    if isinstance(v, TritValue):
        if v.is_string():
            return v.to_payload()
        if v.is_list():
            return [_to_python(x) for x in v.to_payload()]
        if v.is_dict():
            return {_to_python(k): _to_python(x) for k, x in v.to_payload().items()}
        if v.float_val is not None:
            return v.to_float()
        return v.to_int()  # 数值直通：真→1 假→-1 可能→0（见模块 docstring 偏差记录）
    if isinstance(v, list):
        return [_to_python(x) for x in v]
    if isinstance(v, dict):
        return {k: _to_python(x) for k, x in v.items()}
    return v  # str/int/float/None 直通


def _reject_sanyan_callable(values: list) -> dict | None:
    """回调阶段 1 禁止（RFC §3.4 fail-closed）：入参含三言函数值即拒。"""
    for v in values:
        if type(v).__name__ == 'FunctionValue':  # 惰性判型：避免 ops←→evaluator 循环导入
            return _fail('回调暂不支持（阶段1 fail-closed）：不能把三言函数传给 Python')
    return None


def _resolve(evaluator: Any, node: Any) -> Any:
    return evaluator.eval(node)


def _py_import(evaluator: Any, args: list) -> dict:
    """py导入(模块名) → 信封。importlib 进程内导入；同名幂等返回同句柄。"""
    denied = _gate(evaluator)
    if denied:
        return denied
    if len(args) != 1:
        raise SanyanSyntaxError('py导入 需要一个参数（模块名）')
    name = _to_python(_resolve(evaluator, args[0]))
    if not isinstance(name, str):
        return _fail(f'TypeError: 模块名须为字符串，得到 {type(name).__name__}')
    if name in _module_cache:
        return _module_cache[name]
    try:
        mod = importlib.import_module(name)
    except Exception as e:
        return _fail(f'{type(e).__name__}: {str(e)[:200]}')
    h = _wrap_handle(mod)
    if h is None:
        return _fail(f'句柄泄漏疑似：超上限 {_MAX_HANDLES}——用 py释 释放不再需要的句柄')
    env = _envelope(1, value=h)
    _module_cache[name] = env
    return env


def _py_getattr(evaluator: Any, args: list) -> dict:
    """py取(句柄, 属性名) → 信封。getattr；结果按封送表转换（复杂对象→新句柄）。"""
    denied = _gate(evaluator)
    if denied:
        return denied
    if len(args) != 2:
        raise SanyanSyntaxError('py取 需要两个参数（句柄, 属性名）')
    try:
        obj = _to_python(_resolve(evaluator, args[0]))
        attr = _to_python(_resolve(evaluator, args[1]))
        return _ok(getattr(obj, attr))
    except Exception as e:
        return _fail(f'{type(e).__name__}: {str(e)[:200]}')


def _py_call(evaluator: Any, args: list) -> dict:
    """py调(句柄, 参数…) → 信封。调用可调句柄；入参深转换，三言函数值拒（无回调）。"""
    denied = _gate(evaluator)
    if denied:
        return denied
    if len(args) < 1:
        raise SanyanSyntaxError('py调 需要至少一个参数（可调句柄）')
    values = [_resolve(evaluator, a) for a in args]
    rejected = _reject_sanyan_callable(values)
    if rejected:
        return rejected
    try:
        fn = _to_python(values[0])
        call_args = [_to_python(v) for v in values[1:]]
        return _ok(fn(*call_args))
    except Exception as e:
        return _fail(f'{type(e).__name__}: {str(e)[:200]}')


def _py_getitem(evaluator: Any, args: list) -> dict:
    """py项(句柄, 键) → 信封。obj[key]（下标语义，补 py取 的属性语义）。"""
    denied = _gate(evaluator)
    if denied:
        return denied
    if len(args) != 2:
        raise SanyanSyntaxError('py项 需要两个参数（句柄, 键）')
    try:
        obj = _to_python(_resolve(evaluator, args[0]))
        key = _to_python(_resolve(evaluator, args[1]))
        return _ok(obj[key])
    except Exception as e:
        return _fail(f'{type(e).__name__}: {str(e)[:200]}')


def _py_list_handles(evaluator: Any, args: list) -> list:
    """py列() → 活跃句柄清单（id + repr 前 80 字）——排障/教学，不走信封。"""
    return [f'{hid}: {repr(obj)[:80]}' for hid, obj in sorted(_handles.items())]


def _py_release(evaluator: Any, args: list) -> TritValue:
    """py释(句柄) → 真。移除注册表强引用；重复释放幂等返回真。"""
    if len(args) != 1:
        raise SanyanSyntaxError('py释 需要一个参数（句柄）')
    v = _resolve(evaluator, args[0])
    if _is_handle(v):
        hid = v['__py_handle__']
        _handles.pop(hid, None)
        # 模块缓存里的信封若持有该句柄，一并失效（否则 py导入 幂等会复活死句柄）
        for name, env in list(_module_cache.items()):
            val = env.get('值')
            if isinstance(val, dict) and val.get('__py_handle__') == hid:
                del _module_cache[name]
    return TritValue(1)


def _envelope_verdict(evaluator: Any, args: list) -> TritValue:
    """信封判(信封) → 判（TritValue）——供 匹配3 做三态分支（RFC §2.3）。"""
    if len(args) != 1:
        raise SanyanSyntaxError('信封判 需要一个参数（信封）')
    v = _resolve(evaluator, args[0])
    if isinstance(v, dict) and '判' in v:
        j = v['判']
        return j if isinstance(j, TritValue) else TritValue(int(j))
    raise SanyanSyntaxError('信封判 的参数不是三态信封（缺 判 键）')


def _reset_for_tests() -> None:
    """清空句柄注册表与模块缓存（测试隔离用，生产不调用）。"""
    global _next_id
    _handles.clear()
    _module_cache.clear()
    _next_id = 1


register('py导入', _py_import)
register('py取', _py_getattr)
register('py调', _py_call)
register('py项', _py_getitem)
register('py列', _py_list_handles)
register('py释', _py_release)
register('信封判', _envelope_verdict)

# 能力面四算子是信封式：约束块内未 `许 外链` → 判假·因=约束（_gate 自理），分派处不抛。
# py列/py释 是惰性运维（不设门、未标外链类），不登记。
for _op in ('py导入', 'py取', 'py调', 'py项'):
    register_self_guarded(_op)
