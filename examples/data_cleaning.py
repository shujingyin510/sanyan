"""
data_cleaning.py — 数据清洗 NULL 传播（Python 诚实对照）
对照 examples/data_cleaning.san

== 对照说明（诚实版）==
三言用「可能」明确表达「数据不够，无法判定」，且 可能 且 可能 = 可能
（Kleene 自动传播，不用手写）。

Python 这边我给两个版本，诚实对照：
  1) score_careless —— 全部字段未验证时返回 0.0。这是【真实会发生的 bug】：
     下游把 0.0 当成「评分差/信用差」，其实只是数据没到。
  2) score_safe ——  全部字段未验证时返回 None。这是【好的 Python 写法】，
     和三言「可能」语义等价；而且 None 还会在你忘记处理时直接抛错。

== 这个例子差距大吗？偏小，要诚实。==
Python 完全能写对（score_safe == 三言行为）。差别只有两点：
  - 三言的「可能」是一等值，组合时自动传播；Python 的 None 要你每步显式 if 判断；
  - Python 不【强制】你写对——score_careless 这种 bug 写起来毫不费力。
所以这里三言赢在「默认安全 + 自动传播」，不是「Python 做不到」。
"""

import random
from typing import Optional

FIELDS = ['手机_已验证', '邮箱_已验证', '身份证_已验证', '地址_已验证']

# 三态编码：True=真, None=可能(未验证), False=假
TRITS = [True, None, False]


def 随机态():
    return random.choice(TRITS)


def 生成记录() -> dict:
    rec = {'姓名': f'用户_{random.randint(1000, 9999)}'}
    for f in FIELDS:
        rec[f] = 随机态()
    return rec


def score_careless(rec: dict):
    """草率版：全部未验证时返回 0.0 —— 真实会发生的 bug。"""
    total = 0
    valid = 0
    for f in FIELDS:
        s = rec[f]
        if s is None:  # 未验证：跳过
            continue
        elif s is True:
            total += 1
            valid += 1
        else:
            valid += 1
    if valid == 0:
        return 0.0  # ← bug：看起来像「评分 0 = 信用差」
    return total / valid


def score_safe(rec: dict) -> Optional[float]:
    """安全版：全部未验证时返回 None —— 与三言「可能」等价。"""
    total = 0
    valid = 0
    for f in FIELDS:
        s = rec[f]
        if s is None:  # 未验证：跳过
            continue
        elif s is True:
            total += 1
            valid += 1
        else:
            valid += 1
    if valid == 0:
        return None  # ← 正确：数据不够，明确告知下游
    return total / valid


def 描述(v) -> str:
    if v is None:
        return 'None（数据不够，需更多数据）'
    return f'{v:.2f}'


def main():
    print('=== 数据清洗 NULL 传播（Python 对照）===')
    print('三言：可能 一等值 + 自动传播；Python：None，要你显式处理且不被强制')
    print()

    print('--- 普通 3 条记录 ---')
    for i in range(1, 4):
        rec = 生成记录()
        print(
            f'{i}. {rec["姓名"]}  字段={["真" if rec[f] is True else "假" if rec[f] is False else "可能" for f in FIELDS]}'
        )
        print(f'   草率版 score_careless → {描述(score_careless(rec))}')
        print(f'   安全版 score_safe     → {描述(score_safe(rec))}')
        print()

    print('--- 极端 case：全部字段未验证 ---')
    全空 = {'姓名': '用户_未知', **{f: None for f in FIELDS}}
    careless = score_careless(全空)
    safe = score_safe(全空)
    print(f'  草率版 → {描述(careless)}')
    print('    ↑ 返回 0.0：下游会误判为「信用差」，其实只是字段没验证（真实 bug）')
    print(f'  安全版 → {描述(safe)}')
    print('    ↑ 返回 None：与三言「可能」一致，明确告诉下游需要更多数据')
    print()

    print('=== 诚实结论 ===')
    print('Python 能写对（score_safe == 三言行为），所以这不是「Python 做不到」。')
    print('三言的优势是：')
    print('  1) 「可能」是一等值，组合时 Kleene 自动传播，少写显式 None 检查；')
    print('  2) 默认就安全——score_careless 那种返回 0 的坑，在 Python 里太好踩。')


if __name__ == '__main__':
    main()
