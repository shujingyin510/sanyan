"""Decompile sugar.bin at 词法分析 offset"""

import struct

with open('stdlib/sugar.bin', 'rb') as f:
    data = f.read()

code_size = int.from_bytes(data[6:10], 'little')
var_count = data[10]
code = data[11:]
print(f'code_size={code_size}, var_count={var_count}')

# Opcode map from vm.py
OP = {
    0x00: 'NOP',
    0x01: 'PUSH_I',
    0x02: 'ADD',
    0x03: 'SUB',
    0x04: 'MUL',
    0x05: 'DIV',
    0x06: 'MOD',
    0x07: 'LOAD',
    0x08: 'STORE',
    0x09: 'JMP',
    0x0A: 'JZ',
    0x0B: 'JNZ',
    0x0C: 'CALL',
    0x0D: 'RET',
    0x0E: 'PRINT',
    0x0F: 'IO_READ',
    0x10: 'IO_WRITE',
    0x11: 'EQ',
    0x12: 'NE',
    0x13: 'GT',
    0x14: 'LT',
    0x15: 'GTE',
    0x16: 'LTE',
    0x17: 'NOT',
    0x18: 'WAIT',
    0x19: 'CONCAT',
    0x1A: 'STRLEN',
    0x1B: 'STRSUB',
    0x1C: 'STREQ',
    0x1D: 'DICT',
    0x1E: 'DICT_GET',
    0x1F: 'DICT_SET',
    0x20: 'DICT_HAS',
    0x21: 'IS_NUM',
    0x22: 'IS_STR',
    0x23: 'IS_LIST',
    0x24: 'SAME',
    0x25: 'GET',
    0x26: 'SET_ELEMENT',
    0x27: 'LIST_NEW',
    0x28: 'LIST_CONCAT',
    0x29: 'SLICE',
    0x2A: 'LIST_LEN',
    0x2B: 'READ_FILE',
    0x2C: 'WRITE_FILE',
    0x2D: 'PUSH_STR',
    0x2E: 'IMPORT',
    0x2F: 'CALL_EXT',
    0x30: 'WRITE_BINARY',
    0x31: 'ORD',
    0x32: 'DICT_KEYS',
    0x33: 'JMP32',
    0x34: 'OR',
    0x35: 'AND',
    0x36: 'STR_FIND',
    0x37: 'STR_TO_LIST',
    0x38: 'STR_STARTSWITH',
    0x39: 'STR_CONTAINS',
    0x3A: 'DICT_LEN',
    0x3B: 'BIT_AND',
    0x3C: 'BIT_OR',
    0x3D: 'BIT_XOR',
    0x3E: 'BIT_NOT',
    0x3F: 'SHIFT_L',
    0x40: 'SHIFT_R',
    0x41: 'BIT_SET',
    0x42: 'BIT_CLR',
    0x43: 'BIT_TGL',
    0x44: 'BIT_TST',
    0x45: 'LO_BYTE',
    0x46: 'HI_BYTE',
    0x47: 'MRG_BYT',
    0x4B: 'MAKE_CLOSURE',
    0x4C: 'CALL_CLOSURE',
    0xFF: 'HALT',
}

SIZE = {
    0x01: 5,  # PUSH_I: op + 4byte int
    0x2D: lambda d, i: 3 + struct.unpack_from('<H', d, i + 1)[0],  # PUSH_STR: op + 2byte len + string
}

# Make string VAR_NAMES lookup based on source
src = open('stdlib/sugar.san', encoding='utf-8').read()
var_names = {}  # var_index -> name hint from source


def disasm(start, length=300):
    i = start
    end = min(start + length, len(code))
    while i < end:
        op = code[i] & 0xFF
        name = OP.get(op, f'?{op:02X}?')
        if op == 0x01:  # PUSH_I
            val = int.from_bytes(code[i + 1 : i + 5], 'little', signed=True)
            print(f'  [{i:5d}] {name} {val}')
            i += 5
        elif op == 0x2D:  # PUSH_STR
            slen = struct.unpack_from('<H', code, i + 1)[0]
            s = code[i + 3 : i + 3 + slen].decode('utf-8', errors='replace')
            print(f'  [{i:5d}] {name} {repr(s[:60])}')
            i += 3 + slen
        elif op == 0x07:  # LOAD var
            vi = code[i + 1]
            print(f'  [{i:5d}] {name} var[{vi}]')
            i += 2
        elif op == 0x08:  # STORE var
            vi = code[i + 1]
            print(f'  [{i:5d}] {name} var[{vi}]')
            i += 2
        elif op in (0x09, 0x33, 0x0A, 0x0B, 0x0C):  # JMP, JMP32, JZ, JNZ, CALL
            val = int.from_bytes(code[i + 1 : i + 5], 'little', signed=True)
            print(f'  [{i:5d}] {name} -> PC={i + 5 + val if op != 0x0C else val}')
            i += 5
        elif op == 0x4B:  # MAKE_CLOSURE
            val = int.from_bytes(code[i + 1 : i + 5], 'little', signed=True)
            print(f'  [{i:5d}] {name} func_addr={val}')
            i += 5
        elif op == 0x4C:  # CALL_CLOSURE
            print(f'  [{i:5d}] {name}')
            # Next bytes: 0 or more captured var indices (each 1 byte), then RET
            i += 1
        elif op == 0xFF:  # HALT
            print(f'  [{i:5d}] {name}')
            i += 1
        else:
            print(f'  [{i:5d}] {name}')
            i += 1


# 词法分析 at offset 632 (from export)
print('\n=== 词法分析 at offset 632 ===')
disasm(632, 600)

# Also decompile 解析 at 10167
print('\n\n=== 解析 at offset 10167 ===')
disasm(10167, 300)
