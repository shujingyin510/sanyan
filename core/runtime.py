"""运行环境：作用域管理、IoT 设备管理、调试管理、性能分析。

提供 ScopeManager（变量作用域栈）、IoTManager（传感器/执行器）、
DebugManager（断点调试）、ProfileManager（性能追踪）、SanyanRuntime（组合门面）。
"""

from __future__ import annotations
import os
from typing import Any, Dict, List, Optional, Set, Tuple
from core.values import SanyanNameError, SanyanSyntaxError


# ── 作用域栈管理 ──
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
        """从内向外查找变量值，未定义时抛出异常。"""
        for scope in reversed(self._scopes):
            if name in scope:
                return scope[name]
        raise SanyanNameError(f'未定义的符号: {name}')

    def has_var(self, name: str) -> bool:
        """检查变量是否在任意作用域中定义。"""
        for scope in reversed(self._scopes):
            if name in scope:
                return True
        return False

    def set_var(self, name: str, value: Any) -> None:
        """在当前作用域设置变量值。"""
        self._scopes[-1][name] = value

    def push_scope(self) -> None:
        """创建新的作用域层。"""
        self._scopes.append({})

    def pop_scope(self) -> None:
        """移除当前作用域层（保留全局作用域）。"""
        if len(self._scopes) > 1:
            self._scopes.pop()

    def all_scoped_vars(self) -> Dict[str, Any]:
        """合并所有作用域的变量字典（调试/补全用）。"""
        result: Dict[str, Any] = {}
        for scope in self._scopes:
            result.update(scope)
        return result

    def depth(self) -> int:
        """返回当前作用域栈深度。"""
        return len(self._scopes)


# ── IoT 设备管理 ──
class IoTManager:
    """传感器、执行器、设备注册表管理。"""

    def __init__(self) -> None:
        from core.ternary_core import TritValue
        from ops.device_registry import DeviceRegistry, MockDevice

        self.sensors: Dict[str, Any] = {
            '人体': TritValue(0),
            '光线': TritValue(0),
            '温度': TritValue(0),
        }
        self.actuators: Dict[str, Any] = {
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


# ── 断点调试管理 ──
class DebugManager:
    """断点调试管理：断点、监视变量、调试模式。"""

    def __init__(self) -> None:
        self.debug_mode: bool = False
        self._break_all: bool = False
        self._break_ops: set = set()
        self._watched_vars: set = set()
        self.call_stack: List[Any] = []

    def break_add(self, name: str) -> None:
        """添加断点（操作名或内部标识符）。"""
        self._break_ops.add(name)
        self.debug_mode = True

    def break_remove(self, name: str) -> None:
        """移除断点。"""
        self._break_ops.discard(name)

    def watch_add(self, name: str) -> None:
        """添加监视变量。"""
        self._watched_vars.add(name)

    def watch_remove(self, name: str) -> None:
        """移除监视变量。"""
        self._watched_vars.discard(name)

    def should_break(self, internal: str, op: str) -> bool:
        """判断当前操作是否应触发断点。"""
        return self.debug_mode and (self._break_all or op in self._break_ops or internal in self._break_ops)


# ── 性能分析追踪 ──
class ProfileManager:
    """性能分析追踪管理。"""

    def __init__(self) -> None:
        self._profiling: bool = False
        self._profile: Dict[str, dict] = {}

    def start(self) -> None:
        """开始性能分析，清空之前的数据。"""
        self._profiling = True
        self._profile = {}

    def stop(self) -> dict:
        """停止性能分析，返回分析结果副本。"""
        self._profiling = False
        return dict(self._profile)

    def record(self, name: str, dt: float) -> None:
        """记录一次操作的耗时。"""
        if name not in self._profile:
            self._profile[name] = {'count': 0, 'time': 0.0}
        self._profile[name]['count'] += 1
        self._profile[name]['time'] += dt

    def report(self) -> str:
        """生成性能分析报告。"""
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


# 模块级常量，供 lexer.py 等模块导入
# 从语言映射文件自动生成，确保与 sugar/parser.py 的关键字表同步
def _build_builtin_ops() -> set:
    """从 language/*.json 自动生成 BUILTIN_OPS 集合"""
    import json as _json

    ops: set = set()
    base = os.path.dirname(os.path.abspath(__file__))
    for lang_file in ('language/chinese.json', 'language/english.json'):
        path = os.path.join(base, lang_file)
        if not os.path.exists(path):
            continue
        with open(path, encoding='utf-8') as f:
            data = _json.load(f)
        for section in ('keywords', 'operators'):
            for v in data.get(section, {}).values():
                if isinstance(v, list):
                    ops.update(v)
                else:
                    ops.add(v)
        # 三态字面量（在同一个 data 作用域内）
        for names in data.get('ternary_states', {}).values():
            if isinstance(names, list):
                ops.update(names)
            else:
                ops.add(names)
    return ops


BUILTIN_OPS: Set[str] = _build_builtin_ops()


class SanyanRuntime:
    BUILTIN_OPS: Set[str] = BUILTIN_OPS

    def __init__(self, max_loop_steps: Optional[int] = None, skin_manager: Any = None) -> None:
        if max_loop_steps is None:
            max_loop_steps = int(os.environ.get('MAX_LOOP_STEPS', '500'))
        self.max_loop_steps: int = max_loop_steps
        self.commands: Dict[str, Tuple[list, list, dict, Any, dict, str]] = {}
        self.call_depth: int = 0
        self.max_call_depth: int = 200
        self.skin_manager: Any = skin_manager

        # 组合子组件
        # _scopes 保持为 Runtime 直接属性（测试兼容），引用传给 ScopeManager
        self._scopes: List[Dict[str, Any]] = [{}]
        self._scope_mgr = ScopeManager(self._scopes)
        self._iot_mgr = IoTManager()
        self._debug_mgr = DebugManager()
        self._profile_mgr = ProfileManager()

    # ── 作用域委派 ──
    @property
    def scope_vars(self) -> Dict[str, Any]:
        return self._scope_mgr.scope_vars

    @scope_vars.setter
    def scope_vars(self, value: Dict[str, Any]) -> None:
        self._scope_mgr.scope_vars = value

    def get_var(self, name: str) -> Any:
        return self._scope_mgr.get_var(name)

    def has_var(self, name: str) -> bool:
        return self._scope_mgr.has_var(name)

    def set_var(self, name: str, value: Any) -> None:
        self._scope_mgr.set_var(name, value)

    def push_scope(self) -> None:
        self._scope_mgr.push_scope()

    def pop_scope(self) -> None:
        self._scope_mgr.pop_scope()

    def all_scoped_vars(self) -> Dict[str, Any]:
        return self._scope_mgr.all_scoped_vars()

    # ── IoT 委派 ──
    @property
    def sensors(self) -> Dict[str, Any]:
        return self._iot_mgr.sensors

    @sensors.setter
    def sensors(self, value: Dict[str, Any]) -> None:
        self._iot_mgr.sensors = value

    @property
    def actuators(self) -> Dict[str, Any]:
        return self._iot_mgr.actuators

    @actuators.setter
    def actuators(self, value: Dict[str, Any]) -> None:
        self._iot_mgr.actuators = value

    @property
    def device_registry(self) -> Any:
        return self._iot_mgr.device_registry

    @device_registry.setter
    def device_registry(self, value: Any) -> None:
        self._iot_mgr.device_registry = value

    @property
    def context_object(self) -> Optional[str]:
        return self._iot_mgr.context_object

    @context_object.setter
    def context_object(self, value: Optional[str]) -> None:
        self._iot_mgr.context_object = value

    # ── 调试委派 ──
    @property
    def debug_mode(self) -> bool:
        return self._debug_mgr.debug_mode

    @debug_mode.setter
    def debug_mode(self, value: bool) -> None:
        self._debug_mgr.debug_mode = value

    @property
    def call_stack(self) -> List[Tuple[str, list]]:
        return self._debug_mgr.call_stack

    @call_stack.setter
    def call_stack(self, value: List[Tuple[str, list]]) -> None:
        self._debug_mgr.call_stack = value

    # ── 向后兼容属性（evaluator.py / repl.py 直接访问私有属性）──
    @property
    def _break_ops(self) -> Set[str]:
        return self._debug_mgr._break_ops

    @property
    def _break_all(self) -> bool:
        return self._debug_mgr._break_all

    @_break_all.setter
    def _break_all(self, value: bool) -> None:
        self._debug_mgr._break_all = value

    @property
    def _watched_vars(self) -> Set[str]:
        return self._debug_mgr._watched_vars

    @property
    def _profiling(self) -> bool:
        return self._profile_mgr._profiling

    @_profiling.setter
    def _profiling(self, value: bool) -> None:
        self._profile_mgr._profiling = value

    @property
    def _profile(self) -> Dict[str, Dict[str, Any]]:
        return self._profile_mgr._profile

    def break_add(self, name: str) -> None:
        self._debug_mgr.break_add(name)

    def break_remove(self, name: str) -> None:
        self._debug_mgr.break_remove(name)

    def watch_add(self, name: str) -> None:
        self._debug_mgr.watch_add(name)

    def watch_remove(self, name: str) -> None:
        self._debug_mgr.watch_remove(name)

    # ── 性能追踪委派 ──
    def profile_start(self) -> None:
        self._profile_mgr.start()

    def profile_stop(self) -> Dict[str, Dict[str, Any]]:
        return self._profile_mgr.stop()

    def profile_report(self) -> str:
        return self._profile_mgr.report()

    # ── 工具方法 ──
    def _parse_pairs(self, items: List[str]) -> List[Tuple[str, str]]:
        """解析批量设置项，格式统一为 "对象.属性"。

        旧版本支持三种格式（a.b / 交替 . / 分隔 ;），现已精简为
        只支持 a.b 格式，降低复杂度和维护成本。
        """
        pairs: List[Tuple[str, str]] = []
        for item in items:
            if not isinstance(item, str):
                raise SanyanSyntaxError(f'批量设置中发现了非字符串: {item}')
            if '.' not in item:
                raise SanyanSyntaxError(f'无法解析的批量设置项: {item}（需格式: 对象.属性）')
            obj, val = item.split('.', 1)
            pairs.append((obj, val))
        return pairs
