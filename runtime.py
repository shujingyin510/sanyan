"""运行环境：传感器、执行器、变量、命令存储及基础解析"""
import os
from typing import Optional, Dict, List, Any
from ternary_core import TritValue
from values import SanyanNameError, SanyanSyntaxError

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
        '字典', '取键', '置键',
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
        self._scopes: List[Dict[str, Any]] = [{}]
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
        # IoT 设备注册表（新架构）
        from ops.device_registry import DeviceRegistry, MockDevice
        self.device_registry = DeviceRegistry()
        # 注册默认设备（向后兼容）
        for name, val in self.sensors.items():
            self.device_registry.register(name, MockDevice(val))
        for name, val in self.actuators.items():
            self.device_registry.register(name, MockDevice(val))
        self.context_object: Optional[str] = None
        self.commands: Dict[str, Any] = {}
        self.call_depth: int = 0
        self.max_call_depth: int = 200
        self.skin_manager: Any = skin_manager
        self.call_stack: List[Any] = []

    @property
    def vars(self):
        """兼容旧代码：返回当前最内层作用域。写操作直接用此属性。"""
        return self._scopes[-1]

    @vars.setter
    def vars(self, value):
        self._scopes[-1] = value

    def get_var(self, name: str) -> Any:
        for scope in reversed(self._scopes):
            if name in scope:
                return scope[name]
        return None

    def has_var(self, name: str) -> bool:
        for scope in reversed(self._scopes):
            if name in scope:
                return True
        return False

    def set_var(self, name: str, value: Any) -> None:
        self._scopes[-1][name] = value

    def push_scope(self):
        """进入新作用域（函数调用时使用）。"""
        self._scopes.append({})

    def pop_scope(self):
        """退出当前作用域。"""
        if len(self._scopes) > 1:
            self._scopes.pop()

    def all_scoped_vars(self):
        """合并所有作用域变量，供调试和自动补全使用。"""
        result = {}
        for scope in self._scopes:
            result.update(scope)
        return result

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

    def _eval_symbol(self, symbol: str):
        if self.has_var(symbol):
            return self.get_var(symbol)
        if symbol.isdigit() or (symbol.startswith('-') and symbol[1:].isdigit()):
            return TritValue(int(symbol))
        # 使用皮肤判断三态词
        if self.skin_manager:
            state = self.skin_manager.is_ternary_word(symbol)
            if state is not None:
                return TritValue(state)
        # 硬编码兜底（确保皮肤失效时仍能识别）
        if symbol in TritValue.STATE_MAP:
            return TritValue(TritValue.STATE_MAP[symbol])
        if '.' in symbol:
            obj, attr = symbol.split('.')
            if obj in self.actuators:
                val = TritValue.from_string(attr)
                self.actuators[obj] = val
                return val
            if obj in self.sensors:
                sensor_val = self.sensors[obj]
                attr_val = TritValue.from_string(attr)
                return TritValue(1 if sensor_val.symbol == attr_val.symbol else -1)
            raise SanyanNameError(f"未定义的设备: {obj}")
        if '：' in symbol:
            obj, attr = symbol.split('：')
            return self._eval_symbol(obj + '.' + attr)
        if self.context_object is not None:
            obj = self.context_object
            if obj in self.actuators:
                val = TritValue.from_string(symbol)
                self.actuators[obj] = val
                return val
            if obj in self.sensors:
                sensor_val = self.sensors[obj]
                attr_val = TritValue.from_string(symbol)
                return TritValue(1 if sensor_val.symbol == attr_val.symbol else -1)
            if hasattr(self, 'device_registry'):
                dev = self.device_registry.get(obj)
                if dev:
                    val = TritValue.from_string(symbol)
                    dev.write(val)
                    return val
        raise SanyanNameError(f"未定义的符号: {symbol}")
