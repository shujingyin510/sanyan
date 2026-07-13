"""能力门控地基回归钉（v3.57.1 清理）：保护三个既有失效的修复——

- E2 安全门自守恒：`设环境变量` 不得从语言内部翻越 SANYAN_NET/FFI/ALLOW_LOCAL。
- E4a 沙箱去引号：sugar 字面量带引号（'"http读"'）此前永不匹配算子名，沙箱形同虚设。
- E4b 别名连坐：封 'http读' 此前拦不住其别名 'http_get'（同一实现，不同名字）。

沙箱状态是模块级全局（core/sandbox._BLOCKED_OPS，已知限制），故每例 finally 清理。
（此文件在上一轮曾因工具故障未真正落盘，本轮重建并实跑。）
"""

import os

import pytest

from core.evaluator import SanyanEvaluator
from core.sandbox import unblock
from core.values import SanyanRuntimeError
from ops.registry import entry_names


# ── E2：设环境变量 不能翻安全门控 ──


def test_setenv_rejects_security_gate(monkeypatch):
    monkeypatch.setenv('SANYAN_NET', '1')  # 已知初值，由 monkeypatch 回收
    e = SanyanEvaluator()
    with pytest.raises(SanyanRuntimeError, match='安全门控'):
        e.eval(['设环境变量', '"SANYAN_NET"', '"0"'])
    assert os.environ.get('SANYAN_NET') == '1'  # 拦在设值之前，未被翻越
    for gate in ('SANYAN_FFI', 'SANYAN_NET_ALLOW_LOCAL'):
        with pytest.raises(SanyanRuntimeError, match='安全门控'):
            e.eval(['设环境变量', f'"{gate}"', '"0"'])


def test_setenv_allows_normal_var(monkeypatch):
    e = SanyanEvaluator()
    e.eval(['设环境变量', '"SANYAN_CAP_GATE_T"', '"ok"'])
    assert os.environ.get('SANYAN_CAP_GATE_T') == 'ok'
    monkeypatch.delenv('SANYAN_CAP_GATE_T', raising=False)


# ── E4a：沙箱去引号后真正拦截 ──


def test_sandbox_dequotes_and_blocks():
    e = SanyanEvaluator()
    try:
        e.eval(['沙箱', '"debug"'])  # sugar 形态带引号
        with pytest.raises(SanyanRuntimeError, match='沙箱禁止'):
            e.eval(['debug', 'x'])  # 此前带引号 bug 下这里不会抛
    finally:
        unblock()


def test_sandbox_bare_name_blocks():
    e = SanyanEvaluator()
    try:
        e.eval(['沙箱', 'debug'])  # 裸原子形态
        with pytest.raises(SanyanRuntimeError, match='沙箱禁止'):
            e.eval(['debug', 'x'])
    finally:
        unblock()


# ── E4b：别名连坐 ──


def test_sandbox_coblocks_alias_forward():
    e = SanyanEvaluator()
    try:
        e.eval(['沙箱', '"http读"'])
        with pytest.raises(SanyanRuntimeError, match='沙箱禁止'):
            e.eval(['http_get', '"http://example.com"'])  # 别名同一实现，必须一并拦
    finally:
        unblock()


def test_sandbox_coblocks_alias_reverse():
    e = SanyanEvaluator()
    try:
        e.eval(['沙箱', '"http_get"'])  # 封别名
        with pytest.raises(SanyanRuntimeError, match='沙箱禁止'):
            e.eval(['http读', '"http://example.com"'])  # 本名也应被拦
    finally:
        unblock()


# ── entry_names 单元行为 ──


def test_entry_names_groups_alias():
    g = set(entry_names('http读'))
    assert 'http读' in g and 'http_get' in g
    assert 'http请求' not in g and 'http写' not in g  # 不误并其他网络算子


def test_entry_names_distinguishes_shared_func_diff_extra():
    assert 'gt' not in entry_names('eq')  # 共享 _compare 但 extra 不同，不得误并


def test_entry_names_unknown_returns_self():
    assert entry_names('压根不存在的算子') == ['压根不存在的算子']
