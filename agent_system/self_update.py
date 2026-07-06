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

import ast
import builtins
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

    def __init__(
        self,
        repo_root: str,
        oracle: Callable[[str], OracleVerdict],
        *,
        base: str = 'HEAD',
        reject_hook: Optional[Callable[[str, str], None]] = None,
        commit_excludes: Sequence[str] = (),
    ):
        self.repo_root = os.path.abspath(repo_root)
        self.oracle = oracle
        self.base = base
        # 观测钩子：每次拒绝在回滚**之前**以 (worktree路径, 拒绝原因) 调用——被拒改动
        # 随回滚蒸发，这是唯一的尸检窗口（如把 diff 落日志）。异常被吞：观测绝不阻断回滚。
        self.reject_hook = reject_hook
        # 提交排除清单（git pathspec）：agent 运行副产物（学习记录/状态库）不是代码变更。
        # 尸检首战战果：零改动尝试曾靠一条学习记录伪装成真 diff，被 shrink oracle 按
        # "未变短"误拒（真相是根本没改码）；昨日被接受分支也混入了这类噪音。
        self.commit_excludes = tuple(commit_excludes)

    def _git(self, *args: str, cwd: Optional[str] = None) -> subprocess.CompletedProcess:
        # 超时按失败返回（fail-closed）：worktree 被残留子进程锁住时 git 会吊死，
        # 没有超时整个闭环就跟着吊死——P2 首跑实测（孤儿 pytest 锁文件 34 分钟）。
        try:
            return subprocess.run(
                ['git', *args],
                cwd=cwd or self.repo_root,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=120,
            )
        except subprocess.TimeoutExpired:
            return subprocess.CompletedProcess(['git', *args], 124, '', 'git 超时(120s)——工作区疑被其他进程锁定')

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

            # 2. 捕获改动；无 diff 则拒绝（副产物先出栈：只剩副产物即视同零改动）
            self._git('add', '-A', cwd=wt)
            if self.commit_excludes:
                self._git('reset', '-q', '--', *self.commit_excludes, cwd=wt)
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
        if self.reject_hook is not None:
            try:
                self.reject_hook(wt, reason)
            except Exception:
                pass  # 尸检失败不能挡回滚
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


def failing_test_names(text: str, top: int = 3) -> List[str]:
    """从 pytest 短摘要区提取失败/错误用例名——拒绝理由带上名字，分支随回滚蒸发后仍知道挂在哪。"""
    names: List[str] = []
    for n in re.findall(r'^(?:FAILED|ERROR)\s+(\S+)', text, re.M):
        if n not in names:
            names.append(n)
    return names[:top]


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
        text = r.stdout + '\n' + r.stderr
        s = parse_pytest_summary(text)
        if not s['parsed']:
            return OracleVerdict(False, 'pytest 摘要不可解析（fail-closed）', s)
        names = failing_test_names(text)
        if names:
            s['failed_names'] = names
        hint = f'；失败用例: {", ".join(names)}' if names else ''
        if s['errors'] > 0:
            return OracleVerdict(False, f'收集/执行错误 {s["errors"]}（fail-closed）{hint}', s)
        if s['failed'] > baseline_failed:
            return OracleVerdict(False, f'失败数 {s["failed"]} > 基线 {baseline_failed}{hint}', s)
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


def _kill_tree(proc: subprocess.Popen) -> None:
    """杀整棵进程树。subprocess 的 timeout 只杀直接子进程；agent 起的工具子进程
    （如 run_shell 跑的 pytest）会沦为孤儿、锁住 worktree 文件，把回滚一起卡死。"""
    if os.name == 'nt':
        subprocess.run(['taskkill', '/F', '/T', '/PID', str(proc.pid)], capture_output=True, timeout=30)
    else:
        import signal

        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError, OSError):
            proc.kill()


def _run_reaped(cmd, **kw) -> subprocess.CompletedProcess:
    """subprocess.run 兼容的默认 runner：超时先杀整棵树再收管道。

    树死则管道必闭，communicate 不会吊死；残留孤儿为零，worktree 可干净回滚。
    """
    timeout = kw.pop('timeout', None)
    if kw.pop('capture_output', False):
        kw.setdefault('stdout', subprocess.PIPE)
        kw.setdefault('stderr', subprocess.PIPE)
    if os.name != 'nt':
        kw.setdefault('start_new_session', True)  # POSIX：独立进程组，killpg 全收
    proc = subprocess.Popen(cmd, **kw)
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill_tree(proc)
        out, err = proc.communicate()  # 树已死，立即返回
        raise subprocess.TimeoutExpired(cmd, timeout or 0, output=out, stderr=err)
    return subprocess.CompletedProcess(cmd, proc.returncode, out, err)


def tail_file(path: str, n: int = 15) -> str:
    """读文件尾 n 行（诊断用；文件缺失返回空串）。"""
    try:
        with open(path, encoding='utf-8', errors='replace') as f:
            return ''.join(f.readlines()[-n:])
    except OSError:
        return ''


def make_agent_edit_fn(
    prompt: str,
    *,
    agent_cmd: Optional[Sequence[str]] = None,
    timeout: int = 1800,
    runner: Callable[..., subprocess.CompletedProcess] = _run_reaped,
    log_path: str = '',
) -> Callable[[str], None]:
    """把「跑一个 agent 子进程」包装成 edit_fn：`cwd=worktree`，agent 只碰副本（红线②）。

    默认命令 = `python agent_system/run_agent.py <prompt> --auto`，用的是**副本里**的
    run_agent——P4 元循环时 agent 对自身代码的修改也因此落在验证范围内。
    `agent_cmd` 可整体覆盖默认命令（须自含任务描述）。
    密钥经环境变量继承给子进程，绝不写入源码或命令行文件。失败/超时 → 抛异常 → 闭环整体回滚。
    `log_path`：agent 全程输出落此文件（追加，回滚不灭）——P2 排障期因输出只在
    rc≠0 时可见，多跑了一打盲探针；给路径即永久可观测。
    """

    def edit_fn(wt: str) -> None:
        cmd = (
            list(agent_cmd)
            if agent_cmd is not None
            # -u：agent 被超时树杀时满缓冲的 stdout 整体蒸发（实测 600s 只剩启动头），
            # 无缓冲让日志随跑随落、杀掉也留现场
            else [sys.executable, '-X', 'utf8', '-u', os.path.join('agent_system', 'run_agent.py'), prompt, '--auto']
        )
        common = dict(cwd=wt, text=True, encoding='utf-8', errors='replace', timeout=timeout)
        if log_path:
            with open(log_path, 'a', encoding='utf-8', errors='replace') as log:
                log.write(f'\n=== agent 启动 {time.strftime("%H:%M:%S")} cwd={wt} ===\n')
                log.flush()
                r = runner(cmd, stdout=log, stderr=subprocess.STDOUT, **common)
            if r.returncode != 0:
                raise RuntimeError(f'agent 进程失败 rc={r.returncode}: {tail_file(log_path, 8)[-300:]}')
        else:
            r = runner(cmd, capture_output=True, **common)
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


# ── P3：任务感知 oracle ──────────────────────────────────────────────────────


def _has_nested_def(fns: Sequence[ast.AST]) -> bool:
    """任一目标函数体内是否嵌套定义了别的函数（抽取搬进函数内部 → 目标反而变长）。"""
    return any(
        isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)) and m is not fn for fn in fns for m in ast.walk(fn)
    )


def _bound_names(node: ast.AST) -> set[str]:
    """单个节点直接产生的名字绑定（只认绑定形态，不管作用域——作用域由调用方划定）。"""
    names: set[str] = set()
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        for alias in node.names:
            names.add((alias.asname or alias.name).split('.')[0])
    elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
        names.add(node.id)
    elif isinstance(node, ast.Global):
        names.update(node.names)
    elif isinstance(node, ast.ExceptHandler) and node.name:
        names.add(node.name)
    elif isinstance(node, ast.MatchAs) and node.name:
        names.add(node.name)
    elif isinstance(node, ast.MatchStar) and node.name:
        names.add(node.name)
    elif isinstance(node, ast.MatchMapping) and node.rest:
        names.add(node.rest)
    return names


def _scope_names(fn: ast.AST) -> set[str]:
    """函数子树内可见的绑定名：形参 + 局部 Store + 嵌套 def/类名（宽松：含嵌套函数的局部）。"""
    names: set[str] = set()
    for node in ast.walk(fn):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(node.name)
            args = node.args
            for arg in (*args.posonlyargs, *args.args, *args.kwonlyargs):
                names.add(arg.arg)
            if args.vararg:
                names.add(args.vararg.arg)
            if args.kwarg:
                names.add(args.kwarg.arg)
        elif isinstance(node, ast.ClassDef):
            names.add(node.name)
        else:
            names |= _bound_names(node)
    return names


def _unresolved_calls_in_function(tree: ast.Module, func_name: str) -> List[str]:
    """目标函数体内『裸名调用』(``NAME(...)``) 里、按 Python 作用域规则解析不到的名字。

    直击两轮实跑的真候选死法：07-04 尝试 2 抽了 ``_ternary_match_branch_loop(...)``
    却从没定义（全模块查无此名）；07-05 第二轮把辅助函数定义成**类方法**、又在
    ``ternary_match`` 里裸名调用——类体绑定对方法内裸名不可见（LEGB 链里没有类作用域），
    必然 NameError，旧实现把全树 FunctionDef 名一律计入可解析而放行，靠 pytest 才炸。
    此处 ast 级、毫秒成本，在组合首位就把这两类"抽了没落地"当场毙。

    作用域模型（该宽松处仍宽松——宁可漏报、绝不误杀，pytest 是真兜底）：
    裸名解析链 = 目标函数局部（形参/Store/嵌套 def，含闭包外层函数）→ 模块层
    （def/class/import/Store，**不进类体**）→ builtins；函数内 ``global X`` 视同模块层绑定。
    遇到 ``from x import *``（绑定无法静态推断）直接放行，避免误杀。
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and any(a.name == '*' for a in node.names):
            return []

    parents: dict = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent

    # 模块作用域：不下潜进 def/类体——类体里的方法名对方法内裸名解析不可见（0705 实录）
    known = set(dir(builtins))
    stack: List[ast.AST] = list(tree.body)
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            known.add(node.name)  # def/class 名本身绑定在模块层；体内绑定不外泄
            continue
        known |= _bound_names(node)
        stack.extend(ast.iter_child_nodes(node))
    for node in ast.walk(tree):  # 函数内 `global X; X=...` 在模块层制造绑定——宽松计入
        if isinstance(node, ast.Global):
            known.update(node.names)

    unresolved: List[str] = []
    seen: set[str] = set()
    for fn in (
        n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == func_name
    ):
        local = known | _scope_names(fn)
        anc = parents.get(fn)  # 闭包链：目标嵌套在别的函数里时，外层函数局部对它可见
        while anc is not None:
            if isinstance(anc, (ast.FunctionDef, ast.AsyncFunctionDef)):
                local |= _scope_names(anc)
            anc = parents.get(anc)
        for node in ast.walk(fn):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id not in local
                and node.func.id not in seen
            ):
                seen.add(node.func.id)
                unresolved.append(node.func.id)
    return unresolved


def _function_body_lines(source: str, func_name: str) -> List[str]:
    """基线文件里目标函数的『应守恒行』——纯搬运重构下每一行都该在新文件里原样存活。

    取函数体源码行（跳过 def 行/装饰器/docstring），去注释与空行，strip 归一
    （搬进辅助函数只改缩进），只留 ≥8 字符且含字母数字的行（短胶水行 reflow 不该
    误杀）。解析失败/函数不存在返回空——守恒检查静默跳过（宽松方向）。
    """
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return []
    fns = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == func_name]
    if not fns:
        return []
    fn = max(fns, key=lambda n: (getattr(n, 'end_lineno', None) or n.lineno) - n.lineno)
    if not fn.body:
        return []
    first_stmt = fn.body[0]
    start = first_stmt.lineno
    if (
        isinstance(first_stmt, ast.Expr)
        and isinstance(first_stmt.value, ast.Constant)
        and isinstance(first_stmt.value.value, str)
    ):
        start = (first_stmt.end_lineno or first_stmt.lineno) + 1  # docstring 改写不算改行为
    lines = source.splitlines()
    out: List[str] = []
    for raw in lines[start - 1 : fn.end_lineno or fn.lineno]:
        s = raw.strip()
        if len(s) >= 8 and not s.startswith('#') and any(c.isalnum() for c in s):
            out.append(s)
    return out


def make_shrink_oracle(
    rel_path: str,
    func_name: str,
    baseline_span: int,
    *,
    baseline_source: Optional[str] = None,
) -> Callable[[str], OracleVerdict]:
    """任务感知 oracle（P3 第一块）：long_function 重构后目标函数必须真的变短。

    P2 首跑实测：行为不变+测试全绿的"半成品重构"（辅助函数嵌套定义且未被调用、
    目标函数 94→125 行反而变长）会被通用 oracle 放行——通用 oracle 只判"不退化"，
    判不了"有改进"。本 oracle 零成本静态判改进，应放在组合首位先行短路。
    fail-closed：文件不可解析 / 目标函数消失（任务书要求行为不变、保留原名）一律拒绝。
    变短之外还有两道毫秒级静态闸：
    - 『引用可解析』（`_unresolved_calls_in_function`）：抽了辅助函数却没真正落地
      （07-04 未定义 / 07-05 定义成类方法裸名调用）当场拒，不烧 pytest；
    - 『守恒检查』（`_function_body_lines`，需传 `baseline_source`）：0705 第二轮唯一
      真候选死于**重写而非搬运**（校验条件被改写、异常类型被换）——纯搬运重构下原函数
      体每一行都该在新文件里原样存活（缩进不计），消失的行按名列出，喂给带记忆重试。
    """
    conserve = _function_body_lines(baseline_source, func_name) if baseline_source else []
    baseline_total_lines = len(baseline_source.splitlines()) if baseline_source else 0
    # 基线是否本就有嵌套 def：未知（无基线/解析失败）按"有"处理——病灶提示宁缺毋滥
    baseline_nested = True
    if baseline_source:
        try:
            btree = ast.parse(baseline_source)
            baseline_nested = _has_nested_def(
                [
                    n
                    for n in ast.walk(btree)
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == func_name
                ]
            )
        except (SyntaxError, ValueError):
            pass

    def oracle(workdir: str) -> OracleVerdict:
        fp = os.path.join(workdir, rel_path)
        try:
            with open(fp, encoding='utf-8', errors='replace') as f:
                src = f.read()
            tree = ast.parse(src)
        except (SyntaxError, ValueError, OSError) as e:
            return OracleVerdict(False, f'目标文件不可解析（fail-closed）: {e}')
        fns = [
            n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == func_name
        ]
        if not fns:
            return OracleVerdict(False, f'目标函数 {func_name} 消失（fail-closed：任务要求行为不变、保留原名）')
        spans = [(getattr(n, 'end_lineno', None) or n.lineno) - n.lineno + 1 for n in fns]
        span = max(spans)  # 同名多处取最长（保守）
        if span >= baseline_span:
            # 嵌套 def 诊断：P2 首跑与 0706 第五轮尝试 1 同型死法——辅助函数嵌套定义在
            # 目标函数体内，目标反而变长。点名病灶，纠偏才有的放矢（否则模型只知道"没变短"）。
            nested = not baseline_nested and _has_nested_def(fns)
            hint = '；辅助函数嵌套在目标函数内部——须定义在与原函数平级处才可能变短' if nested else ''
            if not hint and baseline_total_lines:
                # 大粘贴诊断（0706 第七轮尝试 3：+390/-0 整段重复贴入）：文件增长超过一个
                # 目标函数的体量，"两步都做完"的药方不对症——病是重复粘贴，不是漏了替换。
                grown = len(src.splitlines()) - baseline_total_lines
                if grown > baseline_span:
                    hint = f'；文件净增 {grown} 行（超过目标函数整体体量）——疑似整段重复粘贴'
            return OracleVerdict(
                False, f'{func_name} 未变短: {span} 行 ≥ 基线 {baseline_span} 行{hint}', {'span': span}
            )
        missing = _unresolved_calls_in_function(tree, func_name)
        if missing:
            names = ', '.join(missing[:3])
            return OracleVerdict(
                False,
                f'{func_name} 调用了模块内解析不到的名字: {names}（fail-closed：抽取的辅助函数没真正定义/导入）',
                {'span': span, 'unresolved': missing},
            )
        if conserve:
            new_lines = {ln.strip() for ln in src.splitlines()}
            lost = [ln for ln in conserve if ln not in new_lines]
            if lost:
                shown = ' ⏎ '.join(lost[:3])
                return OracleVerdict(
                    False,
                    f'{func_name} 重写而非搬运：{len(lost)} 行原始语句消失（守恒检查）: {shown}',
                    {'span': span, 'missing_lines': lost[:10]},
                )
        return OracleVerdict(True, f'{func_name}: {baseline_span} → {span} 行', {'span': span})

    return oracle
