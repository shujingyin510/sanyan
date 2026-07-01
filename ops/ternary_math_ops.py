"""三态高级数学: 分布、熵、校准"""

import math
from core.ternary_core import TritValue
from core.values import SanyanSyntaxError, SanyanTypeError
from ops.registry import register


def _trit_dist(evaluator, args):
    """三态分布(p真, p假, p可能) — 完整概率三元组。
    p真 + p假 + p可能 = 1.0。
    返回: 三态(真, p真) 如果 p真 最大，否则三态(假, p假) 否则三态(可能, p可能)"""
    if len(args) < 3:
        raise SanyanSyntaxError('三态分布 需要 3 个参数: p真, p假, p可能')

    def _to_float(v):
        if isinstance(v, TritValue):
            return v.to_float()
        return float(v)

    p_true = _to_float(evaluator.eval(args[0]))
    p_false = _to_float(evaluator.eval(args[1]))
    p_maybe = _to_float(evaluator.eval(args[2]))

    total = p_true + p_false + p_maybe
    if total == 0:
        return TritValue(0, confidence=0)
    p_true /= total
    p_false /= total
    p_maybe /= total

    if p_true >= p_false and p_true >= p_maybe:
        return TritValue(1, confidence=p_true)
    elif p_false >= p_true and p_false >= p_maybe:
        return TritValue(-1, confidence=p_false)
    else:
        return TritValue(0, confidence=p_maybe)


def _entropy(evaluator, args):
    """熵(x) — 三态值的信息熵。
    H = -c·log2(c) - (1-c)·log2(1-c)（二值熵）
    纯确定态: H=0（无不确定性）
    完全不确定: H=1（最大熵）"""
    if len(args) != 1:
        raise SanyanSyntaxError('熵 需要一个参数')
    val = evaluator.eval(args[0])
    c = val.confidence if isinstance(val, TritValue) else 1.0
    c = max(0.001, min(0.999, c))
    h = -c * math.log2(c) - (1 - c) * math.log2(1 - c)
    return TritValue(float(h), confidence=1.0)


def _cross_entropy(evaluator, args):
    """交叉熵(p, q) — 两个三态值的交叉熵。
    交叉熵越低 → 越一致。"""
    if len(args) != 2:
        raise SanyanSyntaxError('交叉熵 需要两个参数')
    p = evaluator.eval(args[0])
    q = evaluator.eval(args[1])
    pc = p.confidence if isinstance(p, TritValue) else 1.0
    qc = q.confidence if isinstance(q, TritValue) else 1.0
    pc = max(0.001, min(0.999, pc))
    qc = max(0.001, min(0.999, qc))
    h = -pc * math.log2(qc) - (1 - pc) * math.log2(1 - qc)
    return TritValue(float(h))


def _calibrate(evaluator, args):
    """校准(预测列表, 结果列表) — 在线校准置信度。
    统计预测信度与真实准确率的偏差，返回校准因子。
    校准因子 = 真实准确率 / 预测信度均值"""
    if len(args) < 2:
        raise SanyanSyntaxError('校准 需要预测列表和结果列表')
    predictions = evaluator.eval(args[0])
    results = evaluator.eval(args[1])
    if not isinstance(predictions, list) or not isinstance(results, list):
        raise SanyanTypeError('校准 需要两个列表')
    if len(predictions) != len(results):
        raise SanyanTypeError('预测和结果列表长度必须一致')

    total_confidence = 0.0
    correct = 0.0
    n = len(predictions)
    if n == 0:
        return TritValue(1.0)

    for pred, actual in zip(predictions, results):
        pc = pred.confidence if isinstance(pred, TritValue) else 1.0
        pv = pred.to_int() if isinstance(pred, TritValue) else int(pred)
        av = actual.to_int() if isinstance(actual, TritValue) else int(actual)
        total_confidence += pc
        if pv == av:
            correct += 1.0

    accuracy = correct / n
    avg_confidence = total_confidence / n
    if avg_confidence < 0.001:
        return TritValue(1.0)
    factor = accuracy / avg_confidence
    factor = max(0.1, min(2.0, factor))
    return TritValue(float(factor))


def _observe(evaluator, args):
    """观察(预测, 结果) — 单次观察反馈，更新模型信任度。
    返回校准后的信度 = 原始信度 × 校准因子。
    连续学习: 每次观察自动更新校准因子。"""
    if len(args) < 2:
        raise SanyanSyntaxError('观察 需要预测和结果')
    pred = evaluator.eval(args[0])
    actual = evaluator.eval(args[1])

    pc = pred.confidence if isinstance(pred, TritValue) else 1.0
    pv = pred.to_int() if isinstance(pred, TritValue) else int(pred)
    av = actual.to_int() if isinstance(actual, TritValue) else int(actual)

    # 正确 → 信度上升; 错误 → 信度下降
    if pv == av:
        new_c = min(1.0, pc + (1.0 - pc) * 0.1)
    else:
        new_c = pc * 0.8

    if isinstance(pred, TritValue):
        return pred.with_confidence(new_c)
    return TritValue(pv, confidence=new_c)


register('trit_dist', _trit_dist)
register('entropy', _entropy)
register('cross_entropy', _cross_entropy)
register('calibrate', _calibrate)
register('observe', _observe)
