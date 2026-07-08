"""外语互操作库层糖（stdlib/ffi.san）守护——真实求值器导入并调用，不依赖网络。

库层糖 = 解包(py算子(...)) 的固定 arity 便利封装，降样板不改语义；
想按三态分流仍用裸算子。导入库文件本身无害（只定义函数，不触发 py导入）。
"""

import os

import pytest

from core.evaluator import SanyanEvaluator
from core.lexer import tokenize
from core.parser import parse_program
from core.values import SanyanRuntimeError

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_LIB = os.path.join(_ROOT, 'stdlib', 'ffi.san').replace(os.sep, '/')


def _run(src):
    env = SanyanEvaluator()
    result = None
    for form in parse_program(tokenize(src), src):
        result = env.eval(form)
    return result


def test_lib_parses_and_imports_even_gate_off(monkeypatch):
    # 库文件只定义函数、不触发 py导入——门控关闭也能导入（全角 sugar 解析通过）
    monkeypatch.delenv('SANYAN_FFI', raising=False)
    r = _run(f'(导入 "{_LIB}" 为 ffi)')
    from core.values import ModuleValue

    assert isinstance(r, ModuleValue)


def test_py_lib_member_run_end_to_end(monkeypatch):
    monkeypatch.setenv('SANYAN_FFI', '1')
    src = f'''(导入 "{_LIB}" 为 ffi)
(设 j (ffi.库 "json"))
(设 d (ffi.成员 j "dumps"))
(ffi.调用1 d (字典 "a" 1))'''
    assert _run(src) == '{"a": 1}'


def test_py_method_one_step(monkeypatch):
    # obj.method(x) 一步到位（最高频的 Python 用法）
    monkeypatch.setenv('SANYAN_FFI', '1')
    src = f'''(导入 "{_LIB}" 为 ffi)
(设 j (ffi.库 "json"))
(ffi.方法1 j "dumps" (字典 "b" 2))'''
    assert _run(src) == '{"b": 2}'


def test_py_run_arities(monkeypatch):
    monkeypatch.setenv('SANYAN_FFI', '1')
    # 属性直取解包，验证 成员 独立可用（顺带覆盖别名点号访问路径）
    src = f'''(导入 "{_LIB}" 为 ffi)
(设 s (ffi.库 "string"))
(ffi.成员 s "digits")'''
    assert _run(src) == '0123456789'  # 属性直取解包，验证 成员 独立可用


def test_gate_off_raises_readable_error(monkeypatch):
    # 库糖是"失败即抛"：门控关闭时调用点抛可读 SanyanRuntimeError，非裸 traceback
    monkeypatch.delenv('SANYAN_FFI', raising=False)
    with pytest.raises(SanyanRuntimeError, match='FFI 未启用'):
        _run(f'(导入 "{_LIB}" 为 ffi)\n(ffi.库 "json")')


def test_missing_module_raises(monkeypatch):
    monkeypatch.setenv('SANYAN_FFI', '1')
    with pytest.raises(SanyanRuntimeError, match='解包失败'):
        _run(f'(导入 "{_LIB}" 为 ffi)\n(ffi.库 "绝不存在的模块zzz")')
