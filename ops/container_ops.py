"""容器操作：列表、数组、字典、通用索引、映射/过滤/归并"""
from ternary_core import TritValue, ArrayValue
from values import FunctionValue
from values import call_function

class ContainerOps:
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

    @staticmethod
    def make_lambda(evaluator, args):
        if len(args) < 2:
            raise SyntaxError("λ 需要参数列表和体")
        params = args[0]
        if not isinstance(params, list):
            raise SyntaxError("λ 的参数必须是列表")
        body = args[1:]
        return FunctionValue(params, body)

    @staticmethod
    def apply(evaluator, args):
        if len(args) < 1:
            raise SyntaxError("应用 需要函数和参数")
        func = evaluator.eval(args[0])
        func_args = args[1:]
        return call_function(evaluator, func, func_args)

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
            res = call_function(evaluator, func, [item])
            result.append(res)
        return result

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
            res = call_function(evaluator, pred, [item])
            if isinstance(res, TritValue) and res.to_int() == 1:
                result.append(item)
        return result

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
            accumulator = call_function(evaluator, func, [accumulator, container[i]])
        return accumulator