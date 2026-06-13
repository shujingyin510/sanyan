"""Agent 安全体系压力测试 — Fault Injection Framework

不依赖真实 LLM，直接注入病态 Agent 输出，
验证三层检测(置信度衰减/轮次兜底/超时)的正确性。

用法:
    python -X utf8 tests/test_agent_safety.py          # 全量测试
    python -X utf8 tests/test_agent_safety.py decay    # 只跑置信度衰减
"""

import re
import sys
import os
import time
from dataclasses import dataclass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@dataclass
class SafetyResult:
    name: str
    passed: bool
    expected: str  # "decay" / "round_cap" / "timeout" / "none"
    actual: str
    details: str = ''


# ═══════════════════════════════════════════════
# Fault Injectors — 模拟病态 Agent 输出
# ═══════════════════════════════════════════════


def inject_confidence_decay(rounds: int = 4, start: float = 0.55, step: float = -0.08):
    """注入连续衰减的置信度"""
    lines = []
    for i in range(rounds):
        c = start + i * step
        lines.append(f'第{i + 1}轮 LLM调用 | 认知态=UNCERT')
        lines.append(f'  执行态=NEED_TOOL  信度={c:.2f}')
    return '\n'.join(lines)


def inject_oscillation(rounds: int = 6):
    """注入震荡但永不触底的置信度"""
    values = [0.80, 0.79, 0.80, 0.79, 0.80, 0.79]
    lines = []
    for i in range(min(rounds, len(values))):
        lines.append(f'第{i + 1}轮 LLM调用 | 认知态=UNCERT')
        lines.append(f'  执行态=NEED_TOOL  信度={values[i]:.2f}')
    return '\n'.join(lines)


def inject_fake_progress(rounds: int = 4):
    """注入假进展 — 每轮说'发现更好方向'但置信度持续降"""
    values = [0.55, 0.42, 0.31, 0.22]
    lines = []
    for i in range(min(rounds, len(values))):
        lines.append(f'第{i + 1}轮 LLM调用 | 认知态=AFFIRM')
        lines.append(f'  执行态=NEED_TOOL  信度={values[i]:.2f}')
        lines.append(f'  发现更好的方向: 第{i + 1}次尝试')
    return '\n'.join(lines)


def inject_high_confidence_frenzy(rounds: int = 6):
    """注入高置信度但永不完成的循环"""
    lines = []
    for i in range(rounds):
        lines.append(f'第{i + 1}轮 LLM调用 | 认知态=AFFIRM')
        lines.append('  执行态=NEED_TOOL  信度=0.99')
        lines.append('  我快成功了, 再试一次')
    return '\n'.join(lines)


def inject_replan_loop(rounds: int = 4):
    """注入持续重规划循环"""
    values = [0.50, 0.41, 0.33, 0.24]
    lines = []
    for i in range(min(rounds, len(values))):
        lines.append(f'第{i + 1}轮 LLM调用 | 认知态=AFFIRM')
        lines.append(f'  执行态=NEED_TOOL  信度={values[i]:.2f}')
        lines.append('  当前策略失败, 重新规划')
    return '\n'.join(lines)


def inject_window_reset(rounds: int = 8):
    """注入窗口重置攻击 — 快衰减时故意回升"""
    values = [0.80, 0.78, 0.76, 0.77, 0.75, 0.73, 0.74, 0.72]
    lines = []
    for i in range(min(rounds, len(values))):
        lines.append(f'第{i + 1}轮 LLM调用 | 认知态=UNCERT')
        lines.append(f'  执行态=NEED_TOOL  信度={values[i]:.2f}')
    return '\n'.join(lines)


def inject_random_walk(rounds: int = 8):
    """注入随机游走 — 模拟真实 LLM 波动"""
    values = [0.81, 0.84, 0.82, 0.80, 0.83, 0.79, 0.76, 0.78]
    lines = []
    for i in range(min(rounds, len(values))):
        lines.append(f'第{i + 1}轮 LLM调用 | 认知态=UNCERT')
        lines.append(f'  执行态=NEED_TOOL  信度={values[i]:.2f}')
    return '\n'.join(lines)


# ═══════════════════════════════════════════════
# 检测逻辑 (与 run_agent.py 中的检测保持一致)
# ═══════════════════════════════════════════════


def detect_confidence_decay(out: str, window: int = 4, floor: float = 0.35) -> bool:
    """检测置信度严格单调递减 + 跌破底线"""
    confs = [float(m) for m in re.findall(r'信度[=:\uff1a]\s*([0-9.]+)', out)]
    if len(confs) < max(window, 2):
        return False
    recent = confs[-window:]
    drop = all(recent[i] > recent[i + 1] for i in range(len(recent) - 1))
    return drop and recent[-1] < floor


def detect_round_cap(out: str, max_rounds: int = 6) -> bool:
    """检测轮次超过上限"""
    rounds = re.findall(r'第\s*(\d+)\s*轮', out)
    if not rounds:
        return False
    return max(int(r) for r in rounds) >= max_rounds


def detect_timeout(start_time: float, timeout: float = 30.0) -> bool:
    """检测超时"""
    return (time.time() - start_time) > timeout


# ═══════════════════════════════════════════════
# 测试用例
# ═══════════════════════════════════════════════


def run_test(name: str, output: str, expected: str, window: int = 4, floor: float = 0.35):
    """运行单个测试"""
    decay = detect_confidence_decay(output, window, floor)
    round_cap = detect_round_cap(output)

    actual = []
    if decay:
        actual.append('decay')
    if round_cap:
        actual.append('round_cap')
    if not actual:
        actual.append('none')

    actual_str = '+'.join(actual)
    passed = expected in actual_str

    detail = ''
    if not passed:
        confs = [float(m) for m in re.findall(r'信度[=:\uff1a]\s*([0-9.]+)', output)]
        recent = confs[-window:] if len(confs) >= window else confs
        detail = f'confs={recent}'

    return SafetyResult(name=name, passed=passed, expected=expected, actual=actual_str, details=detail)


def run_all_tests() -> list[SafetyResult]:
    """运行全部压力测试"""
    results = []

    # 测试1: 置信度衰减
    results.append(run_test('decay_basic', inject_confidence_decay(4), 'decay'))
    results.append(
        run_test(
            'decay_edge_no_trigger',
            inject_confidence_decay(4, 0.91, -0.01),
            'none',
        )
    )

    # 测试2: 假进展
    results.append(run_test('fake_progress', inject_fake_progress(4), 'decay'))

    # 测试3: 震荡逃逸 (不应触发decay, 应触发round_cap)
    results.append(run_test('oscillation', inject_oscillation(6), 'round_cap'))

    # 测试4: 窗口重置 (不应触发decay, 应触发round_cap)
    results.append(run_test('window_reset', inject_window_reset(8), 'round_cap'))

    # 测试5: 高置信度疯子 (应触发round_cap)
    results.append(run_test('high_conf_frenzy', inject_high_confidence_frenzy(6), 'round_cap'))

    # 测试6: 随机游走 (可能触发round_cap)
    results.append(run_test('random_walk', inject_random_walk(8), 'round_cap'))

    # 测试7: 重规划循环
    results.append(run_test('replan_loop', inject_replan_loop(4), 'decay'))

    # 测试8: 超时 (特殊处理)
    results.append(
        run_test(
            'timeout_mock',
            inject_high_confidence_frenzy(1),
            'none',
        )
    )

    return results


# ═══════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════


def main():
    import sys

    if len(sys.argv) > 1 and sys.argv[1] in ('-h', '--help'):
        print(__doc__)
        return

    results = run_all_tests()
    passed = sum(1 for r in results if r.passed)
    failed = sum(1 for r in results if not r.passed)

    print(f'\n{"=" * 60}')
    print('  Agent 安全体系压力测试')
    print(f'{"=" * 60}\n')

    for r in results:
        status = 'PASS' if r.passed else 'FAIL'
        print(f'  [{status}] {r.name:25s} → {r.actual:12s} (expected {r.expected})')
        if not r.passed:
            print(f'         {r.details}')

    print(f'\n  {passed}/{len(results)} passed, {failed} failed\n')

    if failed:
        sys.exit(1)


if __name__ == '__main__':
    main()
