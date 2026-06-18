"""多模型路由器 — 根据任务类型选择最优模型

功能：
  1. 根据任务类型路由到不同模型
  2. 支持模型降级（主模型失败时用备选）
  3. 成本优化（简单任务用便宜模型）

用法：
  router = ModelRouter()
  model = router.route('code_generation')
  result = router.call('code_generation', prompt)
"""

import os
from typing import Dict, List, Optional


# 默认模型配置
DEFAULT_MODELS = {
    'deepseek-v4-pro': {
        'name': 'DeepSeek V4 Pro',
        'provider': 'deepseek',
        'url': 'https://api.deepseek.com/v1/chat/completions',
        'cost_per_1k': 0.002,  # 每1000 token 成本
        'strengths': ['code_generation', 'code_review', 'reasoning'],
        'max_tokens': 4096,
    },
    'deepseek-coder': {
        'name': 'DeepSeek Coder',
        'provider': 'deepseek',
        'url': 'https://api.deepseek.com/v1/chat/completions',
        'cost_per_1k': 0.001,
        'strengths': ['code_generation', 'code_completion'],
        'max_tokens': 4096,
    },
    'claude-sonnet-4': {
        'name': 'Claude Sonnet 4',
        'provider': 'anthropic',
        'url': 'https://api.anthropic.com/v1/messages',
        'cost_per_1k': 0.015,
        'strengths': ['code_review', 'reasoning', 'analysis'],
        'max_tokens': 4096,
    },
    'gpt-4': {
        'name': 'GPT-4',
        'provider': 'openai',
        'url': 'https://api.openai.com/v1/chat/completions',
        'cost_per_1k': 0.03,
        'strengths': ['code_generation', 'reasoning', 'test_generation'],
        'max_tokens': 4096,
    },
    'local/qwen2.5-0.5b': {
        'name': 'Qwen2.5-0.5B (本地)',
        'provider': 'local',
        'url': '',
        'cost_per_1k': 0.0,  # 本地免费
        'strengths': ['simple', 'code_generation'],
        'max_tokens': 512,
    },
    'local/gpt2': {
        'name': 'GPT-2 (本地)',
        'provider': 'local',
        'url': '',
        'cost_per_1k': 0.0,
        'strengths': ['simple'],
        'max_tokens': 256,
    },
}

# 任务类型到最优模型的映射
TASK_MODEL_MAP = {
    'code_generation': ['deepseek-coder', 'deepseek-v4-pro', 'local/qwen2.5-0.5b'],
    'code_review': ['claude-sonnet-4', 'deepseek-v4-pro', 'local/qwen2.5-0.5b'],
    'test_generation': ['gpt-4', 'deepseek-v4-pro', 'local/qwen2.5-0.5b'],
    'reasoning': ['claude-sonnet-4', 'deepseek-v4-pro', 'local/qwen2.5-0.5b'],
    'analysis': ['claude-sonnet-4', 'deepseek-v4-pro', 'local/qwen2.5-0.5b'],
    'simple': ['local/qwen2.5-0.5b', 'deepseek-v4-pro'],  # 简单任务优先本地
    'default': ['deepseek-v4-pro'],
}


class ModelRouter:
    """多模型路由器"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get('SANYAN_API_KEY', '')
        self.models = DEFAULT_MODELS.copy()
        self.task_map = TASK_MODEL_MAP.copy()
        self._call_count: Dict[str, int] = {}
        self._total_cost: float = 0.0

    def route(self, task_type: str) -> str:
        """根据任务类型选择模型"""
        model_list = self.task_map.get(task_type, self.task_map['default'])
        return model_list[0]  # 返回最优模型

    def get_fallback(self, task_type: str) -> List[str]:
        """获取降级模型列表"""
        return self.task_map.get(task_type, self.task_map['default'])

    def call(self, task_type: str, prompt: str, system_prompt: str = '', **kwargs) -> str:
        """调用模型（支持降级）"""
        models = self.get_fallback(task_type)

        for model_id in models:
            try:
                result = self._call_model(model_id, prompt, system_prompt, **kwargs)
                self._call_count[model_id] = self._call_count.get(model_id, 0) + 1
                return result
            except Exception as e:
                print(f'  [模型] {model_id} 失败: {e}')
                continue

        return 'error|所有模型调用失败'

    def _call_model(self, model_id: str, prompt: str, system_prompt: str = '', **kwargs) -> str:
        """调用单个模型"""
        import json
        import urllib.request

        model_config = self.models.get(model_id)
        if not model_config:
            raise ValueError(f'未知模型: {model_id}')

        url = model_config['url']
        provider = model_config['provider']

        # 构建请求
        if provider == 'deepseek':
            body = json.dumps(
                {
                    'model': model_id,
                    'max_tokens': kwargs.get('max_tokens', model_config['max_tokens']),
                    'temperature': kwargs.get('temperature', 0.7),
                    'messages': [
                        {'role': 'system', 'content': system_prompt or 'You are a helpful assistant.'},
                        {'role': 'user', 'content': prompt},
                    ],
                }
            ).encode('utf-8')
            headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {self.api_key}'}
        elif provider == 'anthropic':
            body = json.dumps(
                {
                    'model': model_id,
                    'max_tokens': kwargs.get('max_tokens', model_config['max_tokens']),
                    'messages': [{'role': 'user', 'content': prompt}],
                }
            ).encode('utf-8')
            headers = {
                'Content-Type': 'application/json',
                'x-api-key': self.api_key,
                'anthropic-version': '2023-06-01',
            }
        elif provider == 'openai':
            body = json.dumps(
                {
                    'model': model_id,
                    'max_tokens': kwargs.get('max_tokens', model_config['max_tokens']),
                    'temperature': kwargs.get('temperature', 0.7),
                    'messages': [
                        {'role': 'system', 'content': system_prompt or 'You are a helpful assistant.'},
                        {'role': 'user', 'content': prompt},
                    ],
                }
            ).encode('utf-8')
            headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {self.api_key}'}
        else:
            raise ValueError(f'不支持的提供商: {provider}')

        # 发送请求
        req = urllib.request.Request(url, data=body, headers=headers, method='POST')
        resp = urllib.request.urlopen(req, timeout=60)
        data = json.loads(resp.read().decode('utf-8'))

        # 解析响应
        if provider == 'deepseek' or provider == 'openai':
            text = data['choices'][0]['message']['content']
            tokens = data.get('usage', {}).get('total_tokens', 0)
        elif provider == 'anthropic':
            text = data['content'][0]['text']
            tokens = data.get('usage', {}).get('input_tokens', 0) + data.get('usage', {}).get('output_tokens', 0)
        else:
            text = str(data)
            tokens = 0

        # 计算成本
        if tokens > 0:
            cost = tokens * model_config['cost_per_1k'] / 1000
            self._total_cost += cost

        return text.strip()

    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            'call_count': self._call_count,
            'total_cost': self._total_cost,
            'models_used': list(self._call_count.keys()),
        }

    def add_model(self, model_id: str, config: Dict):
        """添加自定义模型"""
        self.models[model_id] = config

    def set_task_mapping(self, task_type: str, model_list: List[str]):
        """设置任务到模型的映射"""
        self.task_map[task_type] = model_list


def classify_task_type(task: str) -> str:
    """根据任务描述分类任务类型"""
    if any(w in task for w in ['写代码', '实现', '创建', '新增', 'write', 'implement', 'create']):
        return 'code_generation'
    elif any(w in task for w in ['审查', 'review', '检查', 'check', '分析', 'analyze']):
        return 'code_review'
    elif any(w in task for w in ['测试', 'test', '验证', 'verify']):
        return 'test_generation'
    elif any(w in task for w in ['推理', 'reason', '解释', 'explain', '为什么', 'why']):
        return 'reasoning'
    elif any(w in task for w in ['分析', 'analyze', '调查', 'investigate']):
        return 'analysis'
    else:
        return 'simple'
