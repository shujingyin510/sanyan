"""求值器主类：组合运行环境、内置操作、自定义命令

ops 模块在 SanyanEvaluator 首次实例化时延迟加载，避免模块导入时的启动开销。
"""

from __future__ import annotations
import time
from typing import Any, Dict, Optional
from ternary_core import TritValue, ArrayValue
from runtime import SanyanRuntime
from commands import Commands
from values import FunctionValue, ModuleValue, SrcNode, SanyanError, SanyanNameError, SanyanSyntaxError, SanyanTypeError


def _is_data_list(node: Any) -> bool:
    """区分数据列表（如字面量 [1,2,3]）和 AST 代码节点（SrcNode）。"""
    return isinstance(node, list) and not isinstance(node, SrcNode)

from eval_utils import (
    parse_string_literal,
    parse_numeric_literal,
    is_valid_identifier,
)

_ops_initialized = False
_DEFAULT_RECURSION_LIMIT = 2000


def _debug_before(evaluator, internal: str, op: str, args: list) -> None:
    """操作执行前的调试检查（从 debug_eval.py 合并）"""
    if not evaluator.debug_mode:
        return
    if not evaluator._break_all and op not in evaluator._break_ops and internal not in evaluator._break_ops:
        return
    _debug_prompt(evaluator, internal or op, args)


def _debug_after(evaluator, internal: str, op: str, args: list) -> None:
    """操作执行后的监视变量检查（从 debug_eval.py 合并）"""
    if not evaluator._watched_vars:
        return
    name = internal or op
    if name not in evaluator._watched_vars:
        return
    for v in evaluator._watched_vars:
        if evaluator.has_var(v):
            print(f'  [监视] {v} = {evaluator.get_var(v)}')


def _debug_prompt(evaluator, cur_op: str, args: list) -> None:
    """调试断点交互提示（从 debug_eval.py 合并）"""
    from ops.io_ops import IOOps

    fargs = ', '.join(IOOps.format_value(a) if not isinstance(a, str) else a for a in args)
    print(f'\n⏸ [断点] {cur_op}({fargs})')
    while True:
        try:
            cmd = input('调试> ').strip()
        except (KeyboardInterrupt, EOFError):
            print()
            evaluator.debug_mode = False
            return
        if cmd in ('', 'n', 'next'):
            return
        if cmd in ('c', 'continue'):
            evaluator.debug_mode = False
            return
        if cmd.startswith('p ') or cmd.startswith('print '):
            var = cmd.split(maxsplit=1)[1].strip()
            if evaluator.has_var(var):
                val = evaluator.get_var(var)
                print(f'  {var} = {IOOps.format_value(val) if not isinstance(val, str) else val}')
            else:
                print(f'  {var}: 未定义')
        elif cmd == 'bt':
            print('\n  === 调用栈 ===')
            for oname, oargs in evaluator.call_stack:
                fa = ', '.join(str(a) for a in oargs)
                print(f'    at {oname}({fa})')
            print('  =============')
        elif cmd == 'q':
            import sys; sys.exit(0)
        else:
            print('  命令: [Enter]/n=下一步  c=继续  p 变量  bt=调用栈  q=退出')


# ── 求值辅助函数（从 eval_helpers.py 合并）──

def _resolve_identifier(evaluator, node: str) -> Any:
    """解析标识符：字典点号访问 → 符号求值 → 中文字符串降级"""
    if '.' in node:
        parts = node.split('.', 1)
        var_name, key = parts[0], parts[1]
        if evaluator.has_var(var_name):
            var = evaluator.get_var(var_name)
            if isinstance(var, dict) and key in var:
                return var[key]
    try:
        return _eval_symbol(evaluator, node)
    except SanyanNameError:
        if any('\u4e00' <= c <= '\u9fff' for c in node):
            return node
        raise


def _eval_str(evaluator, node: str) -> Any:
    """求值字符串节点。

    解析顺序：引号字符串 → 数值字面量 → 皮肤关键字 → 变量/命令 → 字面量。
    当标识符是已注册的命令名时，返回 FunctionValue 并捕获当前作用域作为闭包环境，
    使函数可以作为第一类值传递和返回。
    """
    if len(node) >= 2 and node[0] in ('"', '\u201c', '\u2018', "'"):
        return parse_string_literal(node[1:-1])
    numeric = parse_numeric_literal(node)
    if numeric is not None:
        return numeric
    if is_valid_identifier(node):
        if evaluator.skin_manager:
            resolved = evaluator.skin_manager.get_internal_keyword(node) or evaluator.skin_manager.get_internal_op(node)
            if resolved:
                from ops.registry import has_op
                if has_op(resolved):
                    try:
                        return evaluator._apply(node, [])
                    except (SanyanSyntaxError, SanyanTypeError):
                        pass  # not a zero-arg op, treat as literal
        try:
            return _resolve_identifier(evaluator, node)
        except SanyanNameError:
            if hasattr(evaluator, 'commands') and node in evaluator.commands:
                return _make_closure_value(evaluator, node)
            pass  # not a variable, treat as literal string
    return node


def _make_closure_value(evaluator, cmd_name: str) -> Any:
    """将已注册的命令包装为 FunctionValue，捕获当前作用域作为闭包环境。"""
    from values import FunctionValue

    cmd_def = evaluator.commands[cmd_name]
    params = cmd_def[0]
    body = cmd_def[1]
    param_types = dict(cmd_def[2]) if len(cmd_def) > 2 and cmd_def[2] else {}
    return_type = cmd_def[3] if len(cmd_def) > 3 else None
    if return_type:
        param_types['__return__'] = return_type
    closure_vars = dict(evaluator.all_scoped_vars())
    return FunctionValue(params, body, evaluator, closure_vars, param_types)


def _eval_symbol(evaluator, symbol: str) -> Any:
    """求值符号：变量 → 字面量 → 三态词 → IoT 设备 → 上下文对象"""
    if evaluator.has_var(symbol):
        return evaluator.get_var(symbol)
    if symbol.isdigit() or (symbol.startswith('-') and symbol[1:].isdigit()):
        return TritValue(int(symbol))
    if evaluator.skin_manager:
        state = evaluator.skin_manager.is_ternary_word(symbol)
        if state is not None:
            return TritValue(state)
    if symbol in TritValue.STATE_MAP:
        return TritValue(TritValue.STATE_MAP[symbol])
    if '.' in symbol:
        return _eval_dot_symbol(evaluator, symbol)
    if '：' in symbol:
        obj, attr = symbol.split('：')
        return _eval_symbol(evaluator, obj + '.' + attr)
    if evaluator.context_object is not None:
        return _eval_context_symbol(evaluator, symbol)
    raise SanyanNameError(f'未定义的符号: {symbol}')


def _eval_dot_symbol(evaluator, symbol: str) -> Any:
    """解析 对象.属性 形式的 IoT 设备访问"""
    obj, attr = symbol.split('.')
    if obj in evaluator.actuators:
        val = TritValue.from_string(attr)
        evaluator.actuators[obj] = val
        return val
    if obj in evaluator.sensors:
        sensor_val = evaluator.sensors[obj]
        attr_val = TritValue.from_string(attr)
        return TritValue(1 if sensor_val.symbol == attr_val.symbol else -1)
    raise SanyanNameError(f'未定义的设备: {obj}')


def _eval_context_symbol(evaluator, symbol: str) -> Any:
    """在 对 作用域内解析符号为 IoT 设备操作"""
    obj = evaluator.context_object
    if obj in evaluator.actuators:
        val = TritValue.from_string(symbol)
        evaluator.actuators[obj] = val
        return val
    if obj in evaluator.sensors:
        sensor_val = evaluator.sensors[obj]
        attr_val = TritValue.from_string(symbol)
        return TritValue(1 if sensor_val.symbol == attr_val.symbol else -1)
    if hasattr(evaluator, 'device_registry'):
        dev = evaluator.device_registry.get(obj)
        if dev:
            val = TritValue.from_string(symbol)
            dev.write(val)
            return val
    raise SanyanNameError(f'未定义的设备: {obj}')


def _init_ops() -> None:
    """初始化所有操作模块的注册。

    通过 import 触发各模块的模块级 register() 调用。这是显式的
    延迟加载模式——每个 ops/*.py 在 import 时自己注册操作到 _OP_DISPATCH。
    调用方无需关心内部注册时序，只需 import 即可。
    """
    global _ops_initialized
    if _ops_initialized:
        return
    _ops_initialized = True
    import ops.control_ops
    import ops.logic_ops
    import ops.comparison_ops
    import ops.arithmetic_ops
    import ops.math_funcs_ops
    import ops.string_ops
    import ops.list_ops
    import ops.dict_ops
    import ops.iter_ops
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
    import ops.random_ops  # noqa: F401
    import ops.regex_ops  # noqa: F401
    import ops.system_ops  # noqa: F401
    import ops.unicode_ops  # noqa: F401
    import ops.ternary_time_ops  # noqa: F401
    import ops.ternary_container_ops  # noqa: F401
    import ops.ternary_math_ops  # noqa: F401


class SanyanEvaluator(SanyanRuntime):
    """三言求值器核心类，组合运行环境、内置操作、自定义命令。"""

    def __init__(
        self,
        max_loop_steps: Optional[int] = None,
        skin_manager: Optional[Any] = None,
    ) -> None:
        import sys as _sys

        _init_ops()  # 延迟加载 ops 模块
        _sys.setrecursionlimit(max(_sys.getrecursionlimit(), _DEFAULT_RECURSION_LIMIT))
        if skin_manager is None:
            from skin import SkinManager

            skin_manager = SkinManager('chinese')
        super().__init__(max_loop_steps=max_loop_steps, skin_manager=skin_manager)
        self._op_cache: Dict[str, tuple] = {}
        self._name_cache: Dict[str, str] = {}
        self._name_cache_max: int = 5000
        self._module_cache: Dict[str, Any] = {}
        self._import_stack: set = set()

    @staticmethod
    def _is_numeric_string(s: str) -> bool:
        """判断字符串是否为数值（整数、浮点数、十六进制）。"""
        if not s:
            return False
        # 十六进制：0xABC
        if s.startswith('0x') or s.startswith('-0x'):
            hex_part = s.lstrip('-')[2:]
            return len(hex_part) > 0 and all(c in '0123456789abcdefABCDEF' for c in hex_part)
        # 整数或浮点数
        t = s.lstrip('-')
        if not t:
            return False
        if '.' in t:
            parts = t.split('.', 1)
            return len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit()
        return t.isdigit()

    def eval(self, node: Any) -> Any:
        """求值 AST 节点，返回三言值。

        分派规则：
        - TritValue/FunctionValue/ModuleValue → 直接返回
        - dict → 直接返回（数据字典）
        - list → 区分：首元素为字符串 → AST 代码节点求值；否则 → 数据列表直接返回
        - int/float → 包装为 TritValue
        - str → 符号解析或字面量（保持原始 Python 类型以兼容现有 ops）
        """
        if isinstance(node, (TritValue, ArrayValue, FunctionValue, ModuleValue)):
            return node
        if isinstance(node, dict):
            return node
        if isinstance(node, list):
            if len(node) == 0 or not isinstance(node[0], str):
                return node
            if isinstance(node[0], str) and self._is_numeric_string(node[0]):
                return node
            return self._eval_list(node)
        if isinstance(node, (int, float)):
            return TritValue(node)
        if isinstance(node, str):
            return self._eval_str(node)
        return node

    def _eval_list(self, node: list) -> Any:
        """求值列表形式的表达式（函数调用、操作等）。"""
        if len(node) == 0:
            return None
        # 单元素列表：仅数值/字符串字面量直接求值，其他走 op 分派
        if len(node) == 1 and isinstance(node[0], str):
            s = node[0]
            if len(s) >= 2 and s[0] in ('"', '\u201c', '\u2018', "'"):
                return self._parse_string_literal(s[1:-1])
            if self._is_numeric_string(s):
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
        return parse_string_literal(s)

    def _parse_numeric_literal(self, node: str) -> Optional[TritValue]:
        """解析数值字面量字符串"""
        return parse_numeric_literal(node)

    def _resolve_identifier(self, node: str) -> Any:
        """解析标识符：字典点号访问 → 符号求值 → 中文字符串降级"""
        return _resolve_identifier(self, node)

    def _eval_str(self, node: str) -> Any:
        """求值字符串节点"""
        return _eval_str(self, node)

    def _eval_symbol(self, symbol: str) -> Any:
        """求值符号：变量 → 字面量 → 三态词 → IoT 设备 → 上下文对象"""
        return _eval_symbol(self, symbol)

    def _eval_dot_symbol(self, symbol: str) -> Any:
        """解析 对象.属性 形式的 IoT 设备访问"""
        return _eval_dot_symbol(self, symbol)

    def _eval_context_symbol(self, symbol: str) -> Any:
        """在 对 作用域内解析符号为 IoT 设备操作"""
        return _eval_context_symbol(self, symbol)

    def _pos(self, node: Any) -> str:
        """如果节点有源码位置，返回位置前缀。"""
        if isinstance(node, SrcNode) and (node.line or node.col):  # type: ignore[attr-defined]
            return f'第 {node.line} 行，第 {node.col} 列: '  # type: ignore[attr-defined]
        return ''

    def _apply(self, op: str, args: list) -> Any:
        """执行操作：分派到注册的处理函数。返回类型由具体操作决定（TritValue/FunctionValue/ModuleValue/str/list 等）。"""
        from ops.dispatcher import apply

        self._debug_before(op, op, args)
        if self._profiling:
            t0 = time.perf_counter()
        try:
            return apply(self, op, args)
        finally:
            if self._profiling:
                dt = time.perf_counter() - t0
                if op not in self._profile:
                    self._profile[op] = {'count': 0, 'time': 0.0}
                self._profile[op]['count'] += 1
                self._profile[op]['time'] += dt
            self._debug_after(op, op, args)

    def _debug_before(self, internal: str, op: str, args: list) -> None:
        """操作执行前的调试检查"""
        _debug_before(self, internal, op, args)

    def _debug_after(self, internal: str, op: str, args: list) -> None:
        """操作执行后的监视变量检查"""
        _debug_after(self, internal, op, args)

    def _debug_prompt(self, cur_op: str, args: list) -> None:
        """调试断点交互提示"""
        _debug_prompt(self, cur_op, args)

    @staticmethod
    def _is_valid_identifier(s: str) -> bool:
        """检查是否为有效标识符（委派给 eval_helpers）"""
        return is_valid_identifier(s)
