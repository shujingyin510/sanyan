"""
circuit_sim.py — Kleene 三值逻辑电路（Python 诚实对照）
对照 examples/circuit_sim.san

== 对照说明（诚实版）==
三言里 且/或/非 是【内置】的 Kleene 强三值运算符，开箱即用、语义经数学证明。
Python 没有三值布尔。要做同一件事，你必须【先手写整套 Kleene 代数】——
下面的 Trit 类（约 25 行）。地基造好之后，电路表达式和三言一模一样长。

== 这个例子差距大吗？大。==
不是语法糖的差距，是「是否自带一套保证正确的三值代数」的差距：
  - 9 种 / 3^10 种输入组合，真值表由 min/max/negate 数学保证正确；
  - 自己手写时，AND/OR/NOT 的真值表只要错一格，所有下游电路静默出错；
  - 三言把这层地基冻进语言，用户不可能写错。
诚实的结论：三言赢在「内置 + 正确性保证」，不在表达式本身更短。
"""

from itertools import product


# ── 必须先手写 Kleene 强三值代数（三言内置，Python 要自己造）──
# 编码：+1=真, 0=可能, -1=假
# Kleene 强逻辑恰好等于：AND=min, OR=max, NOT=取负。错一格全盘皆错。
class Trit:
    __slots__ = ('v',)
    _名 = {1: '真', 0: '可能', -1: '假'}

    def __init__(self, v: int):
        self.v = v

    def __and__(self, o: 'Trit') -> 'Trit':  # Kleene AND
        return Trit(min(self.v, o.v))

    def __or__(self, o: 'Trit') -> 'Trit':  # Kleene OR
        return Trit(max(self.v, o.v))

    def __invert__(self) -> 'Trit':  # Kleene NOT
        return Trit(-self.v)

    def __eq__(self, o) -> bool:
        return isinstance(o, Trit) and self.v == o.v

    def __hash__(self) -> int:
        return hash(self.v)

    def __repr__(self) -> str:
        return Trit._名[self.v]


真, 可能, 假 = Trit(1), Trit(0), Trit(-1)


def 验证电路(A: Trit, B: Trit) -> Trit:
    # 注意：地基造好后，这一行和三言完全一样
    return (A & B) | (~A)


def 十输入电路(a, b, c, d, e, f, g, h, i, j) -> Trit:
    层1_1 = a & b
    层1_2 = c & d
    层1_3 = e | f
    层1_4 = ~g
    层1_5 = h & i & j
    层2_1 = 层1_1 | 层1_2
    层2_2 = 层1_3 & 层1_4
    层2_3 = 层2_2 | 层1_5
    return 层2_1 & 层2_3


def main():
    print('=== Kleene 三值逻辑电路模拟器（Python 对照）===')
    print('Python 没有内置三值逻辑：上面手写了 Trit 类（约 25 行）才能开始')
    print()

    三态 = [真, 假, 可能]

    print('验证电路：(A 且 B) 或 (非 A) — 全部 9 种输入组合')
    print('A      B      |  左    右    |  输出')
    print('─────  ─────  | ────  ────  | ────')
    for A in 三态:
        for B in 三态:
            左 = A & B
            右 = ~A
            结果 = 左 | 右
            print(f'{A!r:<5}  {B!r:<5}  | {左!r:<4}  {右!r:<4}  | {结果!r}')

    print()
    print('=== 关键点 ===')
    print('当 A=可能, B=真 时：输出=可能（与三言逐格一致）')
    print('  → Python 同样能算对，但前提是你手写的 AND/OR/NOT 真值表一格不错')
    print('  → 三言把这套代数冻进语言，用户无从写错；这才是真正的差距')

    print()
    print('=== 10 输入组合电路全量验证 ===')
    seen = set()
    for combo in product(三态, repeat=10):
        seen.add(十输入电路(*combo).v)
    print(f'输入组合空间: 3^10 = {3**10} 种，全部求值完成')
    print(f'输出取值集合: {sorted(Trit(v).__repr__() for v in seen)}')
    print('（手写 Trit 正确 ⇒ 全部组合语义正确；错一格则此处静默出错）')

    print()
    print('=== 诚实结论 ===')
    print('电路表达式：三言与 Python 等长（都是 (A 且 B) 或 (非 A)）')
    print('差距在地基：三言内置 Kleene 代数且保证正确；Python 要自造且可能写错')


if __name__ == '__main__':
    main()
