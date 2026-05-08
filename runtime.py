"""运行环境：传感器、执行器、变量、命令存储及基础解析"""
import os
from ternary_core import TritValue
from values import SanyanNameError

class SanyanRuntime:
    BUILTIN_OPS = {
        '且', '或', '非',
        '若', '做', '循环', '遍历',
        '设', '定义',
        '置', '查', '对', '读', '输出', '加载', '输入', '调试',
        '加', '减', '乘', '除', '余', '幂', '取位',
        '等于', '大于', '小于', '不等于', '大于等于', '小于等于',
        '同',
        '绝对值', '最大值', '最小值', '平方根', '随机数', '随机态',
        '连接', '取长',
        '列表', '取', '置元素', '列表合', '表长', '字列',
        '数组', '组长', '数组列',
        '字典', '取键', '置键',
        'λ', '函数', '映射', '过滤', '归并', '应用','返回',
        '当前时间',
        '等待', '读文件', '写文件', '是数字', '是字符串', '字符串相等',
        '尝试', '捕获',
    }

    def __init__(self, max_loop_steps=None, skin_manager=None):
        if max_loop_steps is None:
            max_loop_steps = int(os.environ.get("MAX_LOOP_STEPS", "500"))
        self.max_loop_steps = max_loop_steps
        self.vars = {}
        self.sensors = {
            '人体': TritValue(0),
            '光线': TritValue(0),
            '温度': TritValue(0),
        }
        self.actuators = {
            '灯': TritValue(0),
            '风扇': TritValue(0),
            '加热': TritValue(0),
        }
        self.context_object = None
        self.max_loop_steps = max_loop_steps
        self.loop_count = 0
        self.commands = {}
        self.call_depth = 0
        self.max_call_depth = 200
        self.skin_manager = skin_manager

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
                raise SyntaxError(f"批量设置中发现了非字符串: {items[i]}")
            obj = items[i]
            if '.' in obj:
                obj, val = obj.split('.')
                i += 1
            elif i + 2 < len(items) and items[i+1] == '.':
                val = items[i+2]
                i += 3
            else:
                raise SyntaxError(f"无法解析的批量设置项: 从 {items[i]} 开始")
            pairs.append((obj, val))
        return pairs

    def _eval_symbol(self, symbol: str):
        if symbol in self.vars:
            return self.vars[symbol]
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
            val = TritValue.from_string(attr)
            self.actuators[obj] = val
            return val
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
        # 安全网：如果符号包含中文字符且未被识别，将其视为字符串返回
        if any('\u4e00' <= c <= '\u9fff' for c in symbol):
            return symbol
        # 最终回退：如果符号看起来像自然语言文本，当作字符串
        if any(c for c in symbol if '\u4e00' <= c <= '\u9fff'):
            # 含有汉字，且未找到定义，很可能是在字符串外面误用了中文
            return symbol
        raise SanyanNameError(f"未定义的符号: {symbol}")