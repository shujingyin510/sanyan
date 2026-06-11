"""三态容器操作: 列表、字典，每个元素带独立置信度、链式信度传播"""

from ternary_core import TritValue
from values import SanyanSyntaxError, SanyanTypeError, SanyanValueError, SanyanRuntimeError
from ops.registry import register, register_alias


def _trit_list(evaluator, args):
    """三态列(a, b, c) — 创建三态列表。每个元素自动包装为 TritValue。"""
    vals = [evaluator.eval(a) for a in args]
    result = []
    for v in vals:
        if isinstance(v, TritValue):
            result.append(v)
        elif isinstance(v, (int, float)):
            result.append(TritValue(v))
        elif isinstance(v, str):
            result.append(TritValue(v))
        else:
            result.append(v)
    return result  # Python list of TritValues


def _trit_get(evaluator, args):
    """三态取(lst, idx) — 取列表元素，保持其置信度。"""
    if len(args) != 2:
        raise SanyanSyntaxError('三态取 需要列表和索引')
    lst = evaluator.eval(args[0])
    idx = evaluator.eval(args[1])
    if isinstance(idx, TritValue):
        idx = idx.to_int()
    if not isinstance(lst, list):
        raise SanyanTypeError('三态取 的第一个参数必须是列表')
    if idx < 0 or idx >= len(lst):
        raise SanyanTypeError(f'三态取 索引越界: {idx}')
    return lst[idx]


def _trit_set(evaluator, args):
    """三态置(lst, idx, val) — 设置列表元素，保持其置信度。"""
    if len(args) != 3:
        raise SanyanSyntaxError('三态置 需要列表、索引和值')
    lst = evaluator.eval(args[0])
    idx = evaluator.eval(args[1])
    val = evaluator.eval(args[2])
    if isinstance(idx, TritValue):
        idx = idx.to_int()
    if not isinstance(lst, list):
        raise SanyanTypeError('三态置 的第一个参数必须是列表')
    if idx < 0 or idx >= len(lst):
        raise SanyanValueError(f'三态置 索引 {idx} 越界（列表长度 {len(lst)}）')
    lst[idx] = val if isinstance(val, TritValue) else TritValue(val)
    return TritValue(0)


def _trit_list_len(evaluator, args):
    """三态列长(lst) — 列表长度"""
    if len(args) != 1:
        raise SanyanSyntaxError('三态列长 需要一个参数')
    lst = evaluator.eval(args[0])
    if not isinstance(lst, list):
        raise SanyanTypeError('三态列长 的参数必须是列表')
    return TritValue(len(lst))


def _trit_list_map(evaluator, args):
    """三态映射(lst, fn) — 对列表每个元素应用函数，保持独立信度。"""
    if len(args) != 2:
        raise SanyanSyntaxError('三态映射 需要列表和函数名')
    lst = evaluator.eval(args[0])
    fn_name = args[1]
    if isinstance(fn_name, list):
        fn_name = fn_name[0] if fn_name else ''
    if not isinstance(lst, list):
        raise SanyanTypeError('三态映射 的第一个参数必须是列表')
    result = []
    for item in lst:
        r = evaluator.eval([fn_name, item])
        result.append(r)
    return result


def _trit_dict(evaluator, args):
    """三态字典(k1=v1, k2=v2) — 创建三态字典，值保留信度。"""
    if len(args) % 2 != 0:
        raise SanyanSyntaxError('三态字典 需要成对的键和值')
    result = {}
    for i in range(0, len(args), 2):
        key = evaluator.eval(args[i])
        val = evaluator.eval(args[i + 1])
        if isinstance(key, TritValue) and key.is_string():
            key = key.to_payload()
        if isinstance(key, TritValue):
            key = str(key.to_int())
        val = val if isinstance(val, TritValue) else TritValue(val)
        result[key] = val
    return result


def _trit_key_get(evaluator, args):
    """三态键(d, key) — 取字典值，保持信度。"""
    if len(args) != 2:
        raise SanyanSyntaxError('三态键 需要字典和键名')
    d = evaluator.eval(args[0])
    key = evaluator.eval(args[1])
    if isinstance(key, TritValue) and key.is_string():
        key = key.to_payload()
    if isinstance(key, TritValue):
        key = str(key.to_int())
    if not isinstance(d, dict):
        raise SanyanTypeError('三态键 的第一个参数必须是字典')
    if key not in d:
        return TritValue(0)  # 不存在→可能
    return d[key]


def _trit_key_set(evaluator, args):
    """三态置键(d, key, val) — 设置字典值，保持信度。"""
    if len(args) != 3:
        raise SanyanSyntaxError('三态置键 需要字典、键名和值')
    d = evaluator.eval(args[0])
    key = evaluator.eval(args[1])
    val = evaluator.eval(args[2])
    if isinstance(key, TritValue) and key.is_string():
        key = key.to_payload()
    if isinstance(key, TritValue):
        key = str(key.to_int())
    d[key] = val if isinstance(val, TritValue) else TritValue(val)
    return TritValue(0)


register('trit_list', _trit_list)
register('trit_get', _trit_get)
register('trit_set', _trit_set)
register('trit_list_len', _trit_list_len)
register('trit_list_map', _trit_list_map)
register('trit_dict', _trit_dict)
register('trit_key_get', _trit_key_get)
register('trit_key_set', _trit_key_set)


# ── 链式信度传播操作 ──


def _chain(evaluator, args):
    """链(步骤1, 步骤2, ...) — 链式执行，置信度逐级传播。

    每个步骤返回的置信度会乘到后续步骤的置信度上。
    任一步骤返回假(-1)时链中断，返回可能(0)时降低后续置信度。

    示例：链(传感器读数, 数据清洗, 结果验证)
    """
    if not args:
        return TritValue(0)

    chain_conf = 1.0
    last_result = TritValue(0)

    for step in args:
        result = evaluator.eval(step)

        if isinstance(result, TritValue):
            last_result = result
            # 置信度传播：当前置信度 × 步骤置信度
            chain_conf *= result.confidence

            # 用 to_int() 获取整数值，而非 value[0]（多位数时 value[0] 是最高位 trit）
            int_val = result.to_int()

            # 如果步骤返回假，链中断
            if int_val == -1:
                return TritValue(-1, confidence=chain_conf)

            # 如果步骤返回可能，降低后续置信度
            if int_val == 0:
                chain_conf *= 0.8
        else:
            # 非三态值视为真
            last_result = TritValue(1, confidence=chain_conf)

    # 返回最终结果，置信度为链式传播后的值
    if isinstance(last_result, TritValue):
        return TritValue(last_result.value, confidence=chain_conf)
    return TritValue(1, confidence=chain_conf)


def _chain_or_break(evaluator, args):
    """链断(步骤1, 步骤2, ...) — 链式执行，假值中断并抛出异常。

    与链()类似，但假值会抛出 SanyanRuntimeError 而非静默返回。
    """
    if not args:
        return TritValue(0)

    chain_conf = 1.0

    for i, step in enumerate(args):
        result = evaluator.eval(step)

        if isinstance(result, TritValue):
            chain_conf *= result.confidence

            int_val = result.to_int()
            if int_val == -1:
                raise SanyanRuntimeError(f'链断: 步骤 {i + 1} 返回假，链中断')

            if int_val == 0:
                chain_conf *= 0.8
        else:
            chain_conf *= 1.0

    return TritValue(1, confidence=chain_conf)


def _unwrap(evaluator, args):
    """解包(值 [, 默认值]) — 解包三态值，可能时返回默认值。

    - 真(1) → 返回值
    - 假(-1) → 抛出异常
    - 可能(0) → 返回默认值（未指定则抛出异常）
    """
    if len(args) < 1:
        raise SanyanSyntaxError('解包 需要至少一个参数')

    val = evaluator.eval(args[0])

    if not isinstance(val, TritValue):
        return val

    int_val = val.to_int()
    if int_val == 1:
        return val
    elif int_val == -1:
        raise SanyanRuntimeError(f'解包失败: 值为假 (置信度: {val.confidence:.2f})')
    else:
        # 可能
        if len(args) >= 2:
            return evaluator.eval(args[1])
        raise SanyanRuntimeError(f'解包失败: 值为可能 (置信度: {val.confidence:.2f})')


def _unwrap_or(evaluator, args):
    """或解(值, 默认值) — 解包三态值，可能/假时返回默认值。"""
    if len(args) != 2:
        raise SanyanSyntaxError('或解 需要两个参数')

    val = evaluator.eval(args[0])
    default = evaluator.eval(args[1])

    if not isinstance(val, TritValue):
        return val

    if val.to_int() == 1:
        return val
    else:
        return default


def _try_chain(evaluator, args):
    """尝试链(步骤1, 步骤2, ..., 默认值) — 链式执行，失败时返回默认值。

    每个步骤尝试执行，失败时跳过并继续下一步。
    全部失败时返回默认值。
    """
    if len(args) < 1:
        raise SanyanSyntaxError('尝试链 需要至少一个参数')

    default = TritValue(0)
    steps = args

    # 如果最后一个参数是默认值标记
    if len(args) >= 2:
        last = args[-1]
        if isinstance(last, list) and last and last[0] == '默认':
            steps = args[:-1]
            default = evaluator.eval(last[1]) if len(last) > 1 else TritValue(0)

    for step in steps:
        try:
            result = evaluator.eval(step)
            if isinstance(result, TritValue) and result.to_int() == 1:
                return result
        except Exception:
            continue

    return default


def _confidence_guard(evaluator, args):
    """信度守卫(值, 阈值) { 高→..., 低→... } — 置信度门控。

    根据置信度阈值决定执行哪个分支：
    - 高：置信度 >= 阈值
    - 低：置信度 < 阈值
    """
    if len(args) < 2:
        raise SanyanSyntaxError('信度守卫 需要值和阈值')

    val = evaluator.eval(args[0])
    threshold_val = evaluator.eval(args[1])
    threshold = threshold_val.to_float() if isinstance(threshold_val, TritValue) else float(threshold_val)

    if not isinstance(val, TritValue):
        conf = 1.0
    else:
        conf = val.confidence

    # 解析分支
    branches = args[2:]
    for i in range(0, len(branches), 2):
        if i + 1 >= len(branches):
            break

        pattern_node = branches[i]
        body_node = branches[i + 1]

        pattern_str = ''
        if isinstance(pattern_node, str):
            pattern_str = pattern_node
        elif isinstance(pattern_node, list) and pattern_node:
            pattern_str = pattern_node[0] if isinstance(pattern_node[0], str) else str(pattern_node[0])

        if pattern_str in ('高', 'high', '通过'):
            if conf >= threshold:
                return evaluator.eval(body_node)
        elif pattern_str in ('低', 'low', '失败'):
            if conf < threshold:
                return evaluator.eval(body_node)

    return TritValue(0)


register('链', _chain)
register('链断', _chain_or_break)
register('解包', _unwrap)
register('或解', _unwrap_or)
register('尝试链', _try_chain)
register('信度守卫', _confidence_guard)

register_alias('chain', '链')
register_alias('chain_or_break', '链断')
register_alias('unwrap', '解包')
register_alias('unwrap_or', '或解')
register_alias('try_chain', '尝试链')
register_alias('confidence_guard', '信度守卫')

# ternary_container_ops 也注册三态基础操作的中文名
register_alias('三态列', 'trit_list')
register_alias('三态取', 'trit_get')
register_alias('三态置', 'trit_set')
register_alias('三态列长', 'trit_list_len')
register_alias('三态映射', 'trit_list_map')
register_alias('三态字典', 'trit_dict')
register_alias('三态键', 'trit_key_get')
register_alias('三态置键', 'trit_key_set')
register_alias('confidence_guard', '信度守卫')
