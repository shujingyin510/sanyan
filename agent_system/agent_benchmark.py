"""Real Benchmark — 真实基准测试"""

import statistics
import time
from typing import Dict, List


class RealBenchmark:
    """真实基准测试：before/after 耗时对比"""

    def __init__(self):
        self._results: List[Dict] = []

    def measure(self, func, iterations: int = 5) -> Dict:
        """测量函数执行时间"""
        times = []
        for _ in range(iterations):
            start = time.time()
            try:
                func()
            except Exception:
                pass
            times.append(time.time() - start)

        if not times:
            return {'avg_ms': 0, 'min_ms': 0, 'max_ms': 0, 'stdev': 0}

        avg = statistics.mean(times)
        return {
            'avg_ms': avg * 1000,
            'min_ms': min(times) * 1000,
            'max_ms': max(times) * 1000,
            'stdev': statistics.stdev(times) * 1000 if len(times) > 1 else 0,
            'iterations': len(times),
        }

    def compare(self, before_func, after_func, iterations: int = 5) -> Dict:
        """对比 before/after 性能"""
        before = self.measure(before_func, iterations)
        after = self.measure(after_func, iterations)

        if before['avg_ms'] > 0:
            speedup = (before['avg_ms'] - after['avg_ms']) / before['avg_ms']
        else:
            speedup = 0

        result = {
            'before': before,
            'after': after,
            'speedup': speedup,
            'speedup_pct': f'{speedup * 100:.1f}%',
            'improved': speedup > 0,
        }

        self._results.append(result)
        return result

    def summary(self) -> str:
        if not self._results:
            return '无基准测试数据'
        improved = sum(1 for r in self._results if r['improved'])
        avg_speedup = sum(r['speedup'] for r in self._results) / len(self._results)
        return (
            f'基准测试: {len(self._results)}次 | '
            f'提升: {improved}/{len(self._results)} | '
            f'平均提升: {avg_speedup * 100:.1f}%'
        )
