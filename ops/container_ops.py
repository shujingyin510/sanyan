"""容器操作：列表、数组、字典、通用索引、映射/过滤/归并"""
from ternary_core import TritValue, ArrayValue
from values import FunctionValue, call_function
from values import SanyanSyntaxError, SanyanTypeError, SanyanValueError, SanyanKeyError
from ops.registry import register

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
                raise SanyanTypeError("所有参数必须是列表")
            result.extend(lst)
        return result

    @staticmethod
    def list_length(evaluator, args):
        if len(args) != 1:
            raise SanyanSyntaxError("表长 需要一个列表参数")
        lst = evaluator.eval(args[0])
        if not isinstance(lst, list):
            raise SanyanTypeError("参数必须是列表")
        return TritValue(len(lst))

    @staticmethod
    def array_new(evaluator, args):
        if len(args) == 0 or len(args) > 2:
            raise SanyanSyntaxError("数组 需要一个或两个参数: (数组 长度 [默认值])")
        length = evaluator.eval(args[0]).to_int()
        if length < 0:
            raise SanyanValueError("数组长度不能为负数")
        default = evaluator.eval(args[1]) if len(args) == 2 else TritValue(0)
        return ArrayValue(length, default)

    @staticmethod
    def array_length(evaluator, args):
        if len(args) != 1:
            raise SanyanSyntaxError("组长 需要一个数组参数")
        arr = evaluator.eval(args[0])
        if not isinstance(arr, ArrayValue):
            raise SanyanTypeError("参数必须是数组")
        return TritValue(arr.length)

    @staticmethod
    def array_to_list(evaluator, args):
        if len(args) != 1:
            raise SanyanSyntaxError("数组列 需要一个数组参数")
        arr = evaluator.eval(args[0])
        if not isinstance(arr, ArrayValue):
            raise SanyanTypeError("参数必须是数组")
        return arr.to_list()

    @staticmethod
    def generic_get(evaluator, args):
        if len(args) != 2:
            raise SanyanSyntaxError("取 需要容器和索引")
        container = evaluator.eval(args[0])
        index = evaluator.eval(args[1]).to_int()
        if isinstance(container, (list, ArrayValue)):
            return container[index]
        raise SanyanTypeError("第一个参数必须是列表或数组")

    @staticmethod
    def generic_set(evaluator, args):
        if len(args) != 3:
            raise SanyanSyntaxError("置元素 需要容器、索引和新值")
        container = evaluator.eval(args[0])
        index = evaluator.eval(args[1]).to_int()
        value = evaluator.eval(args[2])
        if isinstance(container, (list, ArrayValue)):
            container[index] = value
            return container
        raise SanyanTypeError("第一个参数必须是列表或数组")

    @staticmethod
    def dict_new(evaluator, args):
        if len(args) % 2 != 0:
            raise SanyanSyntaxError("字典 需要偶数个参数（键值对）")
        d = {}
        for i in range(0, len(args), 2):
            key = evaluator.eval(args[i])
            if isinstance(key, TritValue):
                key = key.to_int()
            value = evaluator.eval(args[i+1])
            d[key] = value
        return d

    @staticmethod
    def dict_contains(evaluator, args):
        if len(args) != 2:
            raise SanyanSyntaxError("含键 需要字典和键")
        d = evaluator.eval(args[0])
        if not isinstance(d, dict):
            raise SanyanTypeError("第一个参数必须是字典")
        key = evaluator.eval(args[1])
        if isinstance(key, TritValue):
            key = key.to_int()
        return TritValue(1 if key in d else -1)

    @staticmethod
    def dict_get(evaluator, args):
        if len(args) != 2:
            raise SanyanSyntaxError("取键 需要字典和键")
        d = evaluator.eval(args[0])
        if not isinstance(d, dict):
            raise SanyanTypeError("第一个参数必须是字典")
        key = evaluator.eval(args[1])
        if isinstance(key, TritValue):
            key = key.to_int()
        try:
            return d[key]
        except KeyError:
            raise SanyanKeyError(f"键不存在: {key}")

    @staticmethod
    def dict_set(evaluator, args):
        if len(args) != 3:
            raise SanyanSyntaxError("置键 需要字典、键和新值")
        d = evaluator.eval(args[0])
        if not isinstance(d, dict):
            raise SanyanTypeError("第一个参数必须是字典")
        key = evaluator.eval(args[1])
        if isinstance(key, TritValue):
            key = key.to_int()
        value = evaluator.eval(args[2])
        d[key] = value
        return d

    @staticmethod
    def make_lambda(evaluator, args):
        if len(args) < 2:
            raise SanyanSyntaxError("λ 需要参数列表和体")
        params = args[0]
        if not isinstance(params, list):
            raise SanyanSyntaxError("λ 的参数必须是列表")
        body = args[1:]
        # 捕获当前变量环境（闭包）
        closure_vars = evaluator.all_scoped_vars()
        return FunctionValue(params, body, closure_vars=closure_vars)

    @staticmethod
    def apply(evaluator, args):
        if len(args) < 1:
            raise SanyanSyntaxError("应用 需要函数和参数")
        func = evaluator.eval(args[0])
        func_args = args[1:]
        return call_function(evaluator, func, func_args)

    @staticmethod
    def map_op(evaluator, args):
        if len(args) != 2:
            raise SanyanSyntaxError("映射 需要函数和容器")
        func = evaluator.eval(args[0])
        container = evaluator.eval(args[1])
        if not isinstance(container, (list, ArrayValue)):
            raise SanyanTypeError("第二个参数必须是列表或数组")
        result = []
        for item in container:
            res = call_function(evaluator, func, [item])
            result.append(res)
        return result

    @staticmethod
    def filter_op(evaluator, args):
        if len(args) != 2:
            raise SanyanSyntaxError("过滤 需要谓词和容器")
        pred = evaluator.eval(args[0])
        container = evaluator.eval(args[1])
        if not isinstance(container, (list, ArrayValue)):
            raise SanyanTypeError("第二个参数必须是列表或数组")
        result = []
        for item in container:
            res = call_function(evaluator, pred, [item])
            if isinstance(res, TritValue) and res.to_int() == 1:
                result.append(item)
        return result

    @staticmethod
    def reduce_op(evaluator, args):
        if len(args) < 2 or len(args) > 3:
            raise SanyanSyntaxError("归并 需要二元函数、容器和可选的初始值")
        func = evaluator.eval(args[0])
        container = evaluator.eval(args[1])
        if not isinstance(container, (list, ArrayValue)):
            raise SanyanTypeError("第二个参数必须是列表或数组")
        if len(container) == 0 and len(args) < 3:
            raise SanyanValueError("空容器且无初始值，无法归并")
        if len(args) == 3:
            accumulator = evaluator.eval(args[2])
            start_idx = 0
        else:
            accumulator = container[0]
            start_idx = 1
        for i in range(start_idx, len(container)):
            accumulator = call_function(evaluator, func, [accumulator, container[i]])
        return accumulator

    @staticmethod
    def list_sort(evaluator, args):
        """排序(container) - 对列表排序（升序）"""
        if len(args) != 1:
            raise SanyanSyntaxError("排序 需要 1 个参数: (排序 列表)")
        container = evaluator.eval(args[0])
        if not isinstance(container, (list, ArrayValue)):
            raise SanyanTypeError("参数必须是列表或数组")
        lst = list(container) if isinstance(container, ArrayValue) else container[:]
        def sort_key(x):
            if isinstance(x, TritValue):
                return x.to_float() if x.is_float() else x.to_int()
            if isinstance(x, str):
                return x
            return 0
        lst.sort(key=sort_key)
        return lst

    @staticmethod
    def list_reverse(evaluator, args):
        """反转(container) - 反转列表"""
        if len(args) != 1:
            raise SanyanSyntaxError("反转 需要 1 个参数: (反转 列表)")
        container = evaluator.eval(args[0])
        if not isinstance(container, (list, ArrayValue)):
            raise SanyanTypeError("参数必须是列表或数组")
        lst = list(container) if isinstance(container, ArrayValue) else container[:]
        lst.reverse()
        return lst

    @staticmethod
    def list_contains(evaluator, args):
        """包含(container, item) - 检查列表是否包含元素"""
        if len(args) != 2:
            raise SanyanSyntaxError("包含 需要 2 个参数: (包含 列表 元素)")
        container = evaluator.eval(args[0])
        if not isinstance(container, (list, ArrayValue)):
            raise SanyanTypeError("第一个参数必须是列表或数组")
        item = evaluator.eval(args[1])
        target = item.to_float() if isinstance(item, TritValue) and item.is_float() else item.to_int() if isinstance(item, TritValue) else item
        for elem in container:
            val = elem.to_float() if isinstance(elem, TritValue) and elem.is_float() else elem.to_int() if isinstance(elem, TritValue) else elem
            if val == target:
                return TritValue(1)
        return TritValue(-1)

    @staticmethod
    def list_unique(evaluator, args):
        """去重(container) - 去除列表中的重复元素"""
        if len(args) != 1:
            raise SanyanSyntaxError("去重 需要 1 个参数: (去重 列表)")
        container = evaluator.eval(args[0])
        if not isinstance(container, (list, ArrayValue)):
            raise SanyanTypeError("参数必须是列表或数组")
        seen = []
        result = []
        for item in container:
            key = item.to_float() if isinstance(item, TritValue) and item.is_float() else item.to_int() if isinstance(item, TritValue) else item
            if key not in seen:
                seen.append(key)
                result.append(item)
        return result

    @staticmethod
    def list_slice(evaluator, args):
        """切片(container, start, end) - 提取子列表"""
        if len(args) < 2 or len(args) > 3:
            raise SanyanSyntaxError("切片 需要 2-3 个参数: (切片 列表 起始 [结束])")
        container = evaluator.eval(args[0])
        if not isinstance(container, (list, ArrayValue)):
            raise SanyanTypeError("第一个参数必须是列表或数组")
        start = evaluator.eval(args[1]).to_int()
        if len(args) == 3:
            end = evaluator.eval(args[2]).to_int()
            return list(container)[start:end]
        return list(container)[start:]

    @staticmethod
    def list_count(evaluator, args):
        if len(args) != 2: raise SanyanSyntaxError("计数 需要两个参数")
        lst = evaluator.eval(args[0])
        item = evaluator.eval(args[1])
        if not isinstance(lst, list): return TritValue(0)

        target = item.to_float() if isinstance(item, TritValue) and item.is_float() else item.to_int() if isinstance(item, TritValue) else item
        n = 0
        for elem in lst:
            val = elem.to_float() if isinstance(elem, TritValue) and elem.is_float() else elem.to_int() if isinstance(elem, TritValue) else elem
            if val == target:
                n += 1
        return TritValue(n)

    @staticmethod
    def list_sum(evaluator, args):
        """求和(container) - 计算列表元素之和"""
        if len(args) != 1:
            raise SanyanSyntaxError("求和 需要 1 个参数: (求和 列表)")
        container = evaluator.eval(args[0])
        if not isinstance(container, (list, ArrayValue)):
            raise SanyanTypeError("参数必须是列表或数组")
        has_float = any(isinstance(item, TritValue) and item.is_float() for item in container)
        if has_float:
            total = 0.0
            for item in container:
                if isinstance(item, TritValue):
                    total += item.to_float()
                elif isinstance(item, (int, float)):
                    total += float(item)
            return TritValue(total)
        total = 0
        for item in container:
            if isinstance(item, TritValue):
                total += item.to_int()
            elif isinstance(item, (int, float)):
                total += int(item)
        return TritValue(total)

    @staticmethod
    def list_join(evaluator, args):
        """合并(container, delimiter) - 用分隔符合并列表为字符串"""
        if len(args) != 2:
            raise SanyanSyntaxError("合并 需要 2 个参数: (合并 列表 分隔符)")
        container = evaluator.eval(args[0])
        if not isinstance(container, (list, ArrayValue)):
            raise SanyanTypeError("第一个参数必须是列表或数组")
        delim = evaluator.eval(args[1])
        if not isinstance(delim, str):
            delim = str(delim)
        parts = []
        for item in container:
            if isinstance(item, TritValue):
                if item.is_float():
                    parts.append(str(item.to_float()))
                else:
                    parts.append(str(item.to_int()))
            else:
                parts.append(str(item))
        return delim.join(parts)

# 注册容器操作
register('list', ContainerOps.list_new)
register('list_concat', ContainerOps.list_concat)
register('list_len', ContainerOps.list_length)
register('count', ContainerOps.list_count)
register('array', ContainerOps.array_new)
register('array_len', ContainerOps.array_length)
register('array_to_list', ContainerOps.array_to_list)
register('get', ContainerOps.generic_get)
register('set_element', ContainerOps.generic_set)
register('dict', ContainerOps.dict_new)
register('dict_contains', ContainerOps.dict_contains)
register('get_key', ContainerOps.dict_get)
register('set_key', ContainerOps.dict_set)
register('lambda', ContainerOps.make_lambda)
register('apply', ContainerOps.apply)
register('map', ContainerOps.map_op)
register('filter', ContainerOps.filter_op)
register('reduce', ContainerOps.reduce_op)
register('sort', ContainerOps.list_sort)
register('reverse', ContainerOps.list_reverse)
register('contains', ContainerOps.list_contains)
register('unique', ContainerOps.list_unique)
register('slice', ContainerOps.list_slice)
register('sum', ContainerOps.list_sum)
register('join', ContainerOps.list_join)
