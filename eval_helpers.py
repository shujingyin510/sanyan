"""求值辅助模块：从 evaluator.py 提取的符号解析和字面量处理方法"""

from __future__ import annotations
from typing import Any, Optional
from ternary_core import TritValue
from values import SanyanNameError


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
    """解析数值字面量字符串"""
    if node.replace('.', '', 1).replace('-', '', 1).isdigit():
        return TritValue(float(node)) if '.' in node else TritValue(int(node))
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


def resolve_identifier(evaluator, node: str) -> Any:
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


def eval_str(evaluator, node: str) -> Any:
    """求值字符串节点"""
    if len(node) >= 2 and node[0] in ('"', '\u201c', '\u2018', "'"):
        return parse_string_literal(node[1:-1])
    numeric = parse_numeric_literal(node)
    if numeric is not None:
        return numeric
    if is_valid_identifier(node):
        # 如果标识符经皮肤映射为已注册的内部操作，则作为零参数操作分派（如 跳出→break, 继续→continue）
        if evaluator.skin_manager:
            resolved = evaluator.skin_manager.get_internal_keyword(node) or evaluator.skin_manager.get_internal_op(node)
            if resolved:
                from ops.registry import has_op

                if has_op(resolved):
                    return evaluator._apply(node, [])
        return resolve_identifier(evaluator, node)
    return node


def eval_symbol(evaluator, symbol: str) -> Any:
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
