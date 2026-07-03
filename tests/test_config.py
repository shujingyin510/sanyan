"""单一 typed 配置（阶段 5）：密钥只从环境读取、占位符视为空、字段有类型。"""

from agent_system.config import AgentConfig, api_key_from_env


def _isolate(monkeypatch):
    for var in ('SANYAN_API_KEY', 'LLM_KEY', 'SANYAN_PROVIDER', 'SANYAN_MODEL', 'SANYAN_MODEL_URL', 'SANYAN_TIMEOUT'):
        monkeypatch.delenv(var, raising=False)


def test_api_key_from_env(monkeypatch):
    _isolate(monkeypatch)
    monkeypatch.setenv('SANYAN_API_KEY', 'sk-real-123')
    assert api_key_from_env() == 'sk-real-123'
    assert AgentConfig.from_env().has_key


def test_placeholder_treated_as_empty(monkeypatch):
    _isolate(monkeypatch)
    monkeypatch.setenv('SANYAN_API_KEY', 'sk-你的key')
    assert api_key_from_env() == ''
    assert not AgentConfig.from_env().has_key


def test_llm_key_fallback(monkeypatch):
    _isolate(monkeypatch)
    monkeypatch.setenv('LLM_KEY', 'tp-xyz')
    assert api_key_from_env() == 'tp-xyz'


def test_typed_fields_and_defaults(monkeypatch):
    _isolate(monkeypatch)
    c = AgentConfig.from_env()
    assert c.api_key == '' and c.provider == 'deepseek' and c.timeout == 60
    monkeypatch.setenv('SANYAN_TIMEOUT', '120')
    monkeypatch.setenv('SANYAN_PROVIDER', 'openai')
    c2 = AgentConfig.from_env()
    assert c2.timeout == 120 and isinstance(c2.timeout, int)
    assert c2.provider == 'openai'


def test_bad_timeout_falls_back(monkeypatch):
    _isolate(monkeypatch)
    monkeypatch.setenv('SANYAN_TIMEOUT', 'not-a-number')
    assert AgentConfig.from_env().timeout == 60


def test_llmhandler_get_config_env_fallback(monkeypatch):
    # ev 无该变量 → 回退单一 typed 配置（环境）
    _isolate(monkeypatch)
    monkeypatch.setenv('SANYAN_MODEL', 'my-model')
    from agent_system.agent_llm_handler import LLMHandler

    h = LLMHandler()  # ev=None
    assert h._get_config('模型名', 'default-model') == 'my-model'
    # 未映射键 → 返回 default
    assert h._get_config('某未知键', 'D') == 'D'


def test_llmhandler_get_config_san_overrides_env(monkeypatch):
    # .san 求值器变量优先于环境（保留动态改配置语义）
    _isolate(monkeypatch)
    monkeypatch.setenv('SANYAN_MODEL', 'env-model')
    from agent_system.agent_llm_handler import LLMHandler

    class FakeEv:
        def get_var(self, k):
            return 'san-model' if k == '模型名' else ''

    h = LLMHandler(ev=FakeEv())
    assert h._get_config('模型名', 'd') == 'san-model'


def test_llmhandler_get_config_legacy_llm_env(monkeypatch):
    # 兼容旧环境变量名 LLM_MODEL
    _isolate(monkeypatch)
    monkeypatch.setenv('LLM_MODEL', 'legacy-model')
    from agent_system.agent_llm_handler import LLMHandler

    assert LLMHandler()._get_config('模型名', 'd') == 'legacy-model'


def test_llmhandler_get_config_san_placeholder_falls_through(monkeypatch):
    # .san 侧占位符（如 sk-你的key）不是配置：跳过 evaluator 值、落到环境真值。
    # P2 首跑实测：占位符密钥混进 Authorization 头 → latin-1 编码当场炸（HTTP 头不容汉字）
    _isolate(monkeypatch)
    monkeypatch.setenv('SANYAN_API_KEY', 'sk-real-456')
    from agent_system.agent_llm_handler import LLMHandler

    class FakeEv:
        def get_var(self, k):
            return 'sk-你的key' if k == 'API密钥' else ''

    h = LLMHandler(ev=FakeEv())
    assert h._get_config('API密钥', '') == 'sk-real-456'
