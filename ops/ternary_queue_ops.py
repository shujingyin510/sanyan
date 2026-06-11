"""三态队列与三态栈"""

from typing import Any, List, Tuple
from ternary_core import TritValue
from values import SanyanSyntaxError, SanyanTypeError
from ops.registry import register


class TernaryQueue:
    """三态队列：先进先出，元素带置信度"""

    def __init__(self):
        self._items: List[Tuple[Any, float]] = []

    def enqueue(self, item, confidence=1.0):
        self._items.append((item, confidence))

    def dequeue(self):
        return self._items.pop(0) if self._items else (None, 0.0)

    def peek(self):
        return self._items[0] if self._items else (None, 0.0)

    def size(self):
        return len(self._items)

    def is_empty(self):
        return len(self._items) == 0

    def to_list(self):
        return [(item, conf) for item, conf in self._items]

    def __repr__(self):
        return f'三态队列(长度={len(self._items)})'


class TernaryStack:
    """三态栈：后进先出，元素带置信度"""

    def __init__(self):
        self._items: List[Tuple[Any, float]] = []

    def push(self, item, confidence=1.0):
        self._items.append((item, confidence))

    def pop(self):
        return self._items.pop() if self._items else (None, 0.0)

    def peek(self):
        return self._items[-1] if self._items else (None, 0.0)

    def size(self):
        return len(self._items)

    def is_empty(self):
        return len(self._items) == 0

    def to_list(self):
        return [(item, conf) for item, conf in reversed(self._items)]

    def __repr__(self):
        return f'三态栈(长度={len(self._items)})'


# ── 队列操作 ──


def _ternary_queue_new(evaluator, args):
    return TernaryQueue()


def _ternary_queue_enqueue(evaluator, args):
    if len(args) < 2:
        raise SanyanSyntaxError('三态入队 需要队列和元素')
    q = evaluator.eval(args[0])
    if not isinstance(q, TernaryQueue):
        raise SanyanTypeError('第一个参数必须是三态队列')
    item = evaluator.eval(args[1])
    conf = 1.0
    if len(args) >= 3:
        conf_val = evaluator.eval(args[2])
        conf = conf_val.to_float() if isinstance(conf_val, TritValue) else float(conf_val)
    q.enqueue(item, conf)
    return q


def _ternary_queue_dequeue(evaluator, args):
    if len(args) != 1:
        raise SanyanSyntaxError('三态出队 需要一个参数')
    q = evaluator.eval(args[0])
    if not isinstance(q, TernaryQueue):
        raise SanyanTypeError('参数必须是三态队列')
    item, conf = q.dequeue()
    return item if item is not None else TritValue(-1, confidence=0.0)


def _ternary_queue_peek(evaluator, args):
    if len(args) != 1:
        raise SanyanSyntaxError('三态查看队 需要一个参数')
    q = evaluator.eval(args[0])
    if not isinstance(q, TernaryQueue):
        raise SanyanTypeError('参数必须是三态队列')
    item, conf = q.peek()
    return item if item is not None else TritValue(-1, confidence=0.0)


def _ternary_queue_size(evaluator, args):
    if len(args) != 1:
        raise SanyanSyntaxError('三态队长 需要一个参数')
    q = evaluator.eval(args[0])
    if not isinstance(q, TernaryQueue):
        raise SanyanTypeError('参数必须是三态队列')
    return TritValue(q.size())


# ── 栈操作 ──


def _ternary_stack_new(evaluator, args):
    return TernaryStack()


def _ternary_stack_push(evaluator, args):
    if len(args) < 2:
        raise SanyanSyntaxError('三态压栈 需要栈和元素')
    s = evaluator.eval(args[0])
    if not isinstance(s, TernaryStack):
        raise SanyanTypeError('第一个参数必须是三态栈')
    item = evaluator.eval(args[1])
    conf = 1.0
    if len(args) >= 3:
        conf_val = evaluator.eval(args[2])
        conf = conf_val.to_float() if isinstance(conf_val, TritValue) else float(conf_val)
    s.push(item, conf)
    return s


def _ternary_stack_pop(evaluator, args):
    if len(args) != 1:
        raise SanyanSyntaxError('三态弹栈 需要一个参数')
    s = evaluator.eval(args[0])
    if not isinstance(s, TernaryStack):
        raise SanyanTypeError('参数必须是三态栈')
    item, conf = s.pop()
    return item if item is not None else TritValue(-1, confidence=0.0)


def _ternary_stack_peek(evaluator, args):
    if len(args) != 1:
        raise SanyanSyntaxError('三态查看栈 需要一个参数')
    s = evaluator.eval(args[0])
    if not isinstance(s, TernaryStack):
        raise SanyanTypeError('参数必须是三态栈')
    item, conf = s.peek()
    return item if item is not None else TritValue(-1, confidence=0.0)


def _ternary_stack_size(evaluator, args):
    if len(args) != 1:
        raise SanyanSyntaxError('三态栈长 需要一个参数')
    s = evaluator.eval(args[0])
    if not isinstance(s, TernaryStack):
        raise SanyanTypeError('参数必须是三态栈')
    return TritValue(s.size())


register('三态队列', _ternary_queue_new)
register('三态入队', _ternary_queue_enqueue)
register('三态出队', _ternary_queue_dequeue)
register('三态查看队', _ternary_queue_peek)
register('三态队长', _ternary_queue_size)
register('三态栈', _ternary_stack_new)
register('三态压栈', _ternary_stack_push)
register('三态弹栈', _ternary_stack_pop)
register('三态查看栈', _ternary_stack_peek)
register('三态栈长', _ternary_stack_size)
register('ternary_queue', _ternary_queue_new)
register('ternary_queue_enqueue', _ternary_queue_enqueue)
register('ternary_queue_dequeue', _ternary_queue_dequeue)
register('ternary_queue_peek', _ternary_queue_peek)
register('ternary_queue_size', _ternary_queue_size)
register('ternary_stack', _ternary_stack_new)
register('ternary_stack_push', _ternary_stack_push)
register('ternary_stack_pop', _ternary_stack_pop)
register('ternary_stack_peek', _ternary_stack_peek)
register('ternary_stack_size', _ternary_stack_size)
