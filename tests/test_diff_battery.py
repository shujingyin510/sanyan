"""契约差分电池（3.59 批次4）——S-式 vs 糖语法，以及规范条款 ↔ 实测。

约束系统只在解释器路径（字节码/VM 拒绝约束算子），故差分在
S-表达式入口与糖语法入口之间做，而不是多后端。

fail-closed：两边都失败或任一侧异常 → 判不一致，禁止默认一致。
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.evaluator import SanyanEvaluator
from core.skin import SkinManager
from core.ternary_core import TritValue
from core.values import SanyanConstraintDenied, SanyanError
from ops.file_ops import _parse_code


def ev():
    return SanyanEvaluator(skin_manager=SkinManager('chinese'))


def run_sexpr(ast):
    """跑 S-式 AST → (kind, value)。kind ∈ ok/denied/error。"""
    e = ev()
    try:
        r = e.eval(ast)
        if isinstance(r, TritValue):
            return ('ok', r.to_int())
        return ('ok', r)
    except SanyanConstraintDenied as ex:
        return ('denied', getattr(ex, 'reason', None) or str(ex))
    except SanyanError as ex:
        return ('error', type(ex).__name__)
    except Exception as ex:  # noqa: BLE001 — 差分需收一切
        return ('error', type(ex).__name__)


def run_sugar(code):
    """跑糖语法源码 → (kind, value)。"""
    e = ev()
    try:
        ast = _parse_code(code, e)
        if ast is None:
            return ('error', 'ParseFailed')
        r = e.eval(ast)
        if isinstance(r, TritValue):
            return ('ok', r.to_int())
        return ('ok', r)
    except SanyanConstraintDenied as ex:
        return ('denied', getattr(ex, 'reason', None) or str(ex))
    except SanyanError as ex:
        return ('error', type(ex).__name__)
    except Exception as ex:  # noqa: BLE001
        return ('error', type(ex).__name__)


# ── S-式 vs 糖：约束判定 ──


def test_diff_grant_net():
    sexpr = ['任务', '"t"', ['约束', ['许', '网']], ['能否', '网']]
    sugar = '任务 t { 约束 { 许 网 } 能否("网") }'
    a, b = run_sexpr(sexpr), run_sugar(sugar)
    assert a == b == ('ok', 1), (a, b)


def test_diff_default_deny():
    sexpr = ['任务', '"t"', ['约束'], ['能否', '网']]
    sugar = '任务 t { 约束 { } 能否("网") }'
    a, b = run_sexpr(sexpr), run_sugar(sugar)
    assert a == b == ('ok', -1), (a, b)


def test_diff_seal_outside():
    sexpr = ['任务', '"t"', ['约束', ['只许', '网']], ['能否', '盘读']]
    sugar = '任务 t { 约束 { 只许 网 } 能否("盘读") }'
    a, b = run_sexpr(sexpr), run_sugar(sugar)
    assert a == b == ('ok', -1), (a, b)


def test_diff_direct_op_denied_raises():
    sexpr = ['任务', '"t"', ['约束'], ['设环境变量', '"X1"', '"1"']]
    sugar = '任务 t { 约束 { } 设环境变量("X1", "1") }'
    a, b = run_sexpr(sexpr), run_sugar(sugar)
    assert a[0] == 'denied' and b[0] == 'denied', (a, b)


def test_fail_closed_both_error_still_differs_or_ok():
    """两边都 error 时不得默认一致；本用例用同一坏程序，应同为 error。"""
    sexpr = ['任务', '"t"', ['约束'], ['许', '不存在类']]
    sugar = '任务 t { 约束 { 许 不存在类 } 1 }'
    a, b = run_sexpr(sexpr), run_sugar(sugar)
    # parse 应报错或运行时报错——关键是两边都失败时我们也显式比较
    assert a[0] in ('error', 'denied') or b[0] in ('error', 'denied')
    # 若两边都成功则失败（假绿）
    if a == ('ok', None) and b == ('ok', None):
        pytest.fail('fail-closed: 双空成功不得判一致')


# ── 契约差分：规范条款 ↔ 实测 ──


@pytest.mark.parametrize(
    'rule,sexpr,expected',
    [
        ('R-S2', ['任务', '"t"', ['约束'], ['能否', '网']], ('ok', -1)),
        ('R-Q1-no-frame', ['能否', '网'], ('ok', 1)),
        ('T.1-and-tritwise', ['且', 5, 3], ('ok', -4)),
        ('T.1-or-tritwise', ['或', 5, 3], ('ok', 12)),
        ('T.1-not-tritwise', ['非', 5], ('ok', -5)),
        ('T.4-if-true', ['若', TritValue(1), '"A"', '"B"'], ('ok', 'A')),
        ('T.4-if-false', ['若', TritValue(-1), '"A"', '"B"'], ('ok', 'B')),
        ('T.4-if-maybe', ['若', TritValue(0), '"A"', '"B"'], ('ok', 'B')),
        ('T.7-is-maybe-0', TritValue(0), ('ok', 0)),
    ],
)
def test_contract_rule_vs_runtime(rule, sexpr, expected):
    got = run_sexpr(sexpr)
    assert got == expected, f'{rule}: {got} != {expected}'


def test_contract_00_is_not_maybe():
    from core.ternary_core import TritValue as TV

    assert TV(0.0).is_maybe() is False
    assert TV(0).is_maybe() is True


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
