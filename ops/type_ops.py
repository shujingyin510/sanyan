"""类型判断操作"""

from ternary_core import TritValue
from values import SanyanSyntaxError, SanyanTypeError
from ops.registry import register


class TypeOps:
    @staticmethod
    def is_number(evaluator, args):
        if len(args) != 1:
            raise SanyanSyntaxError('是数字 需要一个参数')
        val = evaluator.eval(args[0])
        if isinstance(val, TritValue):
            return TritValue(1)
        return TritValue(-1)

    @staticmethod
    def is_string(evaluator, args):
        if len(args) != 1:
            raise SanyanSyntaxError('是字符串 需要一个参数')
        val = evaluator.eval(args[0])
        if isinstance(val, str):
            return TritValue(1)
        return TritValue(-1)

    @staticmethod
    def is_list(evaluator, args):
        if len(args) != 1:
            raise SanyanSyntaxError('是列表 需要一个参数')
        val = evaluator.eval(args[0])
        if isinstance(val, list):
            return TritValue(1)
        return TritValue(-1)

    @staticmethod
    def is_dict(evaluator, args):
        if len(args) != 1:
            raise SanyanSyntaxError('是字典 需要一个参数')
        val = evaluator.eval(args[0])
        if isinstance(val, dict):
            return TritValue(1)
        return TritValue(-1)

    @staticmethod
    def str_equals(evaluator, args):
        if len(args) != 2:
            raise SanyanSyntaxError('字符串相等 需要两个参数')
        a = evaluator.eval(args[0])
        b = evaluator.eval(args[1])
        if isinstance(a, str) and isinstance(b, str):
            return TritValue(1 if a == b else -1)
        return TritValue(-1)

    @staticmethod
    def to_number(evaluator, args):
        if len(args) != 1:
            raise SanyanSyntaxError('to_number 需要一个参数')
        val = evaluator.eval(args[0])
        if isinstance(val, TritValue):
            return val
        if isinstance(val, (int, float)):
            return TritValue(val)
        if isinstance(val, str):
            try:
                return (
                    TritValue(int(val))
                    if val.isdigit() or (val.startswith('-') and val[1:].isdigit())
                    else TritValue(float(val))
                )
            except (ValueError, TypeError):
                raise SanyanTypeError(f"无法将 '{val}' 转换为数字")
        raise SanyanTypeError(f'无法将 {type(val).__name__} 转换为数字')

    @staticmethod
    def to_string(evaluator, args):
        if len(args) != 1:
            raise SanyanSyntaxError('字符串 需要一个参数')
        val = evaluator.eval(args[0])
        if isinstance(val, str):
            return val
        if isinstance(val, TritValue):
            if val.is_string():
                return val.to_payload()
            if val.is_float():
                return f'{val.to_float():.4f}'.rstrip('0').rstrip('.')
            return str(val.to_int())
        if isinstance(val, list):
            return '[' + ', '.join(str(v) for v in val) + ']'
        if isinstance(val, dict):
            return '{' + ', '.join(f'{k}: {v}' for k, v in val.items()) + '}'
        if isinstance(val, float):
            return f'{val:.4f}'.rstrip('0').rstrip('.')
        return str(val)

    @staticmethod
    def ternary_value(evaluator, args):
        """构造显式三态值：三态值(v, 置信度, 来源) — 返回带置信度和来源的 TritValue。
        三态值("hello", 0.8, "用户输入") 创建置信度 0.8 的字符串值，来源为用户输入。
        三态值(42, 0.9) 置信度 0.9，无来源。"""
        if len(args) < 1 or len(args) > 3:
            raise SanyanSyntaxError('三态值 需要 1-3 个参数: 值 [, 置信度] [, 来源]')
        val = evaluator.eval(args[0])
        confidence = 1.0
        source = ''
        if len(args) >= 2:
            c = evaluator.eval(args[1])
            if isinstance(c, TritValue):
                confidence = c.to_float()
            elif isinstance(c, (int, float)):
                confidence = float(c)
        if len(args) >= 3:
            s = evaluator.eval(args[2])
            if isinstance(s, TritValue) and s.is_string():
                source = s.to_payload()
            elif isinstance(s, str):
                source = s
        if isinstance(val, TritValue):
            return TritValue(val.to_int() if val.is_numeric() else val.to_payload(),
                           val.precision if val.is_float() else 0,
                           confidence=confidence, source=source or val._source)
        if isinstance(val, str):
            return TritValue(val, confidence=confidence, source=source)
        if isinstance(val, (int, float)):
            return TritValue(val, confidence=confidence, source=source)
        raise SanyanTypeError(f'三态值 不支持类型: {type(val).__name__}')

    @staticmethod
    def ternary_propagate(evaluator, args):
        """贝叶斯置信度传播：传递(上游, 当前) → 新 TritValue with 传播后的置信度。
        传播置信度 = 上游置信度 × 当前置信度（独立贝叶斯更新）。
        来源合并为 "上游来源 → 当前来源"。"""
        if len(args) != 2:
            raise SanyanSyntaxError('传递 需要 2 个参数: (传递 上游值 当前值)')
        upstream = evaluator.eval(args[0])
        current = evaluator.eval(args[1])

        uc = upstream.confidence if isinstance(upstream, TritValue) else 1.0
        cc = current.confidence if isinstance(current, TritValue) else 1.0
        propagated = max(0.0, min(1.0, uc * cc))

        # 合并来源链
        us = upstream._source if isinstance(upstream, TritValue) else ''
        cs = current._source if isinstance(current, TritValue) else ''
        merged_source = ' → '.join(filter(None, [us, cs])) if (us or cs) else ''

        if isinstance(current, TritValue):
            return current.with_confidence(propagated) if not merged_source else \
                   TritValue(current.to_int() if current.is_numeric() else current.to_payload(),
                            confidence=propagated, source=merged_source)
        if isinstance(current, str):
            return TritValue(current, confidence=propagated, source=merged_source)
        if isinstance(current, (int, float)):
            return TritValue(current, confidence=propagated, source=merged_source)
        return TritValue(0, confidence=propagated, source=merged_source)


# 注册类型操作
register('is_number', TypeOps.is_number)
register('is_string', TypeOps.is_string)
register('is_list', TypeOps.is_list)
register('is_dict', TypeOps.is_dict)
register('str_equals', TypeOps.str_equals)
register('ternary_value', TypeOps.ternary_value)
register('ternary_propagate', TypeOps.ternary_propagate)

# ── 来源/证据链操作 ──
from ternary_core import TritValue

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
    vals = [evaluator.eval(a) for a in args[:-1]] if len(args) > 2 else [evaluator.eval(args[0]), evaluator.eval(args[1])]
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
        return v.with_confidence(v.confidence * 0.5) if isinstance(v, TritValue) else \
               TritValue(v if isinstance(v, int) else 0, confidence=0.5, source='冲突合并(优先级)')
    elif strategy == '投票' or strategy == 'vote':
        best, best_c = TritValue(0), 0
        for v in vals:
            c = v.confidence if isinstance(v, TritValue) else 1.0
            if c > best_c:
                best_c = c
                best = v if isinstance(v, TritValue) else TritValue(v)
        return best.with_confidence(best_c * 0.7)
    # 默认: 返回可能
    return TritValue(0, confidence=0, source='冲突合并(默认)')

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
    """融合(列表) — 多源加权融合。信度高的源权重大。
    融合([三态(真,0.9), 三态(可能,0.4), 三态(真,0.7)])
    → 加权结果 with 融合信度 = 加权和 / 总权重"""
    if len(args) == 0:
        return TritValue(0)
    vals = [evaluator.eval(a) for a in args]
    total_weight = 0.0
    weighted_sum = 0.0
    sources = []
    for v in vals:
        if isinstance(v, TritValue):
            w = v.confidence
            total_weight += w
            weighted_sum += v.to_int() * w
            if v._source:
                sources.append(v._source)
        elif isinstance(v, (int, float)):
            total_weight += 1.0
            weighted_sum += float(v)
    if total_weight == 0:
        return TritValue(0, confidence=0)
    result = int(round(weighted_sum / total_weight))
    result = max(-1, min(1, result))
    fused_c = total_weight / len(vals)
    merged_src = '+'.join(sources) if sources else '融合'
    return TritValue(result, confidence=fused_c, source=merged_src)

register('fuse', _fuse)


def _consensus_op(evaluator, args):
    """共识(a, b) — 主观逻辑共识融合算子。
    将 TritValue 映射为信念三元组 (b,d,u):
      v=真: b=c, d=0, u=1-c
      v=假: b=0, d=c, u=1-c
      v=可能: b=0, d=0, u=1
    融合公式: bC = (bA*uB + bB*uA) / (uA + uB - uA*uB)
    返回融合后的 TritValue with 融合信度。
    
    适用场景: 两个独立的传感器/Agent 对同一命题给出意见时融合。"""
    if len(args) < 2:
        raise SanyanSyntaxError('共识 需要至少两个三态值')
    vals = [evaluator.eval(a) for a in args]

    def _to_opinion(v):
        if not isinstance(v, TritValue):
            c = 1.0
            iv = int(v) if isinstance(v, (int, float)) else 0
        else:
            c = v.confidence
            iv = v.to_int() if v.is_numeric() else 0
        if iv == 1:
            return (c, 0.0, 1.0 - c)  # b, d, u
        elif iv == -1:
            return (0.0, c, 1.0 - c)
        else:
            return (0.0, 0.0, 1.0)

    b_total, d_total, u_total = _to_opinion(vals[0])
    for v in vals[1:]:
        b2, d2, u2 = _to_opinion(v)
        denom = u_total + u2 - u_total * u2
        if denom < 1e-10:
            b_total = (b_total + b2) / 2
            d_total = (d_total + d2) / 2
            u_total = 1.0 - b_total - d_total
        else:
            b_total = (b_total * u2 + b2 * u_total) / denom
            d_total = (d_total * u2 + d2 * u_total) / denom
            u_total = max(0.0, 1.0 - b_total - d_total)

    # 信念三元组 → TritValue
    if b_total > d_total and b_total > 0.1:
        result_val, result_c = 1, b_total
    elif d_total > b_total and d_total > 0.1:
        result_val, result_c = -1, d_total
    else:
        result_val, result_c = 0, u_total
    return TritValue(result_val, confidence=min(1.0, result_c / max(0.01, b_total + d_total + u_total)),
                     source='主观逻辑共识')

register('consensus', _consensus_op)


def _bayes_update(evaluator, args):
    """贝叶斯更新(先验, 证据) — P(H|E) = P(E|H) × P(H) / P(E)。
    先验: 当前信念 (TritValue)
    证据: 新观测 (TritValue)
    返回更新后的 TritValue。
    
    如果证据与先验一致: 信度上升。
    如果证据与先验矛盾: 信度下降，值可能翻转。"""
    if len(args) != 2:
        raise SanyanSyntaxError('贝叶斯更新 需要两个参数: 先验值, 证据值')
    prior = evaluator.eval(args[0])
    evidence = evaluator.eval(args[1])

    if not isinstance(prior, TritValue):
        prior = TritValue(int(prior) if isinstance(prior, (int, float)) else 0)
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
        from values import SanyanValueError
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
        if iv == 1: pos += 1
        elif iv == -1: neg += 1
        else: zero += 1
    n = len(vals)
    if n == 0:
        return TritValue(0)
    if pos >= neg and pos >= zero:
        return TritValue(1, confidence=pos / n)
    elif neg >= pos and neg >= zero:
        return TritValue(-1, confidence=neg / n)
    return TritValue(0, confidence=zero / n)

register('majority_vote', _majority_vote)


def _trit_shift(evaluator, args):
    """三态移位(x, n) — trit 位左移 n 位 (×3^n 等价)"""
    if len(args) != 2:
        raise SanyanSyntaxError('三态移位 需要值和位数')
    val = evaluator.eval(args[0])
    n = evaluator.eval(args[1])
    n = n.to_int() if isinstance(n, TritValue) else int(n)
    v = val.to_int() if isinstance(val, TritValue) else int(val)
    c = val.confidence if isinstance(val, TritValue) else 1.0
    result = v * (3 ** n)
    return TritValue(result, confidence=c)

register('trit_shift', _trit_shift)


def _trit_flip(evaluator, args):
    """三态翻转(x) — 所有 trit 翻转: 真↔假, 可能不变"""
    if len(args) != 1:
        raise SanyanSyntaxError('三态翻转 需要一个值')
    val = evaluator.eval(args[0])
    v = val.to_int() if isinstance(val, TritValue) else int(val)
    c = val.confidence if isinstance(val, TritValue) else 1.0
    return TritValue(-v, confidence=c)

register('trit_flip', _trit_flip)


def _trit_compress(evaluator, args):
    """三态压缩(...) — 多个 trit 打包为字节列表。每字节存 3 trit (0-26)。
    三态压缩(+,-,0,+,-,0) → [15] (3^2×1 + 3^1×(-1) + 3^0×0 = 8, ...)"""
    vals = [evaluator.eval(a) for a in args]
    result = []
    buf = []
    for v in vals:
        iv = v.to_int() if isinstance(v, TritValue) else int(v)
        iv = max(-1, min(1, iv)) + 1  # -1→0, 0→1, 1→2
        buf.append(iv)
        if len(buf) == 3:
            byte_val = buf[0] * 9 + buf[1] * 3 + buf[2] * 1
            result.append(TritValue(byte_val))
            buf = []
    if buf:
        while len(buf) < 3:
            buf.append(1)  # 补 0 (可能)
        byte_val = buf[0] * 9 + buf[1] * 3 + buf[2] * 1
        result.append(TritValue(byte_val))
    return result

register('trit_compress', _trit_compress)


def _trit_decompress(evaluator, args):
    """三态解压(字节列表) → 展开为 trit 值列表"""
    bytes_list = [evaluator.eval(a) for a in args]
    result = []
    for b in bytes_list:
        bv = b.to_int() if isinstance(b, TritValue) else int(b)
        for shift in (9, 3, 1):
            digit = (bv // shift) % 3
            result.append(TritValue(digit - 1))
    return result

register('trit_decompress', _trit_decompress)
register('to_string', TypeOps.to_string)
register('to_number', TypeOps.to_number)
