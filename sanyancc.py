"""三言交叉编译器：.san → 平坦字节码 → STM32 C runtime"""

from __future__ import annotations
import struct
import sys

# ── 字节码指令集 ──────────────────────────────────────────
# 所有指令定长：1 字节 opcode + 0~4 字节立即数
INSTR = {
    'NOP': 0x00,
    'PUSH_I': 0x01,  # +4B int32
    'ADD': 0x02,
    'SUB': 0x03,
    'MUL': 0x04,
    'DIV': 0x05,
    'MOD': 0x06,
    'LOAD': 0x07,  # +1B var_index
    'STORE': 0x08,  # +1B var_index
    'JMP': 0x09,  # +2B offset
    'JZ': 0x0A,  # +2B offset (pop, jump if == 0)
    'JNZ': 0x0B,  # +2B offset (pop, jump if != 0)
    'CALL': 0x0C,  # +2B addr
    'RET': 0x0D,
    'PRINT': 0x0E,  # pop and print
    'IO_READ': 0x0F,  # pop device_id → push value
    'IO_WRITE': 0x10,  # pop device_id, pop value → write
    'EQ': 0x11,
    'NE': 0x12,
    'GT': 0x13,
    'LT': 0x14,
    'GTE': 0x15,
    'LTE': 0x16,
    'NOT': 0x17,
    'WAIT': 0x18,  # pop ms → delay
    'HALT': 0xFF,
}
OPCODE = {v: k for k, v in INSTR.items()}

# ── 内置操作名 → 指令映射（编译期用） ──
OP_TO_INSTR = {
    'add': 'ADD',
    'sub': 'SUB',
    'mul': 'MUL',
    'div': 'DIV',
    'mod': 'MOD',
    'eq': 'EQ',
    'ne': 'NE',
    'gt': 'GT',
    'lt': 'LT',
    'gte': 'GTE',
    'lte': 'LTE',
    'not': 'NOT',
    'wait': 'WAIT',
    'io_write': 'IO_WRITE',
    'io_read': 'IO_READ',
    '加': 'ADD',
    '减': 'SUB',
    '乘': 'MUL',
    '除': 'DIV',
    '余': 'MOD',
    '等于': 'EQ',
    '不等': 'NE',
    '大于': 'GT',
    '小于': 'LT',
    '大等': 'GTE',
    '小等': 'LTE',
    '非': 'NOT',
    '等待': 'WAIT',
    'io写': 'IO_WRITE',
    'io读': 'IO_READ',
    '输出': 'PRINT',
}


class BytecodeWriter:
    """字节码缓冲区：emit 指令 + 写入二进制。"""

    def __init__(self):
        self.data = bytearray()

    def emit(self, op: str, *imm: int) -> None:
        self.data.append(INSTR[op])
        for b in imm:
            self.data.append(b & 0xFF)

    def emit_i16(self, val: int) -> None:
        self.data.extend(struct.pack('<h', val))

    def emit_i32(self, val: int) -> None:
        self.data.extend(struct.pack('<i', val))

    def write(self, path: str, var_count: int) -> None:
        cs = len(self.data)
        if cs > 0xFFFF:
            raise ValueError(f'字节码过大: {cs}')
        header = struct.pack('<4sBBH', b'SAN0', 1, var_count & 0xFF, cs)
        with open(path, 'wb') as f:
            f.write(header)
            f.write(self.data)


class CompileContext:
    """编译上下文：变量表、函数表。"""

    def __init__(self):
        self.vars: dict[str, int] = {}  # name → index
        self.funcs: dict[str, int] = {}  # name → bytecode offset
        self.forward_fixups: list = []  # (name, pos) 待回填


def _to_int(s: str) -> int | None:
    """尝试解析数字字符串，失败返回 None。"""
    s = s.strip()
    try:
        return int(s)
    except ValueError:
        pass
    try:
        f = float(s)
        return int(f)
    except ValueError:
        return None


def compile_ast(node, bc: BytecodeWriter, ctx: CompileContext) -> None:
    """递归编译 AST 节点为字节码。"""
    # 字面量
    if isinstance(node, (int, float)):
        bc.emit('PUSH_I')
        bc.emit_i32(int(node))
        return

    if isinstance(node, str):
        n = _to_int(node)
        if n is not None:
            bc.emit('PUSH_I')
            bc.emit_i32(n)
            return
        # 变量名 → LOAD
        idx = ctx.vars.get(node)
        if idx is not None:
            bc.emit('LOAD', idx)
        else:
            raise NameError(f'编译错误: 未定义变量 {node}')
        return

    if not isinstance(node, list) or len(node) < 1:
        raise SyntaxError(f'编译错误: 无法识别的 AST 节点: {node}')

    op = node[0]
    args = node[1:]

    # 内置二元操作
    instr = OP_TO_INSTR.get(op)
    if instr:
        for a in args:
            compile_ast(a, bc, ctx)
        bc.emit(instr)
        return

    # 定义变量: (set name value)
    if op in ('set', '设'):
        if len(args) != 2:
            raise SyntaxError(f'{op} 需要两个参数')
        name = args[0]
        if not isinstance(name, str):
            raise SyntaxError(f'变量名必须是字符串: {name}')
        if name not in ctx.vars:
            idx = len(ctx.vars)
            ctx.vars[name] = idx
        compile_ast(args[1], bc, ctx)
        bc.emit('STORE', ctx.vars[name])
        return

    # do 块
    if op in ('do', '做'):
        for stmt in args:
            compile_ast(stmt, bc, ctx)
        return

    # 输出
    if op in ('print', '输出'):
        if args:
            compile_ast(args[0], bc, ctx)
        bc.emit('PRINT')
        return

    # 条件
    if op in ('if', '若'):
        if len(args) == 2:
            cond, then_branch = args
            compile_ast(cond, bc, ctx)
            buf = BytecodeWriter()
            compile_ast(then_branch, buf, ctx)
            bc.emit('JZ')
            bc.emit_i16(len(buf.data))
            bc.data.extend(buf.data)
        elif len(args) == 3:
            cond, then_branch, else_branch = args
            compile_ast(cond, bc, ctx)
            buf_then = BytecodeWriter()
            compile_ast(then_branch, buf_then, ctx)
            buf_else = BytecodeWriter()
            compile_ast(else_branch, buf_else, ctx)
            bc.emit('JZ')
            bc.emit_i16(len(buf_then.data) + 2)
            bc.data.extend(buf_then.data)
            bc.emit('JMP')
            bc.emit_i16(len(buf_else.data))
            bc.data.extend(buf_else.data)
        else:
            raise SyntaxError(f'{op} 需要 2 或 3 个参数')
        return

    # 循环
    if op in ('loop', '循环'):
        if len(args) != 2:
            raise SyntaxError(f'{op} 需要两个参数 (条件, 体)')
        start_pos = len(bc.data)
        compile_ast(args[0], bc, ctx)  # 条件
        jz_pos = len(bc.data)
        bc.emit('JZ')
        bc.emit_i16(0)  # 占位
        compile_ast(args[1], bc, ctx)  # 体
        jmp_pos = len(bc.data)
        bc.emit('JMP')
        bc.emit_i16(start_pos - jmp_pos - 3)  # 跳回条件
        struct.pack_into('<h', bc.data, jz_pos + 1, len(bc.data) - jz_pos - 3)  # 跳过体+JMP
        return

    # 函数定义
    if op in ('define', 'fn', '定义'):
        if len(args) < 2:
            raise SyntaxError(f'{op} 需要 (name args body)')
        name = args[0]
        params = args[1] if isinstance(args[1], list) else []
        body = args[2] if len(args) > 2 else None
        idx = len(ctx.funcs)
        ctx.funcs[name] = len(bc.data)
        for p in params:
            if p not in ctx.vars:
                ctx.vars[p] = len(ctx.vars)
        if body is not None:
            compile_ast(body, bc, ctx)
        bc.emit('RET')
        return

    # 函数调用
    if op in ctx.funcs:
        addr = ctx.funcs[op]
        for a in args:
            compile_ast(a, bc, ctx)
        bc.emit('CALL')
        bc.emit_i16(addr)
        return

    # 未知操作 → 尝试当作函数调用（提前引用）
    for a in args:
        compile_ast(a, bc, ctx)
    bc.emit('CALL')
    pos = len(bc.data)
    bc.emit_i16(0)
    ctx.forward_fixups.append((op, pos))
    return


def resolve_fixups(bc: BytecodeWriter, ctx: CompileContext) -> None:
    """回填前向引用函数地址。"""
    for name, pos in ctx.forward_fixups:
        addr = ctx.funcs.get(name)
        if addr is None:
            raise NameError(f'编译错误: 未定义的函数 {name}')
        struct.pack_into('<h', bc.data, pos, addr & 0xFFFF)


def compile_source(source: str, skin=None) -> tuple[BytecodeWriter, CompileContext]:
    """解析并编译三言源码。"""
    from lexer import tokenize
    from parser import parse

    tokens = tokenize(source)
    ast = parse(tokens)
    if ast is None:
        raise SyntaxError('解析失败')
    bc = BytecodeWriter()
    ctx = CompileContext()
    compile_ast(ast, bc, ctx)
    resolve_fixups(bc, ctx)
    return bc, ctx


def main() -> None:
    if len(sys.argv) < 2:
        print('用法: python sanyancc.py input.san [-o output.bin]')
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[3] if len(sys.argv) > 3 and sys.argv[2] == '-o' else 'firmware.bin'

    with open(input_path, 'r', encoding='utf-8') as f:
        source = f.read()

    bc, ctx = compile_source(source)
    bc.write(output_path, len(ctx.vars))
    print(f'✓ 编译完成: {output_path}')
    print(f'  变量: {len(ctx.vars)}, 函数: {len(ctx.funcs)}, 字节码: {len(bc.data)} 字节')

    if '--dump' in sys.argv:
        dump(bc)


def dump(bc: BytecodeWriter) -> None:
    """反汇编字节码。"""
    i = 0
    data = bc.data
    while i < len(data):
        op = data[i]
        name = OPCODE.get(op, f'UNK_{op:02X}')
        line = f'  {i:04x}: {name}'
        i += 1
        if op == INSTR['PUSH_I']:
            val = struct.unpack_from('<i', data, i)[0]
            line += f' {val}'
            i += 4
        elif op in (INSTR['LOAD'], INSTR['STORE']):
            line += f' #{data[i]}'
            i += 1
        elif op in (INSTR['JMP'], INSTR['JZ'], INSTR['JNZ'], INSTR['CALL']):
            off = struct.unpack_from('<h', data, i)[0]
            target = i + 2 + off
            line += f' -> 0x{target:04x}'
            i += 2
        print(line)


if __name__ == '__main__':
    main()
