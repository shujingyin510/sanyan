"""Agent 子系统懒加载注册表（阶段1重构）"""

from typing import Any


class LazyRegistry:
    """懒加载：register 后首次访问时才创建实例，之后返回缓存"""

    def __init__(self):
        self._factories: dict[str, Any] = {}
        self._instances: dict[str, Any] = {}

    def register(self, name: str, factory):
        self._factories[name] = factory

    def has(self, name: str) -> bool:
        return name in self._factories

    def get(self, name: str):
        if name in self._instances:
            return self._instances[name]
        factory = self._factories.get(name)
        if factory is None:
            return None
        inst = factory()
        self._instances[name] = inst
        return inst

    def __getattr__(self, name: str):
        if name.startswith('_') or name in ('get', 'items', 'keys', 'values'):
            raise AttributeError(name)
        if name in self._instances:
            return self._instances[name]
        factory = self._factories.get(name)
        if factory is None:
            raise AttributeError(f"未注册的懒加载能力: '{name}'")
        inst = factory()
        self._instances[name] = inst
        return inst
