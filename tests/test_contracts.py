"""LLMProvider 协议一致性 —— 纯 Python，不触网、不调 LLM。

P2 首跑事故的回归守护：运行时统一走 `llm_provider.complete()`（Phase 4 单漏斗），
但 LLMHandler 一度没有 complete 方法——每次 LLM 调用都 AttributeError，agent
「正常跑完」却零产出。单测全用假件、真跑无人做，接口漂移潜伏了整个重构期。
这里把「默认 provider 满足协议」与「seam 路由语义」钉死。

运行： python -X utf8 -m pytest tests/test_contracts.py -q
"""

from agent_system.contracts import LLMProvider


def test_llmhandler_conforms_to_provider():
    from agent_system.agent_llm_handler import LLMHandler

    assert isinstance(LLMHandler(), LLMProvider)


def test_modelrouter_conforms_to_provider():
    from agent_system.model_router import ModelRouter

    assert isinstance(ModelRouter(), LLMProvider)


def test_runtime_routes_llm_through_provider_seam():
    """_llm_call 走 self.llm_provider.complete()，provider 可整体替换、调用方不变。"""
    from agent_system.agent_runtime import AgentRuntime
    from core.evaluator import SanyanEvaluator

    rt = AgentRuntime(SanyanEvaluator(), None)
    # 默认 provider = LLMHandler，且满足契约
    assert isinstance(rt.llm_provider, LLMProvider)

    calls = {}

    class FakeProvider:
        _last_tokens = 7

        def complete(self, prompt, *, system=None):
            calls['prompt'] = prompt
            calls['system'] = system
            return 'FAKE-OK'

    rt.llm_provider = FakeProvider()
    rt._system_prompt = 'SYS-DEFAULT'

    # override=None → 用当前 _system_prompt
    assert rt._llm_call('hello') == 'FAKE-OK'
    assert calls == {'prompt': 'hello', 'system': 'SYS-DEFAULT'}
    # token 追踪取自 provider._last_tokens
    assert rt.memory.get('total_tokens') == 7

    # 显式 override 优先
    rt._llm_call('hi2', override_system_prompt='OVERRIDE')
    assert calls['system'] == 'OVERRIDE'
