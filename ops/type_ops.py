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
register('to_string', TypeOps.to_string)
register('to_number', TypeOps.to_number)
