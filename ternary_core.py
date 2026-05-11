"""三进制核心库：平衡三进制整数、算术逻辑单元、三值对象"""
from typing import Union


class BT:
    SYMBOLS = {1: '+', 0: '0', -1: '-'}
    REVERSE = {'+': 1, '0': 0, '-': -1}

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
                res.append(-1); carry = 1
            elif s == 3:
                res.append(0); carry = 1
            elif s == -2:
                res.append(1); carry = -1
            elif s == -3:
                res.append(0); carry = -1
            else:
                res.append(s); carry = 0
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
            (1, 1): 1, (1, 0): 0, (1, -1): -1,
            (0, 1): 0, (0, 0): 0, (0, -1): -1,
            (-1, 1): -1, (-1, 0): -1, (-1, -1): -1,
        }
        return [table[(x, y)] for x, y in zip(a, b)]

    @staticmethod
    def tritwise_or(a: list, b: list) -> list:
        max_len = max(len(a), len(b))
        a = [0] * (max_len - len(a)) + a
        b = [0] * (max_len - len(b)) + b
        table = {
            (1, 1): 1, (1, 0): 1, (1, -1): 1,
            (0, 1): 1, (0, 0): 0, (0, -1): 0,
            (-1, 1): 1, (-1, 0): 0, (-1, -1): -1,
        }
        return [table[(x, y)] for x, y in zip(a, b)]

    @staticmethod
    def tritwise_not(a: list) -> list:
        return [-x for x in a]
    
    @staticmethod
    def multiply(a: list, b: list) -> list:
        """平衡三进制乘法：通过移位加实现"""
        if TernaryALU.is_zero(a) or TernaryALU.is_zero(b):
            return [0]
        result = [0]
        for i, trit in enumerate(reversed(b)):
            if trit == 1:
                shifted = a + [0] * i
                result = TernaryALU.add(result, shifted)
            elif trit == -1:
                shifted = a + [0] * i
                result = TernaryALU.sub(result, shifted)
        return result

    @staticmethod
    def is_zero(a: list) -> bool:
        return all(x == 0 for x in a)


class TritValue:
    STATE_MAP = {
        '开': 1, '高': 1, '真': 1, '亮': 1, '启': 1, '通': 1, '有': 1, '是': 1,
        '关': -1, '低': -1, '假': -1, '灭': -1, '停': -1, '断': -1, '无': -1, '否': -1,
        '守': 0, '中': 0, '可能': 0, '待': 0, '未知': 0,
    }

    def __init__(self, value: Union[int, list]):
        if isinstance(value, int):
            self.value = BT.from_int(value)
        else:
            self.value = value
        self.symbol = BT.to_str(self.value)

    @staticmethod
    def from_string(word: str) -> 'TritValue':
        if word in TritValue.STATE_MAP:
            return TritValue(TritValue.STATE_MAP[word])
        raise ValueError(f"未知的三态词: {word}")

    def to_int(self):
        return BT.to_int(self.value)

    def __repr__(self):
        return str(self.to_int())      # 只返回整数，如 "3"


class ArrayValue:
    """固定长度数组，元素可以是任意值"""
    def __init__(self, length, default=TritValue(0)):
        self.length = length
        self.data = [default] * length

    def get(self, index):
        if index < 0 or index >= self.length:
            raise IndexError(f"数组索引越界: {index} (长度 {self.length})")
        return self.data[index]

    def set(self, index, value):
        if index < 0 or index >= self.length:
            raise IndexError(f"数组索引越界: {index} (长度 {self.length})")
        self.data[index] = value
        return self

    def to_list(self):
        return self.data[:]

    def __getitem__(self, index):
        return self.get(index)

    def __setitem__(self, index, value):
        self.set(index, value)

    def __repr__(self):
        return '[' + ', '.join(str(x) for x in self.data) + ']'