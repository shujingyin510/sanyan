"""三言字节码汇编器 — 将汇编文本编译为 .bin 字节码

用法:
    python asm.py input.sasm -o output.bin
    python asm.py input.sasm                   # → input.bin
    python -c "print(PUSH_I 42, PRINT, HALT)" | python asm.py - -o test.bin

语法:
    ; 注释
    LABEL:            ; 标签定义
    PUSH_I 42         ; 操作码 + 操作数
    PUSH_STR "hello"  ; 字符串
    JMP loop          ; 跳转到标签
    CALL fn           ; 调用标签
    EXPORT fn         ; 导出函数
    HALT              ; 无操作数 opcode
"""

import struct
import sys
import os
import re

# ═══════════════════════════════════════════════════
# 操作码定义
# ═══════════════════════════════════════════════════
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
GT = 0x13
LT = 0x14
EQ = 0x15
GTE = 0x17
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
LIST_GET = 0x25
SET_ELEMENT = 0x26
LIST_NEW = 0x27
LIST_CONCAT = 0x28
SLICE = 0x29
LIST_LEN = 0x2A
PUSH_STR = 0x2D
WRITE_BINARY = 0x30
ORD = 0x31
DICT_KEYS = 0x32
JMP32 = 0x33
LOAD16 = 0x3B
STORE16 = 0x3C
CALL32 = 0x3D
PUSH_STR16 = 0x3E
CLOSURE = 0x3F
HALT = 0xFF
MAGIC = b'SAN0'
VERSION = 1

# 操作码元信息: (mnemonic, 操作数类型)
OP_INFO = {
    'NOP': (NOP, 'none'),
    'PUSH_I': (PUSH_I, 'i32'),
    'ADD': (ADD, 'none'),
    'SUB': (SUB, 'none'),
    'MUL': (MUL, 'none'),
    'DIV': (DIV, 'none'),
    'MOD': (MOD, 'none'),
    'LOAD': (LOAD, 'u8'),
    'STORE': (STORE, 'u8'),
    'LOAD16': (LOAD16, 'u16'),
    'STORE16': (STORE16, 'u16'),
    'JMP': (JMP, 'label'),
    'JZ': (JZ, 'label'),
    'JNZ': (JNZ, 'label'),
    'CALL': (CALL, 'label'),
    'CALL32': (CALL32, 'label'),
    'RET': (RET, 'none'),
    'PRINT': (PRINT, 'none'),
    'GT': (GT, 'none'),
    'LT': (LT, 'none'),
    'EQ': (EQ, 'none'),
    'GTE': (GTE, 'none'),
    'CONCAT': (CONCAT, 'none'),
    'STRLEN': (STRLEN, 'none'),
    'STRSUB': (STRSUB, 'none'),
    'STREQ': (STREQ, 'none'),
    'DICT': (DICT, 'none'),
    'DICT_GET': (DICT_GET, 'none'),
    'DICT_SET': (DICT_SET, 'none'),
    'DICT_HAS': (DICT_HAS, 'none'),
    'IS_NUM': (IS_NUM, 'none'),
    'IS_STR': (IS_STR, 'none'),
    'IS_LIST': (IS_LIST, 'none'),
    'LIST_GET': (LIST_GET, 'none'),
    'SET_ELEMENT': (SET_ELEMENT, 'none'),
    'LIST_NEW': (LIST_NEW, 'none'),
    'LIST_CONCAT': (LIST_CONCAT, 'none'),
    'SLICE': (SLICE, 'none'),
    'LIST_LEN': (LIST_LEN, 'none'),
    'PUSH_STR': (PUSH_STR, 'str'),
    'PUSH_STR16': (PUSH_STR16, 'str'),
    'WRITE_BINARY': (WRITE_BINARY, 'none'),
    'ORD': (ORD, 'none'),
    'DICT_KEYS': (DICT_KEYS, 'none'),
    'JMP32': (JMP32, 'i32'),
    'CLOSURE': (CLOSURE, 'none'),
    'HALT': (HALT, 'none'),
}


class AssemblerError(Exception):
    pass


class LabelRef:
    """未解析的标签引用"""

    def __init__(self, addr: int, label: str, fixup_fn):
        self.addr = addr
        self.label = label
        self.fixup_fn = fixup_fn


class Assembler:
    def __init__(self):
        self.code = bytearray()
        self.labels: dict[str, int] = {}
        self.refs: list[LabelRef] = []
        self.exports: list[str] = []
        self.var_count = 0
        self.addr = 0

    def emit(self, *bytes_values):
        for v in bytes_values:
            self.code.append(v & 0xFF)
        self.addr += len(bytes_values)

    def emit16(self, val: int):
        self.emit(val & 0xFF, (val >> 8) & 0xFF)

    def emit32(self, val: int):
        self.emit(val & 0xFF, (val >> 8) & 0xFF, (val >> 16) & 0xFF, (val >> 24) & 0xFF)

    def emit_str(self, s: str):
        """发射 UTF-16LE 字符串"""
        self.emit(len(s) & 0xFF)  # PUSH_STR uses u8 length
        for ch in s:
            cp = ord(ch)
            self.emit(cp & 0xFF, (cp >> 8) & 0xFF)

    def parse_line(self, line: str):
        """解析一行汇编"""
        # 去除注释
        line = line.split(';')[0].split('//')[0].strip()
        if not line:
            return

        # 标签定义
        if line.endswith(':'):
            label = line[:-1].strip()
            if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', label):
                raise AssemblerError(f'非法标签名: {label}')
            self.labels[label] = self.addr
            return

        # EXPORT 指令
        if line.startswith('EXPORT '):
            name = line[7:].strip()
            self.exports.append(name)
            return

        # 操作码指令
        parts = line.split(None, 1)
        mnemonic = parts[0].upper()
        operand = parts[1] if len(parts) > 1 else None

        if mnemonic not in OP_INFO:
            raise AssemblerError(f'未知操作码: {mnemonic}')

        opcode, op_type = OP_INFO[mnemonic]
        self.emit(opcode)

        if op_type == 'none':
            if operand:
                raise AssemblerError(f'{mnemonic} 不接受操作数')
            return

        elif op_type == 'i32':
            if operand is None:
                raise AssemblerError(f'{mnemonic} 需要 i32 操作数')
            val = self._parse_int(operand)
            self.emit32(val)

        elif op_type == 'u8':
            if operand is None:
                raise AssemblerError(f'{mnemonic} 需要 u8 操作数')
            val = self._parse_int(operand)
            if val < 0 or val > 255:
                raise AssemblerError(f'{mnemonic} u8 操作数越界: {val}')
            self.emit(val)

        elif op_type == 'u16':
            if operand is None:
                raise AssemblerError(f'{mnemonic} 需要 u16 操作数')
            val = self._parse_int(operand)
            if val < 0 or val > 65535:
                raise AssemblerError(f'{mnemonic} u16 操作数越界: {val}')
            self.emit16(val)

        elif op_type == 'str':
            if operand is None:
                raise AssemblerError(f'{mnemonic} 需要字符串操作数')
            s = self._parse_str(operand)
            self.emit_str(s)

        elif op_type == 'label':
            if operand is None:
                raise AssemblerError(f'{mnemonic} 需要标签操作数')
            # JMP/JZ/JNZ/CALL: 16-bit offset
            # JMP32: 32-bit offset
            # CALL32: 32-bit addr
            if mnemonic in ('JMP32', 'CALL32'):
                # 暂填 0，回填
                pos = self.addr
                self.emit32(0)
                self.refs.append(LabelRef(pos, operand, lambda a, t: self._fixup_abs32(a, t)))
            elif mnemonic in ('CALL',):
                pos = self.addr
                self.emit16(0)
                self.refs.append(LabelRef(pos, operand, lambda a, t: self._fixup_abs16(a, t)))
            else:
                pos = self.addr
                self.emit16(0)
                self.refs.append(LabelRef(pos, operand, lambda a, t: self._fixup16(a, t)))

    def _parse_int(self, s: str) -> int:
        s = s.strip()
        if s.startswith('0x') or s.startswith('0X'):
            return int(s, 16)
        if s.startswith('0b') or s.startswith('0B'):
            return int(s, 2)
        return int(s)

    def _parse_str(self, s: str) -> str:
        s = s.strip()
        if s.startswith('"') and s.endswith('"'):
            return s[1:-1]
        if s.startswith("'") and s.endswith("'"):
            return s[1:-1]
        return s

    def _fixup16(self, addr: int, label: str):
        if label not in self.labels:
            raise AssemblerError(f'未定义标签: {label}')
        target = self.labels[label]
        # JMP/JZ/JNZ: offset from next instruction (addr + 2)
        offset = target - (addr + 2)
        self.code[addr] = offset & 0xFF
        self.code[addr + 1] = (offset >> 8) & 0xFF

    def _fixup_abs16(self, addr: int, label: str):
        if label not in self.labels:
            raise AssemblerError(f'未定义标签: {label}')
        val = self.labels[label]
        self.code[addr] = val & 0xFF
        self.code[addr + 1] = (val >> 8) & 0xFF

    def _fixup_abs32(self, addr: int, label: str):
        if label not in self.labels:
            raise AssemblerError(f'未定义标签: {label}')
        val = self.labels[label]
        self.code[addr] = val & 0xFF
        self.code[addr + 1] = (val >> 8) & 0xFF
        self.code[addr + 2] = (val >> 16) & 0xFF
        self.code[addr + 3] = (val >> 24) & 0xFF

    def _fixup32(self, addr: int, label: str):
        if label not in self.labels:
            raise AssemblerError(f'未定义标签: {label}')
        val = self.labels[label]
        self.code[addr] = val & 0xFF
        self.code[addr + 1] = (val >> 8) & 0xFF
        self.code[addr + 2] = (val >> 16) & 0xFF
        self.code[addr + 3] = (val >> 24) & 0xFF

    def assemble(self, source: str) -> bytearray:
        """汇编源码，返回 .bin 数据"""
        for line in source.splitlines():
            try:
                self.parse_line(line)
            except AssemblerError as e:
                raise AssemblerError(f'行 {line[:50]}: {e}')

        # 回填标签引用
        for ref in self.refs:
            ref.fixup_fn(ref.addr, ref.label)

        # 确保 HALT 结尾
        if len(self.code) == 0 or self.code[-1] != HALT:
            self.emit(HALT)

        return self.code

    def build(self, source: str) -> bytes:
        """构建完整 .bin 文件"""
        code = self.assemble(source)

        # 导出表
        export_data = bytearray()
        export_names = []
        for name in self.exports:
            if name in self.labels:
                export_names.append((name, self.labels[name]))

        if export_names:
            export_data.extend(struct.pack('<H', len(export_names)))
            for name, addr in export_names:
                export_data.extend(struct.pack('<H', len(name)))
                for ch in name:
                    cp = ord(ch)
                    export_data.append(cp & 0xFF)
                    export_data.append((cp >> 8) & 0xFF)
                export_data.extend(struct.pack('<I', addr))

        # 计算变量数
        max_var = 0
        for i in range(0, len(code) - 1, 2):
            if code[i] in (LOAD, STORE) and i + 1 < len(code):
                max_var = max(max_var, code[i + 1])
            elif code[i] in (LOAD16, STORE16) and i + 2 < len(code):
                max_var = max(max_var, code[i + 1] | (code[i + 2] << 8))

        self.var_count = max(max_var + 1, 1)

        # SAN0 头部
        header = struct.pack('<4sBBI', MAGIC, VERSION, self.var_count, len(code))
        return header + code + export_data


def assemble_file(input_path: str, output_path: str) -> bytes:
    """汇编文件"""
    if input_path == '-':
        source = sys.stdin.read()
    else:
        with open(input_path, 'r', encoding='utf-8') as f:
            source = f.read()

    asm = Assembler()
    data = asm.build(source)

    with open(output_path, 'wb') as f:
        f.write(data)

    print(f'[OK] {input_path} → {output_path}: {len(data)} 字节, {asm.var_count} 变量')
    if asm.exports:
        print(f'  导出: {", ".join(asm.exports)}')
    return data


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = None

    for i, arg in enumerate(sys.argv):
        if arg == '-o' and i + 1 < len(sys.argv):
            output_path = sys.argv[i + 1]

    if output_path is None:
        if input_path == '-':
            output_path = 'stdin.bin'
        else:
            output_path = os.path.splitext(input_path)[0] + '.bin'

    try:
        assemble_file(input_path, output_path)
    except AssemblerError as e:
        print(f'错误: {e}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
