"""求值器主类：组合运行环境、内置操作、自定义命令"""
from typing import Any
from ternary_core import TritValue, ArrayValue
from runtime import SanyanRuntime
from commands import Commands
from values import FunctionValue, ModuleValue, call_function, SanyanNameError

# 直接导入 ops 模块的方法
from ops.control_ops import ControlOps
from ops.math_ops import MathOps
from ops.string_ops import StringOps
from ops.container_ops import ContainerOps
from ops.io_ops import IOOps
from ops.iot_ops import IotOps


class SanyanEvaluator(SanyanRuntime):
    # 操作名 → (模块, 方法名, 额外参数) 的静态映射
    _OP_DISPATCH = {
        # 控制
        'if': (ControlOps, 'if_op', False),
        'do': (ControlOps, 'do_op', False),
        'loop': (ControlOps, 'loop_op', False),
        'for': (ControlOps, 'traversal_op', False),
        'forin': (ControlOps, 'forin_op', False),
        'return': (ControlOps, 'return_op', False),
        'break': (ControlOps, 'break_op', False),
        'continue': (ControlOps, 'continue_op', False),
        'try': (ControlOps, 'try_catch', False),
        'judge': (ControlOps, 'judge_op', False),
        # 变量
        'set': (ControlOps, 'define_var', False),
        'fn': (Commands, 'define', False),
        # 逻辑
        'and': (MathOps, 'logic_op', 'and'),
        'or': (MathOps, 'logic_op', 'or'),
        'not': (MathOps, 'logic_op', 'not'),
        # 算术
        'add': (MathOps, 'arithmetic', 'add'),
        'sub': (MathOps, 'arithmetic', 'sub'),
        'mul': (MathOps, 'arithmetic', 'mul'),
        'div': (MathOps, 'arithmetic', 'div'),
        'mod': (MathOps, 'arithmetic', 'mod'),
        'pow': (MathOps, 'arithmetic', 'pow'),
        'digit': (MathOps, 'arithmetic', 'digit'),
        # 比较
        'eq': (MathOps, 'comparison', 'eq'),
        'gt': (MathOps, 'comparison', 'gt'),
        'lt': (MathOps, 'comparison', 'lt'),
        'ne': (MathOps, 'comparison', 'ne'),
        'gte': (MathOps, 'comparison', 'gte'),
        'lte': (MathOps, 'comparison', 'lte'),
        'ngt': (MathOps, 'comparison', 'ngt'),
        'nlt': (MathOps, 'comparison', 'nlt'),
        'same': (MathOps, 'equals_op', False),
        # 数学函数
        'abs': (MathOps, 'math_abs', False),
        'max': (MathOps, 'math_max', False),
        'min': (MathOps, 'math_min', False),
        'sqrt': (MathOps, 'math_sqrt', False),
        'random': (MathOps, 'math_random', False),
        'random_state': (MathOps, 'math_random_state', False),
        'sin': (MathOps, 'math_sin', False),
        'cos': (MathOps, 'math_cos', False),
        'tan': (MathOps, 'math_tan', False),
        'log': (MathOps, 'math_log', False),
        'log10': (MathOps, 'math_log10', False),
        'floor': (MathOps, 'math_floor', False),
        'ceil': (MathOps, 'math_ceil', False),
        'round': (MathOps, 'math_round', False),
        'math_pow': (MathOps, 'math_pow', False),
        'ternary': (MathOps, 'ternary_parse', False),
        # 字符串
        'concat': (StringOps, 'string_concat', False),
        'length': (StringOps, 'string_length', False),
        'str_to_list': (StringOps, 'str_to_list', False),
        'substring': (StringOps, 'string_substring', False),
        'replace': (StringOps, 'string_replace', False),
        'split': (StringOps, 'string_split', False),
        'find': (StringOps, 'string_find', False),
        'trim': (StringOps, 'string_trim', False),
        'upper': (StringOps, 'string_upper', False),
        'lower': (StringOps, 'string_lower', False),
        'startswith': (StringOps, 'string_startswith', False),
        'endswith': (StringOps, 'string_endswith', False),
        # 容器
        'list': (ContainerOps, 'list_new', False),
        'list_concat': (ContainerOps, 'list_concat', False),
        'list_len': (ContainerOps, 'list_length', False),
        'array': (ContainerOps, 'array_new', False),
        'array_len': (ContainerOps, 'array_length', False),
        'array_to_list': (ContainerOps, 'array_to_list', False),
        'get': (ContainerOps, 'generic_get', False),
        'set_element': (ContainerOps, 'generic_set', False),
        'dict': (ContainerOps, 'dict_new', False),
        'get_key': (ContainerOps, 'dict_get', False),
        'set_key': (ContainerOps, 'dict_set', False),
        'lambda': (ContainerOps, 'make_lambda', False),
        'apply': (ContainerOps, 'apply', False),
        'map': (ContainerOps, 'map_op', False),
        'filter': (ContainerOps, 'filter_op', False),
        'reduce': (ContainerOps, 'reduce_op', False),
        'sort': (ContainerOps, 'list_sort', False),
        'reverse': (ContainerOps, 'list_reverse', False),
        'contains': (ContainerOps, 'list_contains', False),
        'unique': (ContainerOps, 'list_unique', False),
        'slice': (ContainerOps, 'list_slice', False),
        'sum': (ContainerOps, 'list_sum', False),
        'join': (ContainerOps, 'list_join', False),
        # IO
        'print': (IOOps, 'output', False),
        'input': (IOOps, 'input_op', False),
        'debug': (IOOps, 'debug_op', False),
        'time': (IOOps, 'time_now', False),
        'sleep': (IOOps, 'sleep_op', False),
        'read_file': (IOOps, 'read_file_op', False),
        'write_file': (IOOps, 'write_file_op', False),
        'is_number': (IOOps, 'is_number', False),
        'is_string': (IOOps, 'is_string', False),
        'str_equals': (IOOps, 'str_equals', False),
        'load': (IOOps, '_load_file', False),
        'import': (IOOps, 'import_module', False),
        # IoT
        'write': (IotOps, 'set_sensor', False),
        'query': (IotOps, 'query', False),
        'context': (IotOps, 'context_op', False),
        'read': (IotOps, 'sensor_read', False),
    }

    def __init__(self, max_loop_steps=None, skin_manager=None):
        super().__init__(max_loop_steps=max_loop_steps, skin_manager=skin_manager)
        self._op_cache = {}

    def eval(self, node: Any):
        if isinstance(node, (TritValue, ArrayValue, FunctionValue, ModuleValue)):
            return node
        if isinstance(node, list):
            if len(node) == 1 and isinstance(node[0], str):
                s = node[0]
                if s.isdigit() or (s.startswith('-') and s[1:].isdigit()):
                    return TritValue(int(s))
            first = node[0]
            if isinstance(first, FunctionValue):
                func = first
                args = node[1:]
                return func.call(self, args)
            if isinstance(first, ModuleValue):
                evaluated_args = [self.eval(a) for a in node[1:]]
                return first.call(self, evaluated_args)
            return self._apply(node[0], node[1:])
        elif isinstance(node, int):
            return TritValue(node)
        elif isinstance(node, str):
            if len(node) >= 2 and node[0] in ('"', '\u201c', '\u2018', "'"):
                return node[1:-1]
            if self._is_valid_identifier(node):
                # 处理字典点号访问：学生.姓名 → 字典取值
                if '.' in node:
                    parts = node.split('.', 1)
                    var_name = parts[0]
                    key = parts[1]
                    if var_name in self.vars:
                        var = self.vars[var_name]
                        if isinstance(var, dict) and key in var:
                            return var[key]
                try:
                    return self._eval_symbol(node)
                except SanyanNameError:
                    # 若包含中文，视为未加引号的字符串字面量，返回其本身
                    if any('\u4e00' <= c <= '\u9fff' for c in node):
                        return node
                    raise
            return node
        else:
            ctx = repr(node)[:100] if not isinstance(node, str) else node[:100]
            raise RuntimeError(f"不支持的节点类型: {type(node).__name__}，内容: {ctx}")

    def _apply(self, op: str, args: list) -> TritValue:
        skin = self.skin_manager
        internal = op
        if skin:
            kw = skin.get_internal_keyword(op)
            if kw:
                internal = kw
            else:
                op_internal = skin.get_internal_op(op)
                if op_internal:
                    internal = op_internal

        # 使用静态分派表（带缓存）
        if internal in self._op_cache:
            method, extra = self._op_cache[internal]
        elif internal in self._OP_DISPATCH:
            module, method_name, extra = self._OP_DISPATCH[internal]
            method = getattr(module, method_name)
            self._op_cache[internal] = (method, extra)
        else:
            method = None

        if method is not None:
            if extra:
                return method(self, extra, args)
            return method(self, args)

        # 处理模块函数调用 (如 test.函数名) 或字典点号访问 (如 学生.姓名)
        if isinstance(op, str) and '.' in op:
            parts = op.split('.', 1)
            module_name = parts[0]
            func_name = parts[1]
            if module_name in self.vars:
                module_val = self.vars[module_name]
                if isinstance(module_val, ModuleValue):
                    evaluated_args = [self.eval(a) for a in args]
                    return module_val.call(self, [func_name] + evaluated_args)
                elif isinstance(module_val, dict):
                    # 字典点号访问：学生.姓名 → 学生["姓名"]
                    if args:
                        # 有参数时视为函数调用（如 dict.method(arg)）
                        raise TypeError(f"字典 '{module_name}' 不支持方法调用")
                    if func_name in module_val:
                        return module_val[func_name]
                    raise KeyError(f"字典 '{module_name}' 中没有键 '{func_name}'")
                elif isinstance(module_val, (list, ArrayValue)):
                    # 列表/数组点号访问：lst.length → 表长(lst)
                    if func_name == 'length' or func_name == '长度':
                        return TritValue(len(module_val) if isinstance(module_val, list) else module_val.length)
                    try:
                        idx = int(func_name)
                        return module_val[idx]
                    except (ValueError, IndexError):
                        raise AttributeError(f"列表 '{module_name}' 没有属性 '{func_name}'")

        # 变量作为函数或容器调用
        if op in self.vars:
            val = self.vars[op]
            if isinstance(val, FunctionValue):
                evaluated_args = [self.eval(a) for a in args]
                return val.call(self, evaluated_args)
            if isinstance(val, ModuleValue):
                evaluated_args = [self.eval(a) for a in args]
                return val.call(self, evaluated_args)
            if isinstance(val, (list, ArrayValue, dict)):
                if len(args) != 1:
                    raise SyntaxError(f"容器索引需要一个参数，但提供了 {len(args)} 个")
                idx = self.eval(args[0])
                if isinstance(val, dict):
                    key = idx.to_int() if isinstance(idx, TritValue) else idx
                    return val[key]
                else:
                    index_int = idx.to_int() if isinstance(idx, TritValue) else idx
                    return val[index_int]
            raise TypeError(f"变量 '{op}' 的值不可调用或索引")
        return Commands.call(self, op, args)

    @staticmethod
    def _is_valid_identifier(s: str) -> bool:
        if not s:
            return False
        for c in s:
            if c.isalnum() or c == '_' or '\u4e00' <= c <= '\u9fff' or '\u3400' <= c <= '\u4dbf':
                continue
            return False
        return True