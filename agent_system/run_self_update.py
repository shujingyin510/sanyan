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
产出：通过 → `self-update/<名>-<时间>` 分支**待人工审查合并**；拒绝 → 整体回滚零残留，
回滚前被拒改动的 diff+stat 自动落 agent 日志（尸检窗口）。
"""

import argparse
import os
import subprocess
import sys
import tempfile
import time
from typing import Callable

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

# P2 十二轮探针 + 0705 两轮实跑的实战最优执行指引，统一追加到任务书尾
_RUNBOOK = (
    ' 用 read_file 查看、replace_in_file 小步修改（每次 old 控制在 30 行内）；'
    '只搬不改：原函数的每一行原样搬进辅助函数或留在原地，不得改写/删除任何语句、'
    '校验条件或异常类型（外部会逐行核对）；辅助函数定义在与原函数平级的位置'
    '（模块级或同一类里），不要嵌套在原函数体内——嵌套定义会让原函数更长；'
    '顺序：先插入辅助函数完整定义，后把原块替换成调用（先替换会引用不存在的名字）；'
    '不要自己运行完整测试套件、不要用 run_shell 数行数/量函数长度，也不要用 '
    'run_shell/sed 读文件——读文件一律 read_file（外部会验证与度量，空转只会烧光轮次）；'
    '改完用 done 结束。'
)


def pick_task(tasks, key: str):
    """按子串挑挖掘任务（匹配 title 或 path）。序号会随代码漂移，子串稳定。"""
    for t in tasks:
        if key in t.title or key in t.path:
            return t
    return None


def classify_tip(reason: str, hints: str = '') -> str:
    """按拒绝原因分类出对症纠偏提示（`build_retry_feedback` 的判案核心，可单独复用）。

    `hints` 为挖掘时静态标出的候选块行区间（有则并入"未变短"纠偏，指名对哪段动手）。
    """
    if '无改动' in reason:
        return '这次务必真正改文件（replace_in_file / replace_lines / write_file），别在 run_shell 里空转数行。'
    if '嵌套在目标函数内部' in reason:
        # 0706 第五轮尝试 1：两步都做了，但辅助函数嵌套在原函数体内 → 94→99 反而变长
        return (
            '你把辅助函数定义在了原函数体内（嵌套 def），原函数反而变长。把辅助函数整体'
            '搬到与原函数平级的位置（模块级或同一类里再定义一个方法），原函数里只留调用。'
        )
    if '解析不到的名字' in reason or 'NameError' in reason:
        return (
            '你抽取了辅助函数却没定义它。这次分两步都落到文件：先用 write_file/replace 把这个'
            '辅助函数的完整定义加进模块（模块级、平级于原函数），再在原函数里调用它。'
        )
    if '重写而非搬运' in reason or '守恒检查' in reason:
        return (
            '你改写了原有语句而不是搬运。上面列出的原始行必须原样保留（搬进辅助函数即可）——'
            '不要改校验条件、异常类型、返回值或文案，只做纯粹的整块搬移 + 调用替换。'
        )
    if '失败用例' in reason or '失败数' in reason or '收集/执行错误' in reason:
        return (
            '你的改动跑挂了上面列出的测试，说明行为变了。回到目标函数，保持逻辑严格等价'
            '（分支条件、返回值一字不差），只做结构拆分，别顺手改逻辑。'
        )
    if '未变短' in reason:
        # 0706 第四轮实录：模型只做了第一步（插入辅助函数），没做第二步（替换原块）——
        # 函数一行没短。两步都点名，且指名候选块。
        extra = f'优先对候选块 {hints} 动手。' if hints else ''
        return (
            '两步都要做完：第一步把候选块整块搬成模块级辅助函数；第二步用 replace_lines 把'
            f'原函数里那段原块替换成对辅助函数的调用——只加辅助函数、不替换原块，函数不会变短。{extra}'
        )
    return '针对上面的原因修正后再试。'


def build_retry_feedback(reason: str, hints: str = '', earlier_tip: str = '') -> str:
    """把上次拒绝原因转成给下一次 agent 的定向纠偏提示，塞回任务书首。

    --attempts 的重试此前是 N 次冷启动，每次都不知道上次为啥挂；可 reject_hook 已把
    失败用例名/被拒 diff 落了盘。弱模型缺的往往就是『有人告诉它错在哪』——把最近一次
    拒绝原因连同分类纠偏喂回，把盲目重试变成迭代修正（零额外成本，只串上下文）。
    `earlier_tip` 为更早尝试的纠偏（0706 第五轮实录：尝试 1 教训"两步都做完"被尝试 2
    的"无改动"顶掉，尝试 3 便重蹈只做第一步——单课链在中间尝试换死因时丢课，故最多带两课）。
    """
    tip = classify_tip(reason, hints)
    block = f'⚠ 上一次尝试被拒，原因：{reason[:300]}\n本次纠偏：{tip}\n'
    if earlier_tip and earlier_tip != tip:
        block += f'⚠ 更早尝试的教训仍有效：{earlier_tip}\n'
    return block + '\n'


def _git_out(wt: str, *args: str) -> str:
    """在被拒 worktree 里跑 git（观测用）。任何失败返回空串——尸检绝不影响回滚。"""
    try:
        r = subprocess.run(
            ['git', *args],
            cwd=wt,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=60,
        )
        return r.stdout
    except Exception:
        return ''


def make_reject_diff_dumper(log_path: str) -> Callable[[str, str], None]:
    """回滚前把被拒改动的 diff 追加进 agent 日志——被拒分支随回滚蒸发，diff 是唯一尸检材料。

    P3 实测的缺口：某次尝试过了 shrink oracle、只差 1 个测试挂掉，但回滚后既不知道
    改成了什么样、也不知道挂的是哪个测试。patch 在前、--stat 概要收尾：CLI 每次拒绝
    打印日志尾，尾部正好是"改了哪些文件几行"。
    """

    def dump(wt: str, reason: str) -> None:
        if not _git_out(wt, 'log', '-1', '--format=%s').startswith('self-update:'):
            return  # 无自更新提交（edit_fn 异常/无改动路径）——没有 diff 可留
        patch = _git_out(wt, 'show', 'HEAD', '--no-color', '--format=')
        stat = _git_out(wt, 'show', 'HEAD', '--no-color', '--format=', '--stat')
        with open(log_path, 'a', encoding='utf-8', errors='replace') as f:
            f.write(f'\n=== 被拒改动尸检 {time.strftime("%H:%M:%S")} 原因: {reason[:200]} ===\n')
            f.write(patch[:8000] + ('\n…(patch 截断)\n' if len(patch) > 8000 else ''))
            f.write(f'—— 被拒改动 stat ——\n{stat}')

    return dump


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
        # 任务感知 oracle 放首位：毫秒级静态检查先行短路，半成品重构不烧全量 pytest。
        # 基线源码给守恒检查（重写而非搬运当场毙）；读不到则守恒静默跳过、其余照跑。
        try:
            with open(os.path.join(ROOT, picked.path), encoding='utf-8', errors='replace') as f:
                baseline_src = f.read()
        except OSError:
            baseline_src = None
        oracles.append(
            make_shrink_oracle(picked.path, picked.title, int(picked.detail.split()[0]), baseline_source=baseline_src)
        )
    oracles.append(make_pytest_oracle(args.baseline, timeout=args.pytest_timeout))
    if not args.no_differential:
        oracles.append(make_differential_oracle())

    # 自更新场景跳过规则生成前奏（省 2-4 次 LLM 调用与分钟级延迟；其产物垃圾参数
    # 规则本就被零改动闸门丢弃），agent 子进程经环境继承此开关
    os.environ['SANYAN_SKIP_RULE_GEN'] = '1'
    # 自更新任务必须落到文件改动：agent 零改动就 done 时循环顶回（loop.py ⑥），逼向
    # 真正的编辑而非 run_shell 空转；经子进程环境继承。
    os.environ['SANYAN_REQUIRE_EDIT'] = '1'
    # 循环总预算放宽到 900s：0705 三连实跑证明代理抖动时默认 420s 会把 agent 掐死在
    # 编辑前（6 次 LLM 超时、零编辑调用、3/3 无改动拒）。--agent-timeout 子进程硬杀兜底。
    os.environ['SANYAN_LOOP_TIME_BUDGET'] = '900'
    # 同工具限额放宽到 10：0706 第四轮实跑，重构 94 行函数读 2-3 窗+改后自检，read_file
    # 全程 5 次不够——尝试 1 成功插入辅助函数后正死于此，第二步替换没机会做。
    os.environ['SANYAN_TOOL_REPEAT_LIMIT'] = '10'
    log_path = os.path.join(tempfile.gettempdir(), f'sanyan-su-agent-{time.strftime("%Y%m%d-%H%M%S")}.log')
    print(f'agent 日志: {log_path}')
    loop = SelfUpdateLoop(
        ROOT,
        combine_oracles(oracles),
        reject_hook=make_reject_diff_dumper(log_path),
        # agent 学习记录/状态库是运行副产物，不属于代码变更（写进提交会伪装零改动、
        # 污染产出分支——今晨尸检与昨日被接受分支双重实证）
        commit_excludes=(
            'agent_system/learned_styles.md',
            'agent_system/agent.db',
            'agent_system/agent_state.db',
        ),
    )
    feedback = ''  # 上一次拒绝的纠偏提示，喂回下一次任务书首（带记忆重试）
    earlier_tip = ''  # 更早尝试的纠偏（最多带两课：中间尝试换死因时不丢前课）
    for attempt in range(1, max(args.attempts, 1) + 1):
        if args.attempts > 1:
            print(f'—— 尝试 {attempt}/{args.attempts} ——')
        if feedback:
            print('  [UR] 已把上次拒绝原因喂回本次任务书（带记忆重试）')
        result = loop.run(name, make_agent_edit_fn(feedback + prompt, timeout=args.agent_timeout, log_path=log_path))
        if result.accepted:
            print(f'✓ oracle 通过，产出分支: {result.branch}（请人工审查后合并）')
            return 0
        print(f'✗ 已回滚: {result.reason}')
        # 最近一课 + 上一课（若不同），避免任务书越滚越长；候选块行区间并入纠偏
        task_hints = picked.hints if picked is not None else ''
        feedback = build_retry_feedback(result.reason, hints=task_hints, earlier_tip=earlier_tip)
        earlier_tip = classify_tip(result.reason, hints=task_hints)
        t = tail_file(log_path)
        if t:
            print(f'—— agent 日志尾 ——\n{t}')
    return 1


if __name__ == '__main__':
    sys.exit(main())
