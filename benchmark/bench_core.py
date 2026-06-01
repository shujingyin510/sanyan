"""三言核心性能基准

运行: python -X utf8 benchmark/bench_core.py
测量: Python 求值器延迟（微秒/操作）
"""

import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from evaluator import SanyanEvaluator

ITERS = 10000


def bench(name, ast_expr):
    e = SanyanEvaluator()
    e.eval(ast_expr)  # warmup
    t0 = time.perf_counter()
    for _ in range(ITERS):
        e.eval(ast_expr)
    us = (time.perf_counter() - t0) * 1_000_000 / ITERS
    print(f'  {name:20s}  {us:8.1f} us/op')


if __name__ == '__main__':
    print(f'三言 Python 求值器基准 ({ITERS} 次迭代)')
    print('-' * 42)
    bench('整数加法', ['add', 10, 20])
    bench('乘法', ['mul', 6, 7])
    bench('条件分支', ['if', ['gt', 5, 3], 1, -1])
    bench('变量设置/读取', ['do', ['set', 'x', 42], 'x'])
    bench('字符串拼接', ['concat', '"hello"', '"world"'])
    bench('列表创建', ['list', 1, 2, 3, 4, 5])
    bench('字典创建', ['dict', '"a"', 1, '"b"', 2])
    print('-' * 42)
