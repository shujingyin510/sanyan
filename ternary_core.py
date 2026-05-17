"""三进制核心库：平衡三进制整数、算术逻辑单元、三值对象"""

from __future__ import annotations
import os
import threading
from collections import OrderedDict
from typing import Union


class BT:
    SYMBOLS = {1: '+', 0: '0', -1: '-'}
    REVERSE = {'+': 1, '0': 0, '-': -1}
    DEFAULT_PRECISION = 16  # 默认小数位数（三进制 trits）

    @staticmethod
    def from_int(n: int, length: int = None) -> list:
        if n == 0:
            trits = [0]
        else:
            abs_n = abs(n)
            trits = []
            while abs_n != 0:
                r = abs_n % 3
                abs_n //= 3
                if r == 2:
                    trits.append(-1)
                    abs_n += 1
                else:
                    trits.append(r)
            trits.reverse()
            if n < 0:
                trits = [-t for t in trits]
        if length:
            trits = ([0] * (length - len(trits))) + trits
        return trits

    @staticmethod
    def to_int(trits: list) -> int:
        val = 0
        for t in trits:
            val = val * 3 + t
        return val

    @staticmethod
    def to_str(trits: list) -> str:
        return ''.join(BT.SYMBOLS[t] for t in trits)

    @staticmethod
    def from_str(s: str) -> list:
        return [BT.REVERSE[c] for c in s]

    @staticmethod
    def from_float(n: float, precision: int = None) -> list:
        """将浮点数转为平衡三进制定点表示。

        使用缩放整数法：将 n * 3^precision 转为整数，再转为平衡三进制。
        """
        if precision is None:
            precision = BT.DEFAULT_PRECISION
        scale = 3**precision
        scaled = int(round(n * scale))
        return BT.from_int(scaled)

    @staticmethod
    def to_float(trits: list, precision: int = None) -> float:
        """将平衡三进制定点表示转回浮点数。"""
        if precision is None:
            precision = BT.DEFAULT_PRECISION
        scale = 3**precision
        int_val = BT.to_int(trits)
        return int_val / scale


class TernaryALU:
    @staticmethod
    def add(a: list, b: list) -> list:
        max_len = max(len(a), len(b))
        a = [0] * (max_len - len(a)) + a
        b = [0] * (max_len - len(b)) + b
        res = []
        carry = 0
        for i in range(max_len - 1, -1, -1):
            s = a[i] + b[i] + carry
            if s == 2:
                res.append(-1)
                carry = 1
            elif s == 3:
                res.append(0)
                carry = 1
            elif s == -2:
                res.append(1)
                carry = -1
            elif s == -3:
                res.append(0)
                carry = -1
            else:
                res.append(s)
                carry = 0
        if carry:
            res.append(carry)
        res.reverse()
        return res

    @staticmethod
    def sub(a: list, b: list):
        return TernaryALU.add(a, [-x for x in b])

    @staticmethod
    def tritwise_and(a: list, b: list) -> list:
        max_len = max(len(a), len(b))
        a = [0] * (max_len - len(a)) + a
        b = [0] * (max_len - len(b)) + b
        table = {
            (1, 1): 1,
            (1, 0): 0,
            (1, -1): -1,
            (0, 1): 0,
            (0, 0): 0,
            (0, -1): -1,
            (-1, 1): -1,
            (-1, 0): -1,
            (-1, -1): -1,
        }
        return [table[(x, y)] for x, y in zip(a, b)]

    @staticmethod
    def tritwise_or(a: list, b: list) -> list:
        max_len = max(len(a), len(b))
        a = [0] * (max_len - len(a)) + a
        b = [0] * (max_len - len(b)) + b
        table = {
            (1, 1): 1,
            (1, 0): 1,
            (1, -1): 1,
            (0, 1): 1,
            (0, 0): 0,
            (0, -1): 0,
            (-1, 1): 1,
            (-1, 0): 0,
            (-1, -1): -1,
        }
        return [table[(x, y)] for x, y in zip(a, b)]

    @staticmethod
    def tritwise_not(a: list) -> list:
        return [-x for x in a]

    @staticmethod
    def multiply(a: list, b: list) -> list:
        """平衡三进制乘法：大数走快速路径，小数走移位加。"""
        if TernaryALU.is_zero(a) or TernaryALU.is_zero(b):
            return [0]
        a_int = BT.to_int(a)
        b_int = BT.to_int(b)
        return BT.from_int(a_int * b_int)

    @staticmethod
    def div(a: list, b: list, precision: int = 0) -> list:
        """定点除法：a / b，精度 precision 位。"""
        if TernaryALU.is_zero(b):
            raise ZeroDivisionError('ternary division by zero')
        a_int = BT.to_int(a)
        b_int = BT.to_int(b)
        return BT.from_int(int(round(a_int * (3**precision) / b_int)))

    @staticmethod
    def fixed_mul(a: list, b: list, precision: int) -> list:
        """定点乘法：a * b / 3^precision"""
        a_int = BT.to_int(a)
        b_int = BT.to_int(b)
        return BT.from_int(int(round(a_int * b_int / (3**precision))))

    @staticmethod
    def fixed_div(a: list, b: list, precision: int) -> list:
        """定点除法：a / b（已按 precision 缩放）"""
        return TernaryALU.div(a, b, precision)

    @staticmethod
    def neg(a: list) -> list:
        return [-x for x in a]

    @staticmethod
    def is_zero(a: list) -> bool:
        return all(x == 0 for x in a)


class TritValue:
    __slots__ = ('value', 'symbol', 'float_val', '_initialized', 'precision')

    STATE_MAP = {
        '开': 1,
        '高': 1,
        '真': 1,
        '亮': 1,
        '启': 1,
        '通': 1,
        '有': 1,
        '是': 1,
        '关': -1,
        '低': -1,
        '假': -1,
        '灭': -1,
        '停': -1,
        '断': -1,
        '无': -1,
        '否': -1,
        '守': 0,
        '中': 0,
        '可能': 0,
        '待': 0,
        '未知': 0,
    }

    _pool = OrderedDict()
    _pool_lock = threading.Lock()
    _MAX_POOL_SIZE = max(1, int(os.environ.get('TRIT_POOL_SIZE', '10000')))

    def __new__(cls, value, precision: int = None):
        def _hashable(v):
            if isinstance(v, list):
                return tuple(_hashable(x) for x in v)
            return v

        key = (
            (value, precision)
            if isinstance(value, (int, float))
            else (_hashable(value), precision)
            if isinstance(value, list)
            else (value, precision)
        )
        with cls._pool_lock:
            if key in cls._pool:
                cls._pool.move_to_end(key)
                return cls._pool[key]
            if len(cls._pool) >= cls._MAX_POOL_SIZE:
                cls._pool.popitem(last=False)
            obj = super().__new__(cls)
            cls._pool[key] = obj
            return obj

    def __init__(self, value: Union[int, float, list], precision: int = None):
        if hasattr(self, '_initialized'):
            return
        self._initialized = True
        self.precision = precision if precision is not None else 0
        self.float_val = None
        if isinstance(value, int):
            self.value = BT.from_int(value)
        elif isinstance(value, float):
            self.float_val = value
            if precision is None:
                self.precision = BT.DEFAULT_PRECISION
            else:
                self.precision = precision
            self.value = BT.from_float(value, self.precision)
        else:
            self.value = value
        self.symbol = BT.to_str(self.value)

    @staticmethod
    def from_string(word: str) -> 'TritValue':
        if word in TritValue.STATE_MAP:
            return TritValue(TritValue.STATE_MAP[word])
        raise ValueError(f'未知的三态词: {word}')

    def to_int(self) -> int:
        if self.float_val is not None:
            return int(round(self.float_val))
        if self.precision > 0:
            return int(BT.to_float(self.value, self.precision))
        return BT.to_int(self.value)

    def to_float(self) -> float:
        if self.float_val is not None:
            return self.float_val
        if self.precision > 0:
            return BT.to_float(self.value, self.precision)
        return float(self.to_int())

    def is_float(self) -> bool:
        return self.float_val is not None or self.precision > 0

    def __repr__(self):
        if self.float_val is not None:
            return f'{self.float_val}'
        return str(self.to_int())  # 只返回整数，如 "3"


class ArrayValue:
    """固定长度数组，元素可以是任意值"""

    __slots__ = ('length', 'data')

    def __init__(self, length: int, default: object = TritValue(0)) -> None:
        self.length = length
        self.data = [default] * length

    def get(self, index: int) -> object:
        if index < 0 or index >= self.length:
            raise IndexError(f'数组索引越界: {index} (长度 {self.length})')
        return self.data[index]

    def set(self, index: int, value: object) -> 'ArrayValue':
        if index < 0 or index >= self.length:
            raise IndexError(f'数组索引越界: {index} (长度 {self.length})')
        self.data[index] = value
        return self

    def to_list(self) -> list:
        return self.data[:]

    def __getitem__(self, index):
        return self.get(index)

    def __setitem__(self, index, value):
        self.set(index, value)

    def __repr__(self):
        return '[' + ', '.join(str(x) for x in self.data) + ']'


# --- 三进制数学函数（纯 trit 定点运算，无 Python float 中间量）---

_TAYLOR_TERMS = 12

# 数学常量缓存（按精度惰性初始化）
_PI_TRITS_CACHE: dict[int, list] = {}
_TWO_PI_TRITS_CACHE: dict[int, list] = {}
_HALF_PI_TRITS_CACHE: dict[int, list] = {}


def _int_at_precision(n: int, precision: int) -> list:
    """将整数 n 提升到定点 scale：返回 n * 3^precision 的三进制表示。"""
    return BT.from_int(n * (3**precision))


def _half_at_precision(precision: int) -> list:
    """返回 0.5 在指定精度的三进制表示。"""
    return BT.from_float(0.5, precision)


def _get_pi(precision: int) -> list:
    if precision not in _PI_TRITS_CACHE:
        _PI_TRITS_CACHE[precision] = BT.from_float(3.141592653589793, precision)
    return _PI_TRITS_CACHE[precision]


def _get_two_pi(precision: int) -> list:
    if precision not in _TWO_PI_TRITS_CACHE:
        _TWO_PI_TRITS_CACHE[precision] = BT.from_float(6.283185307179586, precision)
    return _TWO_PI_TRITS_CACHE[precision]


def _get_half_pi(precision: int) -> list:
    if precision not in _HALF_PI_TRITS_CACHE:
        _HALF_PI_TRITS_CACHE[precision] = BT.from_float(1.5707963267948966, precision)
    return _HALF_PI_TRITS_CACHE[precision]


def _ternary_range_reduce(x_trits: list, precision: int) -> list:
    """纯三进制范围规约：将 x 模 2π 归到 [-π, π]。

    全程使用缩放整数运算，不经过 Python float。
    """
    scale = 3**precision
    x_int = BT.to_int(x_trits)
    two_pi_int = int(round(6.283185307179586 * scale))
    pi_int = int(round(3.141592653589793 * scale))
    reduced = x_int % two_pi_int
    if reduced > pi_int:
        reduced -= two_pi_int
    elif reduced < -pi_int:
        reduced += two_pi_int
    return BT.from_int(reduced)


def ternary_sin(x_trits: list, precision: int = None) -> list:
    """sin(x) 用 Taylor 级数在三进制定点计算。

    Taylor 系数使用纯整数分母，无 Python float 中间量。
    """
    if precision is None:
        precision = BT.DEFAULT_PRECISION
    x = _ternary_range_reduce(x_trits, precision)
    x_sq = TernaryALU.fixed_mul(x, x, precision)
    term = x
    result = term
    for k in range(1, _TAYLOR_TERMS):
        term = TernaryALU.fixed_mul(term, x_sq, precision)
        term = TernaryALU.neg(term)
        denom = (2 * k) * (2 * k + 1)
        term = TernaryALU.fixed_div(term, _int_at_precision(denom, precision), precision)
        result = TernaryALU.add(result, term)
    return result


def ternary_cos(x_trits: list, precision: int = None) -> list:
    """cos(x) = sin(x + pi/2)"""
    if precision is None:
        precision = BT.DEFAULT_PRECISION
    return ternary_sin(TernaryALU.add(x_trits, _get_half_pi(precision)), precision)


def ternary_tan(x_trits: list, precision: int = None) -> list:
    """tan(x) = sin(x) / cos(x)"""
    if precision is None:
        precision = BT.DEFAULT_PRECISION
    s = ternary_sin(x_trits, precision)
    c = ternary_cos(x_trits, precision)
    if TernaryALU.is_zero(c):
        raise ValueError('tan(x): cos(x) is zero')
    return TernaryALU.fixed_div(s, c, precision)


def ternary_sqrt(x_trits: list, precision: int = None) -> list:
    """sqrt(x) Newton 法 — 无 float 初始猜测，纯 trit 迭代"""
    if precision is None:
        precision = BT.DEFAULT_PRECISION
    scale = 3**precision
    if TernaryALU.is_zero(x_trits):
        return BT.from_int(0)
    x_int = BT.to_int(x_trits)
    if x_int < 0:
        raise ValueError('sqrt: negative argument')
    # 初始猜测：x/2 或 1（取决于 x 是否大于 1），全部在定点域计算
    if x_int > scale:
        guess = BT.from_int(int(round(x_int / 2)))
    else:
        guess = BT.from_int(scale)  # 1.0 在定点的表示
    half = _half_at_precision(precision)
    for _ in range(20):
        div = TernaryALU.fixed_div(x_trits, guess, precision)
        guess = TernaryALU.fixed_mul(TernaryALU.add(guess, div), half, precision)
    return guess


def ternary_exp(x_trits: list, precision: int = None) -> list:
    """exp(x) Taylor 级数 — 分母使用纯整数"""
    if precision is None:
        precision = BT.DEFAULT_PRECISION
    one = _int_at_precision(1, precision)
    term = one
    result = one
    for k in range(1, _TAYLOR_TERMS * 2):
        term = TernaryALU.fixed_mul(term, x_trits, precision)
        term = TernaryALU.fixed_div(term, _int_at_precision(k, precision), precision)
        result = TernaryALU.add(result, term)
        if TernaryALU.is_zero(term):
            break
    return result


def ternary_log(x_trits: list, precision: int = None) -> list:
    """ln(x) Newton 法 — 无 float 中间量"""
    if precision is None:
        precision = BT.DEFAULT_PRECISION
    scale = 3**precision
    x_int = BT.to_int(x_trits)
    if x_int <= 0:
        raise ValueError('log: argument must be positive')
    one = _int_at_precision(1, precision)
    # 初始猜测：x/3 或 0.5（取决于 x 是否大于 2），全部在定点域
    if x_int > 2 * scale:
        guess = BT.from_int(int(round(x_int / 3)))
    else:
        guess = _half_at_precision(precision)
    for _ in range(30):
        e = ternary_exp(guess, precision)
        ratio = TernaryALU.fixed_div(x_trits, e, precision)
        guess = TernaryALU.add(guess, TernaryALU.sub(ratio, one))
    return guess


def ternary_log10(x_trits: list, precision: int = None) -> list:
    """log10(x) = ln(x) / ln(10)"""
    if precision is None:
        precision = BT.DEFAULT_PRECISION
    ln_x = ternary_log(x_trits, precision)
    ln_10 = ternary_log(_int_at_precision(10, precision), precision)
    return TernaryALU.fixed_div(ln_x, ln_10, precision)
