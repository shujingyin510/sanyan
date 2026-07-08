"""自更新实跑失败数据库 —— 从 validate/agent 日志提取结构化记录 + 汇总统计。

实验策略 v2（0708）：一次实验的产出不该只是"成功/失败"，而是一条可复用的规律。
25 轮实跑的原始材料（拒绝理由/diff 规模/panel 读数/噪音计数）一直躺在日志里，
本模块把它们变成 JSONL（每次尝试/候选一条记录）与聚合报告：

  python -X utf8 agent_system/su_stats.py <日志文件或目录...> \
      [--jsonl agent_system/data/su_runs.jsonl] [--report]

记录字段：run（日志名）/ mode（attempts|candidates）/ idx / accepted /
reason_class（无改动|未变短|嵌套|大粘贴|解析不到|守恒|pytest|考官域|密钥|其它）/
ins / dels（被拒 diff 规模）/ llm_calls / tokens / tool_steps / stop（零编辑死因）/
noise（该轮 agent 日志 Timeout 计数）/ runbook（任务书指纹变体）/ task。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Iterator, List, Optional

_BLOCK_RE = re.compile(r'^—— (尝试|候选) (\d+)/(\d+) ——')
_REJECT_RE = re.compile(r'^✗ (?:候选 \d+ )?已回滚: (.+)$')
_ACCEPT_RE = re.compile(r'^✓ oracle 通过，产出分支: (\S+)')
_STAT_RE = re.compile(r'(\d+) file[s]? changed(?:, (\d+) insertions?\(\+\))?(?:, (\d+) deletions?\(-\))?')
_PANEL_RES = {
    'llm_calls': re.compile(r'LLM调用:\s+(\d+)'),
    'tokens': re.compile(r'Token用量:\s+(\d+)'),
    'tool_steps': re.compile(r'工具步骤:\s+(\d+)'),
}
_STOP_RE = re.compile(r'输出预览:\s*(.+?)\s*║')
_AGENT_LOG_RE = re.compile(r'^agent 日志: (.+)$')

# 拒绝理由 → 死因类（顺序即优先级：更具体的诊断先匹配）
_REASON_CLASSES = (
    ('考官域', '考官域'),
    ('密钥', '密钥'),
    ('守恒检查', '守恒'),
    ('重写而非搬运', '守恒'),
    ('解析不到的名字', '解析不到'),
    ('嵌套在目标函数内部', '嵌套'),
    ('疑似整段重复粘贴', '大粘贴'),
    ('未变短', '未变短'),
    ('失败用例', 'pytest'),
    ('失败数', 'pytest'),
    ('无改动', '无改动'),
    ('edit_fn 异常', 'edit异常'),
    ('断路', '断路'),
)

# 任务书指纹 → runbook 变体（区分实验条件，0708 受控对比的教训：条件必须入库）
_RUNBOOK_VARIANTS = (
    ('推荐在类内新增 @staticmethod', 'v4-类内推荐'),
    ('首选定义在模块级', 'v3-模块级首选'),
    ('输出每行带 "N│" 行号', 'v2-行号'),
)


def classify_reason(reason: str) -> str:
    for kw, cls in _REASON_CLASSES:
        if kw in reason:
            return cls
    return '其它'


def _runbook_variant(task_line: str) -> str:
    for kw, tag in _RUNBOOK_VARIANTS:
        if kw in task_line:
            return tag
    return 'v1-初版'


def _noise_count(agent_log_path: str) -> Optional[int]:
    try:
        with open(agent_log_path, encoding='utf-8', errors='replace') as f:
            return f.read().count('Timeout')
    except OSError:
        return None


def parse_validate_log(path: str) -> List[dict]:
    """一个 validate 日志 → 每次尝试/候选一条记录。空/半成品日志返回空表。"""
    try:
        with open(path, encoding='utf-8', errors='replace') as f:
            lines = f.read().splitlines()
    except OSError:
        return []
    if not lines:
        return []

    task = ''
    runbook = 'v1-初版'
    noise: Optional[int] = None
    m_task = re.search(r'的超长函数 (\w+)', lines[0])
    if m_task:
        task = m_task.group(1)
    runbook = _runbook_variant(lines[0])

    records: List[dict] = []
    cur: Optional[dict] = None
    run = os.path.splitext(os.path.basename(path))[0]

    for ln in lines:
        m = _AGENT_LOG_RE.match(ln)
        if m:
            noise = _noise_count(m.group(1).strip())
            continue
        m = _BLOCK_RE.match(ln)
        if m:
            if cur:
                records.append(cur)
            cur = {
                'run': run,
                'mode': 'attempts' if m.group(1) == '尝试' else 'candidates',
                'idx': int(m.group(2)),
                'total': int(m.group(3)),
                'accepted': False,
                'reason_class': '',
                'reason': '',
                'ins': 0,
                'dels': 0,
                'llm_calls': None,
                'tokens': None,
                'tool_steps': None,
                'stop': '',
                'task': task,
                'runbook': runbook,
            }
            continue
        if cur is None:
            continue
        m = _REJECT_RE.match(ln)
        if m:
            cur['reason'] = m.group(1)[:200]
            cur['reason_class'] = classify_reason(m.group(1))
            continue
        m = _ACCEPT_RE.match(ln)
        if m:
            cur['accepted'] = True
            cur['reason'] = f'通过: {m.group(1)}'
            cur['reason_class'] = '接受'
            continue
        m = _STAT_RE.search(ln)
        if m:
            cur['ins'] = int(m.group(2) or 0)
            cur['dels'] = int(m.group(3) or 0)
            continue
        for key, pat in _PANEL_RES.items():
            pm = pat.search(ln)
            if pm:
                cur[key] = int(pm.group(1))
        sm = _STOP_RE.search(ln)
        if sm:
            cur['stop'] = sm.group(1).strip()
    if cur:
        records.append(cur)
    for r in records:
        r['noise'] = noise
    return records


def iter_logs(paths: List[str]) -> Iterator[str]:
    for p in paths:
        if os.path.isdir(p):
            for name in sorted(os.listdir(p)):
                if name.startswith('su-validate') and name.endswith('.log'):
                    yield os.path.join(p, name)
        elif os.path.isfile(p):
            yield p


def _noise_band(n: Optional[int]) -> str:
    if n is None:
        return '未知'
    if n <= 6:
        return '干净(≤6)'
    if n < 20:
        return '轻中(7-19)'
    return '风暴(≥20)'


def report(records: List[dict]) -> str:
    """聚合报告：死因分布 / 转化率×条件 / 补丁规模×死因 / 零编辑死法分布。"""
    out: List[str] = []
    total = len(records)
    if not total:
        return '（没有记录）'
    cands = [r for r in records if r['ins'] or r['dels'] or r['accepted']]
    out.append(
        f'== 总量：{total} 次尝试/候选，真候选 {len(cands)}（{len(cands) / total:.0%}），'
        f'接受 {sum(1 for r in records if r["accepted"])} =='
    )

    def _dist(title: str, keyfn, pool: List[dict]) -> None:
        counts: dict = {}
        for r in pool:
            counts[keyfn(r)] = counts.get(keyfn(r), 0) + 1
        out.append(f'-- {title} --')
        for k, v in sorted(counts.items(), key=lambda kv: -kv[1]):
            out.append(f'  {k}: {v}（{v / max(len(pool), 1):.0%}）')

    _dist('死因类分布（全部）', lambda r: r['reason_class'] or '?', records)
    _dist('真候选的死因类', lambda r: r['reason_class'] or '?', cands)
    _dist('零编辑的停机原因', lambda r: r['stop'] or '?', [r for r in records if r['reason_class'] == '无改动'])

    out.append('-- 转化率 × runbook 变体 --')
    by_rb: dict = {}
    for r in records:
        by_rb.setdefault(r['runbook'], []).append(r)
    for rb, pool in sorted(by_rb.items()):
        c = sum(1 for r in pool if r['ins'] or r['dels'] or r['accepted'])
        out.append(f'  {rb}: {c}/{len(pool)}（{c / len(pool):.0%}）')

    out.append('-- 转化率 × 噪音档 --')
    by_nb: dict = {}
    for r in records:
        by_nb.setdefault(_noise_band(r.get('noise')), []).append(r)
    for nb, pool in sorted(by_nb.items()):
        c = sum(1 for r in pool if r['ins'] or r['dels'] or r['accepted'])
        out.append(f'  {nb}: {c}/{len(pool)}（{c / len(pool):.0%}）')

    out.append('-- 补丁规模（中位 ins/dels）× 死因类（仅真候选）--')
    by_cls: dict = {}
    for r in cands:
        by_cls.setdefault(r['reason_class'], []).append(r)
    for cls, pool in sorted(by_cls.items(), key=lambda kv: -len(kv[1])):
        mid = len(pool) // 2
        ins = sorted(x['ins'] for x in pool)[mid]
        dels = sorted(x['dels'] for x in pool)[mid]
        out.append(f'  {cls}（n={len(pool)}）: +{ins}/-{dels}')
    return '\n'.join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='自更新实跑失败数据库：日志 → JSONL + 汇总统计')
    ap.add_argument('paths', nargs='+', help='validate 日志文件或所在目录')
    ap.add_argument('--jsonl', default='', help='追加写出 JSONL 的路径')
    ap.add_argument('--report', action='store_true', help='打印聚合报告')
    args = ap.parse_args(argv)

    records: List[dict] = []
    for log in iter_logs(args.paths):
        records.extend(parse_validate_log(log))
    print(f'解析 {len(records)} 条记录')
    if args.jsonl:
        os.makedirs(os.path.dirname(args.jsonl) or '.', exist_ok=True)
        with open(args.jsonl, 'w', encoding='utf-8') as f:
            for r in records:
                f.write(json.dumps(r, ensure_ascii=False) + '\n')
        print(f'已写 {args.jsonl}')
    if args.report:
        print(report(records))
    return 0


if __name__ == '__main__':
    sys.exit(main())
