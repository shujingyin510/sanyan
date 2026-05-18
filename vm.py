"""字节码 VM — 从 STM32 C runtime 反向移植到 Python

与 sanyancc.py 共用同一指令集，可执行编译后的 .bin 字节码。
用法:
    from vm import VM
    vm = VM.from_bin('firmware.bin')
    vm.run()
"""

from __future__ import annotations
import struct

# ── 指令集（与 sanyancc.py / runtime_stm32.c 一致） ──
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
EQ = 0x11
NE = 0x12
GT = 0x13
LT = 0x14
GTE = 0x15
LTE = 0x16
NOT = 0x17
WAIT = 0x18
HALT = 0xFF

OP_NAMES = {v: k for k, v in vars().items() if isinstance(v, int) and k.isupper()}


class VMError(Exception):
    """VM 运行时错误"""


class VM:
    """栈式字节码虚拟机

    与 runtime_stm32.c 的 vm_run() 等效的 Python 实现。
    """

    def __init__(self, code: bytearray, vars_count: int = 256):
        self.code = code
        self.pc = 0
        self.stack: list[int] = []
        self.vars: list[int] = [0] * max(vars_count, 1)
        self.halted = False
        self.call_stack: list[int] = []

    @classmethod
    def from_bin(cls, path: str) -> VM:
        """从 sanyancc.py 生成的 .bin 文件加载字节码。"""
        with open(path, 'rb') as f:
            data = f.read()
        magic, ver, vc, sz = struct.unpack_from('<4sBBH', data, 0)
        if magic != b'SAN0':
            raise VMError(f'无效的字节码文件: magic={magic!r}')
        code = bytearray(data[8:8 + sz])
        return cls(code, vc)

    def _read_i16(self) -> int:
        val = struct.unpack_from('<h', self.code, self.pc)[0]
        self.pc += 2
        return val

    def _read_i32(self) -> int:
        val = struct.unpack_from('<i', self.code, self.pc)[0]
        self.pc += 4
        return val

    def run(self) -> None:
        """执行字节码直到遇到 HALT 或运行完毕。"""
        while not self.halted and self.pc < len(self.code):
            op = self.code[self.pc]
            self.pc += 1

            if op == NOP:
                pass
            elif op == PUSH_I:
                self.stack.append(self._read_i32())
            elif op == ADD:
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a + b)
            elif op == SUB:
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a - b)
            elif op == MUL:
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a * b)
            elif op == DIV:
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a // b if b else 0)
            elif op == MOD:
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a % b if b else 0)
            elif op == LOAD:
                idx = self.code[self.pc]
                self.pc += 1
                if idx < len(self.vars):
                    self.stack.append(self.vars[idx])
            elif op == STORE:
                idx = self.code[self.pc]
                self.pc += 1
                if idx < len(self.vars):
                    self.vars[idx] = self.stack.pop()
            elif op == JMP:
                off = self._read_i16()
                self.pc += off
            elif op == JZ:
                off = self._read_i16()
                val = self.stack.pop()
                if val == 0:
                    self.pc += off
            elif op == JNZ:
                off = self._read_i16()
                val = self.stack.pop()
                if val != 0:
                    self.pc += off
            elif op == CALL:
                addr = self._read_i16()
                self.call_stack.append(self.pc)
                self.pc = addr
            elif op == RET:
                if self.call_stack:
                    self.pc = self.call_stack.pop()
                else:
                    self.halted = True
            elif op == PRINT:
                val = self.stack.pop()
                print(val)
            elif op == IO_READ:
                self.stack.pop()  # dev_id (discard)
                self.stack.append(0)
            elif op == IO_WRITE:
                val = self.stack.pop()
                self.stack.pop()  # dev_id (discard)
            elif op == EQ:
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(1 if a == b else 0)
            elif op == NE:
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(1 if a != b else 0)
            elif op == GT:
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(1 if a > b else 0)
            elif op == LT:
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(1 if a < b else 0)
            elif op == GTE:
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(1 if a >= b else 0)
            elif op == LTE:
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(1 if a <= b else 0)
            elif op == NOT:
                a = self.stack.pop()
                self.stack.append(1 if a == 0 else 0)
            elif op == WAIT:
                self.stack.pop()  # ms (discard)
            elif op == HALT:
                self.halted = True
                return
            else:
                pass


def disassemble(code: bytearray) -> str:
    """反汇编字节码（用于调试）。"""
    lines = []
    pc = 0
    while pc < len(code):
        op = code[pc]
        name = OP_NAMES.get(op, f'UNK_{op:02X}')
        line = f'{pc:04x}: {name}'
        pc += 1
        if op == PUSH_I:
            val = struct.unpack_from('<i', code, pc)[0]
            line += f' {val}'
            pc += 4
        elif op in (LOAD, STORE):
            line += f' #{code[pc]}'
            pc += 1
        elif op in (JMP, JZ, JNZ, CALL):
            off = struct.unpack_from('<h', code, pc)[0]
            target = pc + 2 + off
            line += f' -> {target:04x}'
            pc += 2
        lines.append(line)
    return '\n'.join(lines)
