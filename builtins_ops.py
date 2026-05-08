"""内置操作：将各模块方法聚合到 Builtins 类，保持兼容"""
from ops.control_ops import ControlOps
from ops.math_ops import MathOps
from ops.string_ops import StringOps
from ops.container_ops import ContainerOps
from ops.io_ops import IOOps
from ops.iot_ops import IotOps
from values import (
    ReturnException, BreakException, SanyanError,
    SanyanSyntaxError, SanyanNameError,
    FunctionValue, call_function
)
from ternary_core import TritValue

class Builtins:
    # 控制
    @staticmethod
    def logic_op(*args):
        return MathOps.logic_op(*args)
    @staticmethod
    def control(evaluator, op, args):
        if op == 'if':
            return ControlOps.if_op(evaluator, args)
        elif op == 'do':
            return ControlOps.do_op(evaluator, args)
        elif op == 'loop':
            return ControlOps.loop_op(evaluator, args)
        raise SanyanSyntaxError(f"未知的控制操作: {op}")
    @staticmethod
    def traversal(evaluator, args):
        return ControlOps.traversal_op(evaluator, args)
    @staticmethod
    def return_op(evaluator, args):
        return ControlOps.return_op(evaluator, args)
    @staticmethod
    def break_op(evaluator, args):
        return ControlOps.break_op(evaluator, args)
    @staticmethod
    def try_catch(evaluator, args):
        return ControlOps.try_catch(evaluator, args)
    @staticmethod
    def judge_op(evaluator, args):
        return ControlOps.judge_op(evaluator, args)
    @staticmethod
    def continue_op(evaluator, args):
        return ControlOps.continue_op(evaluator, args)
    # 数学/逻辑
    @staticmethod
    def arithmetic(evaluator, op, args):
        return MathOps.arithmetic(evaluator, op, args)
    @staticmethod
    def comparison(evaluator, op, args):
        return MathOps.comparison(evaluator, op, args)
    @staticmethod
    def equals_op(evaluator, args):
        return MathOps.equals_op(evaluator, args)
    @staticmethod
    def math_abs(evaluator, args):
        return MathOps.math_abs(evaluator, args)
    @staticmethod
    def math_max(evaluator, args):
        return MathOps.math_max(evaluator, args)
    @staticmethod
    def math_min(evaluator, args):
        return MathOps.math_min(evaluator, args)
    @staticmethod
    def math_sqrt(evaluator, args):
        return MathOps.math_sqrt(evaluator, args)
    @staticmethod
    def math_random(evaluator, args):
        return MathOps.math_random(evaluator, args)
    @staticmethod
    def math_random_state(evaluator, args):
        return MathOps.math_random_state(evaluator, args)
    # 字符串
    @staticmethod
    def string_concat(evaluator, args):
        return StringOps.string_concat(evaluator, args)
    @staticmethod
    def string_length(evaluator, args):
        return StringOps.string_length(evaluator, args)
    @staticmethod
    def str_to_list(evaluator, args):
        return StringOps.str_to_list(evaluator, args)
    # 容器
    @staticmethod
    def list_new(evaluator, args):
        return ContainerOps.list_new(evaluator, args)
    @staticmethod
    def list_concat(evaluator, args):
        return ContainerOps.list_concat(evaluator, args)
    @staticmethod
    def list_length(evaluator, args):
        return ContainerOps.list_length(evaluator, args)
    @staticmethod
    def array_new(evaluator, args):
        return ContainerOps.array_new(evaluator, args)
    @staticmethod
    def array_length(evaluator, args):
        return ContainerOps.array_length(evaluator, args)
    @staticmethod
    def array_to_list(evaluator, args):
        return ContainerOps.array_to_list(evaluator, args)
    @staticmethod
    def generic_get(evaluator, args):
        return ContainerOps.generic_get(evaluator, args)
    @staticmethod
    def generic_set(evaluator, args):
        return ContainerOps.generic_set(evaluator, args)
    @staticmethod
    def dict_new(evaluator, args):
        return ContainerOps.dict_new(evaluator, args)
    @staticmethod
    def dict_get(evaluator, args):
        return ContainerOps.dict_get(evaluator, args)
    @staticmethod
    def dict_set(evaluator, args):
        return ContainerOps.dict_set(evaluator, args)
    @staticmethod
    def make_lambda(evaluator, args):
        return ContainerOps.make_lambda(evaluator, args)
    @staticmethod
    def apply(evaluator, args):
        return ContainerOps.apply(evaluator, args)
    @staticmethod
    def map_op(evaluator, args):
        return ContainerOps.map_op(evaluator, args)
    @staticmethod
    def filter_op(evaluator, args):
        return ContainerOps.filter_op(evaluator, args)
    @staticmethod
    def reduce_op(evaluator, args):
        return ContainerOps.reduce_op(evaluator, args)
    # IO
    @staticmethod
    def output(evaluator, args):
        return IOOps.output(evaluator, args)
    @staticmethod
    def input_op(evaluator, args):
        return IOOps.input_op(evaluator, args)
    @staticmethod
    def debug_op(evaluator, args):
        return IOOps.debug_op(evaluator, args)
    @staticmethod
    def time_now(evaluator, args):
        return IOOps.time_now(evaluator, args)
    @staticmethod
    def sleep_op(evaluator, args):
        return IOOps.sleep_op(evaluator, args)
    @staticmethod
    def read_file_op(evaluator, args):
        return IOOps.read_file_op(evaluator, args)
    @staticmethod
    def write_file_op(evaluator, args):
        return IOOps.write_file_op(evaluator, args)
    @staticmethod
    def is_number(evaluator, args):
        return IOOps.is_number(evaluator, args)
    @staticmethod
    def is_string(evaluator, args):
        return IOOps.is_string(evaluator, args)
    @staticmethod
    def str_equals(evaluator, args):
        return IOOps.str_equals(evaluator, args)
    @staticmethod
    def _load_file(evaluator, args):
        return IOOps._load_file(evaluator, args)
    # IoT
    @staticmethod
    def set_sensor(evaluator, args):
        return IotOps.set_sensor(evaluator, args)
    @staticmethod
    def query(evaluator, args):
        return IotOps.query(evaluator, args)
    @staticmethod
    def context_op(evaluator, args):
        return IotOps.context_op(evaluator, args)
    @staticmethod
    def _sensor_read(evaluator, args):
        return IotOps.sensor_read(evaluator, args)

    # 内部辅助
    @staticmethod
    def _call_function(evaluator, func, args):
        return call_function(evaluator, func, args)

    # 定义变量（此处异常已替换）
    @staticmethod
    def define_var(evaluator, args):
        if not args:
            raise SanyanSyntaxError("设 需要参数，格式: (设 变量名 值)")
        if len(args) == 1 and isinstance(args[0], list):
            pairs = evaluator._parse_pairs(args[0])
            last_val = TritValue(0)
            for var, val_str in pairs:
                val = TritValue.from_string(val_str)
                evaluator.vars[var] = val
                last_val = val
            return last_val
        if len(args) < 2:
            raise SanyanSyntaxError("设 需要变量名和值，格式: (设 变量名 值)")
        var_name = args[0]
        if isinstance(var_name, list):
            var_name = var_name[0]
        value_node = args[1]
        if (isinstance(value_node, list) and len(value_node) == 1 
                and isinstance(value_node[0], str) and value_node[0].isdigit()):
            value = TritValue(int(value_node[0]))
        else:
            value = evaluator.eval(value_node)
        evaluator.vars[var_name] = value
        return value
    
    @staticmethod
    def import_module(evaluator, args):
        return IOOps.import_module(evaluator, args)