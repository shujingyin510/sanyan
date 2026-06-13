"""多Agent死循环测试

扔一个自相矛盾的任务给 LLM，验证三个检测机制:
  1. 置信度衰减 → 重启
  2. 轮次过多 → 截断
  3. 超时 → 杀死

用法: python test_deadloop.py
      python test_deadloop.py --quick    (用简单任务测试框架)
"""

import sys

sys.path.insert(0, '.')
import io
import os
import re
import time

from run_agent import load_api_key, _register_aliases
from evaluator import SanyanEvaluator
from ops.file_ops import clear_cache
from preprocess import preprocess_includes
from sugar.parser import parse_code

QUICK = '--quick' in sys.argv

if QUICK:
    # 简单任务: 不触发 LLM，只测框架
    print('Quick mode: 框架测试')
    from agent_tools import _agent_registry, _spawn_sub_agent

    _agent_registry.clear()
    r = _spawn_sub_agent('name=test\ntask=(输出 (加 1 2))')
    print(r)
    print('OK')
    sys.exit(0)

# ══ 死循环任务: 逻辑自相矛盾 ── LLM 会反复纠结 ══
DEADLOOP_TASK = (
    '写一个函数判断一个正整数是不是质数。'
    '额外要求: 不能使用除法、不能使用取余、不能使用任何循环。'
    '必须精确到大 O 复杂度 O(1)。'
    '用 Sanyan 语法实现，必须能直接运行。'
)

api_key = load_api_key()
if not api_key:
    print('ERROR: 需要 API key (SANYAN_API_KEY 或 agent_policy.san)')
    sys.exit(1)

print(f'API key: OK ({len(api_key)} chars)')
print(f'Task: {DEADLOOP_TASK[:80]}...\n')

clear_cache()
sub = SanyanEvaluator(max_loop_steps=200000)
os.environ['SANYAN_API_KEY'] = api_key
_register_aliases()

src = open('ternary_agent/agent.san', encoding='utf-8').read()
src = preprocess_includes(src)
src = src.replace('sk-你的key', api_key)
ast, _ = parse_code(src)
fixed = [s for s in ast[1:] if not (isinstance(s, list) and s[0] == 'export')]
sub.eval(['do'] + fixed)

print('Agent loaded. Running deadlock task...\n')
t0 = time.time()
old = sys.stdout
sys.stdout = io.StringIO()
try:
    sub.eval(['Agent运行', DEADLOOP_TASK])
    out = sys.stdout.getvalue()
finally:
    sys.stdout = old
elapsed = time.time() - t0

# ══ 检测 ══
confs = [float(m) for m in re.findall(r'信度[=:\uff1a]\s*([0-9.]+)', out)]
rounds = re.findall(r'第\s*(\d+)\s*轮', out)
recent = confs[-4:] if len(confs) >= 4 else confs

print(f'耗时: {elapsed:.1f}s')
print(f'置信度: {confs}')
print(f'最近4轮: {recent}')

if len(recent) >= 2:
    drop = all(recent[i] > recent[i + 1] for i in range(len(recent) - 1))
    print(f'严格单调递减: {drop}')
    if drop and recent[-1] < 0.35:
        print('\n>>> 检测到置信度衰减! 应触发重启 <<<')
    else:
        print('未触发: 置信度未持续下降或未低于底线')

max_r = max(int(r) for r in rounds) if rounds else 0
print(f'最大轮次: {max_r} (≥6触发截断)')
if max_r >= 6:
    print('>>> 轮次过多! 应触发截断 <<<')

if elapsed > 30:
    print(f'>>> 超时 {elapsed:.0f}s! 应触发杀死 <<<')

print(f'\n输出摘要: {out[:300]}')
