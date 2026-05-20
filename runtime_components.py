"""运行时组件：作用域管理、IoT 设备管理、调试管理、性能分析"""

from __future__ import annotations
from typing import Optional, Dict, List, Any
from ternary_core import TritValue
from values import SanyanNameError


class ScopeManager:
    """作用域栈管理：变量定义、查找、生命周期。"""

    def __init__(self, scopes_list: Optional[List[Dict[str, Any]]] = None):
        self._scopes: List[Dict[str, Any]] = scopes_list if scopes_list is not None else [{}]

    @property
    def scope_vars(self) -> Dict[str, Any]:
        return self._scopes[-1]

    @scope_vars.setter
    def scope_vars(self, value: Dict[str, Any]) -> None:
        self._scopes[-1] = value

    def get_var(self, name: str) -> Any:
        for scope in reversed(self._scopes):
            if name in scope:
                return scope[name]
        raise SanyanNameError(f'未定义的符号: {name}')

    def has_var(self, name: str) -> bool:
        for scope in reversed(self._scopes):
            if name in scope:
                return True
        return False

    def set_var(self, name: str, value: Any) -> None:
        self._scopes[-1][name] = value

    def push_scope(self):
        self._scopes.append({})

    def pop_scope(self):
        if len(self._scopes) > 1:
            self._scopes.pop()

    def all_scoped_vars(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        for scope in self._scopes:
            result.update(scope)
        return result

    def depth(self) -> int:
        return len(self._scopes)


class IoTManager:
    """传感器、执行器、设备注册表管理。"""

    def __init__(self):
        from ops.device_registry import DeviceRegistry, MockDevice

        self.sensors: Dict[str, TritValue] = {
            '人体': TritValue(0),
            '光线': TritValue(0),
            '温度': TritValue(0),
        }
        self.actuators: Dict[str, TritValue] = {
            '灯': TritValue(0),
            '风扇': TritValue(0),
            '加热': TritValue(0),
        }
        self.device_registry = DeviceRegistry()
        for name, val in self.sensors.items():
            self.device_registry.register(name, MockDevice(val))
        for name, val in self.actuators.items():
            self.device_registry.register(name, MockDevice(val))
        self.context_object: Optional[str] = None


class DebugManager:
    """断点调试管理：断点、监视变量、调试模式。"""

    def __init__(self):
        self.debug_mode: bool = False
        self._break_all: bool = False
        self._break_ops: set = set()
        self._watched_vars: set = set()
        self.call_stack: List[Any] = []

    def break_add(self, name: str) -> None:
        self._break_ops.add(name)
        self.debug_mode = True

    def break_remove(self, name: str) -> None:
        self._break_ops.discard(name)

    def watch_add(self, name: str) -> None:
        self._watched_vars.add(name)

    def watch_remove(self, name: str) -> None:
        self._watched_vars.discard(name)

    def should_break(self, internal: str, op: str) -> bool:
        return self.debug_mode and (self._break_all or op in self._break_ops or internal in self._break_ops)


class ProfileManager:
    """性能分析追踪管理。"""

    def __init__(self):
        self._profiling: bool = False
        self._profile: Dict[str, dict] = {}

    def start(self) -> None:
        self._profiling = True
        self._profile = {}

    def stop(self) -> dict:
        self._profiling = False
        return dict(self._profile)

    def record(self, name: str, dt: float) -> None:
        if name not in self._profile:
            self._profile[name] = {'count': 0, 'time': 0.0}
        self._profile[name]['count'] += 1
        self._profile[name]['time'] += dt

    def report(self) -> str:
        if not self._profile:
            return '(无性能数据)'
        lines = ['\n=== 性能追踪 ===', f'{"操作":<16} {"调用次数":<10} {"总耗时(ms)":<12} {"平均(ms)":<10}']
        items = sorted(self._profile.items(), key=lambda x: -x[1]['time'])
        for name, d in items:
            count = d['count']
            total_ms = d['time'] * 1000
            avg_ms = total_ms / count if count else 0
            lines.append(f'{name:<16} {count:<10} {total_ms:<12.3f} {avg_ms:<10.3f}')
        lines.append('=' * 48)
        return '\n'.join(lines)
