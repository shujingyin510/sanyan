"""Correct decompilation of 词法分析 function"""

import struct

with open('stdlib/sugar.bin', 'rb') as f:
    data = f.read()

magic, ver, vc, sz = struct.unpack_from('<4sBBI', data, 0)
code = data[10 : 10 + sz]

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


def read_i16(c, pos):
    return struct.unpack_from('<h', c, pos)[0], pos + 2


def read_i32(c, pos):
    return struct.unpack_from('<i', c, pos)[0], pos + 4


def disasm(start, n=200):
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
            length = code[i + 1]
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
        elif op == 7:  # LOAD
            vi = code[i + 1]
            print(f'  [{i:5d}] LOAD var[{vi}]')
            i += 2
        elif op == 8:  # STORE
            vi = code[i + 1]
            print(f'  [{i:5d}] STORE var[{vi}]')
            i += 2
        elif op == 9:  # JMP (16-bit relative)
            off, _ = read_i16(code, i + 1)
            target = i + 3 + off
            print(f'  [{i:5d}] JMP -> {target} (off={off})')
            i += 3
        elif op == 10:  # JZ (16-bit relative)
            off, _ = read_i16(code, i + 1)
            target = i + 3 + off
            print(f'  [{i:5d}] JZ -> {target} (off={off})')
            i += 3
        elif op == 11:  # JNZ (16-bit relative)
            off, _ = read_i16(code, i + 1)
            target = i + 3 + off
            print(f'  [{i:5d}] JNZ -> {target} (off={off})')
            i += 3
        elif op == 12:  # CALL
            target = int.from_bytes(code[i + 1 : i + 5], 'little', signed=True)
            print(f'  [{i:5d}] CALL -> {target}')
            i += 5
        elif op == 51:  # JMP32 (32-bit relative)
            off, _ = read_i32(code, i + 1)
            target = i + 5 + off
            print(f'  [{i:5d}] JMP32 -> {target} (off={off})')
            i += 5
        elif op == 75:  # MAKE_CLOSURE
            addr = int.from_bytes(code[i + 1 : i + 5], 'little', signed=True)
            print(f'  [{i:5d}] MAKE_CLOSURE -> func_addr={addr}')
            i += 5
        elif op == 76:  # CALL_CLOSURE
            print(f'  [{i:5d}] CALL_CLOSURE')
            i += 1
        elif op == 255:
            print(f'  [{i:5d}] HALT')
            i += 1
        elif op in (29, 30, 31, 32, 50, 25, 26, 27, 37, 38, 39, 40, 41, 42, 58):
            print(f'  [{i:5d}] {name}')
            i += 1
        elif op == 17:
            print(f'  [{i:5d}] EQ')
            i += 1
        elif op == 18:
            print(f'  [{i:5d}] NE')
            i += 1
        elif op == 19:
            print(f'  [{i:5d}] GT')
            i += 1
        elif op == 20:
            print(f'  [{i:5d}] LT')
            i += 1
        elif op == 21:
            print(f'  [{i:5d}] GTE')
            i += 1
        elif op == 22:
            print(f'  [{i:5d}] LTE')
            i += 1
        elif op == 23:
            print(f'  [{i:5d}] NOT')
            i += 1
        elif op == 36:
            print(f'  [{i:5d}] SAME')
            i += 1
        elif op == 52:
            print(f'  [{i:5d}] OR')
            i += 1
        elif op == 53:
            print(f'  [{i:5d}] AND')
            i += 1
        elif op == 54:
            print(f'  [{i:5d}] STR_FIND')
            i += 1
        elif op == 28:
            print(f'  [{i:5d}] STREQ')
            i += 1
        elif op in (33, 34, 35):
            print(f'  [{i:5d}] {name}')
            i += 1
        elif op == 56:
            print(f'  [{i:5d}] STR_STARTSWITH')
            i += 1
        elif op == 57:
            print(f'  [{i:5d}] STR_CONTAINS')
            i += 1
        elif op == 49:
            print(f'  [{i:5d}] ORD')
            i += 1
        elif op == 14:
            print(f'  [{i:5d}] PRINT')
            i += 1
        elif op == 0:
            print(f'  [{i:5d}] NOP')
            i += 1
        else:
            print(f'  [{i:5d}] ??? op=0x{op:02X} ({op})')
            i += 1


print('=== 词法分析 (starting at 632) ===')
disasm(632, 400)
