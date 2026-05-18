"""时间操作：时间戳、格式化时间、睡眠"""
import time
from datetime import datetime
from ternary_core import TritValue
from ops.registry import register, register_alias


def time_timestamp(evaluator, args):
    """时间戳() — 返回当前 Unix 时间戳（秒）"""
    return TritValue(int(time.time()))


def time_format(evaluator, args):
    """格式化时间(格式) — 按格式字符串返回当前时间"""
    fmt = '%Y-%m-%d %H:%M:%S'
    if args:
        fmt_arg = evaluator.eval(args[0])
        fmt = str(fmt_arg) if not isinstance(fmt_arg, str) else fmt_arg
    return datetime.now().strftime(fmt)


def time_sleep(evaluator, args):
    """睡眠(毫秒) — 阻塞当前线程指定毫秒"""
    if not args:
        return TritValue(0)
    ms_val = evaluator.eval(args[0])
    ms = ms_val.to_int() if isinstance(ms_val, TritValue) else int(ms_val)
    time.sleep(max(0, ms) / 1000.0)
    return TritValue(0)


def time_perf_counter(evaluator, args):
    """计时() — 返回高精度计时器值（秒）"""
    return TritValue(int(time.perf_counter() * 1000))


register('时间戳', time_timestamp)
register('格式化时间', time_format)
register('睡眠', time_sleep)
register('计时', time_perf_counter)

register_alias('timestamp', '时间戳')
register_alias('format_time', '格式化时间')
register_alias('sleep', '睡眠')
register_alias('perf_counter', '计时')
