"""三态来源/证据链、冲突模型、置信度操作"""

from ternary_core import TritValue
from values import SanyanSyntaxError, SanyanTypeError, SanyanValueError
from ops.registry import register


# ── 来源/证据链操作 ──


def _source_op(evaluator, args):
    """来源(x) — 查询三态值的来源/证据链。"""
    if len(args) != 1:
        raise SanyanSyntaxError('来源 需要一个参数')
    val = evaluator.eval(args[0])
    if isinstance(val, TritValue):
        return TritValue(val._source) if val._source else TritValue('')
    return TritValue('')


def _source_chain_op(evaluator, args):
    """来源链(列表) — 合并多个来源为证据链 'A → B → C'。"""
    sources = []
    for a in args:
        v = evaluator.eval(a)
        if isinstance(v, TritValue) and v._source:
            sources.append(v._source)
        elif isinstance(v, str) and v:
            sources.append(v)
    return TritValue(' → '.join(sources)) if sources else TritValue('')


register('source', _source_op)
register('source_chain', _source_chain_op)

# ── 冲突模型 ──


def _detect_conflict(evaluator, args):
    """检测冲突(a, b) — 两个值矛盾且信度都高→标记冲突。
    返回字典: {冲突: 1/-1/0, 差异度: 0-1, a信度, b信度}"""
    if len(args) < 2:
        raise SanyanSyntaxError('检测冲突 需要至少两个参数')
    vals = [evaluator.eval(a) for a in args]
    # 检查两两矛盾
    for i in range(len(vals)):
        for j in range(i + 1, len(vals)):
            a, b = vals[i], vals[j]
            ai = a.to_int() if isinstance(a, TritValue) else a
            bi = b.to_int() if isinstance(b, TritValue) else b
            ac = a.confidence if isinstance(a, TritValue) else 1.0
            bc = b.confidence if isinstance(b, TritValue) else 1.0
            # 高信度矛盾: 真(+1) vs 假(-1), 且双方信度 > 0.7
            if ai * bi == -1 and ac > 0.7 and bc > 0.7:
                return {'冲突': 1, '差异度': min(ac, bc), 'a信度': ac, 'b信度': bc}
    return {'冲突': 0, '差异度': 0, 'a信度': 0, 'b信度': 0}


register('detect_conflict', _detect_conflict)


def _conflict_merge(evaluator, args):
    """冲突合并(a, b, 策略) — 两个矛盾值按策略合并。
    策略: "保守" → 返回可能(0); "优先级" → 保持第一个; "投票" → 信度高者胜; "新鲜度" → 信度×值"""
    if len(args) < 2:
        raise SanyanSyntaxError('冲突合并 需要至少两个值')
    vals = (
        [evaluator.eval(a) for a in args[:-1]] if len(args) > 2 else [evaluator.eval(args[0]), evaluator.eval(args[1])]
    )
    strategy = evaluator.eval(args[-1])
    if isinstance(strategy, TritValue) and strategy.is_string():
        strategy = strategy.to_payload()
    elif isinstance(strategy, TritValue):
        strategy = str(strategy.to_int())
    else:
        strategy = str(strategy)

    if strategy == '保守' or strategy == 'conservative':
        return TritValue(0, confidence=0.5, source='冲突合并(保守)')
    elif strategy == '优先级' or strategy == 'priority':
        v = vals[0]
        return (
            v.with_confidence(v.confidence * 0.5)
            if isinstance(v, TritValue)
            else TritValue(v if isinstance(v, int) else 0, confidence=0.5, source='冲突合并(优先级)')
        )
    elif strategy == '投票' or strategy == 'vote':
        best, best_c = TritValue(0), 0.0
        for v in vals:
            c = v.confidence if isinstance(v, TritValue) else 1.0
            if c > best_c:
                best_c = c
                best = v if isinstance(v, TritValue) else TritValue(v)
        return best.with_confidence(best_c * 0.7)
    # 默认: 返回可能，保持最低源信度
    min_conf = min((v.confidence for v in vals if isinstance(v, TritValue)), default=0.5)
    return TritValue(0, confidence=min_conf, source='冲突合并(默认)')


register('conflict_merge', _conflict_merge)


def _decide(evaluator, args):
    """判定(v, 阈值) — 硬判定: 置信度≥阈值→输出确定态，<阈值→强制输出可能(0)。
    工业控制默认 0.95，游戏 NPC 默认 0.5。"""
    if len(args) < 1:
        raise SanyanSyntaxError('判定 需要至少 1 个参数')
    val = evaluator.eval(args[0])
    threshold = 0.5
    if len(args) >= 2:
        t = evaluator.eval(args[1])
        if isinstance(t, TritValue):
            threshold = t.to_float()
        elif isinstance(t, (int, float)):
            threshold = float(t)
    if not isinstance(val, TritValue):
        return TritValue(val if isinstance(val, int) else 0)

    c = val.confidence
    if c >= threshold:
        return val  # 确定态，保持原值
    # 信度不足 → 强制可能态
    return TritValue(0, confidence=c, source=val._source or '硬判定降级')


register('decide', _decide)


def _fuse(evaluator, args):
    """融合(列表) 或 融合(a, b, ...) — 多源加权融合。信度高的源权重大。
    融合([三态(真,0.9), 三态(可能,0.4), 三态(真,0.7)])
    → 三态(真, 0.8) (信度加权平均)
    也支持: 融合(三态(真,0.9), 三态(可能,0.4))"""
    if len(args) == 0:
        return TritValue(0, confidence=0)
    if len(args) == 1:
        lst = evaluator.eval(args[0])
        if not isinstance(lst, list):
            raise SanyanTypeError('融合 参数必须是列表')
    else:
        lst = [evaluator.eval(a) for a in args]
    if not lst:
        return TritValue(0, confidence=0)
    total_conf = 0.0
    weighted_sum = 0.0
    for item in lst:
        c = item.confidence if isinstance(item, TritValue) else 1.0
        v = item.to_int() if isinstance(item, TritValue) else (1 if item else 0)
        weighted_sum += v * c
        total_conf += c
    if total_conf == 0:
        return TritValue(0, confidence=0)
    avg = weighted_sum / total_conf
    if avg > 0.3:
        result_val = 1
    elif avg < -0.3:
        result_val = -1
    else:
        result_val = 0
    return TritValue(result_val, confidence=min(total_conf / len(lst), 1.0), source='多源融合')


register('fuse', _fuse)


def _bayes_update(evaluator, args):
    """贝叶斯(先验, 证据) — 贝叶斯置信度更新。
    证据一致 → 信度上升；证据矛盾 → 按信度比例切换。"""
    if len(args) != 2:
        raise SanyanSyntaxError('贝叶斯 需要先验和证据两个参数')
    prior = evaluator.eval(args[0])
    evidence = evaluator.eval(args[1])
    if not isinstance(prior, TritValue):
        prior = TritValue(prior if isinstance(prior, int) else 0)
    if not isinstance(evidence, TritValue):
        evidence = TritValue(int(evidence) if isinstance(evidence, (int, float)) else 0)

    pv = prior.to_int() if prior.is_numeric() else 0
    ev = evidence.to_int() if evidence.is_numeric() else 0
    pc = prior.confidence
    ec = evidence.confidence

    # 简化的贝叶斯更新公式
    if pv == ev:
        # 证据一致: 信度上升
        new_c = 1.0 - (1.0 - pc) * (1.0 - ec)
        new_val = pv
    else:
        # 证据矛盾: 按信度比例切换
        if ec > pc:
            new_val = ev
            new_c = ec * (1.0 - pc) / max(0.01, ec * (1.0 - pc) + (1.0 - ec) * pc)
        else:
            new_val = pv
            new_c = pc * (1.0 - ec) / max(0.01, pc * (1.0 - ec) + (1.0 - pc) * ec)
    new_c = max(0.01, min(0.99, new_c))
    src = f'贝叶斯(先验={prior._source or "?"}→证据={evidence._source or "?"})'
    return TritValue(new_val, confidence=new_c, source=src if src != '贝叶斯(先验=?→证据=?)' else '')


register('bayes_update', _bayes_update)


def _assert_confidence(evaluator, args):
    """断言信度(v, 阈值, [消息]) — 运行时置信度门限检查。
    信度 < 阈值 → 抛出 SanyanValueError，阻止不确定性数据进入安全关键路径。
    编译期等价功能: 在安全关键函数签名中声明 {信度 >= 0.95} 约束。"""
    if len(args) < 2:
        raise SanyanSyntaxError('断言信度 需要值、阈值 [, 消息]')
    val = evaluator.eval(args[0])
    threshold_v = evaluator.eval(args[1])
    threshold = threshold_v.to_float() if isinstance(threshold_v, TritValue) else float(threshold_v)
    msg = ''
    if len(args) >= 3:
        m = evaluator.eval(args[2])
        msg = m.to_payload() if isinstance(m, TritValue) and m.is_string() else str(m)

    c = val.confidence if isinstance(val, TritValue) else 1.0
    if c < threshold:
        raise SanyanValueError(msg or f'信度不足: {c:.3f} < {threshold} (门限)')
    return val


register('assert_confidence', _assert_confidence)


def _quantize(evaluator, args):
    """量化(v) — 将 TritValue 打包为 1 字节整数。
    编码: [bit7-2: 6-bit 信度(0-63)] [bit1-0: 值(00=0,01=1,10=-1)]
    用于嵌入式/网络传输的紧凑存储。"""
    if len(args) != 1:
        raise SanyanSyntaxError('量化 需要一个参数')
    val = evaluator.eval(args[0])
    if not isinstance(val, TritValue):
        return TritValue(0)

    v = val.to_int() if val.is_numeric() else 0
    c = val.confidence

    # 2-bit value encoding
    if v == 1:
        v_bits = 1
    elif v == -1:
        v_bits = 2
    else:
        v_bits = 0

    # 6-bit confidence (0-63)
    c_bits = min(63, max(0, int(round(c * 63))))
    byte_val = (c_bits << 2) | v_bits
    return TritValue(byte_val)


def _dequantize(evaluator, args):
    """反量化(b) — 从 1 字节整数恢复 TritValue。"""
    if len(args) != 1:
        raise SanyanSyntaxError('反量化 需要一个参数')
    val = evaluator.eval(args[0])
    byte_val = val.to_int() if isinstance(val, TritValue) else int(val)

    v_bits = byte_val & 3
    c_bits = (byte_val >> 2) & 63

    if v_bits == 1:
        v = 1
    elif v_bits == 2:
        v = -1
    else:
        v = 0

    c = c_bits / 63.0
    return TritValue(v, confidence=c)


register('quantize', _quantize)
register('dequantize', _dequantize)


def _majority_vote(evaluator, args):
    """表决(a,b,c) — 多数表决: 取出现次数最多的值，信度=多数占比。"""
    vals = [evaluator.eval(a) for a in args]
    pos, neg, zero = 0, 0, 0
    total_c = 0.0
    for v in vals:
        iv = v.to_int() if isinstance(v, TritValue) else int(v)
        c = v.confidence if isinstance(v, TritValue) else 1.0
        total_c += c
        if iv == 1:
            pos += 1
        elif iv == -1:
            neg += 1
        else:
            zero += 1
    n = len(vals)
    if n == 0:
        return TritValue(0)
    if pos >= neg and pos >= zero:
        return TritValue(1, confidence=pos / n)
    elif neg >= pos and neg >= zero:
        return TritValue(-1, confidence=neg / n)
    return TritValue(0, confidence=zero / n)


register('majority_vote', _majority_vote)


def _consensus(evaluator, args):
    """共识(a, b, ...) — 多个传感器共识: 只有所有源都为真才返回真。
    任一为假则返回假，包含可能则返回可能。
    置信度计算: 全部真时取最大值，其他情况取最小值。"""
    if len(args) < 2:
        raise SanyanSyntaxError('共识 需要至少两个参数')
    vals = [evaluator.eval(a) for a in args]
    all_true = True
    any_false = False
    confs = []
    for v in vals:
        iv = v.to_int() if isinstance(v, TritValue) else (1 if v else 0)
        c = v.confidence if isinstance(v, TritValue) else 1.0
        confs.append(c)
        if iv == -1:
            any_false = True
            all_true = False
        elif iv == 0:
            all_true = False
    if all_true:
        # 全部一致时，置信度取最大值（共识增强）
        return TritValue(1, confidence=max(confs), source='共识')
    if any_false:
        return TritValue(-1, confidence=min(confs), source='共识')
    return TritValue(0, confidence=min(confs), source='共识')


register('consensus', _consensus)

# 中文别名
from ops.registry import register_alias as _ra  # noqa: E402

_ra('来源', 'source')
_ra('来源链', 'source_chain')
_ra('检测冲突', 'detect_conflict')
_ra('冲突合并', 'conflict_merge')
_ra('贝叶斯更新', 'bayes_update')
_ra('融合', 'fuse')
_ra('共识', 'consensus')
_ra('断言信度', 'assert_confidence')
_ra('量化', 'quantize')
_ra('反量化', 'dequantize')
_ra('表决', 'majority_vote')
