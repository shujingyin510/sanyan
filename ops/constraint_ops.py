"""能力层约束算子：任务 / 约束 / 能否（S-表达式入口，不依赖 Pratt 糖）。

分层律：`约束` 子句在此被**结构性解析**为能力集操作，绝不把 许/禁/只许 当值算子
分派——共享词汇不共享状态（约束-方向研究 §D1）。四关键字的值层桩在 planned_ops.py。

许（加法下界）/ 只许（封死上界，越界的 许 即 parse 期报错）/ 禁（不可逆挖洞，禁>许）
三关键字进能力帧；允许（容忍轴）与 限时（量化轴）先解析放行、语义留后续刀。糖语法 `任务名{约束{…}}`
待 Pratt，本入口先用 S-式 `(任务 名 (约束 (许 网) …) 体…)`。
"""

from __future__ import annotations

from core.ternary_core import TritValue
from core.values import SanyanSyntaxError, SanyanValueError
from ops.capability import CAP_CLASSES, can, pop_frame, push_frame
from ops.registry import register


def _dequote(s):
    if isinstance(s, str) and len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        return s[1:-1]
    return s


def _to_seconds(node) -> float:
    """限时 参数 → 秒（float）。字面量即可判定，不 eval；接受 int/float/字符串/TritValue。"""
    if isinstance(node, bool):
        raise SanyanValueError('限时 参数必须是数字（秒）')
    if isinstance(node, (int, float)):
        return float(node)
    if isinstance(node, TritValue):
        return float(node.to_float()) if node.is_float() else float(node.to_int())
    if isinstance(node, str):
        try:
            return float(_dequote(node))
        except ValueError:
            raise SanyanValueError(f'限时 参数必须是数字（秒），得到 {node!r}')
    raise SanyanValueError(f'限时 参数必须是数字（秒），得到 {node!r}')


def _parse_constraint(clause) -> tuple[frozenset, frozenset, float | None]:
    """(约束 (许 网) (禁 删) (只许 网) (限时 5) …) → (allowed, denied, timeout秒)。结构解析，不分派值算子。

    可判定性法则：关键字与能力类都是封闭集，非法即解析期报错（不留运行时条件）。
    """
    if not isinstance(clause, list) or not clause or _dequote(clause[0]) != '约束':
        raise SanyanSyntaxError('任务 第二参必须是 (约束 …) 子句')
    granted: set = set()
    sealed: set = set()
    denied: set = set()
    has_seal = False
    timeout: float | None = None
    for sub in clause[1:]:
        if not isinstance(sub, list) or not sub:
            raise SanyanSyntaxError(f'约束子句格式错误: {sub!r}')
        kw = _dequote(sub[0])
        caps = [_dequote(c) for c in sub[1:]]
        if kw in ('许', '只许', '禁'):
            for c in caps:
                if c not in CAP_CLASSES:
                    raise SanyanValueError(f'未知能力类 `{c}`（封闭集: {sorted(CAP_CLASSES)}）')
        if kw == '许':
            granted.update(caps)
        elif kw == '只许':
            has_seal = True
            sealed.update(caps)
        elif kw == '禁':
            denied.update(caps)
        elif kw == '限时':
            if len(sub) != 2:
                raise SanyanSyntaxError('限时 需要恰一个数字参数（秒）')
            secs = _to_seconds(sub[1])
            if secs <= 0:
                raise SanyanValueError(f'限时 预算必须为正数（秒），得到 {secs}')
            timeout = secs if timeout is None else min(timeout, secs)  # 多个 限时 取最紧
        elif kw == '允许':
            pass  # 容忍轴：解析放行，语义留后续刀（见模块头）
        else:
            raise SanyanSyntaxError(f'约束关键字仅限 许/只许/禁/允许/限时，得到 `{kw}`')
    # 封印域：只许 声明"能力宇宙恰为此枚举集"。任何越出封印的 许 = 可判定违规（parse 期报错，
    # 不留运行时条件）——这正是 只许 区别于 许 的地方：许是加法下界，只许是封死的上界。
    if has_seal:
        outside = granted - sealed
        if outside:
            raise SanyanValueError(
                f'许 {sorted(outside)} 越出 只许 封印域 {sorted(sealed)}——封印后不可再加（可判定性法则）'
            )
        allowed: set = sealed
    else:
        allowed = granted
    return frozenset(allowed), frozenset(denied), timeout


def _task_op(evaluator, args):
    """任务(名, (约束 …), 体…) — 在能力帧内执行体，退出必弹帧（单调收紧）。"""
    if len(args) < 2:
        raise SanyanSyntaxError('任务 需要 名 + (约束 …) + 体')
    allowed, denied, timeout = _parse_constraint(args[1])
    push_frame(evaluator, allowed, denied, timeout=timeout)
    try:
        result: object = TritValue(0)
        for expr in args[2:]:
            result = evaluator.eval(expr)
        return result
    finally:
        pop_frame(evaluator)


def _constraint_op(evaluator, args):
    raise SanyanSyntaxError('约束 子句只能作为 任务 的第二参出现，不能单独求值')


def _can_op(evaluator, args):
    """能否(能力类) → 真/假：权限探询，恒不返回可能（认知/权限分层律 D4）。"""
    if len(args) < 1:
        raise SanyanSyntaxError('能否 需要一个能力类参数')
    a = args[0]
    cap = _dequote(a) if isinstance(a, str) else str(evaluator.eval(a))
    return TritValue(1 if can(evaluator, cap) else -1)


register('任务', _task_op)
register('约束', _constraint_op)
register('能否', _can_op)
