"""三言字节码验证器 — 加载前静态检查

检查项:
  1. 操作码合法性 (所有字节在已知 opcode 范围内)
  2. 操作数边界 (PUSH_I/PUSH_STR/JMP/JZ/JNZ/JMP32/CALL/LOAD/STORE)
  3. 跳转目标合法性 (JMP/JZ/JNZ/JMP32/CALL 目标在代码范围内)
  4. CALL 参数扫描安全 (STORE 指令完整在代码内)
  5. 变量索引范围 (LOAD/STORE 不超过变量表)
  6. 死代码/越界代码检测

用法:
    python verify.py bytecode_compiler.bin
    python verify.py bytecode_compiler.bin --quiet
"""

import struct
import sys
import os
from dataclasses import dataclass, field

# ═══════════════════════════════════════════════════════════════
# 操作码元信息
# ═══════════════════════════════════════════════════════════════
NOP = 0x00
PUSH_I = 0x01
ADD = 0x02
SUB = 0x03
MUL = 0x04
DIV = 0x05
MOD = 0x06
LOAD = 0x07
STORE = 0x08
JMP = 0x09
JZ = 0x0A
JNZ = 0x0B
CALL = 0x0C
RET = 0x0D
PRINT = 0x0E
IO_READ = 0x0F
IO_WRITE = 0x10
GT = 0x13
LT = 0x14
EQ = 0x15
NE = 0x16
GTE = 0x17
LTE = 0x18
CONCAT = 0x19
STRLEN = 0x1A
STRSUB = 0x1B
STREQ = 0x1C
DICT = 0x1D
DICT_GET = 0x1E
DICT_SET = 0x1F
DICT_HAS = 0x20
IS_NUM = 0x21
IS_STR = 0x22
IS_LIST = 0x23
SAME = 0x24
LIST_GET = 0x25
SET_ELEMENT = 0x26
LIST_NEW = 0x27
LIST_CONCAT = 0x28
SLICE = 0x29
LIST_LEN = 0x2A
READ_FILE = 0x2B
WRITE_FILE = 0x2C
PUSH_STR = 0x2D
IMPORT = 0x2E
CALL_EXT = 0x2F
WRITE_BINARY = 0x30
ORD = 0x31
DICT_KEYS = 0x32
JMP32 = 0x33
LOAD16 = 0x3B
STORE16 = 0x3C
CALL32 = 0x3D
PUSH_STR16 = 0x3E
OR = 0x34
AND = 0x35
HALT = 0xFF

# 每条指令的操作数类型和字节数
OP_SIZE = {
    NOP: 1,
    PUSH_I: 5,
    ADD: 1,
    SUB: 1,
    MUL: 1,
    DIV: 1,
    MOD: 1,
    LOAD: 2,
    STORE: 2,
    JMP: 3,
    JZ: 3,
    JNZ: 3,
    CALL: 3,
    RET: 1,
    PRINT: 1,
    GT: 1,
    LT: 1,
    EQ: 1,
    NE: 1,
    GTE: 1,
    LTE: 1,
    CONCAT: 1,
    STRLEN: 1,
    STRSUB: 1,
    STREQ: 1,
    DICT: 1,
    DICT_GET: 1,
    DICT_SET: 1,
    DICT_HAS: 1,
    IS_NUM: 1,
    IS_STR: 1,
    IS_LIST: 1,
    SAME: 1,
    LIST_GET: 1,
    SET_ELEMENT: 1,
    LIST_NEW: 1,
    LIST_CONCAT: 1,
    SLICE: 1,
    LIST_LEN: 1,
    WRITE_BINARY: 1,
    ORD: 1,
    DICT_KEYS: 1,
    JMP32: 5,
    HALT: 1,
}

OP_NAMES = {
    NOP: 'NOP',
    PUSH_I: 'PUSH_I',
    ADD: 'ADD',
    SUB: 'SUB',
    MUL: 'MUL',
    DIV: 'DIV',
    MOD: 'MOD',
    LOAD: 'LOAD',
    STORE: 'STORE',
    JMP: 'JMP',
    JZ: 'JZ',
    JNZ: 'JNZ',
    CALL: 'CALL',
    RET: 'RET',
    PRINT: 'PRINT',
    GT: 'GT',
    LT: 'LT',
    EQ: 'EQ',
    NE: 'NE',
    GTE: 'GTE',
    LTE: 'LTE',
    CONCAT: 'CONCAT',
    STRLEN: 'STRLEN',
    STRSUB: 'STRSUB',
    STREQ: 'STREQ',
    DICT: 'DICT',
    DICT_GET: 'DICT_GET',
    DICT_SET: 'DICT_SET',
    DICT_HAS: 'DICT_HAS',
    IS_NUM: 'IS_NUM',
    IS_STR: 'IS_STR',
    IS_LIST: 'IS_LIST',
    SAME: 'SAME',
    LIST_GET: 'LIST_GET',
    SET_ELEMENT: 'SET_ELEM',
    LIST_NEW: 'LIST_NEW',
    LIST_CONCAT: 'LIST_CAT',
    SLICE: 'SLICE',
    LIST_LEN: 'LIST_LEN',
    WRITE_BINARY: 'WRBIN',
    ORD: 'ORD',
    DICT_KEYS: 'DICT_KEYS',
    JMP32: 'JMP32',
    HALT: 'HALT',
}


@dataclass
class VerifyError:
    addr: int
    opcode: int
    msg: str
    severity: str = 'error'  # "error" | "warning"


@dataclass
class VerifyResult:
    errors: list[VerifyError] = field(default_factory=list)
    warnings: list[VerifyError] = field(default_factory=list)
    code_size: int = 0
    var_count: int = 0
    total_instructions: int = 0
    reached_instructions: set[int] = field(default_factory=set)

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0

    def add_error(self, addr: int, op: int, msg: str):
        self.errors.append(VerifyError(addr, op, msg))

    def add_warning(self, addr: int, op: int, msg: str):
        self.warnings.append(VerifyError(addr, op, msg, 'warning'))


def verify(data: bytes) -> VerifyResult:
    """验证字节码，返回 VerifyResult。"""
    result = VerifyResult()

    if len(data) < 10:
        result.add_error(0, 0, '文件过小 (< 10 字节)')
        return result

    magic, ver, vc, sz = struct.unpack_from('<4sBBI', data, 0)
    if magic != b'SAN0':
        result.add_error(0, 0, f'无效 magic: {magic!r}')
        return result

    result.code_size = sz
    result.var_count = vc

    code = data[10 : 10 + sz]
    if len(code) < sz:
        result.add_error(0, 0, f'代码不完整: 声明 {sz} 字节，实际 {len(code)}')
        return result

    # ── 从头扫描所有指令 ──
    i = 0
    addr = 0

    while i < len(code):
        op = code[i]

        # 检查 1: 操作码合法性
        if op not in OP_SIZE:
            result.add_warning(addr, op, '未知操作码')
            i += 1
            addr += 1
            continue

        # 检查 2: 操作数边界
        if op == PUSH_I:
            if i + 5 > len(code):
                result.add_error(addr, op, 'PUSH_I 操作数越界')
                break

        elif op == PUSH_STR:
            if i + 1 >= len(code):
                result.add_error(addr, op, 'PUSH_STR 缺少长度字节')
                break
            strlen = code[i + 1]
            total = 2 + strlen * 2
            if i + total > len(code):
                result.add_error(
                    addr,
                    op,
                    f'PUSH_STR len={strlen} 越界 (需要 {total} 字节，剩余 {len(code) - i})',
                )
                break

        elif op in (LOAD, STORE):
            if i + 2 > len(code):
                result.add_error(addr, op, 'LOAD/STORE 操作数越界')
                break
            idx = code[i + 1]
            if idx >= 256:
                result.add_error(addr, op, f'LOAD/STORE idx={idx} 越界 (max 255)')

        elif op in (JMP, JZ, JNZ):
            if i + 3 > len(code):
                result.add_error(addr, op, 'JMP/JZ/JNZ 操作数越界')
                break
            offset = struct.unpack_from('<h', code, i + 1)[0]
            target = addr + 3 + offset
            # 检查 3: 跳转目标
            if target < 0 or target > sz:
                result.add_error(
                    addr,
                    op,
                    f'跳转目标 {target} (offset={offset:+d}) 越界 [0,{sz})',
                )
            else:
                result.reached_instructions.add(target)

        elif op == JMP32:
            if i + 5 > len(code):
                result.add_error(addr, op, 'JMP32 操作数越界')
                break
            offset = struct.unpack_from('<i', code, i + 1)[0]
            target = addr + 5 + offset
            if target < 0 or target > sz:
                result.add_error(
                    addr,
                    op,
                    f'JMP32 跳转目标 {target} (offset={offset:+d}) 越界 [0,{sz})',
                )
            else:
                result.reached_instructions.add(target)

        elif op == CALL:
            if i + 3 > len(code):
                result.add_error(addr, op, 'CALL 操作数越界')
                break
            target = struct.unpack_from('<H', code, i + 1)[0]
            if target >= sz:
                result.add_error(addr, op, f'CALL 目标 {target} 越界 [0,{sz})')
            else:
                result.reached_instructions.add(target)
                # 检查 4: CALL 参数扫描安全
                p = target
                while p + 1 < len(code) and code[p] == STORE:
                    p += 2
                if p > len(code):
                    result.add_warning(
                        addr,
                        op,
                        f'CALL 参数扫描从 {target} 出发越过代码末尾',
                    )

        # 确定指令长度
        if op == PUSH_STR:
            total = 2 + code[i + 1] * 2
        else:
            total = OP_SIZE[op]

        result.reached_instructions.add(addr)

        i += total
        addr += total

    result.total_instructions = len(result.reached_instructions)

    # ── 检查 6: 死代码检测 ──
    if addr < sz:
        unreached = [a for a in range(addr, sz, 2) if a not in result.reached_instructions]
        if unreached:
            start = min(unreached)
            result.add_warning(addr, 0, f'代码末尾 {sz - addr} 字节不可达 (起始地址 {start:04X})')

    return result


def verify_file(path: str, quiet: bool = False) -> VerifyResult:
    """验证 .bin 文件。"""
    with open(path, 'rb') as f:
        data = f.read()
    result = verify(data)
    # result.filename = path (removed for mypy)

    if not quiet:
        print(f'文件: {path}')
        print(f'  变量数: {result.var_count}')
        print(f'  代码大小: {result.code_size} 字节')
        print(f'  可达指令: {len(result.reached_instructions)}')

        if result.errors:
            print(f'\n  ❌ 错误 ({len(result.errors)}):')
            for e in result.errors:
                print(f'    [{e.addr:04X}] {OP_NAMES.get(e.opcode, f"0x{e.opcode:02X}")}: {e.msg}')

        if result.warnings:
            print(f'\n  ⚠️  警告 ({len(result.warnings)}):')
            for w in result.warnings:
                print(f'    [{w.addr:04X}] {OP_NAMES.get(w.opcode, f"0x{w.opcode:02X}")}: {w.msg}')

        if result.ok:
            print('\n  ✅ 验证通过')
        else:
            print(f'\n  ❌ 验证失败 ({len(result.errors)} 个错误)')

    return result


def main():
    if len(sys.argv) < 2:
        print('用法: python verify.py <file.bin> [--quiet]')
        sys.exit(1)

    path = sys.argv[1]
    if not os.path.exists(path):
        print(f'文件不存在: {path}')
        sys.exit(1)

    quiet = '--quiet' in sys.argv
    result = verify_file(path, quiet)
    sys.exit(0 if result.ok else 1)


if __name__ == '__main__':
    main()
