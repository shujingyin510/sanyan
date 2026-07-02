"""单一 typed 配置入口（阶段 5：配置/密钥集中）。

原则：
  * 密钥只从**环境变量 / 密钥管理**读取，一次加载成一个 typed 对象。
  * 禁止把密钥写进 `.san` 源码，更禁止用 `str.replace` 把密钥注入源码文本
    （后者会让密钥进入内存源码串、日志、缓存，是泄露面）。
  * 占位符（含 "你的"，如 `sk-你的key` / `tp-你的key`）一律视为「未设置」。

环境变量：
  SANYAN_API_KEY（优先）/ LLM_KEY（兼容）、SANYAN_PROVIDER、SANYAN_MODEL、
  SANYAN_MODEL_URL、SANYAN_TIMEOUT。
"""

from __future__ import annotations

import os
from dataclasses import dataclass

_PLACEHOLDER = '你的'  # 占位符标记


def _clean(value: str) -> str:
    value = (value or '').strip()
    return '' if (not value or _PLACEHOLDER in value) else value


def _as_int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class AgentConfig:
    """不可变配置快照。用 from_env() 一次性加载。"""

    api_key: str = ''
    provider: str = 'deepseek'
    model: str = 'deepseek-v4-pro'
    model_url: str = ''
    timeout: int = 60

    @classmethod
    def from_env(cls) -> 'AgentConfig':
        key = _clean(os.environ.get('SANYAN_API_KEY', '')) or _clean(os.environ.get('LLM_KEY', ''))
        # 模型/提供商/URL 兼容两套环境变量名：SANYAN_* 优先，回退旧的 LLM_*
        return cls(
            api_key=key,
            provider=(os.environ.get('SANYAN_PROVIDER') or os.environ.get('LLM_PROVIDER') or 'deepseek').strip(),
            model=(os.environ.get('SANYAN_MODEL') or os.environ.get('LLM_MODEL') or 'deepseek-v4-pro').strip(),
            model_url=(os.environ.get('SANYAN_MODEL_URL') or os.environ.get('LLM_URL') or '').strip(),
            timeout=_as_int(os.environ.get('SANYAN_TIMEOUT'), 60),
        )

    @property
    def has_key(self) -> bool:
        return bool(self.api_key)


def api_key_from_env() -> str:
    """便捷入口：只从环境读取 API 密钥（占位符视为空字符串）。"""
    return AgentConfig.from_env().api_key
