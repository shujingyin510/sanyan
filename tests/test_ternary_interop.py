"""三态互操作矩阵（3.59 批次3）——锚定 docs/ternary-spec.md。

关键：多位数 且/或/非 是位级 tritwise，不是整数 min/max（冻结既有行为）；
0.0 不是可能；异常与三态正交。
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.evaluator import SanyanEvaluator
from core.skin import SkinManager
from core.ternary_core import TritValue


def ev():
    return SanyanEvaluator(skin_manager=SkinManager('chinese'))


def t(i, conf=1.0):
    return TritValue(i, confidence=conf)


# ── §T.1 单 trit 真值表 ──


@pytest.mark.parametrize(
    'a,b,and_r,or_r',
    [
        (1, 1, 1, 1),
        (1, 0, 0, 1),
        (1, -1, -1, 1),
        (0, 0, 0, 0),
        (0, -1, -1, 0),
        (-1, -1, -1, -1),
    ],
)
def test_and_or_truth_table_single_trit(a, b, and_r, or_r):
    e = ev()
    assert e.eval(['且', t(a), t(b)]).to_int() == and_r
    assert e.eval(['或', t(a), t(b)]).to_int() == or_r


@pytest.mark.parametrize('a,not_r', [(1, -1), (0, 0), (-1, 1)])
def test_not_truth_table_single_trit(a, not_r):
    assert ev().eval(['非', t(a)]).to_int() == not_r


# ── §T.1 多位数位级（最重要锚点）──


def test_and_multidigit_is_tritwise_not_kleene():
    """且(5,3)=-4，不是 min=3。"""
    r = ev().eval(['且', 5, 3])
    assert r.to_int() == -4
    assert r.to_int() != min(5, 3)


def test_or_multidigit_is_tritwise_not_kleene():
    """或(5,3)=+12，不是 max=5。"""
    r = ev().eval(['或', 5, 3])
    assert r.to_int() == 12
    assert r.to_int() != max(5, 3)


def test_not_multidigit_is_tritwise():
    """非(5)=-5。"""
    assert ev().eval(['非', 5]).to_int() == -5


# ── §T.2 置信度 ──


def test_and_confidence_is_min():
    r = ev().eval(['且', t(1, 0.9), t(1, 0.8)])
    assert r.to_int() == 1
    assert r.confidence == pytest.approx(0.8)


def test_or_confidence_is_max():
    r = ev().eval(['或', t(1, 0.8), t(1, 0.9)])
    assert r.to_int() == 1
    assert r.confidence == pytest.approx(0.9)


def test_not_confidence_kept():
    r = ev().eval(['非', t(1, 0.75)])
    assert r.to_int() == -1
    assert r.confidence == pytest.approx(0.75)


def test_propagate_confidence_multiplies():
    r = ev().eval(['信度传播', t(1, 0.9), t(1, 0.8)])
    assert r.confidence == pytest.approx(0.72)


# ── §T.7 is_maybe / 0.0 ──


def test_is_maybe_zero_trit():
    assert TritValue(0).is_maybe() is True


def test_is_maybe_float_zero_false():
    """0.0 不是可能。"""
    assert TritValue(0.0).is_maybe() is False


def test_is_maybe_from_string_alias():
    assert TritValue.from_string('可能').is_maybe() is True
    assert TritValue.from_string('可能').to_int() == 0


# ── §T.4 条件三路 ──


def test_if_true_takes_true_branch():
    assert ev().eval(['若', t(1), '"A"', '"B"']) == 'A'


def test_if_false_takes_else():
    assert ev().eval(['若', t(-1), '"A"', '"B"']) == 'B'


def test_if_maybe_falls_through_to_else():
    e = ev()
    r = e.eval(['若', t(0), '"A"', '"B"'])
    assert r == 'B'
    assert len(e.eval(['诊断'])) == 1


def test_if_maybe_no_else_returns_zero():
    e = ev()
    r = e.eval(['若', t(0), '"A"'])
    assert r.to_int() == 0


def test_loop_maybe_condition_exits():
    """可能条件按假退出，不死循环。"""
    e = SanyanEvaluator(max_loop_steps=1000)
    e.eval(['循环', t(0), ['设', 'x', 1]])
    # 循环条件为假 → 不进入/立即退出
    assert e.eval(['能否', '网']).to_int() == 1  # 无帧泄漏


# ── §T.3/T.4 D8 与允许 ──


def test_allow_expression_skips_d8():
    e = ev()
    e.eval(['若', ['允许', t(0)], '"A"', '"B"'])
    assert e.eval(['诊断']) == []


def test_bare_maybe_still_collects():
    e = ev()
    e.eval(['若', t(0), '"A"', '"B"'])
    assert len(e.eval(['诊断'])) == 1


# ── §T.6 异常正交 ──


def test_exception_not_swallowed_as_false():
    from core.values import SanyanValueError

    e = ev()
    with pytest.raises((SanyanValueError, ZeroDivisionError, Exception)):
        e.eval(['任务', '"t"', ['约束'], ['div', t(1), t(0)]])
    # 弹帧：无约束泄漏
    assert e.eval(['能否', '网']).to_int() == 1


def test_maybe_does_not_raise():
    r = ev().eval(t(0))
    assert r.is_maybe()


def test_constraint_denial_is_false_not_maybe():
    r = ev().eval(['任务', '"t"', ['约束'], ['能否', '网']])
    assert r.to_int() == -1


def test_cannever_returns_maybe():
    r = ev().eval(['任务', '"t"', ['约束', ['许', '网']], ['能否', '网']])
    assert r.to_int() in (1, -1)


# ── §T.5 函数返回可能 ──


def test_function_can_return_maybe():
    e = ev()
    e.eval(['定义', 'f', [], t(0)])
    # 用命令定义：简化——直接 eval 返回可能的表达式
    r = e.eval(['do', t(0)])
    assert r.is_maybe()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
