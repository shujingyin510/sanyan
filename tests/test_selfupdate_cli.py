"""run_self_update CLI：--attempts 重试语义 + agent 日志落盘（P3 可观测性）。

P2 排障期 agent 输出只在 rc≠0 时可见，多跑了一打盲探针——日志文件回滚不灭。
"""

import os
import subprocess
from types import SimpleNamespace

import pytest

import agent_system.run_self_update as rsu
from agent_system.self_update import make_agent_edit_fn, tail_file


@pytest.fixture(autouse=True)
def _restore_skip_rule_gen():
    # main() 会写 SANYAN_SKIP_RULE_GEN='1'（自更新子进程继承的正当机制）；测试进程内
    # 直调 main 会把它遗留给同进程后续测试——test_loop 的规则生成用例会被静默关闭
    # （全量按字母序 test_loop 在前侥幸不炸，换序/并行即炸）。显式还原。
    prev = os.environ.get('SANYAN_SKIP_RULE_GEN')
    yield
    if prev is None:
        os.environ.pop('SANYAN_SKIP_RULE_GEN', None)
    else:
        os.environ['SANYAN_SKIP_RULE_GEN'] = prev


def test_attempts_stops_at_first_accept(monkeypatch):
    calls = {'n': 0}

    class FakeLoop:
        def __init__(self, root, oracle, *, reject_hook=None, commit_excludes=()):
            calls['hook'] = reject_hook
            calls['excludes'] = commit_excludes

        def run(self, name, edit_fn):
            calls['n'] += 1
            ok = calls['n'] >= 2
            return SimpleNamespace(accepted=ok, branch='br' if ok else None, reason='假拒绝')

    monkeypatch.setattr(rsu, 'SelfUpdateLoop', FakeLoop)
    monkeypatch.setattr(rsu, 'make_agent_edit_fn', lambda *a, **k: lambda wt: None)
    rc = rsu.main(['--task', 'x', '--attempts', '3'])
    assert rc == 0 and calls['n'] == 2  # 第二次过 oracle 即停，不烧第三次
    assert callable(calls['hook'])  # CLI 接线了尸检钩子
    # 学习记录/状态库属运行副产物，必须排除在自更新提交外（尸检实证：曾伪装成真 diff）
    assert 'agent_system/learned_styles.md' in calls['excludes']


def test_attempts_exhausted_returns_1(monkeypatch):
    class FakeLoop:
        def __init__(self, root, oracle, *, reject_hook=None, commit_excludes=()):
            pass

        def run(self, name, edit_fn):
            return SimpleNamespace(accepted=False, branch=None, reason='拒')

    monkeypatch.setattr(rsu, 'SelfUpdateLoop', FakeLoop)
    monkeypatch.setattr(rsu, 'make_agent_edit_fn', lambda *a, **k: lambda wt: None)
    assert rsu.main(['--task', 'x', '--attempts', '2']) == 1


def test_build_retry_feedback_classifies():
    # 分类纠偏：每类失败给出对症提示，且都带上原因原文
    assert '真正改文件' in rsu.build_retry_feedback('无改动（edit_fn 未产生 diff）')
    fb = rsu.build_retry_feedback('big 调用了模块内解析不到的名字: _helper')
    assert '辅助函数' in fb and '定义' in fb
    assert '逻辑严格等价' in rsu.build_retry_feedback('失败数 3 > 基线 0；失败用例: test_a')
    assert '原样保留' in rsu.build_retry_feedback('big 重写而非搬运：2 行原始语句消失（守恒检查）: ...')
    fb2 = rsu.build_retry_feedback('big 未变短: 94 行 ≥ 基线 94 行', hints='L326-399（循环块，74行）')
    assert '两步都要做完' in fb2 and 'L326-399' in fb2  # 两步点名 + 候选块随纠偏（0706 第四轮：只做第一步）
    assert '两步都要做完' in rsu.build_retry_feedback('big 未变短: 94 行 ≥ 基线 94 行')  # 无 hints 也成句
    assert '上一次尝试被拒' in rsu.build_retry_feedback('莫名其妙的原因')  # 兜底也不丢信息


def test_retry_threads_feedback_into_next_prompt(monkeypatch):
    # 带记忆重试：首轮干净任务书；次轮把上次拒绝原因+纠偏喂回 prompt
    prompts = []

    class FakeLoop:
        def __init__(self, root, oracle, *, reject_hook=None, commit_excludes=()):
            pass

        def run(self, name, edit_fn):
            edit_fn('wt')  # 触发 fake 工厂记录本轮 prompt
            ok = len(prompts) >= 2
            reason = '' if ok else 'oracle 未过: big 调用了模块内解析不到的名字: _helper'
            return SimpleNamespace(accepted=ok, branch='br' if ok else None, reason=reason)

    def fake_edit_factory(prompt, **kw):
        def edit(wt):
            prompts.append(prompt)

        return edit

    monkeypatch.setattr(rsu, 'SelfUpdateLoop', FakeLoop)
    monkeypatch.setattr(rsu, 'make_agent_edit_fn', fake_edit_factory)
    rc = rsu.main(['--task', 'x', '--attempts', '3'])
    assert rc == 0 and len(prompts) == 2
    assert '上一次尝试被拒' not in prompts[0]  # 首轮是干净任务书
    assert '上一次尝试被拒' in prompts[1] and '辅助函数' in prompts[1]  # 次轮带纠偏


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


# ── 被拒改动尸检（reject_hook 落 diff 进 agent 日志）──


def _mini_repo(tmp_path, subject):
    """一次性小仓库充当"被拒 worktree"（HEAD 提交主题可控）。"""
    repo = tmp_path / 'repo'
    repo.mkdir()

    def g(*a):
        subprocess.run(['git', *a], cwd=str(repo), capture_output=True, text=True)

    g('init', '-b', 'main')
    g('config', 'user.email', 't@t')
    g('config', 'user.name', 't')
    g('config', 'commit.gpgsign', 'false')
    (repo / 'code.py').write_text('x = 1\n', encoding='utf-8')
    g('add', '-A')
    g('commit', '-m', subject)
    return str(repo)


def test_reject_diff_dumper_patch_then_stat(tmp_path):
    # 尸检落盘：patch 在前、stat 收尾——CLI 打日志尾时尾部正好是"改了哪些文件几行"
    repo = _mini_repo(tmp_path, 'self-update: demo')
    log = str(tmp_path / 'agent.log')
    rsu.make_reject_diff_dumper(log)(repo, '失败数 1 > 基线 0')
    content = open(log, encoding='utf-8').read()
    assert '被拒改动尸检' in content and '失败数 1 > 基线 0' in content
    assert '+x = 1' in content  # patch 本体在
    assert content.rindex('—— 被拒改动 stat ——') > content.rindex('+x = 1')


def test_reject_diff_dumper_skips_without_selfupdate_commit(tmp_path):
    # HEAD 不是自更新提交（edit_fn 异常/无改动路径）——没有 diff 可留，不产日志
    repo = _mini_repo(tmp_path, '普通提交')
    log = str(tmp_path / 'agent.log')
    rsu.make_reject_diff_dumper(log)(repo, '原因')
    assert not os.path.exists(log)
