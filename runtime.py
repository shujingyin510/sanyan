"""运行环境：组合模式下由 SocketManager/IoTManager/DebugManager/ProfileManager 组成"""
from __future__ import annotations
import os
from typing import Optional, Any
from values import SanyanSyntaxError
from runtime_components import (
    ScopeManager, IoTManager, DebugManager, ProfileManager,
)

# 模块级常量，供 lexer.py 等模块导入
BUILTIN_OPS = {
    '且', '或', '非',
    '若', '做', '循环', '遍历', '判',
    '设', '定义', '返回', '跳出', '继续',
    '置', '查', '对', '读', '输出', '加载', '输入', '调试',
    '导入', '导出', '注册设备',
    '加', '减', '乘', '除', '余', '幂', '取位',
    '等于', '大于', '小于', '不等于', '大于等于', '小于等于', '不大于', '不小于',
    '同',
    '绝对值', '最大值', '最小值', '平方根', '随机数', '随机态', '三进制',
    '正弦', '余弦', '正切', '对数', '常用对数', '向下取整', '向上取整', '四舍五入',
    '连接', '取长', '子串', '替换', '分割', '查找', '去空白',
    '大写', '小写', '前缀', '后缀',
    '排序', '反转', '包含', '去重', '切片', '求和', '合并',
    '列表', '取', '置元素', '列表合', '表长', '字列',
    '数组', '组长', '数组列',
    '字典', '取键', '置键', '含键',
    '计数',
    'λ', '函数', '映射', '过滤', '归并', '应用',
    '当前时间',
    '等待', '读文件', '写文件', '是数字', '是字符串', '字符串相等',
    '转JSON', '解析JSON',
    '尝试', '捕获',
    '读取', '写入', '查询',
    '从', '到', '在',
    '安装', '包列表', '加载包',
}

class SanyanRuntime:
    BUILTIN_OPS = BUILTIN_OPS

    def __init__(self, max_loop_steps: Optional[int] = None, skin_manager: Any = None):
        if max_loop_steps is None:
            max_loop_steps = int(os.environ.get("MAX_LOOP_STEPS", "500"))
        self.max_loop_steps: int = max_loop_steps
        self.commands: dict = {}
        self.call_depth: int = 0
        self.max_call_depth: int = 200
        self.skin_manager: Any = skin_manager

        # 组合子组件
        # _scopes 保持为 Runtime 直接属性（测试兼容），引用传给 ScopeManager
        self._scopes = [{}]
        self._scope_mgr = ScopeManager(self._scopes)
        self._iot_mgr = IoTManager()
        self._debug_mgr = DebugManager()
        self._profile_mgr = ProfileManager()

    # ── 作用域委派 ──
    @property
    def scope_vars(self):
        return self._scope_mgr.scope_vars

    @scope_vars.setter
    def scope_vars(self, value):
        self._scope_mgr.scope_vars = value

    def get_var(self, name: str) -> Any:
        return self._scope_mgr.get_var(name)

    def has_var(self, name: str) -> bool:
        return self._scope_mgr.has_var(name)

    def set_var(self, name: str, value: Any) -> None:
        self._scope_mgr.set_var(name, value)

    def push_scope(self):
        self._scope_mgr.push_scope()

    def pop_scope(self):
        self._scope_mgr.pop_scope()

    def all_scoped_vars(self):
        return self._scope_mgr.all_scoped_vars()

    # ── IoT 委派 ──
    @property
    def sensors(self):
        return self._iot_mgr.sensors

    @sensors.setter
    def sensors(self, value):
        self._iot_mgr.sensors = value

    @property
    def actuators(self):
        return self._iot_mgr.actuators

    @actuators.setter
    def actuators(self, value):
        self._iot_mgr.actuators = value

    @property
    def device_registry(self):
        return self._iot_mgr.device_registry

    @device_registry.setter
    def device_registry(self, value):
        self._iot_mgr.device_registry = value

    @property
    def context_object(self):
        return self._iot_mgr.context_object

    @context_object.setter
    def context_object(self, value):
        self._iot_mgr.context_object = value

    # ── 调试委派 ──
    @property
    def debug_mode(self):
        return self._debug_mgr.debug_mode

    @debug_mode.setter
    def debug_mode(self, value):
        self._debug_mgr.debug_mode = value

    @property
    def call_stack(self):
        return self._debug_mgr.call_stack

    @call_stack.setter
    def call_stack(self, value):
        self._debug_mgr.call_stack = value

    # ── 向后兼容属性（evaluator.py / repl.py 直接访问私有属性）──
    @property
    def _break_ops(self):
        return self._debug_mgr._break_ops

    @property
    def _break_all(self):
        return self._debug_mgr._break_all

    @_break_all.setter
    def _break_all(self, value):
        self._debug_mgr._break_all = value

    @property
    def _watched_vars(self):
        return self._debug_mgr._watched_vars

    @property
    def _profiling(self):
        return self._profile_mgr._profiling

    @_profiling.setter
    def _profiling(self, value):
        self._profile_mgr._profiling = value

    @property
    def _profile(self):
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

    def profile_stop(self) -> dict:
        return self._profile_mgr.stop()

    def profile_report(self) -> str:
        return self._profile_mgr.report()

    # ── 工具方法 ──
    def _parse_pairs(self, items):
        pairs = []
        if all(isinstance(x, str) and '.' in x for x in items):
            for item in items:
                obj, val = item.split('.')
                pairs.append((obj, val))
            return pairs
        i = 0
        while i < len(items):
            if not isinstance(items[i], str):
                raise SanyanSyntaxError(f"批量设置中发现了非字符串: {items[i]}")
            obj = items[i]
            if '.' in obj:
                obj, val = obj.split('.')
                i += 1
            elif i + 2 < len(items) and items[i+1] == '.':
                val = items[i+2]
                i += 3
            else:
                raise SanyanSyntaxError(f"无法解析的批量设置项: 从 {items[i]} 开始")
            pairs.append((obj, val))
        return pairs
