"""求值器主类：组合运行环境、内置操作、自定义命令"""

from __future__ import annotations
import time
import sys
from typing import Any
from ternary_core import TritValue, ArrayValue
from runtime import SanyanRuntime
from commands import Commands
from values import FunctionValue, ModuleValue, SrcNode, SanyanNameError, SanyanError
from values import SanyanRuntimeError


def _init_ops():
    """初始化所有操作模块的注册（仅在首次导入时执行一次）"""
    import ops.control_ops
    import ops.logic_ops
    import ops.comparison_ops
    import ops.arithmetic_ops
    import ops.math_funcs_ops
    import ops.string_ops
    import ops.container_ops
    import ops.io_ops
    import ops.file_ops
    import ops.type_ops
    import ops.iot_ops
    import ops.json_ops
    import ops.package_ops  # noqa: F401
    import commands  # noqa: F401
    import ops.sandbox_ops  # noqa: F401
    import ops.time_ops  # noqa: F401
    import ops.net_ops  # noqa: F401
    import ops.crypto_ops  # noqa: F401
    import ops.math_extra_ops  # noqa: F401
    import ops.concurrent_ops  # noqa: F401


_init_ops()


class SanyanEvaluator(SanyanRuntime):
    def __init__(self, max_loop_steps=None, skin_manager=None):
        if skin_manager is None:
            from skin import SkinManager

            skin_manager = SkinManager('chinese')
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
        raise SanyanRuntimeError(f'不支持的节点类型: {type(node).__name__}，内容: {ctx}')

    def _eval_list(self, node: list) -> Any:
        if len(node) == 0:
            return None
        # 单元素列表：仅数值/字符串字面量直接求值，其他走 op 分派
        if len(node) == 1 and isinstance(node[0], str):
            s = node[0]
            if len(s) >= 2 and s[0] in ('"', '\u201c', '\u2018', "'"):
                return self._parse_string_literal(s[1:-1])
            if s.replace('.', '', 1).replace('-', '', 1).isdigit():
                return TritValue(float(s)) if '.' in s else TritValue(int(s))
        first = node[0]
        if isinstance(first, FunctionValue):
            return Commands.call(self, first.func_name, first.args)  # type: ignore[attr-defined]
        if isinstance(first, ModuleValue):
            target, method = node[1], node[2:]
            return first.get_attr(target)(self, method)  # type: ignore[attr-defined]
        try:
            return self._apply(first, node[1:])
        except SanyanError as e:
            if isinstance(node, SrcNode) and (node.line or node.col):  # type: ignore[attr-defined]
                pos_msg = f'第{node.line}行第{node.col}列: {e}'  # type: ignore[attr-defined]
                if not e.args or not e.args[0].startswith('第'):
                    e.args = (pos_msg,)
            raise

    def _parse_string_literal(self, s: str) -> str:
        """解析字符串字面量的转义序列"""
        result = []
        i = 0
        while i < len(s):
            if s[i] == '\\' and i + 1 < len(s):
                esc = s[i + 1]
                if esc == 'n':
                    result.append('\n')
                    i += 2
                elif esc == 't':
                    result.append('\t')
                    i += 2
                elif esc == 'r':
                    result.append('\r')
                    i += 2
                elif esc == '\\':
                    result.append('\\')
                    i += 2
                elif esc == '"':
                    result.append('"')
                    i += 2
                elif esc == "'":
                    result.append("'")
                    i += 2
                elif esc == 'u' and i + 5 < len(s):
                    try:
                        result.append(chr(int(s[i + 2 : i + 6], 16)))
                        i += 6
                    except ValueError:
                        result.append(s[i])
                        i += 1
                else:
                    result.append(s[i])
                    i += 1
            else:
                result.append(s[i])
                i += 1
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
        raise SanyanNameError(f'未定义的符号: {symbol}')

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
        raise SanyanNameError(f'未定义的设备: {obj}')

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
        raise SanyanNameError(f'未定义的设备: {obj}')

    def _pos(self, node) -> str:
        """如果节点有源码位置，返回位置前缀。"""
        if isinstance(node, SrcNode) and (node.line or node.col):  # type: ignore[attr-defined]
            return f'第 {node.line} 行，第 {node.col} 列: '  # type: ignore[attr-defined]
        return ''

    def _apply(self, op: str, args: list) -> TritValue:
        from ops.dispatcher import resolve_op_name, apply

        internal = resolve_op_name(self, op)
        self._debug_before(internal, op, args)
        if self._profiling:
            t0 = time.perf_counter()
        try:
            return apply(self, op, args)
        finally:
            if self._profiling:
                dt = time.perf_counter() - t0
                name = internal or op
                if name not in self._profile:
                    self._profile[name] = {'count': 0, 'time': 0.0}
                self._profile[name]['count'] += 1
                self._profile[name]['time'] += dt
            self._debug_after(internal, op, args)

    def _debug_before(self, internal: str, op: str, args: list) -> None:
        if not self.debug_mode:
            return
        if not self._break_all and op not in self._break_ops and internal not in self._break_ops:
            return
        self._debug_prompt(internal or op, args)

    def _debug_after(self, internal: str, op: str, args: list) -> None:
        if not self._watched_vars:
            return
        name = internal or op
        if name in self._watched_vars:
            return
        for v in self._watched_vars:
            if self.has_var(v):
                print(f'  [监视] {v} = {self.get_var(v)}')

    def _debug_prompt(self, cur_op: str, args: list) -> None:
        from ops.io_ops import IOOps

        fargs = ', '.join(IOOps.format_value(a) if not isinstance(a, str) else a for a in args)
        print(f'\n⏸ [断点] {cur_op}({fargs})')
        while True:
            try:
                cmd = input('调试> ').strip()
            except (KeyboardInterrupt, EOFError):
                print()
                self.debug_mode = False
                return
            if cmd in ('', 'n', 'next'):
                return
            if cmd in ('c', 'continue'):
                self.debug_mode = False
                return
            if cmd.startswith('p ') or cmd.startswith('print '):
                var = cmd.split(maxsplit=1)[1].strip()
                if self.has_var(var):
                    val = self.get_var(var)
                    print(f'  {var} = {IOOps.format_value(val) if not isinstance(val, str) else val}')
                else:
                    print(f'  {var}: 未定义')
            elif cmd == 'bt':
                print('\n  === 调用栈 ===')
                for oname, oargs in self.call_stack:
                    fa = ', '.join(str(a) for a in oargs)
                    print(f'    at {oname}({fa})')
                print('  =============')
            elif cmd == 'q':
                sys.exit(0)
            else:
                print('  命令: [Enter]/n=下一步  c=继续  p 变量  bt=调用栈  q=退出')



    @staticmethod
    def _is_valid_identifier(s: str) -> bool:
        if not s:
            return False
        for c in s:
            if c.isalnum() or c == '_' or c == '.' or '\u4e00' <= c <= '\u9fff' or '\u3400' <= c <= '\u4dbf':
                continue
            return False
        return True
