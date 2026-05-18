"""共享工具函数"""

from ternary_core import TritValue


def to_str(val):
    if isinstance(val, str):
        return val
    if isinstance(val, TritValue):
        return str(val)
    return str(val)
