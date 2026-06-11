"""三态集：带置信度的集合"""

from typing import Dict
from ternary_core import TritValue
from values import SanyanSyntaxError, SanyanTypeError
from ops.registry import register


class TernarySet:
    """三态集：每个元素带独立置信度的集合"""

    def __init__(self):
        self._elements: Dict[str, TritValue] = {}

    def add(self, elem, confidence=1.0):
        key = str(elem) if not isinstance(elem, str) else elem
        if key in self._elements:
            existing = self._elements[key]
            new_conf = max(existing.confidence, confidence)
            self._elements[key] = TritValue(existing.value, confidence=new_conf)
        else:
            self._elements[key] = TritValue(1, confidence=confidence)

    def remove(self, elem):
        key = str(elem) if not isinstance(elem, str) else elem
        if key in self._elements:
            del self._elements[key]

    def contains(self, elem):
        key = str(elem) if not isinstance(elem, str) else elem
        return self._elements[key].confidence if key in self._elements else 0.0

    def size(self):
        return len(self._elements)

    def to_list(self):
        return list(self._elements.keys())

    def union(self, other: 'TernarySet') -> 'TernarySet':
        result = TernarySet()
        for k, v in self._elements.items():
            result._elements[k] = v
        for k, v in other._elements.items():
            if k in result._elements:
                new_conf = max(result._elements[k].confidence, v.confidence)
                result._elements[k] = TritValue(v.value, confidence=new_conf)
            else:
                result._elements[k] = v
        return result

    def intersection(self, other: 'TernarySet') -> 'TernarySet':
        result = TernarySet()
        for k, v in self._elements.items():
            if k in other._elements:
                new_conf = min(v.confidence, other._elements[k].confidence)
                result._elements[k] = TritValue(v.value, confidence=new_conf)
        return result

    def difference(self, other: 'TernarySet') -> 'TernarySet':
        result = TernarySet()
        for k, v in self._elements.items():
            if k not in other._elements:
                result._elements[k] = v
        return result

    def confidence_sum(self):
        return sum(v.confidence for v in self._elements.values())

    def __repr__(self):
        items = ', '.join(f'{k}({v.confidence:.2f})' for k, v in self._elements.items())
        return f'三态集({items})'


# ── 操作函数 ──


def _ternary_set_new(evaluator, args):
    s = TernarySet()
    for a in args:
        val = evaluator.eval(a)
        if isinstance(val, TritValue):
            s.add(val.to_payload() if val.is_string() else val.to_int(), val.confidence)
        else:
            s.add(val)
    return s


def _ternary_set_add(evaluator, args):
    if len(args) < 2:
        raise SanyanSyntaxError('三态集加 需要集合和元素')
    s = evaluator.eval(args[0])
    if not isinstance(s, TernarySet):
        raise SanyanTypeError('第一个参数必须是三态集')
    elem = evaluator.eval(args[1])
    conf = 1.0
    if len(args) >= 3:
        conf_val = evaluator.eval(args[2])
        conf = conf_val.to_float() if isinstance(conf_val, TritValue) else float(conf_val)
    s.add(elem, conf)
    return s


def _ternary_set_remove(evaluator, args):
    if len(args) != 2:
        raise SanyanSyntaxError('三态集删 需要集合和元素')
    s = evaluator.eval(args[0])
    if not isinstance(s, TernarySet):
        raise SanyanTypeError('第一个参数必须是三态集')
    elem = evaluator.eval(args[1])
    s.remove(elem)
    return s


def _ternary_set_contains(evaluator, args):
    if len(args) != 2:
        raise SanyanSyntaxError('三态集含 需要集合和元素')
    s = evaluator.eval(args[0])
    if not isinstance(s, TernarySet):
        raise SanyanTypeError('第一个参数必须是三态集')
    elem = evaluator.eval(args[1])
    conf = s.contains(elem)
    return TritValue(1 if conf > 0 else -1, confidence=conf)


def _ternary_set_size(evaluator, args):
    if len(args) != 1:
        raise SanyanSyntaxError('三态集长 需要一个参数')
    s = evaluator.eval(args[0])
    if not isinstance(s, TernarySet):
        raise SanyanTypeError('参数必须是三态集')
    return TritValue(s.size())


def _ternary_set_union(evaluator, args):
    if len(args) != 2:
        raise SanyanSyntaxError('三态集并 需要两个集合')
    s1, s2 = evaluator.eval(args[0]), evaluator.eval(args[1])
    if not isinstance(s1, TernarySet) or not isinstance(s2, TernarySet):
        raise SanyanTypeError('参数必须是三态集')
    return s1.union(s2)


def _ternary_set_intersection(evaluator, args):
    if len(args) != 2:
        raise SanyanSyntaxError('三态集交 需要两个集合')
    s1, s2 = evaluator.eval(args[0]), evaluator.eval(args[1])
    if not isinstance(s1, TernarySet) or not isinstance(s2, TernarySet):
        raise SanyanTypeError('参数必须是三态集')
    return s1.intersection(s2)


def _ternary_set_difference(evaluator, args):
    if len(args) != 2:
        raise SanyanSyntaxError('三态集差 需要两个集合')
    s1, s2 = evaluator.eval(args[0]), evaluator.eval(args[1])
    if not isinstance(s1, TernarySet) or not isinstance(s2, TernarySet):
        raise SanyanTypeError('参数必须是三态集')
    return s1.difference(s2)


def _ternary_set_to_list(evaluator, args):
    if len(args) != 1:
        raise SanyanSyntaxError('三态集列 需要一个参数')
    s = evaluator.eval(args[0])
    if not isinstance(s, TernarySet):
        raise SanyanTypeError('参数必须是三态集')
    return s.to_list()


def _ternary_set_conf_sum(evaluator, args):
    if len(args) != 1:
        raise SanyanSyntaxError('三态集信度和 需要一个参数')
    s = evaluator.eval(args[0])
    if not isinstance(s, TernarySet):
        raise SanyanTypeError('参数必须是三态集')
    return TritValue(s.confidence_sum(), confidence=1.0)


# 注册
register('三态集', _ternary_set_new)
register('三态集加', _ternary_set_add)
register('三态集删', _ternary_set_remove)
register('三态集含', _ternary_set_contains)
register('三态集长', _ternary_set_size)
register('三态集并', _ternary_set_union)
register('三态集交', _ternary_set_intersection)
register('三态集差', _ternary_set_difference)
register('三态集列', _ternary_set_to_list)
register('三态集信度和', _ternary_set_conf_sum)
register('ternary_set', _ternary_set_new)
register('ternary_set_add', _ternary_set_add)
register('ternary_set_remove', _ternary_set_remove)
register('ternary_set_contains', _ternary_set_contains)
register('ternary_set_size', _ternary_set_size)
register('ternary_set_union', _ternary_set_union)
register('ternary_set_intersection', _ternary_set_intersection)
register('ternary_set_difference', _ternary_set_difference)
