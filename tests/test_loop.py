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


# ── 生成规则闸门：零改动不收工，回退 LLM 多轮循环（P2 首跑回归守护）──


class _RuleGenRt:
    """覆盖生成规则路径所需最小面：真 RuleExecutor + 假 rule_engine/llm。"""

    def __init__(self, rule, tools=None):
        self.memory = {'history': [], 'modified': [], 'failures': 0}
        self.tools = tools or {}
        self.ternary = types.SimpleNamespace(step=lambda t, r: (1, 0.9, {'action': 'allow'}, 'AFFIRM'))
        self.template_manager = None
        self.rule_engine = types.SimpleNamespace(
            match_rule=lambda task: None,
            llm_fn=lambda p: '',  # truthy → 进入生成分支
            generate_rule=lambda task: rule,
            extract_filename=lambda task: 'x.py',
            extract_module_name=lambda task, fn: 'x',
            rules=[],
        )

    def _build_context(self, *a):
        return 'CTX'

    def _llm_call(self, ctx):
        raise RuntimeError('模拟 LLM 失败')


def test_generated_rule_with_zero_modification_falls_through_to_loop():
    # 今天的案情：LLM 生成的规则参数全是未绑定模板，跑完零改动还 done 谎报完成。
    # 旧行为直接 return 规则结果（answer='按规则…执行完成'）；新行为必须落回 LLM 循环。
    from agent_system.loop import run_legacy

    rule = types.SimpleNamespace(name='garbage-rule', steps=[], validation=None)
    rt = _RuleGenRt(rule)
    r = run_legacy(rt, '重构某函数', 3, dry_run=False)
    assert r['answer'] == '已达3轮'  # 进了 LLM 循环（此处假 LLM 连败退出），而非规则结果
    assert '按规则' not in r['answer']
    assert rt.memory['modified'] == []


def test_skip_rule_gen_env_bypasses_generation(monkeypatch):
    # 自更新场景：SANYAN_SKIP_RULE_GEN 跳过规则生成前奏（省 2-4 次 LLM 调用），
    # 直接进 LLM 主循环
    from agent_system.loop import run_legacy

    monkeypatch.setenv('SANYAN_SKIP_RULE_GEN', '1')

    def _boom(task):
        raise AssertionError('不应调用 generate_rule')

    rt = _RuleGenRt(types.SimpleNamespace(name='x', steps=[], validation=None))
    rt.rule_engine.generate_rule = _boom
    r = run_legacy(rt, '重构某函数', 3, dry_run=False)
    assert r['answer'] == '已达3轮'  # 未触发 _boom，直接进循环（假 LLM 连败退出）


def test_generated_rule_with_dict_args_does_not_crash():
    # P2 探针#10 回归守护：LLM 生成的步骤 args_desc 可能是 dict（协议漂移），
    # 旧实现 .replace 直接 AttributeError 崩掉整个 agent 进程
    from agent_system.loop import run_legacy

    rule = types.SimpleNamespace(
        name='dict-args',
        steps=[{'tool': 'read_file', 'args_desc': {'path': 'x.py', 'start': 1}, 'desc': '读'}],
        validation=None,
    )
    rt = _RuleGenRt(rule, tools={'read_file': lambda p, d: f'content of {p}'})
    r = run_legacy(rt, '重构某函数', 3, dry_run=False)
    assert r['answer'] == '已达3轮'  # 不崩溃, 零改动回退循环（假LLM连败退出）


def test_generated_rule_with_real_modification_returns_rule_result():
    from agent_system.loop import run_legacy

    rule = types.SimpleNamespace(
        name='w',
        steps=[{'tool': 'write_file', 'args_desc': 'x.py|print(1)', 'desc': '写文件'}],
        validation=None,
    )
    rt = _RuleGenRt(rule, tools={'write_file': lambda p, d: f'已写入 {p.split("|")[0]}'})
    r = run_legacy(rt, '创建 x.py', 3, dry_run=False)
    assert r['answer'] == '按规则 [w] 执行完成' and r['auto_rule'] == 'w'
    assert rt.memory['modified'] == ['x.py']


# ── LLM 多轮循环：改动记录只认成功(B) + 零改动 done 顶回(⑥) ──


class _LoopRt:
    """驱动 LLM 多轮主循环的最小 rt：脚本化 (tool, params) 序列 + 真 TernaryEngine。

    用真引擎（而非假 step）才能验证 B：`cog=='AFFIRM'` 门必须依赖真 classify——
    成功替换(已替换)判 AFFIRM 记改动，失败替换(未找到/错误)判 UNCERT 不记。
    """

    def __init__(self, script, tools=None):
        from core.ternary_engine import TernaryEngine

        self._script = list(script)
        self._last = None
        self.ctx_calls = []  # 记录 _build_context 入参（顶推/纠偏文案断言用）
        self.memory = {'history': [], 'modified': [], 'failures': 0, 'retry_count': 0}
        self.tools = tools or {}
        self.ternary = TernaryEngine()
        self.rule_engine = types.SimpleNamespace(match_rule=lambda task: None, llm_fn=None)
        self.profiler = types.SimpleNamespace(record_step=lambda *a: None)
        self.mem = types.SimpleNamespace(add=lambda *a: None)
        self.tracer = types.SimpleNamespace(add_step=lambda *a: None)
        self.context_compressor = types.SimpleNamespace(add_entry=lambda *a: None)
        self.tool_selector = types.SimpleNamespace(record_outcome=lambda *a: None)

    def _build_context(self, *a):
        self.ctx_calls.append(a)
        return 'CTX'

    def _llm_call(self, ctx):
        if self._script:
            self._last = self._script.pop(0)
        return self._last  # 脚本耗尽后重复最后一条（收尾轮不再变化）

    def _parse_tool(self, raw):
        return raw  # 脚本直接给 (tool, params)

    def _fail_closed(self, tool, params, dry_run):
        return False

    def _constraint_violation(self, tool):
        return False

    def _reflect(self, msg, ctx):
        return ctx

    def _test_failed(self, result):
        return False

    def _compress_ctx(self, ctx):
        return ctx


def test_failed_edit_not_recorded_as_modified(monkeypatch):
    # B：替换失败（未找到 → UNCERT）不得记为"修改文件"——否则面板/学习器/⑥ 全被骗
    from agent_system.loop import run_legacy

    monkeypatch.delenv('SANYAN_REQUIRE_EDIT', raising=False)
    rt = _LoopRt(
        script=[('replace_in_file', 'a.py|old|new'), ('done', '')],
        tools={'replace_in_file': lambda p, d: '替换错误: 未找到匹配文本'},
    )
    run_legacy(rt, '改文件', 6, dry_run=False)
    assert rt.memory['modified'] == []


def test_successful_edit_recorded_as_modified(monkeypatch):
    # B：替换成功（已替换 → AFFIRM）正常记录，功能不回退
    from agent_system.loop import run_legacy

    monkeypatch.delenv('SANYAN_REQUIRE_EDIT', raising=False)
    rt = _LoopRt(
        script=[('replace_in_file', 'a.py|old|new'), ('done', '')],
        tools={'replace_in_file': lambda p, d: '已替换 1 处'},
    )
    run_legacy(rt, '改文件', 6, dry_run=False)
    assert rt.memory['modified'] == ['a.py']


def test_zero_mod_done_pushed_back_under_require_edit(monkeypatch):
    # ⑥：SANYAN_REQUIRE_EDIT 下零改动 done 被顶回（至多两次），不首个 done 就收工
    from agent_system.loop import run_legacy

    monkeypatch.setenv('SANYAN_REQUIRE_EDIT', '1')
    rt = _LoopRt(script=[('done', ''), ('done', ''), ('done', '')])
    run_legacy(rt, '重构某函数', 6, dry_run=False)
    assert rt.memory['empty_done'] == 3  # 顶回两次后第三次才停
    assert rt.memory['modified'] == []


def test_zero_mod_done_returns_without_require_edit(monkeypatch):
    # 通用兜底不变：无 REQUIRE_EDIT 时首轮 done 观察一轮、次轮 done 直接收工（非编辑任务）
    from agent_system.loop import run_legacy

    monkeypatch.delenv('SANYAN_REQUIRE_EDIT', raising=False)
    rt = _LoopRt(script=[('done', ''), ('done', '答案')])
    r = run_legacy(rt, '问个问题', 6, dry_run=False)
    assert r['answer'] == '答案' and 'empty_done' not in rt.memory


def test_wandering_nudge_fires_at_midpoint(monkeypatch):
    # 徘徊顶推：REQUIRE_EDIT 下过半仍零改动 → 顶推一次"停止阅读、动手改"（0705 第二轮
    # 实录：预算修好后模型 15 轮全在读，一次编辑不做）
    from agent_system.loop import run_legacy

    monkeypatch.setenv('SANYAN_REQUIRE_EDIT', '1')
    monkeypatch.delenv('SANYAN_LOOP_TIME_BUDGET', raising=False)
    script = [('read_file', f'a.py|{i}') for i in range(1, 5)]  # 参数各异防 UR 退化误停
    rt = _LoopRt(script=script, tools={'read_file': lambda p, d: f'内容 {p}'})
    run_legacy(rt, '重构某函数', 4, dry_run=False)
    nudges = [a for a in rt.ctx_calls if '停止继续阅读' in str(a[0])]
    assert len(nudges) == 1 and nudges[0][1] == 'init'  # 恰好一次，rnd==3（4//2+1）
    assert '重构某函数' in str(nudges[0][0])  # 原任务随顶推保留


def test_wandering_nudge_absent_after_edit(monkeypatch):
    # 已有真实改动就不顶推（顶推只治零改动徘徊，不打扰正常工作流）
    from agent_system.loop import run_legacy

    monkeypatch.setenv('SANYAN_REQUIRE_EDIT', '1')
    script = [('replace_in_file', 'a.py|old|new'), ('read_file', 'a.py|2'), ('read_file', 'a.py|3'), ('done', '完')]
    rt = _LoopRt(
        script=script,
        tools={'replace_in_file': lambda p, d: '已替换 1 处', 'read_file': lambda p, d: f'内容 {p}'},
    )
    run_legacy(rt, '重构某函数', 4, dry_run=False)
    assert not [a for a in rt.ctx_calls if '停止继续阅读' in str(a[0])]


def test_loop_time_budget_env_tunable(monkeypatch):
    # 总预算认 SANYAN_LOOP_TIME_BUDGET（0705 实跑：代理抖动时 420s 掐死在编辑前，
    # 自更新场景放宽）。预算 -1 → 首轮即触护杀，一次 LLM 都不调。
    # （不用 0：Windows time.time() 粒度粗，首轮 elapsed 可恰为 0.0，0.0 > 0 为 False）
    from agent_system.loop import run_legacy

    monkeypatch.delenv('SANYAN_REQUIRE_EDIT', raising=False)
    monkeypatch.setenv('SANYAN_LOOP_TIME_BUDGET', '-1')
    rt = _LoopRt(script=[('done', '答案')])
    run_legacy(rt, '任务', 6, dry_run=False)
    assert rt.memory['failures'] == 1
    assert len(rt._script) == 1  # 脚本没被消费 → 没进过 LLM 轮


def test_loop_time_budget_garbage_falls_back(monkeypatch):
    # 环境值损坏 → 回默认 420s，护杀不失效也不炸；正常脚本照常收工
    from agent_system.loop import run_legacy

    monkeypatch.delenv('SANYAN_REQUIRE_EDIT', raising=False)
    monkeypatch.setenv('SANYAN_LOOP_TIME_BUDGET', '不是数字')
    rt = _LoopRt(script=[('done', ''), ('done', '答案')])
    r = run_legacy(rt, '问个问题', 6, dry_run=False)
    assert r['answer'] == '答案'
