"""诚实度基准 — 原始数据导出 + 从数据重算（CLAIMS 动作 5）

目的：把 honesty_bench 跑出的 honesty_bench_results.json 拆成人可读、可审计的工件：
  1. honesty_questions.csv      —— 题库（100 题 × 5 类，含期望答案）
  2. honesty_per_question.csv   —— 逐题打分表（baseline vs calibrated 对齐）
  3. honesty_recomputed.json    —— 从逐题原始数据重算的头条指标（与报告自带值对账）

本脚本只读取已有的 JSON 结果，不调用 LLM、不需要沙箱，可随时运行。

用法:
    python -m benchmarks.export_honesty_data
    python benchmarks/export_honesty_data.py --in benchmarks/honesty_bench_results.json
"""

import os
import csv
import json
import argparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_IN = os.path.join(ROOT, 'benchmarks', 'honesty_bench_results.json')
OUT_DIR = os.path.join(ROOT, 'benchmarks')

SCORABLE_CATEGORIES = {'hard_fact', 'soft_fact', 'trick'}


def export_question_bank(path: str) -> int:
    """从 honesty_bench.QUESTIONS 导出题库 CSV。"""
    import sys

    sys.path.insert(0, ROOT)
    from benchmarks.honesty_bench import QUESTIONS, CATEGORY_NAMES

    with open(path, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['id', 'category', 'category_cn', 'question', 'expected'])
        for q in QUESTIONS:
            w.writerow(
                [q['id'], q['category'], CATEGORY_NAMES.get(q['category'], q['category']), q['question'], q['expected']]
            )
    return len(QUESTIONS)


def export_per_question(results: list, path: str) -> int:
    """把 baseline / calibrated 逐题结果按 id 对齐成一行，便于人工核对。"""
    by_id = {}
    for r in results:
        row = by_id.setdefault(r['id'], {'id': r['id'], 'category': r['category'], 'question': r['question']})
        src = r.get('source', 'baseline')
        row[f'{src}_answer'] = r.get('answer', '')
        row[f'{src}_correct'] = r.get('correct')
        row[f'{src}_overconfident'] = r.get('overconfident')
        row[f'{src}_confidence'] = r.get('confidence', '')
        row[f'{src}_reason'] = r.get('reason', '')

    cols = [
        'id',
        'category',
        'question',
        'baseline_answer',
        'baseline_correct',
        'baseline_overconfident',
        'baseline_reason',
        'calibrated_answer',
        'calibrated_correct',
        'calibrated_overconfident',
        'calibrated_confidence',
        'calibrated_reason',
    ]

    with open(path, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction='ignore')
        w.writeheader()
        for rid in sorted(by_id):
            w.writerow(by_id[rid])
    return len(by_id)


def recompute_stats(results: list, source: str) -> dict:
    """只用逐题原始数据重算头条三指标，独立于报告自带的汇总值。"""
    rows = [r for r in results if r.get('source') == source]
    scorable = [r for r in rows if r['category'] in SCORABLE_CATEGORIES]

    accuracy = round(sum(1 for r in scorable if r.get('correct')) / len(scorable) * 100, 1) if scorable else None

    wrong = [r for r in rows if r.get('correct') is False]
    wrong_high = [r for r in wrong if r.get('overconfident')]
    overreach = round(len(wrong_high) / len(wrong) * 100, 1) if wrong else 0.0

    return {
        'source': source,
        'n': len(rows),
        'accuracy': accuracy,
        'overreach': overreach,
        'wrong_total': len(wrong),
        'wrong_high': len(wrong_high),
    }


def main():
    parser = argparse.ArgumentParser(description='诚实度基准原始数据导出 + 重算')
    parser.add_argument('--in', dest='infile', default=DEFAULT_IN, help='honesty_bench_results.json 路径')
    args = parser.parse_args()

    if not os.path.exists(args.infile):
        raise SystemExit(f'未找到结果文件: {args.infile}\n先运行: sanyan bench --type honesty')

    with open(args.infile, encoding='utf-8') as f:
        report = json.load(f)
    results = report.get('results', [])

    q_csv = os.path.join(OUT_DIR, 'honesty_questions.csv')
    pq_csv = os.path.join(OUT_DIR, 'honesty_per_question.csv')
    recomp_json = os.path.join(OUT_DIR, 'honesty_recomputed.json')

    n_q = export_question_bank(q_csv)
    n_pq = export_per_question(results, pq_csv)

    base = recompute_stats(results, 'baseline')
    cal = recompute_stats(results, 'calibrated')
    recomputed = {
        'from': os.path.basename(args.infile),
        'baseline': base,
        'calibrated': cal,
        'overreach_improvement': round(base['overreach'] - cal['overreach'], 1),
    }
    with open(recomp_json, 'w', encoding='utf-8') as f:
        json.dump(recomputed, f, ensure_ascii=False, indent=2)

    # 与报告自带的汇总值对账，确保「从数据重算」一致
    rep_base = report.get('baseline', {})
    rep_cal = report.get('calibrated', {})
    print(f'题库:        {q_csv}  ({n_q} 题)')
    print(f'逐题打分表:  {pq_csv}  ({n_pq} 行)')
    print(f'重算结果:    {recomp_json}')
    print('\n— 重算 vs 报告自带值 对账 —')
    print(f'  正确率(baseline):   重算 {base["accuracy"]}%  报告 {rep_base.get("accuracy")}%')
    print(f'  正确率(calibrated): 重算 {cal["accuracy"]}%  报告 {rep_cal.get("accuracy")}%')
    print(f'  认知越界(baseline):   重算 {base["overreach"]}%  报告 {rep_base.get("overconfidence")}%')
    print(f'  认知越界(calibrated): 重算 {cal["overreach"]}%  报告 {rep_cal.get("overconfidence")}%')
    print(f'  越界改善: {recomputed["overreach_improvement"]}%')


if __name__ == '__main__':
    main()
