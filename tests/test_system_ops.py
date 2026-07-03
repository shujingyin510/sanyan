"""系统操作 ops：字符串参数两种形态（裸原子 / sugar 带引号字面量）都必须工作。

P2 首跑挖出的根因回归守护：sugar 解析产物的字面量带引号（['环境变量', '"NAME"']），
op 生取导致查询带引号的名字、永远得空——agent_policy.san 的密钥环境读取从未生效，
占位符 sk-你的key 上位进 HTTP 头引爆 latin-1 编码错。密钥注入反模式（str.replace
写密钥进源码）当年正是给这个 bug 打的补丁；根修后注入再无存在理由。
"""

import os

from core.evaluator import SanyanEvaluator


def test_getenv_quoted_literal(monkeypatch):
    monkeypatch.setenv('SANYAN_TEST_VAR', 'hello123')
    e = SanyanEvaluator()
    assert e.eval(['环境变量', '"SANYAN_TEST_VAR"']) == 'hello123'  # sugar 形态（带引号）
    assert e.eval(['环境变量', 'SANYAN_TEST_VAR']) == 'hello123'  # 裸原子形态


def test_getenv_missing_returns_empty():
    e = SanyanEvaluator()
    assert e.eval(['环境变量', '"SANYAN_不存在的变量"']) == ''


def test_setenv_quoted_literal(monkeypatch):
    monkeypatch.setenv('SANYAN_TEST_VAR2', 'seed')  # 让 monkeypatch 负责回收
    e = SanyanEvaluator()
    e.eval(['设环境变量', '"SANYAN_TEST_VAR2"', '"world"'])
    assert os.environ.get('SANYAN_TEST_VAR2') == 'world'
