"""性能基准测试套件。

运行方式：
    python benchmark/run_benchmark.py               # 运行所有基准
    python benchmark/run_benchmark.py --quick        # 仅运行小规模基准
    python benchmark/run_benchmark.py --profile      # 同时输出 --profile 详情
"""
from __future__ import annotations
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from evaluator import SanyanEvaluator
from skin import SkinManager
from sugar import SugarConverter


BENCH_DIR = os.path.dirname(os.path.abspath(__file__))

BENCHMARKS = [
    ("fibonacci", "fib(25)", "benchmark/fibonacci.san"),
    ("primes", "count_primes(5000)", "benchmark/primes.san"),
    ("fizzbuzz", "fizzbuzz(100)", "benchmark/fizzbuzz.san"),
    ("fib_iter", "fib(10000)", "benchmark/fib_iter.san"),
]


def run_benchmark(name: str, label: str, filepath: str, profile: bool = False) -> dict:
    abs_path = os.path.join(BENCH_DIR, os.path.basename(filepath))
    if not os.path.exists(abs_path):
        alt_path = os.path.join(os.path.dirname(BENCH_DIR), filepath)
        abs_path = alt_path

    with open(abs_path, "r", encoding="utf-8") as f:
        code = f.read()

    skin_mgr = SkinManager("chinese")
    evaluator = SanyanEvaluator(skin_manager=skin_mgr)

    try:
        ast = SugarConverter.convert(code, skin_mgr)
    except SyntaxError:
        return {"name": name, "error": "Python SugarConverter 解析失败"}

    if ast is None:
        return {"name": name, "error": "解析失败"}

    evaluator.profile_start()
    t0 = time.perf_counter()
    evaluator.eval(ast)
    elapsed = time.perf_counter() - t0
    report = evaluator.profile_report() if profile else ""

    return {
        "name": name,
        "label": label,
        "time": elapsed,
        "profile": report,
    }


def main():
    parser = argparse.ArgumentParser(description="三言基准测试套件")
    parser.add_argument("--quick", action="store_true", help="仅运行小规模基准")
    parser.add_argument("--profile", action="store_true", help="输出 profile 详情")
    args = parser.parse_args()

    selected = BENCHMARKS
    if args.quick:
        selected = [b for b in BENCHMARKS if b[0] in ("fibonacci", "fizzbuzz")]

    print("=" * 60)
    print("三言性能基准测试")
    print("=" * 60)

    results = []
    for name, label, filepath in selected:
        print(f"\n▶ 运行: {name} ({label})")
        result = run_benchmark(name, label, filepath, profile=args.profile)
        results.append(result)
        if "error" in result:
            print(f"  ✗ {result['error']}")
        else:
            print(f"  ✓ {result['time']:.4f} 秒")
            if result.get("profile") and args.profile:
                for line in result["profile"].strip().split("\n"):
                    print(f"    {line}")

    print("\n" + "=" * 60)
    print("汇总")
    print("-" * 60)
    for r in results:
        if "error" in r:
            print(f"  {r['name']:20s}  ✗ {r['error']}")
        else:
            print(f"  {r['name']:20s}  {r['time']:.4f} 秒")
    print("=" * 60)


if __name__ == "__main__":
    main()
