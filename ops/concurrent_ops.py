"""并发操作：并发执行、锁、延迟、并发融合"""

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
    except SanyanRuntimeError:
        raise
    except Exception as e:
        raise SanyanRuntimeError(f'并发执行错误: {e}') from e


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


def _fuse_ternary_results(results):
    """融合多个三态结果：使用 Kleene 强逻辑融合置信度。

    融合规则：
    - 所有结果为真(1) → 融合为真，置信度取最小值
    - 所有结果为假(-1) → 融合为假，置信度取最小值
    - 混合结果 → 融合为可能(0)，置信度取平均值
    - 包含可能(0) → 融合为可能，置信度取平均值
    """
    if not results:
        return TritValue(0)

    # 提取所有 TritValue 的值和置信度
    values = []
    confidences = []
    for r in results:
        if isinstance(r, TritValue):
            values.append(r.value[0] if r.value else 0)
            confidences.append(r.confidence)
        elif isinstance(r, (int, float)):
            values.append(1 if r != 0 else 0)
            confidences.append(1.0)
        else:
            values.append(0)
            confidences.append(0.5)

    # Kleene 融合逻辑
    all_pos = all(v == 1 for v in values)
    all_neg = all(v == -1 for v in values)

    if all_pos:
        fused_value = 1
        fused_conf = min(confidences) if confidences else 1.0
    elif all_neg:
        fused_value = -1
        fused_conf = min(confidences) if confidences else 1.0
    else:
        # 混合或包含可能
        fused_value = 0
        fused_conf = sum(confidences) / len(confidences) if confidences else 0.5

    return TritValue(fused_value, confidence=fused_conf)


def concurrent_fusion(evaluator, args):
    """并发融合(任务1, 任务2, ...) — 并发执行多个任务并融合结果。

    与并发()不同，并发融合会：
    1. 并发执行所有任务
    2. 使用 Kleene 强逻辑融合所有结果
    3. 返回单一融合后的三态值（带置信度）

    适用场景：多传感器融合、多源数据验证、冗余计算校验
    """
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

    # 过滤 None 结果
    valid_results = [r for r in results if r is not None]

    return _fuse_ternary_results(valid_results)


def concurrent_race(evaluator, args):
    """并发竞速(超时ms, 任务1, 任务2, ...) — 并发执行，取最先完成的结果。

    超时后未完成的任务被丢弃。
    返回最先完成的结果（带置信度）。
    """
    if len(args) < 2:
        raise SanyanSyntaxError('并发竞速 需要超时毫秒和至少一个任务')

    timeout_val = evaluator.eval(args[0])
    timeout_ms = timeout_val.to_int() if isinstance(timeout_val, TritValue) else int(timeout_val)
    task_nodes = args[1:]

    results = [None] * len(task_nodes)
    completed = threading.Event()
    completed_idx = [-1]

    def worker(idx, fn_node):
        try:
            results[idx] = evaluator.eval(fn_node)
            if not completed.is_set():
                completed_idx[0] = idx
                completed.set()
        except Exception:
            pass

    threads = []
    for i, fn_node in enumerate(task_nodes):
        t = threading.Thread(target=worker, args=(i, fn_node))
        t.daemon = True
        t.start()
        threads.append(t)

    completed.wait(timeout=timeout_ms / 1000.0)

    if completed_idx[0] >= 0:
        return results[completed_idx[0]]
    return TritValue(0)


def concurrent_all(evaluator, args):
    """并发全部(任务1, 任务2, ...) — 并发执行，全部成功才返回真。

    任一任务失败返回假，全部成功返回真。
    置信度为所有任务置信度的最小值。
    """
    if not args:
        return TritValue(1)

    threads = []
    results = [None] * len(args)
    errors = [None] * len(args)

    def safe_worker(idx, fn_node):
        try:
            results[idx] = evaluator.eval(fn_node)
        except Exception as e:
            errors[idx] = str(e)

    for i, fn_node in enumerate(args):
        t = threading.Thread(target=safe_worker, args=(i, fn_node))
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

    # 检查是否有错误
    has_error = any(e is not None for e in errors)

    if has_error:
        return TritValue(-1, confidence=0.8)

    # 全部成功，融合置信度
    confidences = []
    for r in results:
        if isinstance(r, TritValue):
            confidences.append(r.confidence)
        else:
            confidences.append(1.0)

    min_conf = min(confidences) if confidences else 1.0
    return TritValue(1, confidence=min_conf)


register('并发', concurrent_run)
register('并发融合', concurrent_fusion)
register('并发竞速', concurrent_race)
register('并发全部', concurrent_all)
register('延迟', delayed_run)
register('锁', mutex_lock)
register('锁住', mutex_acquire)
register('开锁', mutex_release)

register_alias('concurrent', '并发')
register_alias('concurrent_fusion', '并发融合')
register_alias('concurrent_race', '并发竞速')
register_alias('concurrent_all', '并发全部')
register_alias('delay', '延迟')
register_alias('lock', '锁')
register_alias('lock_acquire', '锁住')
register_alias('lock_release', '开锁')
