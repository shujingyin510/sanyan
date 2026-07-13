"""规划关键字实现：置信度/信度传播/清空/克隆/掩码/约束桩/读取/写入/行号

所有新增操作在此文件中实现并注册。嵌入式/结构等复杂关键字留桩。
"""

from __future__ import annotations

from core.ternary_core import TritValue
from core.values import SanyanSyntaxError, SanyanTypeError, SanyanValueError
from ops.registry import register, register_alias

# ═══════════════════════════════════════════════════════
# 置信度 / 信度传播
# ═══════════════════════════════════════════════════════


def _confidence_op(evaluator, args):
    """置信度(值) → float: 获取值的置信度。非 TritValue 返回 1.0。"""
    if len(args) < 1:
        raise SanyanSyntaxError('置信度 需要一个参数')
    val = evaluator.eval(args[0])
    if isinstance(val, TritValue) and hasattr(val, 'confidence'):
        return val.confidence
    return 1.0


def _propagate_confidence_op(evaluator, args):
    """信度传播(上游, 当前) → TritValue: 上游信度 × 当前信度。"""
    if len(args) < 2:
        raise SanyanSyntaxError('信度传播 需要两个参数（上游, 当前）')
    upstream = evaluator.eval(args[0])
    current = evaluator.eval(args[1])
    uc = upstream.confidence if isinstance(upstream, TritValue) and hasattr(upstream, 'confidence') else 1.0
    cc = current.confidence if isinstance(current, TritValue) and hasattr(current, 'confidence') else 1.0
    return TritValue(current.to_int() if isinstance(current, TritValue) else int(current), confidence=uc * cc)


# ═══════════════════════════════════════════════════════
# 清空 / 克隆
# ═══════════════════════════════════════════════════════


def _clear_op(evaluator, args):
    """清空(容器) → 返回空容器。支持列表/字典/三态集/三态队列/三态栈。"""
    if len(args) < 1:
        raise SanyanSyntaxError('清空 需要一个参数（容器）')
    container = evaluator.eval(args[0])
    if isinstance(container, list):
        container.clear()
        return container
    if isinstance(container, dict):
        container.clear()
        return container
    # 检查三态容器（通过方法名判断）
    if hasattr(container, 'clear'):
        container.clear()
        return container
    raise SanyanTypeError(f'清空 不支持的类型: {type(container).__name__}')


def _clone_op(evaluator, args):
    """克隆(值) → 深拷贝。支持 TritValue/列表/字典。"""
    if len(args) < 1:
        raise SanyanSyntaxError('克隆 需要一个参数')
    val = evaluator.eval(args[0])
    if isinstance(val, TritValue):
        conf = val.confidence if hasattr(val, 'confidence') else 1.0
        return TritValue(val.to_int(), confidence=conf)
    if isinstance(val, list):
        return list(val)
    if isinstance(val, dict):
        return dict(val)
    return val


# ═══════════════════════════════════════════════════════
# 掩码
# ═══════════════════════════════════════════════════════


def _mask_op(evaluator, args):
    """掩码(值, 掩码) → 按位与结果。用于底层寄存器操作。"""
    if len(args) < 2:
        raise SanyanSyntaxError('掩码 需要两个参数（值, 掩码）')
    val = evaluator.eval(args[0])
    mask = evaluator.eval(args[1])
    vi = val.to_int() if isinstance(val, TritValue) else int(val)
    mi = mask.to_int() if isinstance(mask, TritValue) else int(mask)
    return TritValue(vi & mi)


# ═══════════════════════════════════════════════════════
# 读取 / 写入（语义微操：流式 vs 原子）
# ═══════════════════════════════════════════════════════


def _read_stream_op(evaluator, args):
    """读取(源) → 带置信度的流式读取。当前为桩：包装原子 read 并附加置信度 0.9。"""
    if len(args) < 1:
        raise SanyanSyntaxError('读取 需要一个参数')
    val = evaluator.eval(args[0])
    if isinstance(val, TritValue):
        return TritValue(val.to_int(), confidence=0.9)
    return val


def _write_trigger_op(evaluator, args):
    """写入(目标, 值) → 触发式写入。当前为桩：调用原子 write 后返回确认。"""
    if len(args) < 2:
        raise SanyanSyntaxError('写入 需要两个参数（目标, 值）')
    from ops.io_ops import _write_io

    try:
        _write_io(evaluator, args)
    except Exception:
        pass
    return TritValue(1, confidence=0.9)


# ═══════════════════════════════════════════════════════
# 行号
# ═══════════════════════════════════════════════════════


def _line_number_op(evaluator, args):
    """行号() → int: 获取当前执行位置的行号。桩：返回 -1。"""
    return TritValue(-1)


# ═══════════════════════════════════════════════════════
# 约束/权限 桩（用户晚上自测，目前只注册接口）
# ═══════════════════════════════════════════════════════


def _grant_op(evaluator, args):
    """许(条件) → 真: 主动授权。桩实现：始终返回真。"""
    if len(args) < 1:
        raise SanyanSyntaxError('许 需要一个条件参数')
    evaluator.eval(args[0])
    return TritValue(1)


def _allow_op(evaluator, args):
    """允许(x) → x: 修饰子（Modifier），透传 x 的实际判——态度是"容忍可能"，
    不改 x 的真假（annotate 非 map）。区别于构造子 许/禁（制造固定判值）。

    "可容忍"元数据标记暂不挂：需 TritValue 元通道 + "可能即错"消费方（严格判/
    断言），二者动核心值类型、波及 VM/字节码——与 D4「因」字段合并为**一次**
    TritValue 演化（等真实消费者出现再升，先透传诚实恒等）。见 约束-方向研究 §D1/§D4。"""
    if len(args) < 1:
        raise SanyanSyntaxError('允许 需要一个参数')
    return evaluator.eval(args[0])


def _restrict_op(evaluator, args):
    """只许(值, 白名单...) → 值或假: 排他性锁定。桩实现：检查值是否在白名单中。"""
    if len(args) < 2:
        raise SanyanSyntaxError('只许 需要至少两个参数（值, 允许值...）')
    val = evaluator.eval(args[0])
    vi = val.to_int() if isinstance(val, TritValue) else int(val)
    for i in range(1, len(args)):
        allowed = evaluator.eval(args[i])
        ai = allowed.to_int() if isinstance(allowed, TritValue) else int(allowed)
        if vi == ai:
            return val
    return TritValue(-1)


def _deny_op(evaluator, args):
    """禁(条件) → 假: 绝对禁止。桩实现：始终返回假。"""
    if len(args) < 1:
        raise SanyanSyntaxError('禁 需要一个条件参数')
    evaluator.eval(args[0])
    return TritValue(-1)


# ═══════════════════════════════════════════════════════
# 嵌入式/结构 桩
# ═══════════════════════════════════════════════════════


def _interrupt_op(evaluator, args):
    """中断(引脚, 边沿, 处理函数) → 绑定硬件中断。桩：未实现。"""
    raise SanyanValueError('中断：嵌入式硬件中断未实现（需要平台支持）')


def _bind_op(evaluator, args):
    """绑定(引脚, 变量) → 将物理引脚绑定到三态变量。桩：未实现。"""
    raise SanyanValueError('绑定：硬件引脚绑定未实现（需要平台支持）')


def _struct_op(evaluator, args):
    """结构(名称, 字段定义...) → 定义数据结构。桩：未实现。"""
    raise SanyanValueError('结构：数据结构定义未实现（类型系统扩展中）')


def _instance_op(evaluator, args):
    """实例(结构名, 值...) → 实例化结构。桩：未实现。"""
    raise SanyanValueError('实例：结构体实例化未实现（类型系统扩展中）')


def _trait_op(evaluator, args):
    """特征(名称, 方法...) → 定义接口/协议。桩：未实现。"""
    raise SanyanValueError('特征：接口协议未实现（类型系统扩展中）')


# ═══════════════════════════════════════════════════════
# 注册
# ═══════════════════════════════════════════════════════

# 置信度
register('confidence', _confidence_op)
register_alias('置信度', 'confidence')

# 信度传播
register('propagate_confidence', _propagate_confidence_op)
register_alias('信度传播', 'propagate_confidence')

# 清空
register('clear', _clear_op)
register_alias('清空', 'clear')

# 克隆
register('clone', _clone_op)
register_alias('克隆', 'clone')

# 掩码
register('mask', _mask_op)
register_alias('掩码', 'mask')

# 读取 / 写入（流式语义）
register('read_stream', _read_stream_op)
# '读取' 在 language/chinese.json 中已映射为 'read'（传感器读），流式版本暂用英文名

register('write_trigger', _write_trigger_op)
register_alias('写入', 'write_trigger')

# 行号
register('line_number', _line_number_op)
register_alias('行号', 'line_number')

# 约束/权限 桩
register('grant', _grant_op)
register_alias('许', 'grant')

register('allow', _allow_op)
register_alias('允许', 'allow')

register('restrict', _restrict_op)
register_alias('只许', 'restrict')

register('deny', _deny_op)
register_alias('禁', 'deny')

# 嵌入式/结构 桩
register('interrupt', _interrupt_op)
register_alias('中断', 'interrupt')

register('bind_pin', _bind_op)
register_alias('绑定', 'bind_pin')

register('define_struct', _struct_op)
register_alias('结构', 'define_struct')

register('make_instance', _instance_op)
register_alias('实例', 'make_instance')

register('define_trait', _trait_op)
register_alias('特征', 'define_trait')
