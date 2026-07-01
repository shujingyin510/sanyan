"""loop.py：主循环已抽出为 run_legacy(rt, ...) —— 用最小 mock rt 独立验证。

抽出的价值即在此：`_run_legacy` 从 God Object 里搬出后，可脱离完整 AgentRuntime、
以一个只实现所需少量属性/方法的假 rt 驱动（这里覆盖 dry_run 快速路径的三条分支）。
"""

import types


class _FakeRt:
    def __init__(self, forced=None, tools=None):
        self.memory = {'history': []}
        self._forced = forced
        self.tools = tools or {}
        self.ternary = types.SimpleNamespace(step=lambda t, r: (1, 0.9, {}, 'AFFIRM'))

    def _force_tool(self, task):
        return self._forced

    def _extract_key(self, result):
        return f'key:{result}'


def test_run_legacy_dry_run_no_forced_tool():
    from agent_system.loop import run_legacy

    rt = _FakeRt(forced=None)
    assert run_legacy(rt, '任务', 5, dry_run=True) == {'answer': 'dry_run完成', 'memory': {'history': []}}


def test_run_legacy_dry_run_executes_forced_tool():
    from agent_system.loop import run_legacy

    calls = []
    rt = _FakeRt(
        forced=('read_file', 'x.py'),
        tools={'read_file': lambda p, d: calls.append((p, d)) or 'FILE内容'},
    )
    r = run_legacy(rt, '任务', 5, dry_run=True)
    assert r['answer'] == 'key:FILE内容'
    assert calls == [('x.py', True)]  # dry_run 透传给工具
    assert len(rt.memory['history']) == 1 and rt.memory['history'][0]['tool'] == 'read_file'


def test_run_legacy_dry_run_forced_tool_unregistered():
    from agent_system.loop import run_legacy

    rt = _FakeRt(forced=('unknown_tool', 'p'), tools={})  # 强制工具未注册 → 回退
    assert run_legacy(rt, '任务', 5, dry_run=True) == {'answer': 'dry_run完成', 'memory': {'history': []}}
