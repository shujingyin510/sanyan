"""
npc_decision.py — 游戏 NPC「犹豫」状态（Python 诚实对照）
对照 examples/npc_decision.san

== 对照说明（诚实版）==
原 .san 里的二态对照说「不确定时只能随机猜」——这是【稻草人】。
真实的 Python 根本不用随机：把「犹豫」表示成 None（或三态枚举）即可，
和三言的「可能」一一对应、行为完全稳定、不抖动。

下面 npc_decision_honest() 就是这种诚实写法：flee 初始为 None（犹豫），
只有满足确定条件才置 True/False，否则一直保持 None。零随机、零抖动。

== 这个例子差距大吗？小，主要是人体工学。==
三言的优势：「可能」是语言内置的一等值，写起来自然、读起来直观。
Python 用 None/Enum 也能做到同样的事，只是「第三态」要自己约定、
每个 if 分支要记得处理 None。属于「写法顺手」层面的差距，
不是「二值做不到」。把它如实说清楚，比硬编一个随机版稻草人更有说服力。
"""

import random
from typing import Optional


def 感知():
    距离 = random.randint(1, 20)
    威胁 = random.randint(0, 10) / 10
    血量 = random.randint(0, 10) / 10
    return 距离, 威胁, 血量


def npc_decision_honest(距离, 威胁, 血量) -> Optional[bool]:
    """诚实的 Python 写法：None = 犹豫，一等表达，零随机。"""
    flee: Optional[bool] = None  # 默认犹豫（== 三言的「可能」）
    if 距离 < 3 and 威胁 > 0.8:
        flee = True
    elif 血量 < 0.3:
        flee = True
    elif 距离 > 10 and 威胁 < 0.3:
        flee = False
    # 其余情况：保持 None（犹豫），不猜
    return flee


def 描述(flee: Optional[bool]) -> str:
    if flee is True:
        return '逃跑（确定威胁）'
    if flee is False:
        return '进攻（确定安全）'
    return '犹豫中...（巡逻/环顾）'


def main():
    print('=== NPC 行为系统（Python 诚实对照）===')
    print('用 None 表达「犹豫」：稳定、不随机——原 .san 的『二值只能随机猜』是稻草人')
    print()

    for 帧 in range(1, 7):
        距离, 威胁, 血量 = 感知()
        flee = npc_decision_honest(距离, 威胁, 血量)
        print(f'帧{帧}: 距离={距离} 威胁={威胁:.1f} 血量={血量:.1f} → {描述(flee)}')

    print()
    print('=== 诚实结论 ===')
    print('Python 用 None / 三态枚举即可稳定表达「犹豫」，无需随机、不会抖动。')
    print('三言的真实优势是人体工学：「可能」是内置一等值，写读都更自然，')
    print('而 Python 要自己约定第三态、每个分支记得处理 None。差在顺手，不在能不能。')


if __name__ == '__main__':
    main()
