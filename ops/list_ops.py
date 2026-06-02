"""列表和数组操作：创建、长度、索引、切片、排序、反转、去重、求和等。"""

from typing import Any

from ternary_core import TritValue, ArrayValue
from values import SanyanSyntaxError, SanyanTypeError, SanyanValueError, SanyanKeyError, to_num
from ops.registry import register


def _as_list(val):
    """将 ArrayValue 转为 Python list，其他类型原样返回。"""
    if isinstance(val, ArrayValue):
        return val.data
    return val


# ── 列表基础 ──


def _list_new(evaluator, args):
    """创建列表：列表(元素...) → [元素...]"""
    return [evaluator.eval(a) for a in args]


def _list_concat(evaluator, args):
    """列表合并：列表合(list1, list2, ...) → 合并后的列表"""
    if not args:
        return []
    result = evaluator.eval(args[0])
    if not isinstance(result, list):
        raise SanyanTypeError('所有参数必须是列表')
    for arg in args[1:]:
        lst = evaluator.eval(arg)
        if not isinstance(lst, list):
            raise SanyanTypeError('所有参数必须是列表')
        result.extend(lst)
    return result


def _list_length(evaluator, args):
    """列表长度：取长(list) → 元素个数"""
    if len(args) != 1:
        raise SanyanSyntaxError('表长 需要一个列表参数')
    lst = evaluator.eval(args[0])
    if not isinstance(lst, list):
        raise SanyanTypeError('参数必须是列表')
    return TritValue(len(lst))


# ── 数组操作 ──


def _array_new(evaluator, args):
    """数组：数组(长度 [默认值])"""
    if len(args) == 0 or len(args) > 2:
        raise SanyanSyntaxError('数组 需要一个或两个参数: (数组 长度 [默认值])')
    length = evaluator.eval(args[0]).to_int()
    if length < 0:
        raise SanyanValueError('数组长度不能为负数')
    default = evaluator.eval(args[1]) if len(args) == 2 else TritValue(0)
    return ArrayValue(length, default)


def _array_length(evaluator, args):
    """数组长度：组长(arr)"""
    if len(args) != 1:
        raise SanyanSyntaxError('组长 需要一个数组参数')
    arr = evaluator.eval(args[0])
    if not isinstance(arr, ArrayValue):
        raise SanyanTypeError('参数必须是数组')
    return TritValue(arr.length)


def _array_to_list(evaluator, args):
    """数组转列表：数组列(arr)"""
    if len(args) != 1:
        raise SanyanSyntaxError('数组列 需要一个数组参数')
    arr = evaluator.eval(args[0])
    if not isinstance(arr, ArrayValue):
        raise SanyanTypeError('参数必须是数组')
    return arr.to_list()


# ── 通用容器访问 ──


def _generic_get(evaluator, args):
    """通用取值：取(容器, 索引) → 元素。支持列表/数组/字典。"""
    if len(args) != 2:
        raise SanyanSyntaxError('取 需要容器和索引')
    container = evaluator.eval(args[0])
    raw_index = evaluator.eval(args[1])
    index: Any
    if isinstance(raw_index, str):
        index = raw_index
    elif isinstance(raw_index, TritValue):
        index = raw_index.to_int()
    else:
        index = raw_index
    if isinstance(container, dict):
        if isinstance(index, str):
            if index in container:
                return container[index]
            raise SanyanKeyError(f'键 {index!r} 不存在')
        raise SanyanTypeError('字典键必须是字符串')
    if isinstance(container, (list, ArrayValue)):
        try:
            return container[index]
        except (IndexError, ValueError, TypeError):
            return 0
    raise SanyanTypeError('第一个参数必须是列表、数组或字典')


def _generic_set(evaluator, args):
    """通用设值：置元素(容器, 索引, 新值)"""
    if len(args) != 3:
        raise SanyanSyntaxError('置元素 需要容器、索引和新值')
    container = evaluator.eval(args[0])
    index = evaluator.eval(args[1]).to_int()
    value = evaluator.eval(args[2])
    if isinstance(container, (list, ArrayValue)):
        container[index] = value
        return container
    raise SanyanTypeError('第一个参数必须是列表或数组')


# ── 列表高级操作 ──


def _list_sort(evaluator, args):
    """排序：对列表升序排列"""
    if len(args) != 1:
        raise SanyanSyntaxError('排序 需要 1 个参数: (排序 列表)')
    container = evaluator.eval(args[0])
    if not isinstance(container, (list, ArrayValue)):
        raise SanyanTypeError('参数必须是列表或数组')
    lst = _as_list(container)[:]
    lst.sort(key=lambda x: to_num(x) if not isinstance(x, str) else x)
    return lst


def _list_reverse(evaluator, args):
    """反转：反转列表"""
    if len(args) != 1:
        raise SanyanSyntaxError('反转 需要 1 个参数: (反转 列表)')
    container = evaluator.eval(args[0])
    if not isinstance(container, (list, ArrayValue)):
        raise SanyanTypeError('参数必须是列表或数组')
    lst = _as_list(container)[:]
    lst.reverse()
    return lst


def _list_contains(evaluator, args):
    """包含：检查列表是否包含元素"""
    if len(args) != 2:
        raise SanyanSyntaxError('包含 需要 2 个参数: (包含 列表 元素)')
    container = evaluator.eval(args[0])
    if not isinstance(container, (list, ArrayValue)):
        raise SanyanTypeError('第一个参数必须是列表或数组')
    target = to_num(evaluator.eval(args[1]))
    for elem in container:
        if to_num(elem) == target:
            return TritValue(1)
    return TritValue(-1)


def _list_unique(evaluator, args):
    """去重：去除列表中的重复元素"""
    if len(args) != 1:
        raise SanyanSyntaxError('去重 需要 1 个参数: (去重 列表)')
    container = evaluator.eval(args[0])
    if not isinstance(container, (list, ArrayValue)):
        raise SanyanTypeError('参数必须是列表或数组')
    seen = []
    result = []
    for item in _as_list(container):
        key = to_num(item)
        if key not in seen:
            seen.append(key)
            result.append(item)
    return result


def _list_slice(evaluator, args):
    """切片：提取子列表"""
    if len(args) < 2 or len(args) > 3:
        raise SanyanSyntaxError('切片 需要 2-3 个参数: (切片 列表 起始 [结束])')
    container = evaluator.eval(args[0])
    if not isinstance(container, (list, ArrayValue)):
        raise SanyanTypeError('第一个参数必须是列表或数组')
    start = evaluator.eval(args[1]).to_int()
    if len(args) == 3:
        end = evaluator.eval(args[2]).to_int()
        return _as_list(container)[start:end]
    return _as_list(container)[start:]


def _list_count(evaluator, args):
    """计数：统计元素出现次数"""
    if len(args) != 2:
        raise SanyanSyntaxError('计数 需要两个参数')
    lst = evaluator.eval(args[0])
    if not isinstance(lst, list):
        return TritValue(0)
    target = to_num(evaluator.eval(args[1]))
    return TritValue(sum(1 for elem in lst if to_num(elem) == target))


def _list_sum(evaluator, args):
    """求和：计算列表元素之和"""
    if len(args) != 1:
        raise SanyanSyntaxError('求和 需要 1 个参数: (求和 列表)')
    container = evaluator.eval(args[0])
    if not isinstance(container, (list, ArrayValue)):
        raise SanyanTypeError('参数必须是列表或数组')
    container = _as_list(container)
    has_float = any(isinstance(item, TritValue) and item.is_float() for item in container)
    if has_float:
        total = 0.0
        for item in container:
            if isinstance(item, TritValue):
                total += item.to_float()
            elif isinstance(item, (int, float)):
                total += float(item)
            else:
                raise SanyanTypeError(f'求和遇到非数字元素: {type(item).__name__}')
        return TritValue(total)
    total = 0
    for item in container:
        if isinstance(item, TritValue):
            total += item.to_int()
        elif isinstance(item, (int, float)):
            total += int(item)
        else:
            raise SanyanTypeError(f'求和遇到非数字元素: {type(item).__name__}')
    return TritValue(total)


def _list_join(evaluator, args):
    """合并：用分隔符合并列表为字符串"""
    if len(args) != 2:
        raise SanyanSyntaxError('合并 需要 2 个参数: (合并 列表 分隔符)')
    container = evaluator.eval(args[0])
    if not isinstance(container, (list, ArrayValue)):
        raise SanyanTypeError('第一个参数必须是列表或数组')
    delim = evaluator.eval(args[1])
    if not isinstance(delim, str):
        delim = str(delim)
    parts = []
    for item in _as_list(container):
        if isinstance(item, TritValue):
            parts.append(str(item.to_float() if item.is_float() else item.to_int()))
        else:
            parts.append(str(item))
    return delim.join(parts)


# ── 注册 ──
register('list', _list_new)
register('list_concat', _list_concat)
register('list_len', _list_length)
register('count', _list_count)
register('array', _array_new)
register('array_len', _array_length)
register('array_to_list', _array_to_list)
register('get', _generic_get)
register('set_element', _generic_set)
register('sort', _list_sort)
register('reverse', _list_reverse)
register('contains', _list_contains)
register('unique', _list_unique)
register('slice', _list_slice)
register('sum', _list_sum)

# ── 二分查找 ──


def _binary_search(evaluator, args):
    """二分查找(有序列表, 目标): 返回索引，未找到返回 -1"""
    if len(args) != 2:
        raise SanyanSyntaxError('二分查找 需要列表和目标值')
    lst = evaluator.eval(args[0])
    target = evaluator.eval(args[1])
    if not isinstance(lst, list):
        raise SanyanTypeError('二分查找 需要有序列表')
    tv = target.to_int() if isinstance(target, TritValue) else target

    lo, hi = 0, len(lst) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        item = lst[mid]
        iv = item.to_int() if isinstance(item, TritValue) else item
        if iv == tv:
            return TritValue(mid)
        elif iv < tv:
            lo = mid + 1
        else:
            hi = mid - 1
    return TritValue(-1)


register('binary_search', _binary_search)
register('join', _list_join)
