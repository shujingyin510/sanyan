"""接口/协议系统：定义和检查对象是否满足特定接口。

功能：
- 定义接口（协议）：指定必须实现的方法和属性
- 运行时检查：验证对象是否满足接口
- 类型标注：支持接口类型标注

用法：
    from core.protocols import Protocol, implements

    # 定义协议
    可序列化 = Protocol('可序列化', methods=['序列化', '反序列化'])

    # 检查对象是否实现协议
    class MyData:
        def 序列化(self): return '{}'
        def 反序列化(self, s): pass

    implements(MyData(), 可序列化)  # True
"""

from __future__ import annotations
from typing import Any, Optional


class Protocol:
    """接口/协议定义。

    指定必须实现的方法和属性。
    """

    def __init__(self, name: str, methods: list[str] | None = None, properties: list[str] | None = None) -> None:
        self.name = name
        self.methods = methods or []
        self.properties = properties or []

    def __repr__(self) -> str:
        parts = []
        if self.methods:
            parts.append(f'方法: {", ".join(self.methods)}')
        if self.properties:
            parts.append(f'属性: {", ".join(self.properties)}')
        return f'协议 {self.name}({"; ".join(parts)})'


def implements(obj: Any, protocol: Protocol) -> bool:
    """检查对象是否实现指定协议。

    返回 True 如果对象满足协议的所有要求。
    """
    # 检查方法
    for method in protocol.methods:
        if not hasattr(obj, method):
            return False
        if not callable(getattr(obj, method)):
            return False

    # 检查属性
    for prop in protocol.properties:
        if not hasattr(obj, prop):
            return False

    return True


def implements_error(obj: Any, protocol: Protocol) -> str | None:
    """检查对象是否实现指定协议，返回错误消息或 None。"""
    missing_methods = []
    missing_properties = []

    for method in protocol.methods:
        if not hasattr(obj, method):
            missing_methods.append(method)
        elif not callable(getattr(obj, method)):
            missing_methods.append(f'{method} (不是方法)')

    for prop in protocol.properties:
        if not hasattr(obj, prop):
            missing_properties.append(prop)

    if missing_methods or missing_properties:
        parts = []
        if missing_methods:
            parts.append(f'缺少方法: {", ".join(missing_methods)}')
        if missing_properties:
            parts.append(f'缺少属性: {", ".join(missing_properties)}')
        return f'对象不满足协议 {protocol.name}: {"; ".join(parts)}'

    return None


# ── 预定义协议 ──
预定义协议 = {
    '可序列化': Protocol('可序列化', methods=['序列化']),
    '可迭代': Protocol('可迭代', methods=['__iter__']),
    '可调用': Protocol('可调用', methods=['__call__']),
    '可比较': Protocol('可比较', methods=['__eq__', '__lt__']),
    '可哈希': Protocol('可哈希', methods=['__hash__']),
}


def get_protocol(name: str) -> Optional[Protocol]:
    """获取预定义协议。"""
    return 预定义协议.get(name)


def register_protocol(name: str, protocol: Protocol) -> None:
    """注册新的预定义协议。"""
    预定义协议[name] = protocol


def check_type_protocol(value: Any, type_name: str) -> str | None:
    """检查值是否满足类型标注的协议。

    如果类型标注是协议名，检查值是否实现该协议。
    返回 None 表示通过，返回错误消息表示不匹配。
    """
    protocol = get_protocol(type_name)
    if protocol is None:
        return None  # 不是协议类型，跳过

    return implements_error(value, protocol)
