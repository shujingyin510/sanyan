"""三言字节码反汇编器

用法:
    python disasm.py bytecode_compiler.bin
    python disasm.py bytecode_compiler.bin --brief     # 仅统计
    python disasm.py bytecode_compiler.bin --hex       # 十六进制+反汇编
"""

import struct
import sys
import os

# ═══════════════════════════════════════════════════════════════
# 操作码定义 (与 vm.py 一致)
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
LIST_GET = 0x25  # GET
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
OR = 0x34
AND = 0x35
STR_FIND = 0x36
STR_TO_LIST = 0x37
STR_STARTSWITH = 0x38
STR_CONTAINS = 0x39
DICT_LEN = 0x3A
PUSH_FLOAT = 0x48
HALT = 0xFF

# ═══════════════════════════════════════════════════════════════
# 操作码元信息: (助记符, 操作数类型, 指令总字节数)
#   操作数类型: 'none' | 'i32' | 'i16' | 'u8' | 'str'
#   0 = 变长 (str 类)
# ═══════════════════════════════════════════════════════════════
OP_META = {
    NOP: ("NOP", "none", 1),
    PUSH_I: ("PUSH_I", "i32", 5),
    ADD: ("ADD", "none", 1),
    SUB: ("SUB", "none", 1),
    MUL: ("MUL", "none", 1),
    DIV: ("DIV", "none", 1),
    MOD: ("MOD", "none", 1),
    LOAD: ("LOAD", "u8", 2),
    STORE: ("STORE", "u8", 2),
    JMP: ("JMP", "i16", 3),
    JZ: ("JZ", "i16", 3),
    JNZ: ("JNZ", "i16", 3),
    CALL: ("CALL", "i16", 3),
    RET: ("RET", "none", 1),
    PRINT: ("PRINT", "none", 1),
    GT: ("GT", "none", 1),
    LT: ("LT", "none", 1),
    EQ: ("EQ", "none", 1),
    NE: ("NE", "none", 1),
    GTE: ("GTE", "none", 1),
    LTE: ("LTE", "none", 1),
    CONCAT: ("CONCAT", "none", 1),
    STRLEN: ("STRLEN", "none", 1),
    STRSUB: ("STRSUB", "none", 1),
    STREQ: ("STREQ", "none", 1),
    DICT: ("DICT", "none", 1),
    DICT_GET: ("DICT_GET", "none", 1),
    DICT_SET: ("DICT_SET", "none", 1),
    DICT_HAS: ("DICT_HAS", "none", 1),
    IS_NUM: ("IS_NUM", "none", 1),
    IS_STR: ("IS_STR", "none", 1),
    IS_LIST: ("IS_LIST", "none", 1),
    SAME: ("SAME", "none", 1),
    LIST_GET: ("LIST_GET", "none", 1),  # 原 GET
    SET_ELEMENT: ("SET_ELEM", "none", 1),
    LIST_NEW: ("LIST_NEW", "none", 1),
    LIST_CONCAT: ("LIST_CAT", "none", 1),
    SLICE: ("SLICE", "none", 1),
    LIST_LEN: ("LIST_LEN", "none", 1),
    PUSH_STR: ("PUSH_STR", "str", 0),  # 变长
    ORD: ("ORD", "none", 1),
    DICT_KEYS: ("DICT_KEYS", "none", 1),
    JMP32: ("JMP32", "i32", 5),
    WRITE_BINARY: ("WRBIN", "none", 1),
    HALT: ("HALT", "none", 1),
}

OP_NAMES = {k: v[0] for k, v in OP_META.items()}


def disasm(data: bytes, show_hex: bool = False) -> str:
    """反汇编 .bin 字节码数据，返回可读字符串。"""
    if len(data) < 10:
        return "文件过小"

    magic, ver, vc, sz = struct.unpack_from("<4sBBI", data, 0)
    if magic != b"SAN0":
        return f"无效 magic: {magic!r}"

    lines = []
    lines.append(f"; magic={magic.decode()} ver={ver} vars={vc} code_size={sz}")
    lines.append("")

    code = data[10 : 10 + sz]
    i = 0
    addr = 0

    while i < len(code):
        op = code[i]

        if op == HALT:
            if show_hex:
                lines.append(f"  {addr:04X}: {op:02X}          HALT")
            else:
                lines.append(f"  {addr:04X}: HALT")
            i += 1
            addr += 1
            continue

        meta = OP_META.get(op)
        if meta is None:
            lines.append(f"  {addr:04X}: {op:02X}          ; ??? UNKNOWN")
            i += 1
            addr += 1
            continue

        mnemonic, op_type, total_size = meta

        if op_type == "none":
            lines.append(f"  {addr:04X}: {mnemonic}")
            i += 1
            addr += 1

        elif op_type == "u8":
            val = code[i + 1]
            if show_hex:
                lines.append(f"  {addr:04X}: {op:02X} {val:02X}       {mnemonic} {val}")
            else:
                lines.append(f"  {addr:04X}: {mnemonic} {val}")
            i += 2
            addr += 2

        elif op_type == "i32":
            val = struct.unpack_from("<i", code, i + 1)[0]
            hex_bytes = " ".join(f"{b:02X}" for b in code[i : i + 5])
            if show_hex:
                lines.append(f"  {addr:04X}: {hex_bytes}  {mnemonic} {val}")
            else:
                lines.append(f"  {addr:04X}: {mnemonic} {val}")
            i += 5
            addr += 5

        elif op_type == "i16":
            val = struct.unpack_from("<h", code, i + 1)[0]
            target = addr + 3 + val
            hex_bytes = " ".join(f"{b:02X}" for b in code[i : i + 3])
            if show_hex:
                if op in (JMP, JZ, JNZ):
                    lines.append(
                        f"  {addr:04X}: {hex_bytes}     {mnemonic} {val:+d} → {target:04X}"
                    )
                else:
                    lines.append(
                        f"  {addr:04X}: {hex_bytes}     {mnemonic} {val} (→ {target:04X})"
                    )
            else:
                if op in (JMP, JZ, JNZ):
                    lines.append(f"  {addr:04X}: {mnemonic} {val:+d} → {target:04X}")
                else:
                    lines.append(f"  {addr:04X}: {mnemonic} {val} → {target:04X}")
            i += 3
            addr += 3

        elif op_type == "str":
            strlen = code[i + 1]
            utf16_data = code[i + 2 : i + 2 + strlen * 2]
            # UTF-16LE → Python str
            try:
                text = utf16_data.decode("utf-16-le")
            except UnicodeDecodeError:
                text = repr(utf16_data)
            total = 2 + strlen * 2
            if show_hex:
                hex_prefix = " ".join(f"{b:02X}" for b in code[i : i + min(total, 8)])
                dots = "..." if total > 8 else ""
                lines.append(
                    f'  {addr:04X}: {hex_prefix}{dots}   {mnemonic} len={strlen} "{text}"'
                )
            else:
                lines.append(f'  {addr:04X}: {mnemonic} len={strlen} "{text}"')
            i += total
            addr += total

        else:
            lines.append(f"  {addr:04X}: {op:02X}          ; ??? {mnemonic}")
            i += 1
            addr += 1

    lines.append("")
    lines.append(f"; {addr} bytes, {len(lines) - 3} instructions")

    return "\n".join(lines)


def disasm_file(path: str, show_hex: bool = False, brief: bool = False) -> str:
    """反汇编 .bin 文件。"""
    with open(path, "rb") as f:
        data = f.read()

    # 解析导出表
    magic, ver, vc, sz = struct.unpack_from("<4sBBI", data, 0)
    exports = {}
    pos = 10 + sz
    if len(data) > pos + 2:
        try:
            export_count = struct.unpack_from("<H", data, pos)[0]
            pos += 2
            for _ in range(export_count):
                if pos + 2 > len(data):
                    break
                name_len = struct.unpack_from("<H", data, pos)[0]
                pos += 2
                if pos + name_len * 2 + 4 > len(data):
                    break
                chars = []
                for _ in range(name_len):
                    lo = data[pos]
                    hi = data[pos + 1]
                    pos += 2
                    chars.append(chr(lo | (hi << 8)))
                name = "".join(chars)
                addr = struct.unpack_from("<I", data, pos)[0]
                pos += 4
                exports[name] = addr
        except (struct.error, IndexError):
            pass

    result = disasm(data, show_hex)

    if export_count:
        result += "\n\n; ── 导出表 ──\n"
        for name, addr in exports.items():
            result += f";   {name} → 0x{addr:04X}\n"

    if brief:
        # 统计 opcode 分布
        from collections import Counter

        counter = Counter()
        code = data[10 : 10 + sz]
        i = 0
        while i < len(code):
            op = code[i]
            meta = OP_META.get(op)
            name = meta[0] if meta else f"UNK_{op:02X}"
            counter[name] += 1
            if meta and meta[1] == "str":
                strlen = code[i + 1]
                i += 2 + strlen * 2
            else:
                i += meta[2] if meta else 1

        result += "\n; ── 统计 ──\n"
        for name, count in counter.most_common(30):
            result += f";   {name}: {count}\n"

    return result


def main():
    if len(sys.argv) < 2:
        print("用法: python disasm.py <file.bin> [--hex] [--brief]")
        print("  --hex     显示十六进制字节")
        print("  --brief   仅显示头部和统计信息")
        print("  --export  仅显示导出表")
        sys.exit(1)

    path = sys.argv[1]
    if not os.path.exists(path):
        print(f"文件不存在: {path}")
        sys.exit(1)

    show_hex = "--hex" in sys.argv
    brief = "--brief" in sys.argv
    show_export = "--export" in sys.argv

    if show_export:
        with open(path, "rb") as f:
            data = f.read()
        magic, ver, vc, sz = struct.unpack_from("<4sBBI", data, 0)
        pos = 10 + sz
        if len(data) > pos + 2:
            export_count = struct.unpack_from("<H", data, pos)[0]
            print(f"导出表 ({export_count} 项):")
            pos += 2
            for _ in range(export_count):
                name_len = struct.unpack_from("<H", data, pos)[0]
                pos += 2
                chars = []
                for _ in range(name_len):
                    lo = data[pos]; hi = data[pos + 1]; pos += 2
                    chars.append(chr(lo | (hi << 8)))
                name = "".join(chars)
                addr = struct.unpack_from("<I", data, pos)[0]; pos += 4
                print(f"  {name} → 0x{addr:04X}")
        return

    if brief:
        # 只打印统计
        with open(path, "rb") as f:
            data = f.read()
        magic, ver, vc, sz = struct.unpack_from("<4sBBI", data, 0)
        print(f"magic={magic.decode()} ver={ver} vars={vc} code_size={sz}")
        print(disasm_file(path, brief=True).split("; ── 统计 ──\n")[-1])
    else:
        print(disasm_file(path, show_hex))


if __name__ == "__main__":
    main()
