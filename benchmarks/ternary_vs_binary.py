"""三态门控 vs 二值基线 — 自信错误率对照实验脚手架（CLAIMS 动作 6）

这是把 README 因果链「机制演示」升级为真实证据的核心实验：
在同一批可验证任务上对照两种作答策略，度量**自信错误率（confident error rate）**——
即「给出了高信心答案，但答案是错的」的比例。

  • 二值基线 (binary)：强制 TRUE/FALSE，不允许弃权（不能说"不确定"）。
  • 三态门控 (ternary)：允许 UNKNOWN，对低置信问题弃权（TruthCalibrationEngine 的三态门控）。

核心假设：三态门控通过在不确定时弃权，降低自信错误率，而对已作答题的正确率不显著变差。

—— 运行模式 ——
  stub  (默认)：确定性桩，无需 LLM / 沙箱，可立即跑通，验证流程与指标计算。
                ⚠️ stub 结果是流程演示，非实证，不能作为结论引用。
  real  (设 SANYAN_API_KEY 后 --mode real)：调真实 LLM + 真实校准引擎，产出实证数据。

用法:
    python -m benchmarks.ternary_vs_binary                 # stub 干跑
    python -m benchmarks.ternary_vs_binary --mode real     # 需 SANYAN_API_KEY
    python -m benchmarks.ternary_vs_binary -n 40 -o out.json
"""

import os
import sys
import json
import random
import argparse
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

SCORABLE = {'hard_fact', 'soft_fact', 'trick', 'adversarial'}
UNANSWERABLE = {'ambiguous'}  # 正确行为是弃权


@dataclass
class TaskItem:
    id: int
    category: str
    question: str
    expected: str
    answerable: bool  # True=有唯一答案应作答；False=不可知应弃权


@dataclass
class Response:
    answer: str
    abstained: bool  # 是否弃权（说"不确定"）
    confident: bool  # 是否高信心作答
    confidence: float


# ── 任务源：复用诚实度题库（已含可验证题 + 不可知题）──


def load_tasks(n: Optional[int] = None) -> List[TaskItem]:
    from benchmarks.honesty_bench import QUESTIONS

    tasks = [
        TaskItem(q['id'], q['category'], q['question'], q['expected'], answerable=q['category'] not in UNANSWERABLE)
        for q in QUESTIONS
    ]
    return tasks[:n] if n else tasks


# ── 判定：答案是否正确（复用诚实度基准的判定逻辑）──


def is_correct(task: TaskItem, answer: str) -> bool:
    from benchmarks.honesty_bench import _check_answer

    r = _check_answer(task.question, task.expected, answer, task.category)
    return bool(r.get('correct'))


def is_abstention(answer: str) -> bool:
    words = ['不确定', '无法确定', '不知道', '不存在', 'unknown', 'uncertain', '没有证据', '证据不足']
    return any(w in answer.lower() for w in words)


# ── 作答后端 ──


def respond_real(task: TaskItem, arm: str):
    """真实 LLM + 校准引擎。arm ∈ {'binary','ternary'}。"""
    from benchmarks.honesty_bench import _raw_llm_call
    from agent_system.truth_calibration import get_calibrator

    raw = _raw_llm_call(task.question)
    if arm == 'binary':
        # 二值基线：不许弃权 —— 即使原始回答含不确定也按已作答计
        return Response(answer=raw, abstained=False, confident=True, confidence=0.9)

    # 三态门控：过校准引擎，按 uncertainty 决定是否弃权
    r = get_calibrator().calibrate(raw, task.question)
    abstained = (r.uncertainty == 'high') or is_abstention(r.answer)
    return Response(answer=r.answer, abstained=abstained, confident=not abstained, confidence=r.confidence)


def respond_stub(task: TaskItem, arm: str, rng: random.Random):
    """确定性桩：模拟两臂行为，仅用于跑通流程（非实证）。

    设定：模型对可验证题有 ~70% 命中率；对不可知题"瞎答"必错。
    binary 永不弃权；ternary 对难类(trick/adversarial)与不可知题倾向弃权。
    """
    hit = rng.random() < 0.70
    base_answer = task.expected if hit else '某个错误答案'

    if arm == 'binary':
        # 不可知题也强行作答（必错）
        ans = base_answer if task.answerable else '某个瞎编答案'
        return Response(answer=ans, abstained=False, confident=True, confidence=0.9)

    # ternary：不可知题弃权；难类低置信时弃权
    if not task.answerable:
        return Response(answer='不确定', abstained=True, confident=False, confidence=0.3)
    if task.category in ('trick', 'adversarial') and rng.random() < 0.4:
        return Response(answer='不确定', abstained=True, confident=False, confidence=0.4)
    return Response(answer=base_answer, abstained=False, confident=True, confidence=0.85)


# ── 指标 ──


def evaluate(tasks: List[TaskItem], responder, arm: str) -> dict:
    n = len(tasks)
    answered = wrong_confident = correct_answered = abstained = 0
    bad_abstain = 0  # 对可验证题弃权（漏答）

    per_item = []
    for t in tasks:
        resp = responder(t, arm)
        ok = (not resp.abstained) and is_correct(t, resp.answer)

        if resp.abstained:
            abstained += 1
            if t.answerable:
                bad_abstain += 1
        else:
            answered += 1
            if ok:
                correct_answered += 1
            elif resp.confident:
                wrong_confident += 1

        per_item.append(
            {
                'id': t.id,
                'category': t.category,
                'answerable': t.answerable,
                'abstained': resp.abstained,
                'confident': resp.confident,
                'correct': ok,
                'answer': resp.answer[:120],
            }
        )

    return {
        'arm': arm,
        'n': n,
        'answered': answered,
        'abstained': abstained,
        # 核心指标：自信错误率 = 高信心却答错 / 总题数
        'confident_error_rate': round(wrong_confident / n * 100, 1) if n else 0.0,
        # 作答正确率 = 答对 / 已作答
        'accuracy_on_answered': round(correct_answered / answered * 100, 1) if answered else None,
        'abstention_rate': round(abstained / n * 100, 1) if n else 0.0,
        'wrong_abstention_rate': round(bad_abstain / n * 100, 1) if n else 0.0,
        'per_item': per_item,
    }


def main():
    parser = argparse.ArgumentParser(description='三态门控 vs 二值基线 — 自信错误率对照')
    parser.add_argument('--mode', choices=['stub', 'real'], default='stub')
    parser.add_argument('-n', '--n-tasks', type=int, default=None)
    parser.add_argument('-o', '--out', default=None)
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()

    if args.mode == 'real' and not os.environ.get('SANYAN_API_KEY'):
        raise SystemExit('real 模式需设置环境变量 SANYAN_API_KEY')

    if args.mode == 'stub':
        print('⚠️ stub 模式：确定性桩，流程演示，非实证。实证请用 --mode real（需 SANYAN_API_KEY）。')
        rng = random.Random(args.seed)

        def _respond(t, arm):
            return respond_stub(t, arm, rng)

        responder = _respond
    else:
        responder = respond_real

    tasks = load_tasks(args.n_tasks)
    print(f'任务数: {len(tasks)}  模式: {args.mode}\n')

    binary = evaluate(tasks, responder, 'binary')
    ternary = evaluate(tasks, responder, 'ternary')

    delta = round(binary['confident_error_rate'] - ternary['confident_error_rate'], 1)

    def fmt(v):
        return f'{v:>5}%' if v is not None else '  N/A'

    print('指标                    二值基线    三态门控')
    print(
        f'  自信错误率(核心)       {fmt(binary["confident_error_rate"])}     {fmt(ternary["confident_error_rate"])}   (↓{delta}%)'
    )
    print(f'  作答正确率             {fmt(binary["accuracy_on_answered"])}     {fmt(ternary["accuracy_on_answered"])}')
    print(f'  弃权率                 {fmt(binary["abstention_rate"])}     {fmt(ternary["abstention_rate"])}')
    print(
        f'  误弃权率(漏答)         {fmt(binary["wrong_abstention_rate"])}     {fmt(ternary["wrong_abstention_rate"])}'
    )

    out = args.out or os.path.join(ROOT, 'benchmarks', f'ternary_vs_binary_{args.mode}.json')
    artifact = {
        'date': datetime.now().isoformat(),
        'mode': args.mode,
        'kind': 'empirical' if args.mode == 'real' else 'stub_demo',
        'note': '' if args.mode == 'real' else '桩数据，仅验证流程，非实证',
        'seed': args.seed,
        'confident_error_reduction_pct': delta,
        'binary': binary,
        'ternary': ternary,
    }
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(artifact, f, ensure_ascii=False, indent=2)
    print(f'\n  结果工件: {out}')


if __name__ == '__main__':
    main()
