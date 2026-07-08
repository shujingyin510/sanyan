"""求值器主类：组合运行环境、内置操作、自定义命令

ops 模块在 SanyanEvaluator 首次实例化时延迟加载，避免模块导入时的启动开销。
"""

from __future__ import annotations
import difflib
import time
from typing import Any, Dict, Optional
from core.ternary_core import TritValue, ArrayValue
from core.runtime import SanyanRuntime
from core.values import (
    FunctionValue,
    ModuleValue,
    SrcNode,
    SanyanError,
    SanyanNameError,
    SanyanRuntimeError,
    SanyanSyntaxError,
    SanyanTypeError,
)
from core.eval_utils import (
    parse_string_literal,
    parse_numeric_literal,
    is_valid_identifier,
)

_ops_initialized = False
_DEFAULT_RECURSION_LIMIT = 2000

# ── 源码缓存（用于错误信息显示）──
_source_lines_cache: Dict[str, list[str]] = {}


def _get_source_line(source: str, line_num: int) -> str:
    """从源码中获取指定行的内容。"""
    if source not in _source_lines_cache:
        _source_lines_cache[source] = source.split('\n')
    lines = _source_lines_cache[source]
    if 1 <= line_num <= len(lines):
        return lines[line_num - 1]
    return ''


def _format_error_with_context(
    error: Exception,
    source: str,
    line: int,
    col: int,
    evaluator: Any = None,
) -> str:
    """格式化错误信息，添加源码上下文和变量建议。

    输出格式：
        错误: 未定义的符号: x
          --> file.san:15:8
           |
        15 | 输出(x + 1)
           |        ^
        提示: 你是否想使用 'x_val'？（在第 12 行定义）
    """
    parts = []
    msg = str(error)
    parts.append(f'错误: {msg}')

    if line > 0:
        parts.append(f'  --> 第{line}行第{col}列')
        src_line = _get_source_line(source, line)
        if src_line:
            parts.append('   |')
            parts.append(f'{line:4d} | {src_line}')
            parts.append(f'   | {" " * (col - 1)}^')

    # 为 SanyanNameError 添加变量名建议
    if isinstance(error, SanyanNameError) and evaluator is not None:
        name = msg.split(':')[-1].strip() if ':' in msg else msg.replace('未定义的符号: ', '').strip()
        suggestions = _suggest_similar_names(name, evaluator)
        if suggestions:
            hint = ', '.join(f"'{s}'" for s in suggestions[:3])
            parts.append(f'  提示: 你是否想使用 {hint}？')

    return '\n'.join(parts)


def _suggest_similar_names(name: str, evaluator: Any) -> list[str]:
    """根据编辑距离建议相似的变量名。"""
    candidates = set()
    # 从当前作用域收集变量名
    for scope in evaluator._scopes:
        candidates.update(scope.keys())
    # 从命令收集
    if hasattr(evaluator, 'commands'):
        candidates.update(evaluator.commands.keys())
    # 从全局变量收集
    if hasattr(evaluator, '_global_vars'):
        candidates.update(evaluator._global_vars.keys())

    matches = difflib.get_close_matches(name, candidates, n=3, cutoff=0.6)
    return matches


def _debug_before(evaluator: Any, internal: str, op: str, args: list) -> None:  # pragma: no cover
    """操作执行前的调试检查（从 debug_eval.py 合并）"""
    if not evaluator.debug_mode:
        return
    if not evaluator._break_all and op not in evaluator._break_ops and internal not in evaluator._break_ops:
        return
    _debug_prompt(evaluator, internal or op, args)


def _debug_after(evaluator: Any, internal: str, op: str, args: list) -> None:  # pragma: no cover
    """操作执行后的监视变量检查（从 debug_eval.py 合并）"""
    if not evaluator._watched_vars:
        return
    name = internal or op
    if name not in evaluator._watched_vars:
        return
    for v in evaluator._watched_vars:
        if evaluator.has_var(v):
            print(f'  [监视] {v} = {evaluator.get_var(v)}')


def _debug_prompt(evaluator: Any, cur_op: str, args: list) -> None:  # pragma: no cover
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
            import sys

            sys.exit(0)
        else:
            print('  命令: [Enter]/n=下一步  c=继续  p 变量  bt=调用栈  q=退出')


# ── 求值辅助函数（从 eval_helpers.py 合并）──


def _resolve_identifier(evaluator: Any, node: str) -> Any:  # pragma: no cover — 通过 wrapper 间接覆盖
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
        # 检查是否为已定义的函数
        if hasattr(evaluator, 'commands') and node in evaluator.commands:
            return _make_closure_value(evaluator, node)
        if any('\u4e00' <= c <= '\u9fff' for c in node):
            return node
        raise


def _eval_str(evaluator: Any, node: str) -> Any:  # pragma: no cover — 通过 wrapper 间接覆盖
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


def _make_closure_value(evaluator: Any, cmd_name: str) -> Any:  # pragma: no cover — 通过 wrapper 间接覆盖
    """将已注册的命令包装为 FunctionValue，捕获当前作用域作为闭包环境。"""
    from core.values import FunctionValue

    cmd_def = evaluator.commands[cmd_name]
    params = cmd_def[0]
    body = cmd_def[1]
    param_types = dict(cmd_def[2]) if len(cmd_def) > 2 and cmd_def[2] else {}
    return_type = cmd_def[3] if len(cmd_def) > 3 else None
    if return_type:
        param_types['__return__'] = return_type
    closure_vars = dict(evaluator.all_scoped_vars())
    return FunctionValue(params, body, evaluator, closure_vars, param_types)


def _eval_symbol(evaluator: Any, symbol: str) -> Any:  # pragma: no cover — 通过 wrapper 间接覆盖
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
        # split 一次：多个全角冒号不再裸 ValueError 穿透（对抗探针 0708）
        obj, attr = symbol.split('：', 1)
        return _eval_symbol(evaluator, obj + '.' + attr)
    if evaluator.context_object is not None:
        return _eval_context_symbol(evaluator, symbol)
    raise SanyanNameError(f'未定义的符号: {symbol}')


def _eval_dot_symbol(evaluator: Any, symbol: str) -> Any:  # pragma: no cover — 通过 wrapper 间接覆盖
    """解析 对象.属性 形式的 IoT 设备访问。

    健壮性（对抗探针 0708）：symbol 含多个点时 `obj, attr = split('.')` 曾裸
    ValueError 穿透（畸形数字 `1.2.3`、多级 `a.b.c` 作为参数值时）——改 split 一次，
    畸形数字字面量给清晰语法错误，多级点当设备名找不到而非崩。
    """
    obj, attr = symbol.split('.', 1)
    # 数字开头且含点又走到这里 = 畸形数字字面量（合法浮点在词法层已处理）
    if obj[:1].isdigit() or (obj[:1] == '-' and obj[1:2].isdigit()):
        raise SanyanSyntaxError(f'无法解析数字字面量: {symbol}')
    if obj in evaluator.actuators:
        val = TritValue.from_string(attr)
        evaluator.actuators[obj] = val
        return val
    if obj in evaluator.sensors:
        sensor_val = evaluator.sensors[obj]
        attr_val = TritValue.from_string(attr)
        return TritValue(1 if sensor_val.symbol == attr_val.symbol else -1)
    raise SanyanNameError(f'未定义的设备: {obj}')


def _eval_context_symbol(evaluator: Any, symbol: str) -> Any:  # pragma: no cover — 通过 wrapper 间接覆盖
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
    import ops.sandbox_ops  # noqa: F401
    import ops.time_ops  # noqa: F401
    import ops.net_ops  # noqa: F401
    import ops.crypto_ops  # noqa: F401
    import ops.math_extra_ops  # noqa: F401
    import ops.macro_ops  # noqa: F401
    import ops.concurrent_ops  # noqa: F401
    import ops.random_ops  # noqa: F401
    import ops.regex_ops  # noqa: F401
    import ops.system_ops  # noqa: F401
    import ops.unicode_ops  # noqa: F401
    import ops.ternary_time_ops  # noqa: F401
    import ops.ternary_container_ops  # noqa: F401
    import ops.ternary_math_ops  # noqa: F401
    import ops.sqlite_ops  # noqa: F401
    import ops.ternary_set_ops  # noqa: F401
    import ops.ternary_graph_ops  # noqa: F401
    import ops.ternary_queue_ops  # noqa: F401
    import ops.ternary_source_ops  # noqa: F401
    import ops.ternary_util_ops  # noqa: F401
    import ops.web_ops  # noqa: F401
    import ops.data_pipeline_ops  # noqa: F401
    import ops.py_bridge_ops  # noqa: F401  — FFI 层 A（SANYAN_FFI 未开时为报假桩）
    import ops.c_ffi_ops  # noqa: F401  — FFI 层 B 在线半（同一门控）


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
            from core.skin import SkinManager

            skin_manager = SkinManager('chinese')
        super().__init__(max_loop_steps=max_loop_steps, skin_manager=skin_manager)
        self._op_cache: Dict[str, tuple] = {}
        self._name_cache: Dict[str, str] = {}
        self._name_cache_max: int = 5000
        self._module_cache: Dict[str, Any] = {}
        self._import_stack: set = set()
        self._type_warnings: list = []  # 类型检查警告收集
        self._apply_fn: Any = None  # 缓存 dispatcher.apply
        self._check_types_fn: Any = None  # 缓存 type_checker.check_types
        self._source: str = ''  # 当前执行的源码（用于错误信息显示）
        self._type_env: Any = None  # 类型推断环境（延迟初始化）

    @property
    def type_env(self) -> Any:
        """获取类型推断环境（延迟初始化）。"""
        if self._type_env is None:
            from core.type_inference import TypeEnv

            self._type_env = TypeEnv()
        return self._type_env

    # 数值字符串缓存
    _NUMERIC_CACHE: dict[str, bool] = {}

    @staticmethod
    def _is_numeric_string(s: str) -> bool:
        """判断字符串是否为数值（整数、浮点数、十六进制）。"""
        cache = SanyanEvaluator._NUMERIC_CACHE
        if s in cache:
            return cache[s]
        result = SanyanEvaluator._is_numeric_string_impl(s)
        # 缓存常用长度的字符串
        if len(s) <= 10:
            cache[s] = result
        return result

    @staticmethod
    def _is_numeric_string_impl(s: str) -> bool:
        """判断字符串是否为数值（实际实现）。"""
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

    # 常用 TritValue 缓存（-100 到 100）
    _TRIT_CACHE: dict[int, TritValue] = {}

    def eval(self, node: Any) -> Any:
        """求值 AST 节点，返回三言值。

        分派规则：
        - TritValue/FunctionValue/ModuleValue → 直接返回
        - dict → 直接返回（数据字典）
        - list → 区分：首元素为字符串 → AST 代码节点求值；否则 → 数据列表直接返回
        - int/float → 包装为 TritValue
        - str → 符号解析或字面量（保持原始 Python 类型以兼容现有 ops）

        对抗探针 0708：整个体包 try，深嵌套数据/表达式的 RecursionError 捕获转清晰
        SanyanError，不裸栈溢出崩。**内联 try 不增每层递归帧数**（CPython zero-cost，
        wrapper 分层会砍半递归深度、卡死自举），也不主动限深、不降低合法递归能力。
        """
        try:
            # SrcNode 和 list 都需要走 _eval_list
            if isinstance(node, list):
                if len(node) == 0:
                    return node
                first = node[0]
                if type(first) is not str:
                    return node
                if self._is_numeric_string(first):
                    return node
                return self._eval_list(node)
            if type(node) is str:
                return self._eval_str(node)
            if type(node) is int:
                # 缓存常用整数值
                cache = SanyanEvaluator._TRIT_CACHE
                if node in cache:
                    return cache[node]
                tv = TritValue(node)
                if -100 <= node <= 100:
                    cache[node] = tv
                return tv
            if type(node) is float:
                return TritValue(node)
            if type(node) is dict:
                return node
            # TritValue/FunctionValue/ModuleValue 等自定义类型
            if isinstance(node, (TritValue, ArrayValue, FunctionValue, ModuleValue)):
                return node
            return node
        except RecursionError:
            raise SanyanRuntimeError('求值嵌套过深：数据/表达式递归栈溢出（防裸崩）') from None

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
            return first.call(self, node[1:])
        if isinstance(first, ModuleValue):
            target, method = node[1], node[2:]
            return first.get_attr(target)(self, method)  # type: ignore[attr-defined]
        try:
            return self._apply(first, node[1:])
        except SanyanError as e:
            if isinstance(node, SrcNode) and (node.line or node.col):  # type: ignore[attr-defined]
                line = node.line  # type: ignore[attr-defined]
                col = node.col  # type: ignore[attr-defined]
                if self._source:
                    enhanced = _format_error_with_context(e, self._source, line, col, self)
                    e.args = (enhanced,)
                else:
                    pos_msg = f'第{line}行第{col}列: {e}'
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
        """执行操作：分派到注册的处理函数。返回类型由具体操作决定（TritValue/FunctionValue/ModuleValue/str/list 等）。

        优化：当无调试/类型检查/分析需求时，走快速路径直接分派。
        """
        # 缓存函数引用，避免每次调用重复 import
        if self._apply_fn is None:
            from ops.dispatcher import apply as _apply_fn

            self._apply_fn = _apply_fn

        # 快速路径：无调试、无类型检查、无分析时直接分派
        if not self.debug_mode and not self._profiling:
            return self._apply_fn(self, op, args)

        # 慢速路径：需要调试/分析时执行完整检查
        if self._check_types_fn is None:
            from core.type_checker import check_types as _check_types_fn

            self._check_types_fn = _check_types_fn

        # 静态类型检查：对字面量参数做类型断言
        if args:
            try:
                simpl: list = []
                for a in args:
                    if isinstance(a, (int, float, str, list, dict)) and not isinstance(a, SrcNode):
                        simpl.append(a)
                    else:
                        simpl.append(None)
                if any(v is not None for v in simpl) and all(v is not None for v in simpl):
                    err = self._check_types_fn(op, args, simpl)
                    if err:
                        self._type_warnings.append(err)
            except Exception:
                pass  # 类型检查失败不阻塞执行

        # 编译期不确定性检查：拒绝将不确定值传给确定[X] 参数
        try:
            self._check_uncertainty(op, args)
        except SanyanTypeError:
            raise  # 效应类型错误向上传播
        except Exception:
            pass  # 检查失败不阻塞执行

        self._debug_before(op, op, args)
        if self._profiling:
            t0 = time.perf_counter()
        try:
            return self._apply_fn(self, op, args)
        finally:
            if self._profiling:
                dt = time.perf_counter() - t0
                if op not in self._profile:
                    self._profile[op] = {'count': 0, 'time': 0.0}
                self._profile[op]['count'] += 1
                self._profile[op]['time'] += dt
            self._debug_after(op, op, args)

    def _check_uncertainty(self, op: str, args: list) -> None:
        """编译期不确定性检查：拒绝将不确定值传给确定[X] 参数。

        当函数标注了确定[X] 类型参数时，检查对应实参是否为不确定表达式。
        若是，抛出 SanyanTypeError 拒绝编译。
        """
        from core.values import SanyanTypeError

        if op not in self.commands:
            return
        cmd_data = self.commands[op]
        param_names = cmd_data[0]
        param_types = cmd_data[2] if len(cmd_data) > 2 else {}
        if not param_types:
            return
        for i, arg in enumerate(args):
            if i >= len(param_names):
                break
            pname = param_names[i]
            expected = param_types.get(pname, '')
            if expected.startswith('确定[') and self._is_uncertain_expr(arg):
                raise SanyanTypeError(f"编译期拒绝：参数 '{pname}' 期望 确定，但表达式 {arg!r} 产生不确定值")

    def _is_uncertain_expr(self, expr: Any) -> bool:
        """推断表达式是否产生不确定值。

        规则：
        - 字面量 int/float/str → 确定（False）
        - TritValue 信度 < 0.99 → 不确定（True）
        - 函数返回类型标注 不确定[X] → 不确定（True）
        - 函数返回类型标注 确定[X] → 确定（False）
        - 算术运算：任一参数不确定 → 不确定
        - 其他 → 保守返回确定（False，不阻塞）
        """
        from core.ternary_core import TritValue

        # 已求值的 TritValue
        if isinstance(expr, TritValue):
            return expr.confidence < 0.99
        # Python 原生数值/字符串视为确定
        if isinstance(expr, (int, float, str)):
            return False
        # 列表表达式（函数调用/运算）
        if isinstance(expr, list) and len(expr) > 0:
            op = expr[0]
            # 检查函数返回类型
            if op in self.commands:
                cmd_data = self.commands[op]
                ret_type = cmd_data[3] if len(cmd_data) > 3 else None
                if ret_type and isinstance(ret_type, str):
                    if ret_type.startswith('不确定['):
                        return True
                    if ret_type.startswith('确定['):
                        return False
            # 算术运算：任一参数不确定 → 结果不确定
            if op in ('add', '加', 'sub', '减', 'mul', '乘', 'div', '除', 'mod', '余'):
                return any(self._is_uncertain_expr(a) for a in expr[1:])
        return False

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
