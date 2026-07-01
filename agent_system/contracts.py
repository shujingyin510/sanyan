"""Agent 系统协议接口（seam 抽象）"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol


class ToolStatus(Enum):
    """工具执行状态"""

    OK = 'ok'
    ERROR = 'error'
    TIMEOUT = 'timeout'
    NOT_FOUND = 'not_found'


@dataclass
class ToolResult:
    """工具返回结果（阶段3重构：消灭 string sniff）"""

    status: ToolStatus = ToolStatus.OK
    ok: bool = True
    failed: bool = False
    output: str = ''
    error: str = ''
    data: Any = None
    meta: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """从 status 自动推导 ok/failed"""
        if self.status == ToolStatus.ERROR:
            self.ok = False
            self.failed = True
            if not self.error and isinstance(self.data, str):
                self.error = self.data
        elif self.status == ToolStatus.OK:
            self.ok = True
            self.failed = False


class LLMProvider(Protocol):
    """LLM 补全协议：统一 seam，支持多 provider / 成本路由"""

    def complete(self, prompt: str, system: str | None = None) -> str:
        """执行 LLM 补全，返回响应文本"""
        ...
