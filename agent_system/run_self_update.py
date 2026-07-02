"""自更新闭环 CLI（P2）：挖任务 → 真 agent 在隔离 worktree 改代码 → oracle 门 → 产出分支。

用法（仓库根执行）:
  python -X utf8 agent_system/run_self_update.py --list             # 只看挖到的任务
  python -X utf8 agent_system/run_self_update.py                    # 取排名第一的任务跑闭环
  python -X utf8 agent_system/run_self_update.py --task "任务书"     # 自定义任务
  python -X utf8 agent_system/run_self_update.py --pytest-log f.txt # 失败测试来源（pytest 输出）

oracle = pytest 全量基线（--baseline，默认 0 失败）AND 差分一致性（--no-differential 可关）。
密钥：SANYAN_API_KEY 环境变量，经子进程继承；绝不写入源码。
产出：通过 → `self-update/<名>-<时间>` 分支**待人工审查合并**；拒绝 → 整体回滚零残留。
"""

import argparse
import os
import sys

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
)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='三言自更新闭环（P2）——安全自编辑，产出分支由人合并')
    parser.add_argument('--list', action='store_true', help='只列出挖到的任务')
    parser.add_argument('--task', default='', help='自定义任务书（跳过挖掘）')
    parser.add_argument('--pytest-log', default='', help='pytest 输出文件（提供 failing_test 来源）')
    parser.add_argument('--baseline', type=int, default=0, help='pytest 失败数基线（默认 0）')
    parser.add_argument('--pytest-timeout', type=int, default=900, help='oracle 中 pytest 超时秒数')
    parser.add_argument('--agent-timeout', type=int, default=1800, help='agent 子进程超时秒数')
    parser.add_argument('--no-differential', action='store_true', help='关闭差分一致性 oracle')
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

    if args.task:
        prompt, name = args.task, 'custom'
    else:
        top = tasks[0]
        prompt = top.prompt()
        name = f'{top.kind}-{os.path.splitext(os.path.basename(top.path))[0]}'
    print(f'任务书: {prompt}')

    oracles = [make_pytest_oracle(args.baseline, timeout=args.pytest_timeout)]
    if not args.no_differential:
        oracles.append(make_differential_oracle())

    loop = SelfUpdateLoop(ROOT, combine_oracles(oracles))
    result = loop.run(name, make_agent_edit_fn(prompt, timeout=args.agent_timeout))
    if result.accepted:
        print(f'✓ oracle 通过，产出分支: {result.branch}（请人工审查后合并）')
        return 0
    print(f'✗ 已回滚: {result.reason}')
    return 1


if __name__ == '__main__':
    sys.exit(main())
