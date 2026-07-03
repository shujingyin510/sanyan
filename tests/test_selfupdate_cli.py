"""run_self_update CLI：--attempts 重试语义 + agent 日志落盘（P3 可观测性）。

P2 排障期 agent 输出只在 rc≠0 时可见，多跑了一打盲探针——日志文件回滚不灭。
"""

from types import SimpleNamespace

import agent_system.run_self_update as rsu
from agent_system.self_update import make_agent_edit_fn, tail_file


def test_attempts_stops_at_first_accept(monkeypatch):
    calls = {'n': 0}

    class FakeLoop:
        def __init__(self, root, oracle):
            pass

        def run(self, name, edit_fn):
            calls['n'] += 1
            ok = calls['n'] >= 2
            return SimpleNamespace(accepted=ok, branch='br' if ok else None, reason='假拒绝')

    monkeypatch.setattr(rsu, 'SelfUpdateLoop', FakeLoop)
    monkeypatch.setattr(rsu, 'make_agent_edit_fn', lambda *a, **k: lambda wt: None)
    rc = rsu.main(['--task', 'x', '--attempts', '3'])
    assert rc == 0 and calls['n'] == 2  # 第二次过 oracle 即停，不烧第三次


def test_attempts_exhausted_returns_1(monkeypatch):
    class FakeLoop:
        def __init__(self, root, oracle):
            pass

        def run(self, name, edit_fn):
            return SimpleNamespace(accepted=False, branch=None, reason='拒')

    monkeypatch.setattr(rsu, 'SelfUpdateLoop', FakeLoop)
    monkeypatch.setattr(rsu, 'make_agent_edit_fn', lambda *a, **k: lambda wt: None)
    assert rsu.main(['--task', 'x', '--attempts', '2']) == 1


def test_edit_fn_writes_agent_log(tmp_path):
    log = str(tmp_path / 'agent.log')

    def fake_runner(cmd, **kw):
        kw['stdout'].write('agent说了点什么\n')  # 输出进日志文件而非管道
        return SimpleNamespace(returncode=0, stdout=None, stderr=None)

    make_agent_edit_fn('任务', runner=fake_runner, log_path=log)(str(tmp_path))
    content = open(log, encoding='utf-8').read()
    assert 'agent 启动' in content and 'agent说了点什么' in content


def test_edit_fn_failure_reports_log_tail(tmp_path):
    log = str(tmp_path / 'agent.log')

    def fail_runner(cmd, **kw):
        kw['stdout'].write('崩溃前的最后遗言\n')
        return SimpleNamespace(returncode=3, stdout=None, stderr=None)

    try:
        make_agent_edit_fn('任务', runner=fail_runner, log_path=log)(str(tmp_path))
        raise AssertionError('应抛 RuntimeError')
    except RuntimeError as e:
        assert 'rc=3' in str(e) and '最后遗言' in str(e)


def test_tail_file_missing_returns_empty(tmp_path):
    assert tail_file(str(tmp_path / '不存在.log')) == ''
