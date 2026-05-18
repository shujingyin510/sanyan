"""并发操作：并发执行、锁、延迟"""

import threading
from ternary_core import TritValue, ArrayValue
from values import SanyanSyntaxError, SanyanRuntimeError
from ops.registry import register, register_alias


class _ConcurrentContext:
    _lock = threading.Lock()
    _mutexes: dict[str, threading.Lock] = {}


def _spawn_thread(evaluator, fn_node, results, idx):
    try:
        results[idx] = evaluator.eval(fn_node)
    except Exception:
        results[idx] = TritValue(0)


def concurrent_run(evaluator, args):
    """并发(args...) — 并发执行多个函数调用，返回结果列表"""
    if not args:
        return TritValue(0)
    from evaluator import SanyanEvaluator

    threads = []
    results = [None] * len(args)

    for i, fn_node in enumerate(args):
        sub = SanyanEvaluator(max_loop_steps=evaluator.max_loop_steps)
        t = threading.Thread(target=_spawn_thread, args=(sub, fn_node, results, i))
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

    arr = ArrayValue(len(results), TritValue(0))
    for i, r in enumerate(results):
        arr.set(i, r if r is not None else TritValue(0))
    return arr


def delayed_run(evaluator, args):
    """延迟(毫秒, fn) — 等待指定毫秒后执行函数"""
    if len(args) < 2:
        raise SanyanSyntaxError('延迟 需要 毫秒 和 函数参数')
    ms_val = evaluator.eval(args[0])
    ms = ms_val.to_int() if isinstance(ms_val, TritValue) else int(ms_val)
    fn_node = args[1]

    import time

    time.sleep(ms / 1000.0)
    return evaluator.eval(fn_node)


def mutex_lock(evaluator, args):
    """锁(名称) — 创建或获取一个命名互斥锁，返回锁对象"""
    if not args:
        raise SanyanSyntaxError('锁 需要一个名称参数')
    name = args[0] if isinstance(args[0], str) else str(evaluator.eval(args[0]))
    with _ConcurrentContext._lock:
        if name not in _ConcurrentContext._mutexes:
            _ConcurrentContext._mutexes[name] = threading.Lock()
    return name


def mutex_acquire(evaluator, args):
    """锁住(名称) — 获取锁（阻塞直到可用）"""
    if not args:
        raise SanyanSyntaxError('锁住 需要一个锁名称')
    name = args[0] if isinstance(args[0], str) else str(evaluator.eval(args[0]))
    m = _ConcurrentContext._mutexes.get(name)
    if m is None:
        raise SanyanRuntimeError(f'未定义的锁: {name}')
    m.acquire()
    return TritValue(1)


def mutex_release(evaluator, args):
    """开锁(名称) — 释放锁"""
    if not args:
        raise SanyanSyntaxError('开锁 需要一个锁名称')
    name = args[0] if isinstance(args[0], str) else str(evaluator.eval(args[0]))
    m = _ConcurrentContext._mutexes.get(name)
    if m is None:
        raise SanyanRuntimeError(f'未定义的锁: {name}')
    try:
        m.release()
    except RuntimeError:
        pass
    return TritValue(0)


register('并发', concurrent_run)
register('延迟', delayed_run)
register('锁', mutex_lock)
register('锁住', mutex_acquire)
register('开锁', mutex_release)

register_alias('concurrent', '并发')
register_alias('delay', '延迟')
register_alias('lock', '锁')
register_alias('lock_acquire', '锁住')
register_alias('lock_release', '开锁')
