"""Agent 系统协议接口（seam 抽象）"""

from typing import Protocol


class LLMProvider(Protocol):
    """LLM 补全协议：统一 seam，支持多 provider / 成本路由"""

    def complete(self, prompt: str, system: str | None = None) -> str:
        """执行 LLM 补全，返回响应文本"""
        ...
