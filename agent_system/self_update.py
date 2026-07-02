"""P1：单任务安全自更新闭环（self-update loop）。

北极星第一步——把"能改代码的 agent"变成"能**安全自改**的 agent"：在**隔离的 git worktree**
里让一个 `edit_fn` 改代码，用 **fail-closed oracle** 判定，过则留一个**待人工合并**的分支、
败则整体回滚（删 worktree + 删分支）。

两条不可动摇的红线（见 REFACTOR_PLAN「北极星」）：
  1. 运行中的进程**绝不改自己**——改的是 worktree 副本，主工作树全程不动；
  2. **绝不自动合并**——只产出分支，由人来 merge。

`oracle` 与 `edit_fn` 都可注入：便于测试（假件驱动），也便于将来把 `edit_fn` 换成真 agent、
把 `oracle` 换成 pytest 基线 / 差分验证 / 自举验证的组合。
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Sequence


@dataclass
class OracleVerdict:
    """oracle 判定结果。ok=False 即拒绝（fail-closed：任何不确定都应判 False）。"""

    ok: bool
    reason: str = ''
    report: dict = field(default_factory=dict)


@dataclass
class UpdateResult:
    accepted: bool
    branch: Optional[str]
    reason: str
    report: dict = field(default_factory=dict)


class SelfUpdateLoop:
    """隔离 → 改 → 验（fail-closed）→ 过则留分支 / 败则回滚。绝不自动合并。"""

    def __init__(self, repo_root: str, oracle: Callable[[str], OracleVerdict], *, base: str = 'HEAD'):
        self.repo_root = os.path.abspath(repo_root)
        self.oracle = oracle
        self.base = base

    def _git(self, *args: str, cwd: Optional[str] = None) -> subprocess.CompletedProcess:
        return subprocess.run(
            ['git', *args],
            cwd=cwd or self.repo_root,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
        )

    def run(self, task_name: str, edit_fn: Callable[[str], object]) -> UpdateResult:
        ts = time.strftime('%Y%m%d-%H%M%S')
        safe = ''.join(c if (c.isalnum() or c in '-_') else '-' for c in task_name)[:40] or 'task'
        branch = f'self-update/{safe}-{ts}'
        holder = tempfile.mkdtemp(prefix='sanyan-su-')  # worktree 放仓库外，杜绝污染
        wt = os.path.join(holder, 'wt')

        r = self._git('worktree', 'add', '-b', branch, wt, self.base)
        if r.returncode != 0:
            shutil.rmtree(holder, ignore_errors=True)
            return UpdateResult(False, None, f'worktree 创建失败: {r.stderr.strip()[:200]}')

        try:
            # 1. 让 edit_fn 在副本里改代码
            try:
                edit_fn(wt)
            except Exception as e:  # edit 失败 → 回滚
                return self._reject(holder, wt, branch, f'edit_fn 异常: {e}')

            # 2. 捕获改动；无 diff 则拒绝
            self._git('add', '-A', cwd=wt)
            if not self._git('diff', '--cached', '--stat', cwd=wt).stdout.strip():
                return self._reject(holder, wt, branch, '无改动（edit_fn 未产生 diff）')
            self._git('commit', '-m', f'self-update: {task_name}', cwd=wt)

            # 3. fail-closed oracle：异常一律判拒绝
            try:
                verdict = self.oracle(wt)
            except Exception as e:
                return self._reject(holder, wt, branch, f'oracle 异常（fail-closed 拒绝）: {e}')
            if not verdict.ok:
                return self._reject(holder, wt, branch, f'oracle 未过: {verdict.reason}', verdict.report)

            # 4. 接受——保留分支供**人工合并**，仅移除 worktree（不自动 merge）
            self._git('worktree', 'remove', '--force', wt)
            shutil.rmtree(holder, ignore_errors=True)
            return UpdateResult(True, branch, f'通过 oracle: {verdict.reason}', verdict.report)
        except Exception as e:  # 兜底：任何意外 → 回滚
            return self._reject(holder, wt, branch, f'循环异常（fail-closed）: {e}')

    def _reject(self, holder: str, wt: str, branch: str, reason: str, report: Optional[dict] = None) -> UpdateResult:
        self._git('worktree', 'remove', '--force', wt)
        shutil.rmtree(holder, ignore_errors=True)
        self._git('branch', '-D', branch)  # 丢弃分支（worktree 已移除，可删）
        return UpdateResult(False, None, reason, report or {})


# ── oracle：pytest 基线（最强、最难作弊的 canonical 信号）──────────────────────

_KW = ('passed', 'failed', 'error', 'errors')


def parse_pytest_summary(text: str) -> dict:
    """从 pytest 尾部摘要解析计数。`parsed=False` 表示摘要不可信（应 fail-closed）。"""
    counts = {}
    for kw in _KW:
        m = re.search(r'(\d+)\s+' + kw + r'\b', text)
        counts[kw] = int(m.group(1)) if m else 0
    errors = counts['error'] + counts['errors']
    parsed = bool(re.search(r'\d+\s+(passed|failed|error)', text))
    return {'passed': counts['passed'], 'failed': counts['failed'], 'errors': errors, 'parsed': parsed}


def make_pytest_oracle(
    baseline_failed: int,
    scope: Sequence[str] = ('tests',),
    *,
    timeout: int = 600,
    python: str = 'python',
    extra: Sequence[str] = ('-q', '-p', 'no:cacheprovider'),
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> Callable[[str], OracleVerdict]:
    """构造一个 fail-closed 的 pytest 基线 oracle：worktree 里跑 pytest，失败数不得超过基线、
    不得有收集/执行错误、摘要须可解析；超时/启动失败一律拒绝。`runner` 可注入便于测试。"""

    def oracle(workdir: str) -> OracleVerdict:
        try:
            r = runner(
                [python, '-X', 'utf8', '-m', 'pytest', *scope, *extra],
                cwd=workdir,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return OracleVerdict(False, f'pytest 超时 {timeout}s（fail-closed）')
        except Exception as e:
            return OracleVerdict(False, f'pytest 启动失败（fail-closed）: {e}')
        s = parse_pytest_summary(r.stdout + '\n' + r.stderr)
        if not s['parsed']:
            return OracleVerdict(False, 'pytest 摘要不可解析（fail-closed）', s)
        if s['errors'] > 0:
            return OracleVerdict(False, f'收集/执行错误 {s["errors"]}（fail-closed）', s)
        if s['failed'] > baseline_failed:
            return OracleVerdict(False, f'失败数 {s["failed"]} > 基线 {baseline_failed}', s)
        return OracleVerdict(True, f'失败 {s["failed"]} ≤ 基线 {baseline_failed}，通过 {s["passed"]}', s)

    return oracle


def combine_oracles(oracles: List[Callable[[str], OracleVerdict]]) -> Callable[[str], OracleVerdict]:
    """与逻辑串联多个 oracle（全过才过），任一拒绝即短路——fail-closed 组合。"""

    def oracle(workdir: str) -> OracleVerdict:
        reports = {}
        for i, o in enumerate(oracles):
            try:
                v = o(workdir)
            except Exception as e:
                return OracleVerdict(False, f'oracle#{i} 异常（fail-closed）: {e}', reports)
            reports[f'oracle{i}'] = {'ok': v.ok, 'reason': v.reason, **v.report}
            if not v.ok:
                return OracleVerdict(False, f'oracle#{i} 拒绝: {v.reason}', reports)
        return OracleVerdict(True, '全部 oracle 通过', reports)

    return oracle


# ── P2：把真 agent 接成 edit_fn + 差分一致性 oracle ──────────────────────────


def make_agent_edit_fn(
    prompt: str,
    *,
    agent_cmd: Optional[Sequence[str]] = None,
    timeout: int = 1800,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> Callable[[str], None]:
    """把「跑一个 agent 子进程」包装成 edit_fn：`cwd=worktree`，agent 只碰副本（红线②）。

    默认命令 = `python agent_system/run_agent.py <prompt> --auto`，用的是**副本里**的
    run_agent——P4 元循环时 agent 对自身代码的修改也因此落在验证范围内。
    `agent_cmd` 可整体覆盖默认命令（须自含任务描述）。
    密钥经环境变量继承给子进程，绝不写入源码或命令行文件。失败/超时 → 抛异常 → 闭环整体回滚。
    """

    def edit_fn(wt: str) -> None:
        cmd = (
            list(agent_cmd)
            if agent_cmd is not None
            else [sys.executable, '-X', 'utf8', os.path.join('agent_system', 'run_agent.py'), prompt, '--auto']
        )
        r = runner(cmd, cwd=wt, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=timeout)
        if r.returncode != 0:
            raise RuntimeError(f'agent 进程失败 rc={r.returncode}: {(r.stderr or r.stdout)[-300:]}')

    return edit_fn


def make_differential_oracle(
    cases: Optional[List[dict]] = None,
    *,
    verifier_factory: Optional[Callable[[str], object]] = None,
) -> Callable[[str], OracleVerdict]:
    """差分一致性 oracle：解释器(--eval) vs 字节码 VM 输出全一致才放行（fail-closed）。

    在 **worktree** 里跑副本引擎（cwd=workdir），验证的是改过的代码。零用例判拒绝、
    异常判拒绝。`verifier_factory(workdir)` 可注入（测试）。
    """

    def oracle(workdir: str) -> OracleVerdict:
        try:
            if verifier_factory is not None:
                verifier = verifier_factory(workdir)
            else:
                from agent_system.agent_evolution import DifferentialVerifier

                verifier = DifferentialVerifier(cwd=workdir)
            report = verifier.verify_consistency(cases)
        except Exception as e:
            return OracleVerdict(False, f'差分验证异常（fail-closed）: {e}')
        total, consistent = report.get('total', 0), report.get('consistent', 0)
        if total <= 0:
            return OracleVerdict(False, '差分零用例（fail-closed）', report)
        if consistent < total:
            return OracleVerdict(False, f'差分不一致 {consistent}/{total}', report)
        return OracleVerdict(True, f'差分一致 {total}/{total}', report)

    return oracle
