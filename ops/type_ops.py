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
            return TritValue(
                val.to_int() if val.is_numeric() else val.to_payload(),
                val.precision if val.is_float() else 0,
                confidence=confidence,
                source=source or val._source,
            )
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
        propagated = uc * cc
        us = upstream._source if isinstance(upstream, TritValue) and upstream._source else ''
        cs = current._source if isinstance(current, TritValue) and current._source else ''
        merged_source = f'{us} → {cs}' if us and cs else (us or cs or '')
        if isinstance(current, TritValue):
            return (
                current.with_confidence(propagated)
                if not merged_source
                else TritValue(
                    current.to_int() if current.is_numeric() else current.to_payload(),
                    confidence=propagated,
                    source=merged_source,
                )
            )
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
register('to_string', TypeOps.to_string)
register('to_number', TypeOps.to_number)
