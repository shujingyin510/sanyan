"""求值器主类：组合运行环境、内置操作、自定义命令"""
from typing import Any
from ternary_core import TritValue, ArrayValue
from runtime import SanyanRuntime
from builtins_ops import Builtins
from commands import Commands
from values import FunctionValue

class SanyanEvaluator(SanyanRuntime):
    def __init__(self, max_loop_steps=None, skin_manager=None):
        super().__init__(max_loop_steps=max_loop_steps, skin_manager=skin_manager)

    def eval(self, node: Any):
        # 直接返回已求值对象（用于高阶函数等）
        if isinstance(node, (TritValue, ArrayValue, FunctionValue)):
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
            return self._apply(node[0], node[1:])
        elif isinstance(node, int):
            return TritValue(node)
        elif isinstance(node, str):
            if len(node) >= 2 and node[0] in ('"', '\u201c', '\u2018', "'"):
                return node[1:-1]
            if self._is_valid_identifier(node):
                return self._eval_symbol(node)
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
            'if': lambda: Builtins.control(self, 'if', args),
            'do': lambda: Builtins.control(self, 'do', args),
            'loop': lambda: Builtins.control(self, 'loop', args),
            'for': lambda: Builtins.traversal(self, args),
            'return': lambda: Builtins.return_op(self, args),
            'break': lambda: Builtins.break_op(self, args),
            'try': lambda: Builtins.try_catch(self, args),
            'judge': lambda: Builtins.judge_op(self, args),
            'and': lambda: Builtins.logic_op(self, 'and', args),
            'or': lambda: Builtins.logic_op(self, 'or', args),
            'not': lambda: Builtins.logic_op(self, 'not', args),
            'add': lambda: Builtins.arithmetic(self, 'add', args),
            'sub': lambda: Builtins.arithmetic(self, 'sub', args),
            'mul': lambda: Builtins.arithmetic(self, 'mul', args),
            'div': lambda: Builtins.arithmetic(self, 'div', args),
            'mod': lambda: Builtins.arithmetic(self, 'mod', args),
            'pow': lambda: Builtins.arithmetic(self, 'pow', args),
            'digit': lambda: Builtins.arithmetic(self, 'digit', args),
            'eq': lambda: Builtins.comparison(self, 'eq', args),
            'gt': lambda: Builtins.comparison(self, 'gt', args),
            'lt': lambda: Builtins.comparison(self, 'lt', args),
            'ne': lambda: Builtins.comparison(self, 'ne', args),
            'gte': lambda: Builtins.comparison(self, 'gte', args),
            'lte': lambda: Builtins.comparison(self, 'lte', args),
            'same': lambda: Builtins.equals_op(self, args),
            'abs': lambda: Builtins.math_abs(self, args),
            'max': lambda: Builtins.math_max(self, args),
            'min': lambda: Builtins.math_min(self, args),
            'sqrt': lambda: Builtins.math_sqrt(self, args),
            'random': lambda: Builtins.math_random(self, args),
            'random_state': lambda: Builtins.math_random_state(self, args),
            'concat': lambda: Builtins.string_concat(self, args),
            'length': lambda: Builtins.string_length(self, args),
            'str_to_list': lambda: Builtins.str_to_list(self, args),
            'list': lambda: Builtins.list_new(self, args),
            'list_concat': lambda: Builtins.list_concat(self, args),
            'list_len': lambda: Builtins.list_length(self, args),
            'array': lambda: Builtins.array_new(self, args),
            'array_len': lambda: Builtins.array_length(self, args),
            'array_to_list': lambda: Builtins.array_to_list(self, args),
            'get': lambda: Builtins.generic_get(self, args),
            'set_element': lambda: Builtins.generic_set(self, args),
            'dict': lambda: Builtins.dict_new(self, args),
            'get_key': lambda: Builtins.dict_get(self, args),
            'set_key': lambda: Builtins.dict_set(self, args),
            'lambda': lambda: Builtins.make_lambda(self, args),
            'apply': lambda: Builtins.apply(self, args),
            'map': lambda: Builtins.map_op(self, args),
            'filter': lambda: Builtins.filter_op(self, args),
            'reduce': lambda: Builtins.reduce_op(self, args),
            'print': lambda: Builtins.output(self, args),
            'input': lambda: Builtins.input_op(self, args),
            'debug': lambda: Builtins.debug_op(self, args),
            'time': lambda: Builtins.time_now(self, args),
            'sleep': lambda: Builtins.sleep_op(self, args),
            'read_file': lambda: Builtins.read_file_op(self, args),
            'write_file': lambda: Builtins.write_file_op(self, args),
            'is_number': lambda: Builtins.is_number(self, args),
            'is_string': lambda: Builtins.is_string(self, args),
            'str_equals': lambda: Builtins.str_equals(self, args),
            'load': lambda: Builtins._load_file(self, args),
            'write': lambda: Builtins.set_sensor(self, args),
            'query': lambda: Builtins.query(self, args),
            'context': lambda: Builtins.context_op(self, args),
            'read': lambda: Builtins._sensor_read(self, args),
            'set': lambda: Builtins.define_var(self, args),
            'fn': lambda: Commands.define(self, args),
        }

        if internal in dispatch:
            return dispatch[internal]()

        # 变量作为函数或容器调用
        if op in self.vars:
            val = self.vars[op]
            if isinstance(val, FunctionValue):
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