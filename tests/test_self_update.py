"""P1：单任务安全自更新闭环 —— 隔离/回滚/fail-closed 的核心安全属性。

用一次性 tmp git 仓库驱动真实 worktree 机制；oracle 判定逻辑用注入的假 runner 测（不跑真 pytest）。
关键安全属性：过则留分支、败则**整体回滚**、主工作树全程不动、oracle 异常一律拒绝。
"""

import os
import subprocess
from types import SimpleNamespace

from agent_system.self_update import (
    OracleVerdict,
    SelfUpdateLoop,
    make_agent_edit_fn,
    make_differential_oracle,
    make_pytest_oracle,
    parse_pytest_summary,
)


def _git(repo, *a):
    return subprocess.run(
        ['git', *a], cwd=str(repo), capture_output=True, text=True, encoding='utf-8', errors='replace'
    )


def _init_repo(repo):
    repo.mkdir()
    _git(repo, 'init', '-b', 'main')
    _git(repo, 'config', 'user.email', 't@t')
    _git(repo, 'config', 'user.name', 't')
    _git(repo, 'config', 'commit.gpgsign', 'false')
    (repo / 'code.py').write_text('x = 1\n', encoding='utf-8')
    _git(repo, 'add', '-A')
    _git(repo, 'commit', '-m', 'init')
    return repo


def _branches(repo):
    return _git(repo, 'branch', '--list').stdout


def _worktree_count(repo):
    out = _git(repo, 'worktree', 'list').stdout
    return len([ln for ln in out.splitlines() if ln.strip()])


def _write_edit(name, content):
    def edit(wt):
        with open(os.path.join(wt, name), 'w', encoding='utf-8') as f:
            f.write(content)

    return edit


def test_accept_keeps_branch_removes_worktree(tmp_path):
    repo = _init_repo(tmp_path / 'repo')
    loop = SelfUpdateLoop(str(repo), oracle=lambda wt: OracleVerdict(True, 'fake-ok'))
    res = loop.run('demo', _write_edit('code.py', 'x = 2\n'))

    assert res.accepted and res.branch.startswith('self-update/demo-')
    assert res.branch in _branches(repo)  # 分支保留供人工合并
    assert (repo / 'code.py').read_text(encoding='utf-8') == 'x = 1\n'  # 主工作树未动
    assert _worktree_count(repo) == 1  # worktree 已清理（只剩主）


def test_reject_rolls_back_everything(tmp_path):
    repo = _init_repo(tmp_path / 'repo')
    loop = SelfUpdateLoop(str(repo), oracle=lambda wt: OracleVerdict(False, 'nope'))
    res = loop.run('demo', _write_edit('code.py', 'x = 999\n'))

    assert not res.accepted and res.branch is None
    assert 'self-update/demo' not in _branches(repo)  # 分支已删（整体回滚）
    assert (repo / 'code.py').read_text(encoding='utf-8') == 'x = 1\n'
    assert _worktree_count(repo) == 1


def test_no_change_rejected(tmp_path):
    repo = _init_repo(tmp_path / 'repo')
    loop = SelfUpdateLoop(str(repo), oracle=lambda wt: OracleVerdict(True))
    res = loop.run('noop', lambda wt: None)  # edit_fn 什么都不改
    assert not res.accepted and '无改动' in res.reason
    assert _worktree_count(repo) == 1


def test_oracle_exception_is_fail_closed(tmp_path):
    repo = _init_repo(tmp_path / 'repo')

    def boom(wt):
        raise RuntimeError('oracle 崩了')

    loop = SelfUpdateLoop(str(repo), oracle=boom)
    res = loop.run('demo', _write_edit('code.py', 'x = 2\n'))
    assert not res.accepted and 'fail-closed' in res.reason
    assert 'self-update/demo' not in _branches(repo)  # 异常也回滚


def test_oracle_sees_worktree_content(tmp_path):
    repo = _init_repo(tmp_path / 'repo')

    def oracle(wt):
        content = open(os.path.join(wt, 'code.py'), encoding='utf-8').read()
        return OracleVerdict('BROKEN' not in content, 'contains BROKEN' if 'BROKEN' in content else 'clean')

    loop = SelfUpdateLoop(str(repo), oracle=oracle)
    assert not loop.run('bad', _write_edit('code.py', 'BROKEN\n')).accepted
    assert loop.run('good', _write_edit('code.py', 'x = 42\n')).accepted


def test_reject_hook_sees_worktree_before_rollback(tmp_path):
    # 尸检窗口：钩子在回滚**前**拿到 (被拒worktree, 原因)，此刻还能读被拒内容
    repo = _init_repo(tmp_path / 'repo')
    seen = {}

    def hook(wt, reason):
        seen['reason'] = reason
        seen['content'] = open(os.path.join(wt, 'code.py'), encoding='utf-8').read()

    loop = SelfUpdateLoop(str(repo), oracle=lambda wt: OracleVerdict(False, 'nope'), reject_hook=hook)
    assert not loop.run('demo', _write_edit('code.py', 'x = 999\n')).accepted
    assert seen['content'] == 'x = 999\n' and 'nope' in seen['reason']
    assert 'self-update/demo' not in _branches(repo) and _worktree_count(repo) == 1  # 回滚不受影响


def test_reject_hook_exception_never_blocks_rollback(tmp_path):
    repo = _init_repo(tmp_path / 'repo')

    def bad_hook(wt, reason):
        raise RuntimeError('尸检崩了')

    loop = SelfUpdateLoop(str(repo), oracle=lambda wt: OracleVerdict(False, 'no'), reject_hook=bad_hook)
    assert not loop.run('demo', _write_edit('code.py', 'x = 2\n')).accepted
    assert 'self-update/demo' not in _branches(repo) and _worktree_count(repo) == 1


# ── commit_excludes：agent 运行副产物不进自更新提交 ──


def test_commit_excludes_kept_out_of_branch(tmp_path):
    # 副产物（学习记录/状态库）被 git reset 出暂存区：产出分支只含真代码改动
    repo = _init_repo(tmp_path / 'repo')

    def edit(wt):
        with open(os.path.join(wt, 'code.py'), 'w', encoding='utf-8') as f:
            f.write('x = 2\n')
        with open(os.path.join(wt, 'noise.md'), 'w', encoding='utf-8') as f:
            f.write('运行副产物\n')

    loop = SelfUpdateLoop(str(repo), oracle=lambda wt: OracleVerdict(True), commit_excludes=('noise.md',))
    res = loop.run('demo', edit)
    assert res.accepted
    files = _git(repo, 'show', '--name-only', '--format=', res.branch).stdout
    assert 'code.py' in files and 'noise.md' not in files  # 只提交真代码


def test_only_excluded_change_rejected(tmp_path):
    # 只动了副产物 → 排除后暂存区为空 → 视同零改动拒绝（不产出噪音分支）
    repo = _init_repo(tmp_path / 'repo')
    loop = SelfUpdateLoop(str(repo), oracle=lambda wt: OracleVerdict(True), commit_excludes=('noise.md',))
    res = loop.run('demo', _write_edit('noise.md', '只有副产物\n'))
    assert not res.accepted and '无改动' in res.reason
    assert 'self-update/demo' not in _branches(repo)


# ── oracle 判定逻辑（注入假 runner，不跑真 pytest）──


class _Fake:
    def __init__(self, stdout):
        self.stdout = stdout
        self.stderr = ''


def test_parse_pytest_summary():
    assert parse_pytest_summary('41 failed, 2330 passed, 2 skipped in 61.51s') == {
        'passed': 2330,
        'failed': 41,
        'errors': 0,
        'parsed': True,
    }
    b = parse_pytest_summary('290 passed in 44.84s')
    assert b['passed'] == 290 and b['failed'] == 0 and b['parsed']
    c = parse_pytest_summary('3 failed, 5 passed, 1 error in 2s')
    assert c['failed'] == 3 and c['errors'] == 1
    assert parse_pytest_summary('INTERNALERROR 崩溃，无摘要')['parsed'] is False  # 不可解析 → fail-closed


def test_pytest_oracle_baseline_gate():
    assert make_pytest_oracle(41, runner=lambda *a, **k: _Fake('41 failed, 2400 passed in 60s'))('.').ok
    assert not make_pytest_oracle(41, runner=lambda *a, **k: _Fake('42 failed, 2399 passed in 60s'))('.').ok
    assert not make_pytest_oracle(41, runner=lambda *a, **k: _Fake('1 error in 2s'))('.').ok
    assert not make_pytest_oracle(41, runner=lambda *a, **k: _Fake('乱七八糟无摘要'))('.').ok  # 不可解析 → 拒绝


def test_pytest_oracle_reason_names_failed_tests():
    # P3 实测缺口：拒绝理由只有"失败数 1 > 基线 0"，挂的是哪个测试随回滚一起消失
    out = (
        'FAILED tests/test_a.py::test_x - AssertionError: 1 != 2\n'
        'FAILED tests/test_b.py::test_y - KeyError\n'
        'FAILED tests/test_c.py::test_z - x\n'
        'FAILED tests/test_d.py::test_w - x\n'
        '4 failed, 10 passed in 3s\n'
    )
    v = make_pytest_oracle(0, runner=lambda *a, **k: _Fake(out))('.')
    assert not v.ok and 'tests/test_a.py::test_x' in v.reason and 'tests/test_c.py::test_z' in v.reason
    assert 'tests/test_d.py::test_w' not in v.reason  # 封顶 3 个，拒绝理由不爆长
    assert v.report['failed_names'][0] == 'tests/test_a.py::test_x'  # 完整名单进 report


# ── P2：agent edit_fn + 差分 oracle（注入假件，不跑真 agent/真引擎）──


def test_agent_edit_fn_runs_agent_in_worktree(tmp_path):
    repo = _init_repo(tmp_path / 'repo')
    calls = {}

    def fake_agent(cmd, **kw):
        calls['cmd'], calls['cwd'] = cmd, kw.get('cwd')
        # agent 在副本里改文件（真 agent 也是这样产生 diff 的）
        with open(os.path.join(kw['cwd'], 'code.py'), 'w', encoding='utf-8') as f:
            f.write('x = 7\n')
        return SimpleNamespace(returncode=0, stdout='ok', stderr='')

    loop = SelfUpdateLoop(str(repo), oracle=lambda wt: OracleVerdict(True))
    res = loop.run('agent-task', make_agent_edit_fn('修复某测试', runner=fake_agent))
    assert res.accepted
    assert calls['cwd'] != str(repo) and '修复某测试' in calls['cmd']  # cwd=worktree 而非主仓库（红线②）
    assert '-u' in calls['cmd']  # 无缓冲：超时树杀不再吞掉整段日志
    assert (repo / 'code.py').read_text(encoding='utf-8') == 'x = 1\n'  # 主工作树未动


def test_agent_edit_fn_failure_rolls_back(tmp_path):
    repo = _init_repo(tmp_path / 'repo')

    def failing_agent(cmd, **kw):
        return SimpleNamespace(returncode=1, stdout='', stderr='agent 崩了')

    loop = SelfUpdateLoop(str(repo), oracle=lambda wt: OracleVerdict(True))
    res = loop.run('agent-task', make_agent_edit_fn('任务', runner=failing_agent))
    assert not res.accepted and 'edit_fn 异常' in res.reason
    assert 'self-update/agent-task' not in _branches(repo)  # 整体回滚


def _fake_verifier(report):
    def factory(workdir):
        return SimpleNamespace(verify_consistency=lambda cases=None: report)

    return factory


def test_differential_oracle_gates_and_fail_closed():
    assert make_differential_oracle(verifier_factory=_fake_verifier({'total': 4, 'consistent': 4}))('.').ok
    assert not make_differential_oracle(verifier_factory=_fake_verifier({'total': 4, 'consistent': 3}))('.').ok
    assert not make_differential_oracle(verifier_factory=_fake_verifier({'total': 0, 'consistent': 0}))(
        '.'
    ).ok  # 零用例拒

    def boom(workdir):
        raise RuntimeError('验证器起不来')

    v = make_differential_oracle(verifier_factory=boom)('.')
    assert not v.ok and 'fail-closed' in v.reason
