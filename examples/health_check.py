"""
health_check.py — API 三态健康检测（Python 诚实对照）
对照 examples/health_check.san

== 对照说明（诚实版）==
场景：HTTP 超时 ≠ 服务宕机。需要 在线 / 超时 / 宕机 三种状态。

== 这个例子差距大吗？弱。要老实承认。==
Python 用一个 Enum{UP, TIMEOUT, DOWN} 就能干净地表达三态，
聚合逻辑（数 宕机/超时/在线）两边几乎一模一样、代码量相当。
也就是说：这个例子【证明不了】二值的根本短板——枚举就是三态。

三言在这里唯一的额外优势，是聚合可以直接用 Kleene 的 且/或 传播
（一个超时 + 一个正常 = 不确定），写法更短；但只要你像下面这样
用显式计数，Python 与三言完全打平。

结论：想真正展示三态价值，circuit_sim（内置 Kleene 代数）才是有力的例子，
health_check 更多是「枚举的可读写法」，不该宣称「二值做不到」。
"""

from enum import Enum
import random


class Health(Enum):
    UP = '在线'
    TIMEOUT = '超时'  # 不等于宕机！
    DOWN = '宕机'


def 读健康状态(name: str) -> Health:
    r = random.randint(1, 10)
    if r <= 5:
        return Health.UP
    elif r <= 8:
        return Health.TIMEOUT
    return Health.DOWN


def 系统健康(services: list[str]) -> Health:
    counts = {Health.UP: 0, Health.TIMEOUT: 0, Health.DOWN: 0}
    for s in services:
        st = 读健康状态(s)
        print(f'  [检测] {s} → {st.value}')
        counts[st] += 1

    print(f'  汇总: 在线={counts[Health.UP]} 超时={counts[Health.TIMEOUT]} 宕机={counts[Health.DOWN]}')

    # 与三言完全相同的显式聚合逻辑
    if counts[Health.DOWN] > 0:
        print('  → 综合判定：系统故障')
        return Health.DOWN
    if counts[Health.TIMEOUT] == 0:
        print('  → 综合判定：系统正常')
        return Health.UP
    if counts[Health.TIMEOUT] == len(services):
        print('  → 综合判定：网络可能中断（全部超时）')
        return Health.TIMEOUT
    print('  → 综合判定：系统部分不确定')
    return Health.TIMEOUT


def main():
    print('=== API 三态健康检测（Python 对照）===')
    print('Python 的 Enum 就能表达 在线/超时/宕机 三态——本例二值并不吃亏')
    print()

    services = ['用户服务', '订单服务', '支付服务', '库存服务']
    result = 系统健康(services)
    print(f'最终判定: {result.value}')
    print()

    print('=== 诚实结论 ===')
    print('超时≠宕机这个洞见是对的，但用 Enum 三态即可，二值并非做不到。')
    print('三言此处仅在『用 且/或 表达聚合传播』时写法更短；显式计数则两边等价。')
    print('真正能拉开差距的三态例子是 circuit_sim（内置 Kleene 代数，正确性保证）。')


if __name__ == '__main__':
    main()
