"""求值器主类：组合运行环境、内置操作、自定义命令"""
from typing import Any
from ternary_core import TritValue, ArrayValue
from runtime import SanyanRuntime
from builtins_ops import Builtins
from commands import Commands
from builtins_ops import Builtins, FunctionValue


class SanyanEvaluator(SanyanRuntime):
    def __init__(self, max_loop_steps=500):
        super().__init__(max_loop_steps)

    def eval(self, node: Any):
        if isinstance(node, list):
            # 统一容错：单元素列表且为数字字符串
            if len(node) == 1 and isinstance(node[0], str):
                s = node[0]
                if s.isdigit() or (s.startswith('-') and s[1:].isdigit()):
                    return TritValue(int(s))
            # 如果第一个元素是 FunctionValue，则调用它
            first = node[0]
            if isinstance(first, FunctionValue):
                func = first
                args = node[1:]
                return func.call(self, args)
            return self._apply(node[0], node[1:])
        elif isinstance(node, int):
            return TritValue(node)
        elif isinstance(node, str):
            # 处理字符串字面量（带引号）
            if len(node) >= 2 and node[0] in ('"', '\u201c', '\u2018'):
                # 去除首尾引号
                return node[1:-1]
            # 否则走符号解析，如果找不到就当作普通字符串值返回
            try:
                return self._eval_symbol(node)
            except NameError:
                return node
        else:
            raise RuntimeError(f"不支持的节点类型: {type(node)}")

    def _apply(self, op: str, args: list) -> TritValue:
        dispatch = {
            '且': lambda: Builtins.logic_op(self, op, args),
            '或': lambda: Builtins.logic_op(self, op, args),
            '非': lambda: Builtins.logic_op(self, op, args),
            '若': lambda: Builtins.control(self, op, args),
            '做': lambda: Builtins.control(self, op, args),
            '循环': lambda: Builtins.control(self, op, args),
            '遍历': lambda: Builtins.traversal(self, args),
            '设': lambda: Builtins.define_var(self, args),
            '定义': lambda: Commands.define(self, args),
            '置': lambda: Builtins.set_sensor(self, args),
            '查': lambda: Builtins.query(self, args),
            '对': lambda: Builtins.context_op(self, args),
            '读': lambda: Builtins._sensor_read(self, args),
            '输出': lambda: Builtins.output(self, args),
            '加载': lambda: Builtins._load_file(self, args),
            '输入': lambda: Builtins.input_op(self, args),
            '调试': lambda: Builtins.debug_op(self, args),
            '加': lambda: Builtins.arithmetic(self, op, args),
            '减': lambda: Builtins.arithmetic(self, op, args),
            '乘': lambda: Builtins.arithmetic(self, op, args),
            '除': lambda: Builtins.arithmetic(self, op, args),
            '余': lambda: Builtins.arithmetic(self, op, args),
            '幂': lambda: Builtins.arithmetic(self, op, args),
            '取位': lambda: Builtins.arithmetic(self, op, args),
            '等于': lambda: Builtins.comparison(self, op, args),
            '大于': lambda: Builtins.comparison(self, op, args),
            '小于': lambda: Builtins.comparison(self, op, args),
            '不等于': lambda: Builtins.comparison(self, op, args),
            '大于等于': lambda: Builtins.comparison(self, op, args),
            '小于等于': lambda: Builtins.comparison(self, op, args),
            '同': lambda: Builtins.equals_op(self, args),
            '绝对值': lambda: Builtins.math_abs(self, args),
            '最大值': lambda: Builtins.math_max(self, args),
            '最小值': lambda: Builtins.math_min(self, args),
            '平方根': lambda: Builtins.math_sqrt(self, args),
            '随机数': lambda: Builtins.math_random(self, args),
            '随机态': lambda: Builtins.math_random_state(self, args),
            '连接': lambda: Builtins.string_concat(self, args),
            '取长': lambda: Builtins.string_length(self, args),
            '列表': lambda: Builtins.list_new(self, args),
            '列表合': lambda: Builtins.list_concat(self, args),
            '表长': lambda: Builtins.list_length(self, args),
            '字列': lambda: Builtins.str_to_list(self, args),
            '数组': lambda: Builtins.array_new(self, args),
            '组长': lambda: Builtins.array_length(self, args),
            '数组列': lambda: Builtins.array_to_list(self, args),
            '取': lambda: Builtins.generic_get(self, args),
            '置元素': lambda: Builtins.generic_set(self, args),
            '字典': lambda: Builtins.dict_new(self, args),
            '取键': lambda: Builtins.dict_get(self, args),
            '置键': lambda: Builtins.dict_set(self, args),
            'λ': lambda: Builtins.make_lambda(self, args),
            '函数': lambda: Builtins.make_lambda(self, args),
            '应用': lambda: Builtins.apply(self, args),
            '映射': lambda: Builtins.map_op(self, args),
            '过滤': lambda: Builtins.filter_op(self, args),
            '归并': lambda: Builtins.reduce_op(self, args),
        }

        if op in dispatch:
            return dispatch[op]()
        # 变量作为函数或容器调用
        if op in self.vars:
            val = self.vars[op]
            from builtins_ops import FunctionValue
            # 1. 函数调用
            if isinstance(val, FunctionValue):
                evaluated_args = [self.eval(a) for a in args]
                return val.call(self, evaluated_args)
            # 2. 容器索引（列表/数组/字典）
            if isinstance(val, (list, ArrayValue, dict)):
                if len(args) != 1:
                    raise SyntaxError(f"容器索引需要一个参数，但提供了 {len(args)} 个")
                idx = self.eval(args[0])
                if isinstance(val, dict):
                    # 字典的键可以是整数或字符串，TritValue 自动转整数
                    key = idx.to_int() if isinstance(idx, TritValue) else idx
                    return val[key]
                else:
                    # 列表、数组用整数索引
                    index_int = idx.to_int() if isinstance(idx, TritValue) else idx
                    return val[index_int]
            # 变量既不是函数也不是容器
            raise TypeError(f"变量 '{op}' 的值不可调用或索引")
        return Commands.call(self, op, args)