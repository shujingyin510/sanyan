"""求值辅助模块：从 evaluator.py 提取的符号解析和字面量处理方法

提供字面量解析、标识符求值、符号解析等辅助函数。
闭包支持：当标识符是已注册的命令名时，返回 FunctionValue 并捕获当前作用域。
"""

from __future__ import annotations
from typing import Any, Optional, TYPE_CHECKING
from ternary_core import TritValue
from values import SanyanNameError, SanyanSyntaxError, SanyanTypeError

if TYPE_CHECKING:
    from evaluator import SanyanEvaluator


def parse_string_literal(s: str) -> str:
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


def parse_numeric_literal(node: str) -> Optional[TritValue]:
    """解析数值字面量字符串（支持十进制和十六进制）"""
    try:
        if node.startswith('0x') or node.startswith('0X'):
            return TritValue(int(node, 16))
        stripped = node.replace('.', '', 1).replace('-', '', 1)
        if stripped.isdigit():
            return TritValue(float(node)) if '.' in node else TritValue(int(node))
    except ValueError:
        pass
    return None


def is_valid_identifier(s: str) -> bool:
    """检查是否为有效标识符"""
    if not s:
        return False
    for c in s:
        if c.isalnum() or c == '_' or c == '.' or '\u4e00' <= c <= '\u9fff' or '\u3400' <= c <= '\u4dbf':
            continue
        return False
    return True


def resolve_identifier(evaluator: SanyanEvaluator, node: str) -> Any:
    """解析标识符：字典点号访问 → 符号求值 → 中文字符串降级"""
    if '.' in node:
        parts = node.split('.', 1)
        var_name, key = parts[0], parts[1]
        if evaluator.has_var(var_name):
            var = evaluator.get_var(var_name)
            if isinstance(var, dict) and key in var:
                return var[key]
    try:
        return eval_symbol(evaluator, node)
    except SanyanNameError:
        if any('\u4e00' <= c <= '\u9fff' for c in node):
            return node
        raise


def eval_str(evaluator: SanyanEvaluator, node: str) -> Any:
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
            return resolve_identifier(evaluator, node)
        except SanyanNameError:
            # 检查是否为已注册的命令（函数），返回 FunctionValue 支持第一类函数
            if hasattr(evaluator, 'commands') and node in evaluator.commands:
                return _make_closure_value(evaluator, node)
            pass  # not a variable, treat as literal string
    return node


def _make_closure_value(evaluator: SanyanEvaluator, cmd_name: str) -> Any:
    """将已注册的命令包装为 FunctionValue，捕获当前作用域作为闭包环境。

    当函数名作为独立表达式求值时（如 返回 inner、设 f = inner），
    创建 FunctionValue 并快照当前所有可见变量，使函数返回后仍能访问外层变量。
    """
    from values import FunctionValue

    cmd_def = evaluator.commands[cmd_name]
    params = cmd_def[0]
    body = cmd_def[1]
    param_types = dict(cmd_def[2]) if len(cmd_def) > 2 and cmd_def[2] else {}
    return_type = cmd_def[3] if len(cmd_def) > 3 else None
    if return_type:
        param_types['__return__'] = return_type
    # 捕获当前所有可见变量作为闭包环境
    closure_vars = dict(evaluator.all_scoped_vars())
    return FunctionValue(params, body, evaluator, closure_vars, param_types)


def unwrap_trit(value: Any) -> Any:
    """从 TritValue 中提取原始值（字符串→str，数值→int，列表/字典→原值）。
    非 TritValue 原样返回。用于 ops 中统一处理三态值。
    """
    from ternary_core import TritValue
    if isinstance(value, TritValue):
        if value.is_string():
            return value.to_payload()
        if value.is_list():
            return value.to_payload()
        if value.is_dict():
            return value.to_payload()
        return value.to_int()
    return value


def propagated_confidence(*values: Any) -> float:
    """计算贝叶斯传播置信度：所有 TritValue 输入置信度的乘积。
    
    传播规则: C_result = C_a × C_b × C_c × ...
    独立贝叶斯更新: 每个不确定源独立贡献，置信度累积衰减。
    纯 Python 值（非 TritValue）视为置信度 1.0。
    用于所有算术/比较/逻辑运算的自动置信度级联。
    """
    c = 1.0
    for v in values:
        from ternary_core import TritValue
        if isinstance(v, TritValue):
            c *= v.confidence
    return max(0.0, min(1.0, c))


def eval_symbol(evaluator: SanyanEvaluator, symbol: str) -> Any:
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
        return eval_symbol(evaluator, obj + '.' + attr)
    if evaluator.context_object is not None:
        return _eval_context_symbol(evaluator, symbol)
    raise SanyanNameError(f'未定义的符号: {symbol}')


def _eval_dot_symbol(evaluator: SanyanEvaluator, symbol: str) -> Any:
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


def _eval_context_symbol(evaluator: SanyanEvaluator, symbol: str) -> Any:
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
