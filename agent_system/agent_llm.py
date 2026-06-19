"""LLM Provider — OpenAI Compatible Adapter

支持模型厂商：
- OpenAI (gpt-5, gpt-5-mini, gpt-5-nano)
- DeepSeek (deepseek-v4-pro, deepseek-v4-flash)
- Anthropic Claude (claude-sonnet-4, claude-opus-4) — 需单独适配
- Google Gemini (gemini-2.5-pro, gemini-2.5-flash)
- 阿里 Qwen (qwen-max, qwen-plus, qwen-turbo)
- 智谱 GLM (glm-4.5, glm-4-air)
- Moonshot/Kimi (kimi-k2, kimi-latest)
- SiliconFlow (多模型聚合)
- OpenRouter (几百个模型)

用法：
    provider = LLMProvider.create('deepseek', api_key='sk-xxx')
    response = provider.chat([{'role': 'user', 'content': '你好'}])
"""

import json
import os
import time
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional


class LLMProvider:
    """LLM 提供者基类"""

    def __init__(self, api_key: str, model: str, base_url: str = ''):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.timeout = 60

    def chat(
        self, messages: List[Dict[str, str]], temperature: float = 0.7, max_tokens: int = 4096, **kwargs
    ) -> Dict[str, Any]:
        """发送聊天请求，返回完整响应"""
        raise NotImplementedError

    def chat_simple(self, prompt: str, system_msg: str = '') -> str:
        """简单聊天，返回文本"""
        messages = []
        if system_msg:
            messages.append({'role': 'system', 'content': system_msg})
        messages.append({'role': 'user', 'content': prompt})

        response = self.chat(messages)
        return response.get('content', '')

    def _make_request(self, url: str, body: Dict, headers: Dict) -> Dict:
        """发送 HTTP 请求"""
        data = json.dumps(body, ensure_ascii=False).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers=headers, method='POST')

        for attempt in range(3):
            try:
                resp = urllib.request.urlopen(req, timeout=self.timeout)
                return json.loads(resp.read().decode('utf-8'))
            except (urllib.error.HTTPError, urllib.error.URLError, OSError):
                if attempt < 2:
                    time.sleep(1.0 * (attempt + 1))
                    continue
                raise

    @classmethod
    def create(
        cls, provider: str, api_key: str, model: Optional[str] = None, base_url: Optional[str] = None, **kwargs
    ) -> 'LLMProvider':
        """工厂方法：根据 provider 名称创建实例"""
        providers = {
            'openai': OpenAIProvider,
            'deepseek': DeepSeekProvider,
            'anthropic': AnthropicProvider,
            'gemini': GeminiProvider,
            'qwen': QwenProvider,
            'glm': GLMProvider,
            'moonshot': MoonshotProvider,
            'siliconflow': SiliconFlowProvider,
            'openrouter': OpenRouterProvider,
        }

        provider_class = providers.get(provider.lower(), OpenAIProvider)
        return provider_class(api_key=api_key, model=model, base_url=base_url, **kwargs)


class OpenAIProvider(LLMProvider):
    """OpenAI 提供者"""

    DEFAULT_BASE_URL = 'https://api.openai.com/v1'
    DEFAULT_MODEL = 'gpt-4o'

    def __init__(self, api_key: str, model: Optional[str] = None, base_url: Optional[str] = None, **kwargs):
        super().__init__(
            api_key=api_key,
            model=model or self.DEFAULT_MODEL,
            base_url=base_url or self.DEFAULT_BASE_URL,
        )

    def chat(
        self, messages: List[Dict[str, str]], temperature: float = 0.7, max_tokens: int = 4096, **kwargs
    ) -> Dict[str, Any]:
        url = f'{self.base_url}/chat/completions'
        body = {
            'model': self.model,
            'messages': messages,
            'temperature': temperature,
            'max_tokens': max_tokens,
        }
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.api_key}',
        }

        resp = self._make_request(url, body, headers)

        choice = resp.get('choices', [{}])[0]
        message = choice.get('message', {})
        usage = resp.get('usage', {})

        return {
            'content': message.get('content', ''),
            'role': message.get('role', 'assistant'),
            'finish_reason': choice.get('finish_reason', ''),
            'usage': {
                'prompt_tokens': usage.get('prompt_tokens', 0),
                'completion_tokens': usage.get('completion_tokens', 0),
                'total_tokens': usage.get('total_tokens', 0),
            },
        }


class DeepSeekProvider(LLMProvider):
    """DeepSeek 提供者"""

    DEFAULT_BASE_URL = 'https://api.deepseek.com/v1'
    DEFAULT_MODEL = 'deepseek-v4-pro'

    def __init__(self, api_key: str, model: Optional[str] = None, base_url: Optional[str] = None, **kwargs):
        super().__init__(
            api_key=api_key,
            model=model or self.DEFAULT_MODEL,
            base_url=base_url or self.DEFAULT_BASE_URL,
        )

    def chat(
        self, messages: List[Dict[str, str]], temperature: float = 0.7, max_tokens: int = 4096, **kwargs
    ) -> Dict[str, Any]:
        url = f'{self.base_url}/chat/completions'
        body = {
            'model': self.model,
            'messages': messages,
            'temperature': temperature,
            'max_tokens': max_tokens,
        }

        # DeepSeek thinking 模式
        if kwargs.get('thinking', False):
            body['thinking'] = {'type': 'enabled', 'budget_tokens': 2048}

        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.api_key}',
        }

        resp = self._make_request(url, body, headers)

        choice = resp.get('choices', [{}])[0]
        message = choice.get('message', {})
        usage = resp.get('usage', {})

        return {
            'content': message.get('content', '') or message.get('reasoning_content', ''),
            'role': message.get('role', 'assistant'),
            'finish_reason': choice.get('finish_reason', ''),
            'usage': {
                'prompt_tokens': usage.get('prompt_tokens', 0),
                'completion_tokens': usage.get('completion_tokens', 0),
                'total_tokens': usage.get('total_tokens', 0),
            },
        }


class AnthropicProvider(LLMProvider):
    """Anthropic Claude 提供者（非 OpenAI 格式，单独适配）"""

    DEFAULT_BASE_URL = 'https://api.anthropic.com'
    DEFAULT_MODEL = 'claude-sonnet-4-20250514'

    def __init__(self, api_key: str, model: Optional[str] = None, base_url: Optional[str] = None, **kwargs):
        super().__init__(
            api_key=api_key,
            model=model or self.DEFAULT_MODEL,
            base_url=base_url or self.DEFAULT_BASE_URL,
        )

    def chat(
        self, messages: List[Dict[str, str]], temperature: float = 0.7, max_tokens: int = 4096, **kwargs
    ) -> Dict[str, Any]:
        url = f'{self.base_url}/v1/messages'

        # Anthropic 格式：system 单独传
        system_msg = ''
        user_messages = []
        for msg in messages:
            if msg['role'] == 'system':
                system_msg = msg['content']
            else:
                user_messages.append(msg)

        body = {
            'model': self.model,
            'max_tokens': max_tokens,
            'messages': user_messages,
        }
        if system_msg:
            body['system'] = system_msg

        headers = {
            'Content-Type': 'application/json',
            'x-api-key': self.api_key,
            'anthropic-version': '2023-06-01',
        }

        resp = self._make_request(url, body, headers)

        content = resp.get('content', [{}])
        text = content[0].get('text', '') if content else ''
        usage = resp.get('usage', {})

        return {
            'content': text,
            'role': 'assistant',
            'finish_reason': resp.get('stop_reason', ''),
            'usage': {
                'prompt_tokens': usage.get('input_tokens', 0),
                'completion_tokens': usage.get('output_tokens', 0),
                'total_tokens': usage.get('input_tokens', 0) + usage.get('output_tokens', 0),
            },
        }


class GeminiProvider(LLMProvider):
    """Google Gemini 提供者"""

    DEFAULT_BASE_URL = 'https://generativelanguage.googleapis.com/v1beta'
    DEFAULT_MODEL = 'gemini-2.5-flash'

    def __init__(self, api_key: str, model: Optional[str] = None, base_url: Optional[str] = None, **kwargs):
        super().__init__(
            api_key=api_key,
            model=model or self.DEFAULT_MODEL,
            base_url=base_url or self.DEFAULT_BASE_URL,
        )

    def chat(
        self, messages: List[Dict[str, str]], temperature: float = 0.7, max_tokens: int = 4096, **kwargs
    ) -> Dict[str, Any]:
        url = f'{self.base_url}/models/{self.model}:generateContent?key={self.api_key}'

        # Gemini 格式
        contents = []
        for msg in messages:
            role = 'user' if msg['role'] == 'user' else 'model'
            contents.append({'role': role, 'parts': [{'text': msg['content']}]})

        body = {
            'contents': contents,
            'generationConfig': {
                'temperature': temperature,
                'maxOutputTokens': max_tokens,
            },
        }

        headers = {'Content-Type': 'application/json'}

        resp = self._make_request(url, body, headers)

        candidates = resp.get('candidates', [])
        text = candidates[0]['content']['parts'][0]['text'] if candidates else ''
        usage = resp.get('usageMetadata', {})

        return {
            'content': text,
            'role': 'assistant',
            'finish_reason': candidates[0].get('finishReason', '') if candidates else '',
            'usage': {
                'prompt_tokens': usage.get('promptTokenCount', 0),
                'completion_tokens': usage.get('candidatesTokenCount', 0),
                'total_tokens': usage.get('totalTokenCount', 0),
            },
        }


class QwenProvider(LLMProvider):
    """阿里 Qwen 提供者（OpenAI 兼容）"""

    DEFAULT_BASE_URL = 'https://dashscope.aliyuncs.com/compatible-mode/v1'
    DEFAULT_MODEL = 'qwen-max'

    def __init__(self, api_key: str, model: Optional[str] = None, base_url: Optional[str] = None, **kwargs):
        super().__init__(
            api_key=api_key,
            model=model or self.DEFAULT_MODEL,
            base_url=base_url or self.DEFAULT_BASE_URL,
        )

    def chat(
        self, messages: List[Dict[str, str]], temperature: float = 0.7, max_tokens: int = 4096, **kwargs
    ) -> Dict[str, Any]:
        # Qwen 使用 OpenAI 兼容格式
        return OpenAIProvider.chat(self, messages, temperature, max_tokens, **kwargs)


class GLMProvider(LLMProvider):
    """智谱 GLM 提供者（OpenAI 兼容）"""

    DEFAULT_BASE_URL = 'https://open.bigmodel.cn/api/paas/v4'
    DEFAULT_MODEL = 'glm-4'

    def __init__(self, api_key: str, model: Optional[str] = None, base_url: Optional[str] = None, **kwargs):
        super().__init__(
            api_key=api_key,
            model=model or self.DEFAULT_MODEL,
            base_url=base_url or self.DEFAULT_BASE_URL,
        )

    def chat(
        self, messages: List[Dict[str, str]], temperature: float = 0.7, max_tokens: int = 4096, **kwargs
    ) -> Dict[str, Any]:
        # GLM 使用 OpenAI 兼容格式
        return OpenAIProvider.chat(self, messages, temperature, max_tokens, **kwargs)


class MoonshotProvider(LLMProvider):
    """Moonshot/Kimi 提供者（OpenAI 兼容）"""

    DEFAULT_BASE_URL = 'https://api.moonshot.cn/v1'
    DEFAULT_MODEL = 'moonshot-v1-8k'

    def __init__(self, api_key: str, model: Optional[str] = None, base_url: Optional[str] = None, **kwargs):
        super().__init__(
            api_key=api_key,
            model=model or self.DEFAULT_MODEL,
            base_url=base_url or self.DEFAULT_BASE_URL,
        )

    def chat(
        self, messages: List[Dict[str, str]], temperature: float = 0.7, max_tokens: int = 4096, **kwargs
    ) -> Dict[str, Any]:
        # Moonshot 使用 OpenAI 兼容格式
        return OpenAIProvider.chat(self, messages, temperature, max_tokens, **kwargs)


class SiliconFlowProvider(LLMProvider):
    """SiliconFlow 提供者（多模型聚合，OpenAI 兼容）"""

    DEFAULT_BASE_URL = 'https://api.siliconflow.cn/v1'
    DEFAULT_MODEL = 'deepseek-ai/DeepSeek-V3'

    def __init__(self, api_key: str, model: Optional[str] = None, base_url: Optional[str] = None, **kwargs):
        super().__init__(
            api_key=api_key,
            model=model or self.DEFAULT_MODEL,
            base_url=base_url or self.DEFAULT_BASE_URL,
        )

    def chat(
        self, messages: List[Dict[str, str]], temperature: float = 0.7, max_tokens: int = 4096, **kwargs
    ) -> Dict[str, Any]:
        # SiliconFlow 使用 OpenAI 兼容格式
        return OpenAIProvider.chat(self, messages, temperature, max_tokens, **kwargs)


class OpenRouterProvider(LLMProvider):
    """OpenRouter 提供者（几百个模型聚合）"""

    DEFAULT_BASE_URL = 'https://openrouter.ai/api/v1'
    DEFAULT_MODEL = 'anthropic/claude-sonnet-4'

    def __init__(self, api_key: str, model: Optional[str] = None, base_url: Optional[str] = None, **kwargs):
        super().__init__(
            api_key=api_key,
            model=model or self.DEFAULT_MODEL,
            base_url=base_url or self.DEFAULT_BASE_URL,
        )

    def chat(
        self, messages: List[Dict[str, str]], temperature: float = 0.7, max_tokens: int = 4096, **kwargs
    ) -> Dict[str, Any]:
        # OpenRouter 使用 OpenAI 兼容格式
        return OpenAIProvider.chat(self, messages, temperature, max_tokens, **kwargs)


# ── 本地模型 ──


class LocalProvider(LLMProvider):
    """本地模型提供者（HuggingFace transformers）

    支持模型：
    - Qwen/Qwen2.5-0.5B (954 MB)
    - openai-community/gpt2 (526 MB)
    - openai-community/gpt2-medium (1.5 GB)
    - openai-community/gpt2-large (3.1 GB)

    用法：
        provider = LocalProvider.create('qwen2.5-0.5b')
        response = provider.chat([{'role': 'user', 'content': '你好'}])
    """

    # 模型别名映射
    MODEL_ALIASES = {
        'qwen2.5-0.5b': 'Qwen/Qwen2.5-0.5B',
        'qwen': 'Qwen/Qwen2.5-0.5B',
        'gpt2': 'openai-community/gpt2',
        'gpt2-medium': 'openai-community/gpt2-medium',
        'gpt2-large': 'openai-community/gpt2-large',
    }

    def __init__(self, model_name: str = 'Qwen/Qwen2.5-0.5B', **kwargs):
        super().__init__(api_key='local', model=model_name)
        self._model = None
        self._tokenizer = None

    def _load_model(self):
        """懒加载模型（从本地缓存）"""
        if self._model is not None:
            return

        try:
            import os as _os
            _os.environ['HF_HUB_OFFLINE'] = '1'
            _os.environ['TRANSFORMERS_OFFLINE'] = '1'

            from transformers import AutoModelForCausalLM, AutoTokenizer
            import torch

            model_id = self.MODEL_ALIASES.get(self.model, self.model)
            print(f'[本地模型] 加载 {model_id}...')
            self._tokenizer = AutoTokenizer.from_pretrained(
                model_id,
                local_files_only=True,
                trust_remote_code=True,
            )
            self._model = AutoModelForCausalLM.from_pretrained(
                model_id,
                torch_dtype=torch.float32,
                local_files_only=True,
                trust_remote_code=True,
            )
            print('[本地模型] 加载完成')
        except Exception as e:
            raise RuntimeError(f'加载本地模型失败: {e}')

    def _get_local_path(self) -> str:
        """获取本地缓存路径"""
        import os

        # HuggingFace 缓存目录
        cache_dir = os.path.expanduser('~/.cache/huggingface/hub')

        # 模型目录名
        model_name = self.model.replace('/', '--')
        model_dir = os.path.join(cache_dir, f'models--{model_name}')

        if os.path.exists(model_dir):
            # 找 snapshots 目录下的最新版本
            snapshots_dir = os.path.join(model_dir, 'snapshots')
            if os.path.exists(snapshots_dir):
                snapshots = os.listdir(snapshots_dir)
                if snapshots:
                    return os.path.join(snapshots_dir, snapshots[0])

        # 如果找不到缓存，返回原始名称
        return self.model

    def chat(
        self, messages: List[Dict[str, str]], temperature: float = 0.7, max_tokens: int = 512, **kwargs
    ) -> Dict[str, Any]:
        """发送聊天请求"""
        self._load_model()

        import torch

        # 构建 prompt
        prompt = self._messages_to_prompt(messages)

        # 编码
        inputs = self._tokenizer(prompt, return_tensors='pt')

        # 生成
        with torch.no_grad():
            outputs = self._model.generate(
                **inputs,
                max_new_tokens=max_tokens,
                temperature=temperature if temperature > 0 else None,
                do_sample=temperature > 0,
                top_p=0.9 if temperature > 0 else None,
                pad_token_id=self._tokenizer.eos_token_id,
            )

        # 解码
        generated = outputs[0][inputs['input_ids'].shape[1] :]
        text = self._tokenizer.decode(generated, skip_special_tokens=True)

        return {
            'content': text.strip(),
            'model': self.model,
            'usage': {
                'input_tokens': inputs['input_ids'].shape[1],
                'output_tokens': len(generated),
            },
        }

    def _messages_to_prompt(self, messages: List[Dict[str, str]]) -> str:
        """将消息列表转为 prompt"""
        parts = []
        for msg in messages:
            role = msg.get('role', 'user')
            content = msg.get('content', '')
            if role == 'system':
                parts.append(f'System: {content}')
            elif role == 'user':
                parts.append(f'User: {content}')
            elif role == 'assistant':
                parts.append(f'Assistant: {content}')
        parts.append('Assistant:')
        return '\n'.join(parts)

    @classmethod
    def create(cls, model: str, **kwargs) -> 'LocalProvider':
        """创建本地模型实例"""
        # 解析别名
        model_name = cls.MODEL_ALIASES.get(model.lower(), model)
        return cls(model_name=model_name, **kwargs)


# ── 配置管理 ──


class LLMConfig:
    """LLM 配置管理"""

    # 预定义配置
    PRESETS = {
        'deepseek': {
            'provider': 'deepseek',
            'model': 'deepseek-v4-pro',
            'base_url': 'https://api.deepseek.com/v1',
        },
        'deepseek-reasoner': {
            'provider': 'deepseek',
            'model': 'deepseek-v4-pro',
            'base_url': 'https://api.deepseek.com/v1',
            'thinking': True,
        },
        'openai': {
            'provider': 'openai',
            'model': 'gpt-4o',
            'base_url': 'https://api.openai.com/v1',
        },
        'claude': {
            'provider': 'anthropic',
            'model': 'claude-sonnet-4-20250514',
            'base_url': 'https://api.anthropic.com',
        },
        'gemini': {
            'provider': 'gemini',
            'model': 'gemini-2.5-flash',
            'base_url': 'https://generativelanguage.googleapis.com/v1beta',
        },
        'qwen': {
            'provider': 'qwen',
            'model': 'qwen-max',
            'base_url': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
        },
        'glm': {
            'provider': 'glm',
            'model': 'glm-4',
            'base_url': 'https://open.bigmodel.cn/api/paas/v4',
        },
        'moonshot': {
            'provider': 'moonshot',
            'model': 'moonshot-v1-8k',
            'base_url': 'https://api.moonshot.cn/v1',
        },
        'siliconflow': {
            'provider': 'siliconflow',
            'model': 'deepseek-ai/DeepSeek-V3',
            'base_url': 'https://api.siliconflow.cn/v1',
        },
        'openrouter': {
            'provider': 'openrouter',
            'model': 'anthropic/claude-sonnet-4',
            'base_url': 'https://openrouter.ai/api/v1',
        },
    }

    def __init__(self, config_path: Optional[str] = None):
        self.config = self._load_config(config_path)

    def _load_config(self, config_path: Optional[str] = None) -> Dict:
        """加载配置"""
        if config_path and os.path.exists(config_path):
            with open(config_path, encoding='utf-8') as f:
                return json.load(f)

        # 尝试从环境变量加载
        provider = os.environ.get('LLM_PROVIDER', 'deepseek')
        api_key = os.environ.get('SANYAN_API_KEY', os.environ.get('LLM_KEY', ''))
        model = os.environ.get('LLM_MODEL', '')

        return {
            'provider': provider,
            'api_key': api_key,
            'model': model,
        }

    def create_provider(self) -> LLMProvider:
        """根据配置创建 LLM Provider"""
        provider_name = self.config.get('provider', 'deepseek')
        api_key = self.config.get('api_key', '')

        if not api_key:
            api_key = os.environ.get('SANYAN_API_KEY', os.environ.get('LLM_KEY', ''))

        if not api_key:
            raise ValueError('No API key provided. Set SANYAN_API_KEY environment variable.')

        # 使用预设配置
        preset = self.PRESETS.get(provider_name, {})
        model = self.config.get('model') or preset.get('model')
        base_url = self.config.get('base_url') or preset.get('base_url')

        return LLMProvider.create(
            provider=provider_name,
            api_key=api_key,
            model=model,
            base_url=base_url,
        )

    def summary(self) -> str:
        """配置摘要"""
        provider = self.config.get('provider', 'unknown')
        model = self.config.get('model', 'default')
        return f'LLM: {provider}/{model}'
