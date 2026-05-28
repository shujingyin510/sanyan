"""运行环境：组合模式下由 SocketManager/IoTManager/DebugManager/ProfileManager 组成"""

from __future__ import annotations
import os
from typing import Any, Dict, List, Optional, Set, Tuple
from values import SanyanSyntaxError
from runtime_components import (
    ScopeManager,
    IoTManager,
    DebugManager,
    ProfileManager,
)


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
    # 三态字面量
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
        self.commands: Dict[str, Tuple[list, list, dict]] = {}
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
        pairs: List[Tuple[str, str]] = []
        if all(isinstance(x, str) and '.' in x for x in items):
            for item in items:
                obj, val = item.split('.')
                pairs.append((obj, val))
            return pairs
        i = 0
        while i < len(items):
            if not isinstance(items[i], str):
                raise SanyanSyntaxError(f'批量设置中发现了非字符串: {items[i]}')
            obj = items[i]
            if '.' in obj:
                obj, val = obj.split('.')
                i += 1
            elif i + 2 < len(items) and items[i + 1] == '.':
                val = items[i + 2]
                i += 3
            else:
                raise SanyanSyntaxError(f'无法解析的批量设置项: 从 {items[i]} 开始')
            pairs.append((obj, val))
        return pairs
