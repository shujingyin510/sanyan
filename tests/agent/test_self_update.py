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
    UpdateResult,
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


# ── S2 候选淘汰赛（0707 第十三轮定论后动工）──────────────────────────────


class _TourneyLoop:
    """假 loop：按脚本吐 UpdateResult，记录消费个数。"""

    def __init__(self, results):
        self._results = list(results)
        self.runs = 0

    def run(self, name, edit_fn):
        self.runs += 1
        return self._results.pop(0)


def _factory_recorder(seen):
    def factory(k, feedback):
        seen.append((k, feedback))
        return lambda wt: None

    return factory


def test_tournament_stops_on_first_accept():
    # 首个 accepted 立即返回，不烧后续候选
    from agent_system.self_update import run_tournament

    loop = _TourneyLoop(
        [
            UpdateResult(False, None, 'big 未变短: 12 行 ≥ 基线 10 行'),
            UpdateResult(True, 'self-update/x-1', 'ok'),
            UpdateResult(False, None, '不该被消费'),
        ]
    )
    seen = []
    r = run_tournament(loop, 't', _factory_recorder(seen), 3)
    assert r.accepted and r.branch == 'self-update/x-1'
    assert loop.runs == 2  # 第三个候选没跑
    assert seen[0] == (1, '')  # 首个候选无教训


def test_tournament_returns_most_informative_reject():
    # 全败返回信息量最大的拒绝：守恒/解析类 > 未变短 > 无改动
    from agent_system.self_update import run_tournament

    loop = _TourneyLoop(
        [
            UpdateResult(False, None, '无改动（edit_fn 未产生 diff）'),
            UpdateResult(False, None, 'big 重写而非搬运：2 行原始语句消失（守恒检查）: x'),
            UpdateResult(False, None, 'big 未变短: 12 行 ≥ 基线 10 行'),
        ]
    )
    r = run_tournament(loop, 't', _factory_recorder([]), 3)
    assert not r.accepted and '守恒检查' in r.reason
    assert r.report['candidates_run'] == 3


def test_tournament_breaker_on_consecutive_zero_edit():
    # 连续 breaker 个候选零编辑 → 判风暴断路，不再投入后续候选
    from agent_system.self_update import run_tournament

    loop = _TourneyLoop(
        [
            UpdateResult(False, None, '无改动（edit_fn 未产生 diff）'),
            UpdateResult(False, None, '无改动（edit_fn 未产生 diff）'),
            UpdateResult(False, None, '不该被消费'),
        ]
    )
    r = run_tournament(loop, 't', _factory_recorder([]), 3, breaker=2)
    assert not r.accepted and '断路' in r.reason and '零编辑' in r.reason
    assert loop.runs == 2


def test_tournament_feedback_dedups_across_candidates():
    # 教训跨候选去重累积：相同拒因只留一课，不同拒因逐条追加（把抽签变爬山）
    from agent_system.self_update import run_tournament

    loop = _TourneyLoop(
        [
            UpdateResult(False, None, 'big 未变短: 12 行 ≥ 基线 10 行'),
            UpdateResult(False, None, 'big 未变短: 12 行 ≥ 基线 10 行'),
            UpdateResult(False, None, 'big 重写而非搬运：2 行原始语句消失（守恒检查）: x'),
            UpdateResult(False, None, '无改动（edit_fn 未产生 diff）'),
        ]
    )
    seen = []
    tips = {'未变短': '两步都要做完', '守恒': '这些行原样保留'}

    def tip_fn(reason):
        for k, v in tips.items():
            if k in reason:
                return v
        return ''

    run_tournament(loop, 't', _factory_recorder(seen), 4, breaker=99, tip_fn=tip_fn)
    assert seen[1][1] == '两步都要做完'
    assert seen[2][1] == '两步都要做完'  # 相同教训不重复
    assert seen[3][1] == '两步都要做完\n这些行原样保留'  # 新教训追加，旧课不丢


# ── S4 考官域写保护 + P5 密钥闸（红线①机械化）──────────────────────────────


def _write_edit_nested(relpath, content):
    def edit(wt):
        p = os.path.join(wt, relpath)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, 'w', encoding='utf-8') as f:
            f.write(content)

    return edit


def test_examiner_domain_write_rejected_before_oracle(tmp_path):
    # 触碰 tests/ 的候选必拒且**先于 oracle**（oracle 恒过也拦）——pytest oracle
    # 防不住"把测试改成恒过"（循环论证）；拒绝理由点名红线①与命中路径
    repo = _init_repo(tmp_path / 'repo')
    oracle_calls = []

    def oracle(wt):
        oracle_calls.append(wt)
        return OracleVerdict(True, '恒过')

    loop = SelfUpdateLoop(str(repo), oracle=oracle)
    res = loop.run('evil', _write_edit_nested('tests/x.py', 'def test_always_pass():\n    assert True\n'))
    assert not res.accepted and '考官域' in res.reason and '红线①' in res.reason and 'tests/x.py' in res.reason
    assert oracle_calls == []  # 保护检查在 oracle 之前短路
    assert 'self-update/evil' not in _branches(repo)  # 整体回滚


def test_oracle_file_write_rejected(tmp_path):
    # 改判考官本体（self_update.py）同拒
    repo = _init_repo(tmp_path / 'repo')
    loop = SelfUpdateLoop(str(repo), oracle=lambda wt: OracleVerdict(True))
    res = loop.run('evil2', _write_edit_nested('agent_system/self_update.py', 'HACKED = True\n'))
    assert not res.accepted and '考官域' in res.reason


def test_secret_literal_in_added_lines_rejected(tmp_path):
    # 新增行注入密钥环境写入 → P5 密钥闸拒
    repo = _init_repo(tmp_path / 'repo')
    loop = SelfUpdateLoop(str(repo), oracle=lambda wt: OracleVerdict(True))
    res = loop.run('leak', _write_edit('code.py', "import os\nos.environ['SANYAN_API_KEY'] = 'sk-abcdefghijklmnop'\n"))
    assert not res.accepted and '密钥' in res.reason


def test_normal_change_unaffected_by_protection(tmp_path):
    # 常规文件改动不受保护闸影响，照常走 oracle 接受
    repo = _init_repo(tmp_path / 'repo')
    loop = SelfUpdateLoop(str(repo), oracle=lambda wt: OracleVerdict(True, 'ok'))
    res = loop.run('normal', _write_edit('code.py', 'x = 2\n'))
    assert res.accepted and res.branch in _branches(repo)


# ── 拆步流程（实验策略 v2：固定两步计划 + 阶段间静态检查）──────────────────


def test_staged_edit_runs_stages_in_order(tmp_path):
    # 两阶段按序执行于同一 worktree；阶段检查通过则继续
    from agent_system.self_update import make_staged_edit_fn

    calls = []

    def fake_runner(cmd, **kw):
        calls.append(cmd[5])  # prompt 位于命令第 6 位
        (tmp_path / f'stage{len(calls)}.txt').write_text('x', encoding='utf-8')
        return SimpleNamespace(returncode=0, stdout='', stderr='')

    def check_a(wt):
        return '' if (tmp_path / 'stage1.txt').exists() else '阶段A产物缺失'

    fn = make_staged_edit_fn([('步1', check_a), ('步2', None)], runner=fake_runner)
    fn(str(tmp_path))
    assert calls == ['步1', '步2']


def test_staged_edit_aborts_on_failed_check(tmp_path):
    # 阶段检查不过 → 抛异常（外层按 edit_fn 异常整体回滚），阶段 B 不烧调用
    import pytest

    from agent_system.self_update import make_staged_edit_fn

    calls = []

    def fake_runner(cmd, **kw):
        calls.append(cmd[5])
        return SimpleNamespace(returncode=0, stdout='', stderr='')

    fn = make_staged_edit_fn([('步1', lambda wt: 'helper 未定义'), ('步2', None)], runner=fake_runner)
    with pytest.raises(RuntimeError, match='阶段1/2未达标'):
        fn(str(tmp_path))
    assert calls == ['步1']  # 阶段 B 没跑


def test_def_exists_check(tmp_path):
    from agent_system.self_update import make_def_exists_check

    (tmp_path / 'm.py').write_text('def _f_block(x):\n    return x\n', encoding='utf-8')
    assert make_def_exists_check('m.py', '_f_block')(str(tmp_path)) == ''
    assert '未找到 _nope' in make_def_exists_check('m.py', '_nope')(str(tmp_path))
    (tmp_path / 'bad.py').write_text('def broken(:\n', encoding='utf-8')
    assert '不可解析' in make_def_exists_check('bad.py', '_f_block')(str(tmp_path))


def test_build_stage_plans_shape():
    # 计划模板：两步、各一动作、步1带 def 检查、行区间与 helper 名进任务书
    import agent_system.run_self_update as rsu

    plans = rsu.build_stage_plans('ops/control_ops.py', 'ternary_match', 'L326-399（循环块，74行）')
    assert len(plans) == 2
    (pa, ca), (pb, cb) = plans
    assert '只插入' in pa and '_ternary_match_block' in pa and 'L326-399' in pa and '不要替换原块' in pa
    assert '只替换' in pb and '_ternary_match_block' in pb and 'L326-399' in pb
    assert '类名._ternary_match_block' in pb  # 调用形式占位指引（0705/0716 类内裸名死法的预防）
    assert ca is not None and cb is None
