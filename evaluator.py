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
    def __init__(self, max_loop_steps=None, skin_manager=None):
        super().__init__(max_loop_steps=max_loop_steps, skin_manager=skin_manager)

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
                evaluated_args = [self.eval(a) for a in args]
                return first.call(self, evaluated_args)
            return self._apply(node[0], node[1:])
        elif isinstance(node, int):
            return TritValue(node)
        elif isinstance(node, str):
            if len(node) >= 2 and node[0] in ('"', '\u201c', '\u2018', "'"):
                return node[1:-1]
            if self._is_valid_identifier(node):
                try:
                    return self._eval_symbol(node)
                except SanyanNameError:
                    # 若包含中文，视为未加引号的字符串字面量，返回其本身
                    if any('\u4e00' <= c <= '\u9fff' for c in node):
                        return node
                    raise
            return node
        else:
            raise RuntimeError(f"不支持的节点类型: {type(node)}")

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

        dispatch = {
            # 控制
            'if': lambda: ControlOps.if_op(self, args),
            'do': lambda: ControlOps.do_op(self, args),
            'loop': lambda: ControlOps.loop_op(self, args),
            'for': lambda: ControlOps.traversal_op(self, args),
            'forin': lambda: ControlOps.forin_op(self, args),
            'return': lambda: ControlOps.return_op(self, args),
            'break': lambda: ControlOps.break_op(self, args),
            'continue': lambda: ControlOps.continue_op(self, args),
            'try': lambda: ControlOps.try_catch(self, args),
            'judge': lambda: ControlOps.judge_op(self, args),
            # 变量
            'set': lambda: ControlOps.define_var(self, args),
            'fn': lambda: Commands.define(self, args),
            # 逻辑
            'and': lambda: MathOps.logic_op(self, 'and', args),
            'or': lambda: MathOps.logic_op(self, 'or', args),
            'not': lambda: MathOps.logic_op(self, 'not', args),
            # 算术
            'add': lambda: MathOps.arithmetic(self, 'add', args),
            'sub': lambda: MathOps.arithmetic(self, 'sub', args),
            'mul': lambda: MathOps.arithmetic(self, 'mul', args),
            'div': lambda: MathOps.arithmetic(self, 'div', args),
            'mod': lambda: MathOps.arithmetic(self, 'mod', args),
            'pow': lambda: MathOps.arithmetic(self, 'pow', args),
            'digit': lambda: MathOps.arithmetic(self, 'digit', args),
            # 比较
            'eq': lambda: MathOps.comparison(self, 'eq', args),
            'gt': lambda: MathOps.comparison(self, 'gt', args),
            'lt': lambda: MathOps.comparison(self, 'lt', args),
            'ne': lambda: MathOps.comparison(self, 'ne', args),
            'gte': lambda: MathOps.comparison(self, 'gte', args),
            'lte': lambda: MathOps.comparison(self, 'lte', args),
            'same': lambda: MathOps.equals_op(self, args),
            # 数学函数
            'abs': lambda: MathOps.math_abs(self, args),
            'max': lambda: MathOps.math_max(self, args),
            'min': lambda: MathOps.math_min(self, args),
            'sqrt': lambda: MathOps.math_sqrt(self, args),
            'random': lambda: MathOps.math_random(self, args),
            'random_state': lambda: MathOps.math_random_state(self, args),
            # 字符串
            'concat': lambda: StringOps.string_concat(self, args),
            'length': lambda: StringOps.string_length(self, args),
            'str_to_list': lambda: StringOps.str_to_list(self, args),
            # 容器
            'list': lambda: ContainerOps.list_new(self, args),
            'list_concat': lambda: ContainerOps.list_concat(self, args),
            'list_len': lambda: ContainerOps.list_length(self, args),
            'array': lambda: ContainerOps.array_new(self, args),
            'array_len': lambda: ContainerOps.array_length(self, args),
            'array_to_list': lambda: ContainerOps.array_to_list(self, args),
            'get': lambda: ContainerOps.generic_get(self, args),
            'set_element': lambda: ContainerOps.generic_set(self, args),
            'dict': lambda: ContainerOps.dict_new(self, args),
            'get_key': lambda: ContainerOps.dict_get(self, args),
            'set_key': lambda: ContainerOps.dict_set(self, args),
            'lambda': lambda: ContainerOps.make_lambda(self, args),
            'apply': lambda: ContainerOps.apply(self, args),
            'map': lambda: ContainerOps.map_op(self, args),
            'filter': lambda: ContainerOps.filter_op(self, args),
            'reduce': lambda: ContainerOps.reduce_op(self, args),
            # IO
            'print': lambda: IOOps.output(self, args),
            'input': lambda: IOOps.input_op(self, args),
            'debug': lambda: IOOps.debug_op(self, args),
            'time': lambda: IOOps.time_now(self, args),
            'sleep': lambda: IOOps.sleep_op(self, args),
            'read_file': lambda: IOOps.read_file_op(self, args),
            'write_file': lambda: IOOps.write_file_op(self, args),
            'is_number': lambda: IOOps.is_number(self, args),
            'is_string': lambda: IOOps.is_string(self, args),
            'str_equals': lambda: IOOps.str_equals(self, args),
            'load': lambda: IOOps._load_file(self, args),
            'import': lambda: IOOps.import_module(self, args),
            # IoT
            'write': lambda: IotOps.set_sensor(self, args),
            'query': lambda: IotOps.query(self, args),
            'context': lambda: IotOps.context_op(self, args),
            'read': lambda: IotOps.sensor_read(self, args),
        }

        if internal in dispatch:
            return dispatch[internal]()

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