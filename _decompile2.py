"""Decompile sugar.bin correctly using 1-byte PUSH_STR length"""

import struct

with open('stdlib/sugar.bin', 'rb') as f:
    data = f.read()

magic, ver, vc, sz = struct.unpack_from('<4sBBI', data, 0)
code = data[10 : 10 + sz]
print(f'Total code size: {sz}, var_count: {vc}')

OP = {
    0: 'NOP',
    1: 'PUSH_I',
    2: 'ADD',
    3: 'SUB',
    4: 'MUL',
    5: 'DIV',
    6: 'MOD',
    7: 'LOAD',
    8: 'STORE',
    9: 'JMP',
    10: 'JZ',
    11: 'JNZ',
    12: 'CALL',
    13: 'RET',
    14: 'PRINT',
    15: 'IO_READ',
    16: 'IO_WRITE',
    17: 'EQ',
    18: 'NE',
    19: 'GT',
    20: 'LT',
    21: 'GTE',
    22: 'LTE',
    23: 'NOT',
    24: 'WAIT',
    25: 'CONCAT',
    26: 'STRLEN',
    27: 'STRSUB',
    28: 'STREQ',
    29: 'DICT',
    30: 'DICT_GET',
    31: 'DICT_SET',
    32: 'DICT_HAS',
    33: 'IS_NUM',
    34: 'IS_STR',
    35: 'IS_LIST',
    36: 'SAME',
    37: 'GET',
    38: 'SET_ELEMENT',
    39: 'LIST_NEW',
    40: 'LIST_CONCAT',
    41: 'SLICE',
    42: 'LIST_LEN',
    43: 'READ_FILE',
    44: 'WRITE_FILE',
    45: 'PUSH_STR',
    46: 'IMPORT',
    47: 'CALL_EXT',
    48: 'WRITE_BINARY',
    49: 'ORD',
    50: 'DICT_KEYS',
    51: 'JMP32',
    52: 'OR',
    53: 'AND',
    54: 'STR_FIND',
    55: 'STR_TO_LIST',
    56: 'STR_STARTSWITH',
    57: 'STR_CONTAINS',
    58: 'DICT_LEN',
    75: 'MAKE_CLOSURE',
    76: 'CALL_CLOSURE',
    255: 'HALT',
}


def disasm(start, n=300):
    i = start
    end = min(start + n, len(code))
    while i < end:
        op = code[i]
        name = OP.get(op, f'?{op:02X}?')

        if op == 1:  # PUSH_I
            val = int.from_bytes(code[i + 1 : i + 5], 'little', signed=True)
            print(f'  [{i:5d}] PUSH_I {val}')
            i += 5
        elif op == 45:  # PUSH_STR
            length = code[i + 1]  # 1 byte: number of UTF-16 code units
            chars = []
            pos = i + 2
            for _ in range(length):
                lo = code[pos]
                hi = code[pos + 1]
                chars.append(chr(lo | (hi << 8)))
                pos += 2
            s = ''.join(chars)
            print(f'  [{i:5d}] PUSH_STR {repr(s[:60])}')
            i = pos
        elif op in (7, 8):  # LOAD, STORE
            vi = code[i + 1]
            print(f'  [{i:5d}] {name} var[{vi}]')
            i += 2
        elif op == 9:  # JMP (absolute)
            offset = int.from_bytes(code[i + 1 : i + 5], 'little', signed=True)
            print(f'  [{i:5d}] JMP -> {offset}')
            i += 5
        elif op in (10, 11):  # JZ, JNZ (relative)
            offset = int.from_bytes(code[i + 1 : i + 5], 'little', signed=True)
            target = i + 5 + offset
            print(f'  [{i:5d}] {name} -> {target}')
            i += 5
        elif op == 12:  # CALL
            target = int.from_bytes(code[i + 1 : i + 5], 'little', signed=True)
            print(f'  [{i:5d}] CALL -> {target}')
            i += 5
        elif op == 51:  # JMP32 (relative)
            offset = int.from_bytes(code[i + 1 : i + 5], 'little', signed=True)
            target = i + 5 + offset
            print(f'  [{i:5d}] JMP32 -> {target}')
            i += 5
        elif op == 75:  # MAKE_CLOSURE
            addr = int.from_bytes(code[i + 1 : i + 5], 'little', signed=True)
            print(f'  [{i:5d}] MAKE_CLOSURE func_addr={addr}')
            i += 5
        elif op == 76:  # CALL_CLOSURE
            print(f'  [{i:5d}] CALL_CLOSURE')
            i += 1
        elif op == 255:
            print(f'  [{i:5d}] HALT')
            i += 1
        elif op == 29:  # DICT
            print(f'  [{i:5d}] DICT')
            i += 1
        elif op in (
            30,
            31,
            32,
            49,
            50,
            25,
            26,
            27,
            37,
            38,
            39,
            40,
            41,
            42,
            58,
            17,
            18,
            19,
            20,
            21,
            22,
            23,
            36,
            33,
            34,
            35,
            28,
            54,
        ):
            print(f'  [{i:5d}] {name}')
            i += 1
        else:
            print(f'  [{i:5d}] ??? op={op} ({name})')
            i += 1


# Decompile at 词法分析 offset 632
print('\n=== 词法分析 (632) ===')
disasm(632, 500)

# Also check at 解析 offset 10167
print('\n\n=== 解析 (10167) ===')
disasm(10167, 200)
