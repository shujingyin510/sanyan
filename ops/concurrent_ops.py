"""并发操作：并发执行、锁、延迟、并发融合"""

import threading
from core.ternary_core import TritValue, ArrayValue
from core.values import SanyanSyntaxError, SanyanRuntimeError
from ops.capability import capture_stack, install_stack
from ops.registry import register, register_alias
import concurrent.futures
from typing import Any


class _ConcurrentContext:
    _lock = threading.Lock()
    _mutexes: dict[str, threading.Lock] = {}


def _spawn_thread(evaluator, fn_node, results, idx):
    try:
        results[idx] = evaluator.eval(fn_node)
    except Exception as e:
        # 任务异常写进结果槽为可见错误标记（对抗探针 0708）——先前在子线程 re-raise，
        # 而子线程异常不传播到主线程：只打印 traceback 到 stderr、results[idx] 留 None、
        # 被主线程默认成 TritValue(0)，失败任务静默成合法值 0（除零→0 混进结果）。
        # 改为写错误字符串（与 并行块 的错误标记一致，不静默、不裸崩、无 stderr 噪音）。
        results[idx] = TritValue(f'并发执行错误: {e}')


def concurrent_run(evaluator, args):
    """并发(args...) — 并发执行多个函数调用，返回结果列表"""
    if not args:
        return TritValue(0)
    from core.evaluator import SanyanEvaluator

    threads = []
    results = [None] * len(args)
    snap = capture_stack(evaluator)  # E7：子求值器继承 spawn 时的约束

    for i, fn_node in enumerate(args):
        sub = SanyanEvaluator(max_loop_steps=evaluator.max_loop_steps)
        install_stack(sub, snap)
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


def _lock_name(evaluator, arg) -> str:
    """锁名 = eval 参数后的字符串——统一支持字面量与变量（对抗探针 0708 修复）。

    先前用 `arg if isinstance(arg, str) else eval(arg)`：**变量引用在 AST 里也是 str**，
    被当字面量符号名直用而非 eval 成其值——`(锁住 变量)` 永远查不到锁（用了符号名 'l'
    而非变量值 'a'），锁无法配合变量使用；且字面量 args 含引号使锁名带引号。统一 eval：
    字面量 eval 得字符串（不含引号），变量 eval 得其值，两条路径一致。
    """
    val = evaluator.eval(arg)
    if isinstance(val, TritValue) and val.is_string():
        return val.to_payload()
    return str(val)


def mutex_lock(evaluator, args):
    """锁(名称) — 创建或获取一个命名互斥锁，返回锁名"""
    if not args:
        raise SanyanSyntaxError('锁 需要一个名称参数')
    name = _lock_name(evaluator, args[0])
    with _ConcurrentContext._lock:
        if name not in _ConcurrentContext._mutexes:
            _ConcurrentContext._mutexes[name] = threading.Lock()
    return name


def mutex_acquire(evaluator, args):
    """锁住(名称) — 获取锁（阻塞直到可用）"""
    if not args:
        raise SanyanSyntaxError('锁住 需要一个锁名称')
    name = _lock_name(evaluator, args[0])
    m = _ConcurrentContext._mutexes.get(name)
    if m is None:
        raise SanyanRuntimeError(f'未定义的锁: {name}')
    m.acquire()
    return TritValue(1)


def mutex_release(evaluator, args):
    """开锁(名称) — 释放锁"""
    if not args:
        raise SanyanSyntaxError('开锁 需要一个锁名称')
    name = _lock_name(evaluator, args[0])
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
    from core.evaluator import SanyanEvaluator

    threads = []
    results = [None] * len(args)
    snap = capture_stack(evaluator)  # E7：子求值器继承 spawn 时的约束

    for i, fn_node in enumerate(args):
        sub = SanyanEvaluator(max_loop_steps=evaluator.max_loop_steps)
        install_stack(sub, snap)
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
register_alias('竞速', '并发竞速')
register_alias('concurrent_all', '并发全部')
register_alias('delay', '延迟')
register_alias('lock', '锁')
register_alias('lock_acquire', '锁住')
register_alias('lock_release', '开锁')


# ── 异步/并发语法扩展 ──

# 线程池（复用，避免频繁创建销毁）
_thread_pool = None


def _get_thread_pool():
    global _thread_pool
    if _thread_pool is None:
        _thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers=8)
    return _thread_pool


class Future:
    """异步结果包装器。"""

    def __init__(self, future: concurrent.futures.Future):
        self._future = future

    def is_done(self) -> bool:
        return self._future.done()

    def result(self, timeout: float | None = None) -> Any:
        try:
            return self._future.result(timeout=timeout)
        except Exception as e:
            raise SanyanRuntimeError(f'异步执行错误: {e}') from e

    def cancel(self) -> bool:
        return self._future.cancel()


def async_define(evaluator, args):
    """异步定义(args...) — 创建异步任务，返回 Future 对象。

    用法: (异步定义 (函数调用))
    """
    if not args:
        raise SanyanSyntaxError('异步定义 需要一个表达式参数')

    fn_node = args[0]
    pool = _get_thread_pool()
    snap = capture_stack(evaluator)  # E7：spawn 时捕获（异步延迟执行时父可能已退出约束块）

    def _run():
        from core.evaluator import SanyanEvaluator

        sub = SanyanEvaluator(max_loop_steps=evaluator.max_loop_steps)
        install_stack(sub, snap)
        # 复制作用域
        for scope in evaluator._scopes:
            for k, v in scope.items():
                sub.set_var(k, v)
        return sub.eval(fn_node)

    future = pool.submit(_run)
    return Future(future)


def async_await(evaluator, args):
    """等待(future) — 等待异步任务完成，返回结果。

    用法: (等待 future)
    """
    if not args:
        raise SanyanSyntaxError('等待 需要一个 Future 参数')

    future_val = evaluator.eval(args[0])
    if not isinstance(future_val, Future):
        # 如果不是 Future，直接返回值
        return future_val

    try:
        return future_val.result(timeout=30)
    except Exception as e:
        raise SanyanRuntimeError(f'等待异步任务失败: {e}') from e


def async_parallel(evaluator, args):
    """并行块(args...) — 并行执行多个表达式，返回结果列表。

    用法: (并行块 expr1 expr2 expr3)
    """
    if not args:
        return ArrayValue(0, TritValue(0))

    pool = _get_thread_pool()
    futures = []
    snap = capture_stack(evaluator)  # E7：spawn 时捕获约束

    for expr in args:

        def _run(e=expr):
            from core.evaluator import SanyanEvaluator

            sub = SanyanEvaluator(max_loop_steps=evaluator.max_loop_steps)
            install_stack(sub, snap)
            # 复制作用域
            for scope in evaluator._scopes:
                for k, v in scope.items():
                    sub.set_var(k, v)
            return sub.eval(e)

        futures.append(pool.submit(_run))

    results = []
    for f in futures:
        try:
            results.append(f.result(timeout=30))
        except Exception as e:
            results.append(SanyanRuntimeError(f'并行执行错误: {e}'))

    arr = ArrayValue(len(results), TritValue(0))
    for i, r in enumerate(results):
        arr.set(i, r if r is not None else TritValue(0))
    return arr


def async_is_done(evaluator, args):
    """异步完成(future) — 检查异步任务是否完成。

    用法: (异步完成 future)
    """
    if not args:
        raise SanyanSyntaxError('异步完成 需要一个 Future 参数')

    future_val = evaluator.eval(args[0])
    if not isinstance(future_val, Future):
        return TritValue(1)  # 非 Future 视为已完成

    return TritValue(1 if future_val.is_done() else -1)


def async_cancel(evaluator, args):
    """异步取消(future) — 取消异步任务。

    用法: (异步取消 future)
    """
    if not args:
        raise SanyanSyntaxError('异步取消 需要一个 Future 参数')

    future_val = evaluator.eval(args[0])
    if not isinstance(future_val, Future):
        return TritValue(-1)  # 非 Future 无法取消

    return TritValue(1 if future_val.cancel() else -1)


# 注册异步操作
register('异步定义', async_define)
register('等待', async_await)
register('并行块', async_parallel)
register('异步完成', async_is_done)
register('异步取消', async_cancel)

register_alias('async', '异步定义')
register_alias('await', '等待')
register_alias('parallel', '并行块')
register_alias('async_done', '异步完成')
register_alias('async_cancel', '异步取消')
