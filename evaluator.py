"""求值器主类：组合运行环境、内置操作、自定义命令"""
from __future__ import annotations
from typing import Any
from ternary_core import TritValue, ArrayValue
from runtime import SanyanRuntime
from commands import Commands
from values import FunctionValue, ModuleValue, SanyanNameError
from values import SanyanSyntaxError, SanyanTypeError, SanyanKeyError, SanyanAttributeError, SanyanRuntimeError


def _init_ops():
    """初始化所有操作模块的注册（仅在首次导入时执行一次）"""
    import ops.control_ops
    import ops.math_ops
    import ops.string_ops
    import ops.container_ops
    import ops.io_ops
    import ops.file_ops
    import ops.type_ops
    import ops.iot_ops
    import ops.json_ops
    import ops.package_ops  # noqa: F401
    import commands  # noqa: F401


_init_ops()


class SanyanEvaluator(SanyanRuntime):


    def __init__(self, max_loop_steps=None, skin_manager=None):
        super().__init__(max_loop_steps=max_loop_steps, skin_manager=skin_manager)
        self._op_cache = {}
        self._name_cache = {}
        self._name_cache_max = 5000

    def eval(self, node: Any) -> Any:
        if isinstance(node, (TritValue, ArrayValue, FunctionValue, ModuleValue)):
            return node
        if isinstance(node, list):
            return self._eval_list(node)
        if isinstance(node, (int, float)):
            return TritValue(node)
        if isinstance(node, str):
            return self._eval_str(node)
        ctx = repr(node)[:100] if not isinstance(node, str) else node[:100]
        raise SanyanRuntimeError(f"不支持的节点类型: {type(node).__name__}，内容: {ctx}")

    def _eval_list(self, node: list) -> Any:
        if len(node) == 1 and isinstance(node[0], str):
            s = node[0]
            if s.isdigit() or (s.startswith('-') and s[1:].isdigit()):
                return TritValue(int(s))
            try:
                return TritValue(float(s))
            except ValueError:
                pass
        first = node[0]
        if isinstance(first, FunctionValue):
            args = [self.eval(a) for a in node[1:]]
            return first.call(self, args)
        if isinstance(first, ModuleValue):
            evaluated_args = [self.eval(a) for a in node[1:]]
            return first.call(self, evaluated_args)
        return self._apply(node[0], node[1:])

    def _parse_string_literal(self, s: str) -> str:
        """解析字符串字面量的转义序列"""
        result = []
        i = 0
        while i < len(s):
            if s[i] == '\\' and i + 1 < len(s):
                esc = s[i + 1]
                if esc == 'n':
                    result.append('\n'); i += 2
                elif esc == 't':
                    result.append('\t'); i += 2
                elif esc == 'r':
                    result.append('\r'); i += 2
                elif esc == '\\':
                    result.append('\\'); i += 2
                elif esc == '"':
                    result.append('"'); i += 2
                elif esc == "'":
                    result.append("'"); i += 2
                elif esc == 'u' and i + 5 < len(s):
                    try:
                        result.append(chr(int(s[i+2:i+6], 16)))
                        i += 6
                    except ValueError:
                        result.append(s[i]); i += 1
                else:
                    result.append(s[i]); i += 1
            else:
                result.append(s[i]); i += 1
        return ''.join(result)

    def _parse_numeric_literal(self, node: str):
        """解析数值字面量字符串"""
        if node.replace('.', '', 1).replace('-', '', 1).isdigit():
            return TritValue(float(node)) if '.' in node else TritValue(int(node))
        return None

    def _resolve_identifier(self, node: str):
        """解析标识符：字典点号访问 → 符号求值 → 中文字符串降级"""
        if '.' in node:
            parts = node.split('.', 1)
            var_name, key = parts[0], parts[1]
            if self.has_var(var_name):
                var = self.get_var(var_name)
                if isinstance(var, dict) and key in var:
                    return var[key]
        try:
            return self._eval_symbol(node)
        except SanyanNameError:
            if any('\u4e00' <= c <= '\u9fff' for c in node):
                return node
            raise

    def _eval_str(self, node: str) -> Any:
        if len(node) >= 2 and node[0] in ('"', '\u201c', '\u2018', "'"):
            return self._parse_string_literal(node[1:-1])
        numeric = self._parse_numeric_literal(node)
        if numeric is not None:
            return numeric
        if self._is_valid_identifier(node):
            return self._resolve_identifier(node)
        return node

    def _eval_symbol(self, symbol: str):
        """求值符号：变量 → 字面量 → 三态词 → IoT 设备 → 上下文对象"""
        if self.has_var(symbol):
            return self.get_var(symbol)
        if symbol.isdigit() or (symbol.startswith('-') and symbol[1:].isdigit()):
            return TritValue(int(symbol))
        if self.skin_manager:
            state = self.skin_manager.is_ternary_word(symbol)
            if state is not None:
                return TritValue(state)
        if symbol in TritValue.STATE_MAP:
            return TritValue(TritValue.STATE_MAP[symbol])
        if '.' in symbol:
            return self._eval_dot_symbol(symbol)
        if '：' in symbol:
            obj, attr = symbol.split('：')
            return self._eval_symbol(obj + '.' + attr)
        if self.context_object is not None:
            return self._eval_context_symbol(symbol)
        raise SanyanNameError(f"未定义的符号: {symbol}")

    def _eval_dot_symbol(self, symbol: str):
        """解析 对象.属性 形式的 IoT 设备访问"""
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

    def _eval_context_symbol(self, symbol: str):
        """在 对 作用域内解析符号为 IoT 设备操作"""
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
        raise SanyanNameError(f"未定义的设备: {obj}")

    def _apply(self, op: str, args: list) -> TritValue:
        internal = self._resolve_op_name(op)
        result = self._dispatch_op(internal, args)
        if result is not None:
            return result
        result = self._handle_dot_access(op, args)
        if result is not None:
            return result
        result = self._handle_variable_call(op, args)
        if result is not None:
            return result
        return Commands.call(self, op, args)

    def _resolve_op_name(self, op: str) -> str:
        cached = self._name_cache.get(op)
        if cached is not None:
            return cached
        internal = op
        skin = self.skin_manager
        if skin:
            kw = skin.get_internal_keyword(op) or skin.get_internal_op(op)
            if kw:
                internal = kw
        if len(self._name_cache) >= self._name_cache_max:
            self._name_cache.pop(next(iter(self._name_cache)))
        self._name_cache[op] = internal
        return internal

    def _dispatch_op(self, internal: str, args: list):
        from ops.registry import get_op
        if internal in self._op_cache:
            method, extra = self._op_cache[internal]
        else:
            entry = get_op(internal)
            if entry is not None:
                method, extra = entry
                self._op_cache[internal] = entry
            else:
                return None
        if extra:
            return method(self, extra, args)
        return method(self, args)

    def _handle_dot_access(self, op: str, args: list):
        if not isinstance(op, str) or '.' not in op:
            return None
        module_name, func_name = op.split('.', 1)
        if not self.has_var(module_name):
            return None
        module_val = self.get_var(module_name)
        if isinstance(module_val, ModuleValue):
            if not module_val.is_exported(func_name):
                raise SanyanNameError(f"模块 '{module_name}' 未导出 '{func_name}'")
            evaluated_args = [self.eval(a) for a in args]
            return module_val.call(self, [func_name] + evaluated_args)
        if isinstance(module_val, dict):
            if args:
                raise SanyanTypeError(f"字典 '{module_name}' 不支持方法调用")
            if func_name in module_val:
                return module_val[func_name]
            raise SanyanKeyError(f"字典 '{module_name}' 中没有键 '{func_name}'")
        if isinstance(module_val, (list, ArrayValue)):
            if func_name in ('length', '长度'):
                return TritValue(len(module_val) if isinstance(module_val, list) else module_val.length)
            try:
                return module_val[int(func_name)]
            except (ValueError, IndexError):
                raise SanyanAttributeError(f"列表 '{module_name}' 没有属性 '{func_name}'")
        return None

    def _handle_variable_call(self, op: str, args: list):
        if not self.has_var(op):
            return None
        val = self.get_var(op)
        if isinstance(val, FunctionValue):
            evaluated_args = [self.eval(a) for a in args]
            return val.call(self, evaluated_args)
        if isinstance(val, ModuleValue):
            evaluated_args = [self.eval(a) for a in args]
            return val.call(self, evaluated_args)
        if isinstance(val, (list, ArrayValue, dict)):
            if len(args) != 1:
                raise SanyanSyntaxError(f"容器索引需要一个参数，但提供了 {len(args)} 个")
            idx = self.eval(args[0])
            if isinstance(val, dict):
                key = idx.to_int() if isinstance(idx, TritValue) else idx
                return val[key]
            index_int = idx.to_int() if isinstance(idx, TritValue) else idx
            return val[index_int]
        if len(args) == 0:
            return val
        raise SanyanTypeError(f"变量 '{op}' 的值不可调用或索引")

    @staticmethod
    def _is_valid_identifier(s: str) -> bool:
        if not s:
            return False
        for c in s:
            if c.isalnum() or c == '_' or c == '.' or '\u4e00' <= c <= '\u9fff' or '\u3400' <= c <= '\u4dbf':
                continue
            return False
        return True
