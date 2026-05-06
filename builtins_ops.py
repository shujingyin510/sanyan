"""内置操作：所有原生指令的实现"""
from ternary_core import BT, TernaryALU, TritValue, ArrayValue
import math
import random

class ReturnException(Exception):
    """用于函数提前返回的内部异常"""
    def __init__(self, value):
        self.value = value

class FunctionValue:
    """三言中的可调用函数对象（普通函数/lambda）"""
    def __init__(self, params, body, evaluator=None):
        self.params = params      # list of param names
        self.body = body          # list of expressions (AST nodes)
        self.evaluator = evaluator

    def call(self, evaluator, args):
        if len(args) != len(self.params):
            raise SyntaxError(f"函数需要 {len(self.params)} 个参数，但提供了 {len(args)} 个")
        saved = {}
        for param, arg_node in zip(self.params, args):
            if param in evaluator.vars:
                saved[param] = evaluator.vars[param]
            try:
                val = evaluator.eval(arg_node)
            except:
                # 允许传递未求值的节点（例如在映射中，元素已求值，但这里arg_node可能是值）
                val = arg_node
            evaluator.vars[param] = val

        try:
            result = None
            for expr in self.body:
                try:
                    result = evaluator.eval(expr)
                except ReturnException as ret:
                    result = ret.value
                    break
            return result if result is not None else TritValue(0)
        finally:
            for param in self.params:
                if param in saved:
                    evaluator.vars[param] = saved[param]
                else:
                    if param in evaluator.vars:
                        del evaluator.vars[param]

    def __repr__(self):
        return f"<函数 λ {self.params}>"

class Builtins:
    @staticmethod
    def logic_op(evaluator, op, args):
        if op in ('且', '或'):
            if len(args) == 0:
                return TritValue(0)
            result = evaluator.eval(args[0])
            for i in range(1, len(args)):
                next_val = evaluator.eval(args[i])
                if op == '且':
                    res_trits = TernaryALU.tritwise_and(result.value, next_val.value)
                else:
                    res_trits = TernaryALU.tritwise_or(result.value, next_val.value)
                result = TritValue(BT.to_int(res_trits))
            return result
        elif op == '非':
            a = evaluator.eval(args[0])
            res = TernaryALU.tritwise_not(a.value)
            return TritValue(BT.to_int(res))
        raise ValueError(f"未知的逻辑操作: {op}")

    @staticmethod
    def control(evaluator, op, args):
        if op == '若':
            if len(args) < 2:
                raise SyntaxError("若 需要条件和真分支")
            cond_node = evaluator._maybe_implicit_and(args[0])
            cond = evaluator.eval(cond_node)
            if BT.to_int(cond.value) == 1:
                return evaluator.eval(args[1])
            elif len(args) >= 3:
                return evaluator.eval(args[2])
            else:
                return TritValue(0)
        elif op == '做':
            if not args:
                return TritValue(0)
            result = None
            for statement in args:
                result = evaluator.eval(statement)
            return result if result is not None else TritValue(0)
        elif op == '循环':
            if len(args) < 2:
                raise SyntaxError("循环 需要条件和体")
            cond_node = evaluator._maybe_implicit_and(args[0])
            body = args[1:]
            result = TritValue(0)
            evaluator.loop_count = 0
            while evaluator.loop_count < evaluator.max_loop_steps:
                cond = evaluator.eval(cond_node)
                if BT.to_int(cond.value) != 1:
                    break
                for statement in body:
                    result = evaluator.eval(statement)
                evaluator.loop_count += 1
            return result
        raise ValueError(f"未知的控制操作: {op}")

    @staticmethod
    def define_var(evaluator, args):
        if not args:
            raise SyntaxError("设 需要参数，格式: (设 变量名 值)")
        if len(args) == 1 and isinstance(args[0], list):
            pairs = evaluator._parse_pairs(args[0])
            last_val = TritValue(0)
            for var, val_str in pairs:
                val = TritValue.from_string(val_str)
                evaluator.vars[var] = val
                last_val = val
            return last_val
        if len(args) < 2:
            raise SyntaxError("设 需要变量名和值，格式: (设 变量名 值)")
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
    def set_sensor(evaluator, args):
        if not args:
            raise SyntaxError("置 需要参数")
        target = args[0]
        if isinstance(target, list):
            pairs = evaluator._parse_pairs(target)
            last_state = TritValue(0)
            for obj, val_str in pairs:
                state = TritValue.from_string(val_str)
                if obj in evaluator.sensors:
                    evaluator.sensors[obj] = state
                elif obj in evaluator.actuators:
                    evaluator.actuators[obj] = state
                else:
                    evaluator.actuators[obj] = state
                last_state = state
            return last_state
        elif isinstance(target, str):
            if len(args) >= 2:
                sensor_name = target
                state = evaluator.eval(args[1])
            elif '.' in target:
                sensor_name, attr = target.split('.')
                state = TritValue.from_string(attr)
            elif '：' in target:
                sensor_name, attr = target.split('：')
                state = TritValue.from_string(attr)
            else:
                raise SyntaxError("置 的用法: (置 对象 状态) 或 (置 (对象.状态 ...))")
            if sensor_name in evaluator.sensors:
                evaluator.sensors[sensor_name] = state
            elif sensor_name in evaluator.actuators:
                evaluator.actuators[sensor_name] = state
            else:
                evaluator.actuators[sensor_name] = state
            return state
        else:
            raise SyntaxError("置 的参数格式错误")

    @staticmethod
    def query(evaluator, args):
        target = args[0]
        if isinstance(target, list):
            results = []
            for item in target:
                result = Builtins.query(evaluator, [item])
                results.append(result)
            return results[-1] if results else TritValue(0)
        if target in evaluator.actuators:
            val = evaluator.actuators[target]
            state_map = {1: "开", 0: "守", -1: "关", '+': "开", '0': "守", '-': "关"}
            state_word = state_map.get(val.to_int(), val.symbol)
            print(f"  {target} 当前状态: {state_word} ({val.symbol})")
            return val
        if target in evaluator.sensors:
            val = evaluator.sensors[target]
            print(f"  {target} 当前状态: {val.symbol} (值: {val.to_int()})")
            return val
        if isinstance(target, str) and '.' in target:
            obj, attr = target.split('.')
            if obj in evaluator.actuators:
                val = evaluator.actuators[obj]
                print(f"  {obj} 当前状态: {val.symbol} (值: {val.to_int()})")
                return val
            if obj in evaluator.sensors:
                sensor_val = evaluator.sensors[obj]
                attr_val = TritValue.from_string(attr)
                print(f"  传感器 {obj} 当前值: {sensor_val.symbol}")
                return TritValue(1 if sensor_val.symbol == attr_val.symbol else -1)
        if isinstance(target, str) and '：' in target:
            obj, attr = target.split('：')
            return Builtins.query(evaluator, [obj + '.' + attr])
        raise NameError(f"无法查看: {target}（执行器、传感器中均不存在）")

    @staticmethod
    def context_op(evaluator, args):
        obj = evaluator.eval(args[0])
        if isinstance(obj, TritValue):
            obj = obj.symbol
        if obj not in evaluator.actuators and obj not in evaluator.sensors:
            evaluator.actuators[obj] = TritValue(0)
        old_ctx = evaluator.context_object
        evaluator.context_object = obj
        try:
            result = None
            for action in args[1:]:
                val = evaluator.eval(action)
                if evaluator.context_object in evaluator.actuators and isinstance(val, TritValue):
                    evaluator.actuators[evaluator.context_object] = val
                result = val
            return result if result is not None else TritValue(0)
        finally:
            evaluator.context_object = old_ctx

    @staticmethod
    def arithmetic(evaluator, op, args):
        if op == '加':
            # 尝试整数加法，若失败则自动转为字符串拼接
            try:
                total = 0
                for arg in args:
                    total += evaluator.eval(arg).to_int()
                return TritValue(total)
            except (AttributeError, TypeError):
                parts = []
                for arg in args:
                    val = evaluator.eval(arg)
                    if isinstance(val, str):
                        parts.append(val)
                    elif isinstance(val, TritValue):
                        parts.append(str(val.to_int()))
                    else:
                        parts.append(str(val))
                return ''.join(parts)
        elif op == '减':
            if len(args) < 2:
                raise SyntaxError("减 需要至少两个参数")
            result = evaluator.eval(args[0]).to_int()
            for arg in args[1:]:
                result -= evaluator.eval(arg).to_int()
            return TritValue(result)
        elif op == '乘':
            result = 1
            for arg in args:
                result *= evaluator.eval(arg).to_int()
            return TritValue(result)
        elif op == '除':
            if len(args) != 2:
                raise SyntaxError("除 需要两个参数")
            a = evaluator.eval(args[0]).to_int()
            b = evaluator.eval(args[1]).to_int()
            if b == 0:
                raise ValueError("除数不能为零")
            return TritValue(a // b)
        elif op == '余':
            if len(args) != 2:
                raise SyntaxError("余 需要两个参数")
            a = evaluator.eval(args[0]).to_int()
            b = evaluator.eval(args[1]).to_int()
            return TritValue(a % b)
        elif op == '幂':
            if len(args) != 2:
                raise SyntaxError("幂 需要两个参数")
            a = evaluator.eval(args[0]).to_int()
            b = evaluator.eval(args[1]).to_int()
            return TritValue(a ** b)
        elif op == '取位':
            if len(args) != 2:
                raise SyntaxError("取位 需要数字和位置")
            num = evaluator.eval(args[0]).to_int()
            pos = evaluator.eval(args[1]).to_int()
            digit = (abs(num) // (10 ** pos)) % 10
            return TritValue(digit)
        raise ValueError(f"未知的算术操作: {op}")

    @staticmethod
    def comparison(evaluator, op, args):
        if len(args) != 2:
            raise SyntaxError(f"{op} 需要两个参数")
        a = evaluator.eval(args[0]).to_int()
        b = evaluator.eval(args[1]).to_int()
        truth = False
        if op == '等于':   truth = a == b
        elif op == '大于': truth = a > b
        elif op == '小于': truth = a < b
        elif op == '不等于': truth = a != b
        elif op == '大于等于': truth = a >= b
        elif op == '小于等于': truth = a <= b
        return TritValue(1 if truth else -1)

    @staticmethod
    def traversal(evaluator, args):
        if len(args) < 4:
            raise SyntaxError("遍历 需要 变量名 起始 结束 体")
        var_name = args[0]
        start = evaluator.eval(args[1]).to_int()
        end = evaluator.eval(args[2]).to_int()
        body = args[3:]
        result = TritValue(0)
        for i in range(start, end + 1):
            evaluator.vars[var_name] = TritValue(i)
            for expr in body:
                result = evaluator.eval(expr)
        return result

    @staticmethod
    def output(evaluator, args):
        if len(args) == 0:
            return TritValue(0)
        val = evaluator.eval(args[0])
        if isinstance(val, TritValue):
            print(f"  => {val.to_int()}  (三进制: {val.symbol})")
        elif isinstance(val, str):
            print(f"  => {val}")
        else:
            print(f"  => {val}")
        return val

    @staticmethod
    def equals_op(evaluator, args):
        a = evaluator.eval(args[0])
        b = evaluator.eval(args[1])
        return TritValue(1 if a.symbol == b.symbol else -1)

    @staticmethod
    def input_op(evaluator, args):
        prompt = "请输入一个值: "
        if args:
            prompt = str(args[0])
        user_input = input(prompt).strip()
        if user_input.isdigit() or (user_input.startswith('-') and user_input[1:].isdigit()):
            return TritValue(int(user_input))
        if user_input in TritValue.STATE_MAP:
            return TritValue.from_string(user_input)
        raise ValueError(f"无法识别的输入: {user_input}")

    @staticmethod
    def debug_op(evaluator, args):
        print("=== 调试信息 ===")
        print("变量:")
        for name, val in evaluator.vars.items():
            print(f"  {name}: {val}")
        print("传感器:")
        for name, val in evaluator.sensors.items():
            print(f"  {name}: {val.symbol} (int: {val.to_int()})")
        print("执行器:")
        for name, val in evaluator.actuators.items():
            print(f"  {name}: {val.symbol} (int: {val.to_int()})")
        print("================")
        return TritValue(0)

    # ── 新增数学函数 ──
    @staticmethod
    def math_abs(evaluator, args):
        if len(args) != 1:
            raise SyntaxError("绝对值 需要一个参数")
        val = evaluator.eval(args[0]).to_int()
        return TritValue(abs(val))

    @staticmethod
    def math_max(evaluator, args):
        if len(args) < 2:
            raise SyntaxError("最大值 需要至少两个参数")
        max_val = None
        for arg in args:
            v = evaluator.eval(arg).to_int()
            if max_val is None or v > max_val:
                max_val = v
        return TritValue(max_val)

    @staticmethod
    def math_min(evaluator, args):
        if len(args) < 2:
            raise SyntaxError("最小值 需要至少两个参数")
        min_val = None
        for arg in args:
            v = evaluator.eval(arg).to_int()
            if min_val is None or v < min_val:
                min_val = v
        return TritValue(min_val)

    @staticmethod
    def math_sqrt(evaluator, args):
        if len(args) != 1:
            raise SyntaxError("平方根 需要一个参数")
        val = evaluator.eval(args[0]).to_int()
        if val < 0:
            raise ValueError("负数不能开平方根")
        return TritValue(int(math.isqrt(val)))

    @staticmethod
    def math_random(evaluator, args):
        if len(args) == 0:
            return TritValue(random.choice([0, 1]))
        elif len(args) == 1:
            end = evaluator.eval(args[0]).to_int()
            return TritValue(random.randint(0, end))
        elif len(args) == 2:
            start = evaluator.eval(args[0]).to_int()
            end = evaluator.eval(args[1]).to_int()
            return TritValue(random.randint(start, end))
        else:
            raise SyntaxError("随机数 最多接受两个参数")

    @staticmethod
    def math_random_state(evaluator, args):
        return TritValue(random.choice([1, 0, -1]))

    # ── 字符串操作 ──
    @staticmethod
    def _arg_to_str(evaluator, arg):
        val = evaluator.eval(arg) if not isinstance(arg, (str, int)) else arg
        if isinstance(val, str):
            return val
        if isinstance(val, TritValue):
            return str(val.to_int())
        return str(val)

    @staticmethod
    def string_concat(evaluator, args):
        if len(args) < 2:
            raise SyntaxError("连接 需要至少两个参数")
        parts = []
        for a in args:
            val = evaluator.eval(a)
            if isinstance(val, str):
                parts.append(val)
            elif isinstance(val, TritValue):
                parts.append(str(val.to_int()))
            else:
                parts.append(str(val))
        return ''.join(parts)

    @staticmethod
    def string_length(evaluator, args):
        if len(args) != 1:
            raise SyntaxError("取长 需要一个参数")
        val = evaluator.eval(args[0])      # 先求值
        if isinstance(val, str):
            return TritValue(len(val))
        if isinstance(val, TritValue):
            return TritValue(len(str(val.to_int())))
        # 其他类型尝试转字符串
        return TritValue(len(str(val)))

    # ── 列表操作 ──
    @staticmethod
    def list_new(evaluator, args):
        items = [evaluator.eval(a) for a in args]
        return items

    @staticmethod
    def list_concat(evaluator, args):
        result = []
        for arg in args:
            lst = evaluator.eval(arg)
            if not isinstance(lst, list):
                raise TypeError("所有参数必须是列表")
            result.extend(lst)
        return result

    @staticmethod
    def list_length(evaluator, args):
        if len(args) != 1:
            raise SyntaxError("表长 需要一个列表参数")
        lst = evaluator.eval(args[0])
        if not isinstance(lst, list):
            raise TypeError("参数必须是列表")
        return TritValue(len(lst))

    @staticmethod
    def str_to_list(evaluator, args):
        if len(args) != 1:
            raise SyntaxError("字列 需要一个字符串参数")
        val = evaluator.eval(args[0])
        if isinstance(val, str):
            return list(val)
        raise TypeError("字列 需要字符串")

    # ── 数组操作 ──
    @staticmethod
    def array_new(evaluator, args):
        if len(args) == 0 or len(args) > 2:
            raise SyntaxError("数组 需要一个或两个参数: (数组 长度 [默认值])")
        length = evaluator.eval(args[0]).to_int()
        if length < 0:
            raise ValueError("数组长度不能为负数")
        default = evaluator.eval(args[1]) if len(args) == 2 else TritValue(0)
        return ArrayValue(length, default)

    @staticmethod
    def array_length(evaluator, args):
        if len(args) != 1:
            raise SyntaxError("组长 需要一个数组参数")
        arr = evaluator.eval(args[0])
        if not isinstance(arr, ArrayValue):
            raise TypeError("参数必须是数组")
        return TritValue(arr.length)

    @staticmethod
    def array_to_list(evaluator, args):
        if len(args) != 1:
            raise SyntaxError("数组列 需要一个数组参数")
        arr = evaluator.eval(args[0])
        if not isinstance(arr, ArrayValue):
            raise TypeError("参数必须是数组")
        return arr.to_list()

    # ── 通用容器操作（列表 & 数组）──
    @staticmethod
    def generic_get(evaluator, args):
        if len(args) != 2:
            raise SyntaxError("取 需要容器和索引")
        container = evaluator.eval(args[0])
        index = evaluator.eval(args[1]).to_int()
        if isinstance(container, (list, ArrayValue)):
            return container[index]
        raise TypeError("第一个参数必须是列表或数组")

    @staticmethod
    def generic_set(evaluator, args):
        if len(args) != 3:
            raise SyntaxError("置元素 需要容器、索引和新值")
        container = evaluator.eval(args[0])
        index = evaluator.eval(args[1]).to_int()
        value = evaluator.eval(args[2])
        if isinstance(container, (list, ArrayValue)):
            container[index] = value
            return container
        raise TypeError("第一个参数必须是列表或数组")

    # ── 字典操作 ──
    @staticmethod
    def dict_new(evaluator, args):
        if len(args) % 2 != 0:
            raise SyntaxError("字典 需要偶数个参数（键值对）")
        d = {}
        for i in range(0, len(args), 2):
            key = evaluator.eval(args[i])
            if isinstance(key, TritValue):
                key = key.to_int()
            value = evaluator.eval(args[i+1])
            d[key] = value
        return d

    @staticmethod
    def dict_get(evaluator, args):
        if len(args) != 2:
            raise SyntaxError("取键 需要字典和键")
        d = evaluator.eval(args[0])
        if not isinstance(d, dict):
            raise TypeError("第一个参数必须是字典")
        key = evaluator.eval(args[1])
        if isinstance(key, TritValue):
            key = key.to_int()
        return d[key]

    @staticmethod
    def dict_set(evaluator, args):
        if len(args) != 3:
            raise SyntaxError("置键 需要字典、键和新值")
        d = evaluator.eval(args[0])
        if not isinstance(d, dict):
            raise TypeError("第一个参数必须是字典")
        key = evaluator.eval(args[1])
        if isinstance(key, TritValue):
            key = key.to_int()
        value = evaluator.eval(args[2])
        d[key] = value
        return d

    # ── 内部辅助 ──
    @staticmethod
    def _sensor_read(evaluator, args):
        sensor_name = args[0]
        if sensor_name in evaluator.sensors:
            return evaluator.sensors[sensor_name]
        raise NameError(f"未知传感器: {sensor_name}")

    @staticmethod
    def _load_file(evaluator, args):
        if len(args) != 1:
            raise SyntaxError("加载 需要文件路径")
        path = args[0]
        if isinstance(path, list):
            path = path[0]
        with open(path, 'r', encoding='utf-8') as f:
            code = f.read()
        if not code.strip():
            return TritValue(0)
        # 自动判断糖语法
        if '{' in code or ';' in code or '；' in code:
            from sugar import SugarConverter
            ast = SugarConverter.convert(code)
            return evaluator.eval(ast)
        else:
            # 原生语法按行处理
            from lexer import tokenize
            from parser import parse
            lines = code.splitlines()
            last_result = TritValue(0)
            for line in lines:
                line = line.strip()
                if not line or line.startswith('；') or line.startswith(';') or line.startswith('//'):
                    continue
                tokens = tokenize(line)
                if not tokens:
                    continue
                ast = parse(tokens)
                last_result = evaluator.eval(ast)
            return last_result
    
        # ── Lambda 创建 ──
    @staticmethod
    def make_lambda(evaluator, args):
        """(λ (参数...) 体...)"""
        if len(args) < 2:
            raise SyntaxError("λ 需要参数列表和体")
        params = args[0]
        if not isinstance(params, list):
            raise SyntaxError("λ 的参数必须是列表")
        body = args[1:]
        return FunctionValue(params, body)

    # ── 通用函数应用 ──
    @staticmethod
    def apply(evaluator, args):
        """(应用 函数 参数...) 显式调用函数"""
        if len(args) < 1:
            raise SyntaxError("应用 需要函数和参数")
        func = evaluator.eval(args[0])
        func_args = args[1:]
        return Builtins._call_function(evaluator, func, func_args)

    # ── 映射 ──
    @staticmethod
    def map_op(evaluator, args):
        if len(args) != 2:
            raise SyntaxError("映射 需要函数和容器")
        func = evaluator.eval(args[0])
        container = evaluator.eval(args[1])
        if not isinstance(container, (list, ArrayValue)):
            raise TypeError("第二个参数必须是列表或数组")
        result = []
        for item in container:
            # 对每个元素应用函数：将元素转换为 TritValue 或保持原样后作为参数传递
            res = Builtins._call_function(evaluator, func, [item])
            result.append(res)
        return result

    # ── 过滤 ──
    @staticmethod
    def filter_op(evaluator, args):
        if len(args) != 2:
            raise SyntaxError("过滤 需要谓词和容器")
        pred = evaluator.eval(args[0])
        container = evaluator.eval(args[1])
        if not isinstance(container, (list, ArrayValue)):
            raise TypeError("第二个参数必须是列表或数组")
        result = []
        for item in container:
            res = Builtins._call_function(evaluator, pred, [item])
            # 谓词应返回 TritValue，我们检查其整数值是否为 1（真）
            if isinstance(res, TritValue) and res.to_int() == 1:
                result.append(item)
        return result

    # ── 归并 ──
    @staticmethod
    def reduce_op(evaluator, args):
        if len(args) < 2 or len(args) > 3:
            raise SyntaxError("归并 需要二元函数、容器和可选的初始值")
        func = evaluator.eval(args[0])
        container = evaluator.eval(args[1])
        if not isinstance(container, (list, ArrayValue)):
            raise TypeError("第二个参数必须是列表或数组")
        if len(container) == 0 and len(args) < 3:
            raise ValueError("空容器且无初始值，无法归并")
        if len(args) == 3:
            accumulator = evaluator.eval(args[2])
            start_idx = 0
        else:
            accumulator = container[0]
            start_idx = 1
        for i in range(start_idx, len(container)):
            accumulator = Builtins._call_function(evaluator, func, [accumulator, container[i]])
        return accumulator

    # ── 内部函数调用器 ──
    @staticmethod
    def _call_function(evaluator, func, args):
        """通用函数调用：func 可以是字符串、FunctionValue、或自定义命令名"""
        if isinstance(func, str):
            # 内置操作或自定义命令
            from evaluator import SanyanEvaluator
            if isinstance(evaluator, SanyanEvaluator):
                return evaluator._apply(func, args)
            else:
                # fallback
                return evaluator.eval([func] + args)
        elif isinstance(func, FunctionValue):
            return func.call(evaluator, args)
        else:
            raise TypeError(f"不可调用的对象: {type(func)}")
        
    @staticmethod
    def return_op(evaluator, args):
        """(返回 值) 在函数中提前退出并返回指定值"""
        if len(args) == 0:
            raise ReturnException(TritValue(0))
        value = evaluator.eval(args[0])
        raise ReturnException(value)
    
    @staticmethod
    def time_now(evaluator, args):
        import time
        return TritValue(int(time.time()))  # 返回Unix时间戳整数
    
    # ── 新增实用函数 ──
    @staticmethod
    def sleep_op(evaluator, args):
        import time
        if len(args) != 1:
            raise SyntaxError("等待 需要一个参数（秒数）")
        sec = evaluator.eval(args[0]).to_int()
        try:
            time.sleep(sec)
        except KeyboardInterrupt:
            raise RuntimeError("等待被用户中断（Ctrl+C）")
        return TritValue(0)

    @staticmethod
    def read_file_op(evaluator, args):
        if len(args) != 1:
            raise SyntaxError("读文件 需要文件路径")
        path = evaluator.eval(args[0])
        if hasattr(path, 'to_int'):
            path = str(path.to_int())
        with open(str(path), 'r', encoding='utf-8') as f:
            content = f.read()
        return content

    @staticmethod
    def write_file_op(evaluator, args):
        if len(args) != 2:
            raise SyntaxError("写文件 需要路径和内容")
        path = evaluator.eval(args[0])
        content = evaluator.eval(args[1])
        if hasattr(path, 'to_int'):
            path = str(path.to_int())
        if not isinstance(content, str):
            content = str(content)
        with open(str(path), 'w', encoding='utf-8') as f:
            f.write(content)
        return TritValue(0)

    @staticmethod
    def is_number(evaluator, args):
        if len(args) != 1:
            raise SyntaxError("是数字 需要一个参数")
        val = evaluator.eval(args[0])
        if isinstance(val, TritValue):
            return TritValue(1)
        return TritValue(-1)

    @staticmethod
    def is_string(evaluator, args):
        if len(args) != 1:
            raise SyntaxError("是字符串 需要一个参数")
        val = evaluator.eval(args[0])
        if isinstance(val, str):
            return TritValue(1)
        return TritValue(-1)

    @staticmethod
    def str_equals(evaluator, args):
        if len(args) != 2:
            raise SyntaxError("字符串相等 需要两个参数")
        a = evaluator.eval(args[0])
        b = evaluator.eval(args[1])
        if isinstance(a, str) and isinstance(b, str):
            return TritValue(1 if a == b else -1)
        return TritValue(-1)
    
    @staticmethod
    def try_catch(evaluator, args):
        if len(args) != 2:
            raise SyntaxError("尝试 需要两个参数：尝试体和捕获体")
        try_body = args[0]
        catch_spec = args[1]

        if not isinstance(catch_spec, list) or len(catch_spec) < 2 or catch_spec[0] != '捕获':
            raise SyntaxError("捕获体格式应为 (捕获 (错误变量) 体...)")
        error_var = catch_spec[1]
        if isinstance(error_var, list):
            if len(error_var) != 1:
                raise SyntaxError("捕获的错误变量必须是一个标识符")
            error_var = error_var[0]
        catch_body = catch_spec[2:]

        try:
            return evaluator.eval(try_body)
        except Exception as e:
            saved = None
            if error_var in evaluator.vars:
                saved = evaluator.vars[error_var]
            evaluator.vars[error_var] = str(e)
            try:
                result = None
                for expr in catch_body:
                    result = evaluator.eval(expr)
                return result if result is not None else TritValue(0)
            finally:
                if saved is not None:
                    evaluator.vars[error_var] = saved
                else:
                    if error_var in evaluator.vars:
                        del evaluator.vars[error_var]