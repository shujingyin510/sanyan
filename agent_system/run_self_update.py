"""自更新闭环 CLI（P2）：挖任务 → 真 agent 在隔离 worktree 改代码 → oracle 门 → 产出分支。

用法（仓库根执行）:
  python -X utf8 agent_system/run_self_update.py --list             # 只看挖到的任务
  python -X utf8 agent_system/run_self_update.py                    # 取排名第一的任务跑闭环
  python -X utf8 agent_system/run_self_update.py --pick ternary_match  # 按子串挑挖掘任务
  python -X utf8 agent_system/run_self_update.py --task "任务书"     # 自定义任务
  python -X utf8 agent_system/run_self_update.py --pytest-log f.txt # 失败测试来源（pytest 输出）

oracle = 任务感知静态检查（P3：long_function 必须真变短，组合首位零成本短路）
AND pytest 全量基线（--baseline，默认 0 失败）AND 差分一致性（--no-differential 可关）。
密钥：SANYAN_API_KEY 环境变量，经子进程继承；绝不写入源码。
产出：通过 → `self-update/<名>-<时间>` 分支**待人工审查合并**；拒绝 → 整体回滚零残留。
"""

import argparse
import os
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from agent_system import task_mining  # noqa: E402
from agent_system.self_update import (  # noqa: E402
    SelfUpdateLoop,
    combine_oracles,
    make_agent_edit_fn,
    make_differential_oracle,
    make_pytest_oracle,
    make_shrink_oracle,
    tail_file,
)

# P2 十二轮探针的实战最优执行指引，统一追加到任务书尾
_RUNBOOK = (
    ' 用 read_file 查看、replace_in_file 小步修改（每次 old 控制在 30 行内）；'
    '不要自己运行完整测试套件（外部验证会跑）；改完用 done 结束。'
)


def pick_task(tasks, key: str):
    """按子串挑挖掘任务（匹配 title 或 path）。序号会随代码漂移，子串稳定。"""
    for t in tasks:
        if key in t.title or key in t.path:
            return t
    return None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='三言自更新闭环（P2）——安全自编辑，产出分支由人合并')
    parser.add_argument('--list', action='store_true', help='只列出挖到的任务')
    parser.add_argument('--pick', default='', help='按子串挑挖掘任务（匹配函数名或路径），替代默认取榜首')
    parser.add_argument('--task', default='', help='自定义任务书（跳过挖掘，无任务感知 oracle）')
    parser.add_argument('--pytest-log', default='', help='pytest 输出文件（提供 failing_test 来源）')
    parser.add_argument('--baseline', type=int, default=0, help='pytest 失败数基线（默认 0）')
    parser.add_argument('--pytest-timeout', type=int, default=900, help='oracle 中 pytest 超时秒数')
    parser.add_argument('--agent-timeout', type=int, default=1800, help='agent 子进程超时秒数')
    parser.add_argument('--no-differential', action='store_true', help='关闭差分一致性 oracle')
    parser.add_argument(
        '--attempts', type=int, default=1, help='最多尝试次数（P3：弱模型方差靠重试摊薄，首个过 oracle 即停）'
    )
    args = parser.parse_args(argv)

    log_text = ''
    if args.pytest_log:
        with open(args.pytest_log, encoding='utf-8', errors='replace') as f:
            log_text = f.read()
    tasks = task_mining.mine_all(ROOT, pytest_output=log_text)

    if args.list or (not args.task and not tasks):
        if not tasks:
            print('（没挖到任务）')
        for t in tasks[:30]:
            print(f'[{t.kind}] {t.path}:{t.line}  {t.title}  {t.detail}'.rstrip())
        return 0

    picked = None
    if args.task:
        prompt, name = args.task, 'custom'
    else:
        picked = pick_task(tasks, args.pick) if args.pick else tasks[0]
        if picked is None:
            print(f'--pick "{args.pick}" 未命中任何任务（--list 查看候选）')
            return 2
        prompt = picked.prompt()
        name = f'{picked.kind}-{os.path.splitext(os.path.basename(picked.path))[0]}'
    prompt += _RUNBOOK
    print(f'任务书: {prompt}')

    oracles = []
    if picked is not None and picked.kind == 'long_function':
        # 任务感知 oracle 放首位：毫秒级静态检查先行短路，半成品重构不烧全量 pytest
        oracles.append(make_shrink_oracle(picked.path, picked.title, int(picked.detail.split()[0])))
    oracles.append(make_pytest_oracle(args.baseline, timeout=args.pytest_timeout))
    if not args.no_differential:
        oracles.append(make_differential_oracle())

    # 自更新场景跳过规则生成前奏（省 2-4 次 LLM 调用与分钟级延迟；其产物垃圾参数
    # 规则本就被零改动闸门丢弃），agent 子进程经环境继承此开关
    os.environ['SANYAN_SKIP_RULE_GEN'] = '1'
    log_path = os.path.join(tempfile.gettempdir(), f'sanyan-su-agent-{time.strftime("%Y%m%d-%H%M%S")}.log')
    print(f'agent 日志: {log_path}')
    loop = SelfUpdateLoop(ROOT, combine_oracles(oracles))
    for attempt in range(1, max(args.attempts, 1) + 1):
        if args.attempts > 1:
            print(f'—— 尝试 {attempt}/{args.attempts} ——')
        result = loop.run(name, make_agent_edit_fn(prompt, timeout=args.agent_timeout, log_path=log_path))
        if result.accepted:
            print(f'✓ oracle 通过，产出分支: {result.branch}（请人工审查后合并）')
            return 0
        print(f'✗ 已回滚: {result.reason}')
        t = tail_file(log_path)
        if t:
            print(f'—— agent 日志尾 ——\n{t}')
    return 1


if __name__ == '__main__':
    sys.exit(main())
