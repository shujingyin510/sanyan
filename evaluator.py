"""求值器主类：组合运行环境、内置操作、自定义命令

ops 模块在 SanyanEvaluator 首次实例化时延迟加载，避免模块导入时的启动开销。
"""

from __future__ import annotations
import time
from typing import Any, Dict, Optional, cast
from ternary_core import TritValue, ArrayValue
from runtime import SanyanRuntime
from commands import Commands
from values import FunctionValue, ModuleValue, SrcNode, SanyanError

from eval_helpers import (
    parse_string_literal,
    parse_numeric_literal,
    is_valid_identifier,
    resolve_identifier,
    eval_str,
    eval_symbol,
)
from debug_eval import debug_before, debug_after, debug_prompt

_ops_initialized = False


def _init_ops() -> None:
    """初始化所有操作模块的注册（延迟加载，仅在首次实例化时执行）"""
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
    import ops.random_ops  # noqa: F401
    import ops.regex_ops  # noqa: F401
    import ops.system_ops  # noqa: F401
    import ops.unicode_ops  # noqa: F401


class SanyanEvaluator(SanyanRuntime):
    """三言求值器核心类，组合运行环境、内置操作、自定义命令。"""

    def __init__(
        self,
        max_loop_steps: Optional[int] = None,
        skin_manager: Optional[Any] = None,
    ) -> None:
        import sys as _sys

        _init_ops()  # 延迟加载 ops 模块
        _sys.setrecursionlimit(max(_sys.getrecursionlimit(), 2000))
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
        """求值 AST 节点，返回三言值。"""
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
        """解析字符串字面量的转义序列（委派给 eval_helpers）"""
        return parse_string_literal(s)

    def _parse_numeric_literal(self, node: str) -> Optional[TritValue]:
        """解析数值字面量字符串（委派给 eval_helpers）"""
        return parse_numeric_literal(node)

    def _resolve_identifier(self, node: str) -> Any:
        """解析标识符：字典点号访问 → 符号求值 → 中文字符串降级（委派给 eval_helpers）"""
        return resolve_identifier(self, node)

    def _eval_str(self, node: str) -> Any:
        """求值字符串节点（委派给 eval_helpers）"""
        return eval_str(self, node)

    def _eval_symbol(self, symbol: str) -> Any:
        """求值符号：变量 → 字面量 → 三态词 → IoT 设备 → 上下文对象（委派给 eval_helpers）"""
        return eval_symbol(self, symbol)

    def _eval_dot_symbol(self, symbol: str) -> Any:
        """解析 对象.属性 形式的 IoT 设备访问（委派给 eval_helpers）"""
        from eval_helpers import _eval_dot_symbol

        return _eval_dot_symbol(self, symbol)

    def _eval_context_symbol(self, symbol: str) -> Any:
        """在 对 作用域内解析符号为 IoT 设备操作（委派给 eval_helpers）"""
        from eval_helpers import _eval_context_symbol

        return _eval_context_symbol(self, symbol)

    def _pos(self, node: Any) -> str:
        """如果节点有源码位置，返回位置前缀。"""
        if isinstance(node, SrcNode) and (node.line or node.col):  # type: ignore[attr-defined]
            return f'第 {node.line} 行，第 {node.col} 列: '  # type: ignore[attr-defined]
        return ''

    def _apply(self, op: str, args: list) -> TritValue:
        """执行操作：解析操作名、分派、性能分析。"""
        from ops.dispatcher import apply

        self._debug_before(op, op, args)
        if self._profiling:
            t0 = time.perf_counter()
        try:
            return cast(TritValue, apply(self, op, args))
        finally:
            if self._profiling:
                dt = time.perf_counter() - t0
                if op not in self._profile:
                    self._profile[op] = {'count': 0, 'time': 0.0}
                self._profile[op]['count'] += 1
                self._profile[op]['time'] += dt
            self._debug_after(op, op, args)

    def _debug_before(self, internal: str, op: str, args: list) -> None:
        """操作执行前的调试检查（委派给 debug_eval）"""
        debug_before(self, internal, op, args)

    def _debug_after(self, internal: str, op: str, args: list) -> None:
        """操作执行后的监视变量检查（委派给 debug_eval）"""
        debug_after(self, internal, op, args)

    def _debug_prompt(self, cur_op: str, args: list) -> None:
        """调试断点交互提示（委派给 debug_eval）"""
        debug_prompt(self, cur_op, args)

    @staticmethod
    def _is_valid_identifier(s: str) -> bool:
        """检查是否为有效标识符（委派给 eval_helpers）"""
        return is_valid_identifier(s)
