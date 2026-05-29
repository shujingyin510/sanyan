"""字节码 VM — 从 STM32 C runtime 反向移植到 Python

与 sanyancc.py 共用同一指令集，可执行编译后的 .bin 字节码。
用法:
    from vm import VM
    vm = VM.from_bin('firmware.bin')
    vm.run()
"""

from __future__ import annotations
import struct
from typing import Callable

# ═══════════════════════════════════════════════════════════════
# 指令集（与 sanyancc.py / runtime_stm32.c 一致）
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
EQ = 0x11
NE = 0x12
GT = 0x13
LT = 0x14
GTE = 0x15
LTE = 0x16
NOT = 0x17
WAIT = 0x18
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
GET = 0x25
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
HALT = 0xFF

OP_NAMES = {v: k for k, v in vars().items() if isinstance(v, int) and k.isupper()}


class VMError(Exception):
    """VM 运行时错误"""


class VM:
    """栈式字节码虚拟机

    与 runtime_stm32.c 的 vm_run() 等效的 Python 实现。

    关键状态:
        code       — 当前执行的字节码数组（只读，不修改）
        pc         — 程序计数器（指向下一条要执行的指令）
        stack      — 数据栈（运算数、函数参数、返回值）
        vars       — 变量数组（STORE 写入、LOAD 读取，长度固定）
        call_stack — 调用栈：每帧为 (返回地址, vars快照)
        halted     — 是否已停机
    """

    def __init__(self, code: bytearray, vars_count: int = 256, exports: dict | None = None):
        self.code = code
        self.pc = 0
        self.stack: list = []
        self.vars: list = [0] * max(vars_count, 1)
        self.halted = False
        self.call_stack: list[tuple[int, list, int]] = []
        self.exports: dict[str, int] = exports or {}
        self.modules: dict[str, 'VM'] = {}
        self.modules_by_id: dict[int, 'VM'] = {}

    # ── 导出查找 ─────────────────────────────────────────────
    def get_export(self, name: str) -> int | None:
        return self.exports.get(name)

    # ── 模块注册与导入 ───────────────────────────────────────
    def register_module(self, name: str, vm: 'VM') -> None:
        self.modules[name] = vm
        self.modules_by_id[id(vm)] = vm

    def import_module(self, path: str) -> int:
        """导入另一个 .bin 模块，返回模块句柄。"""
        vm = VM.from_bin(path)
        name = path.split('/')[-1].replace('.bin', '')
        self.modules[name] = vm
        self.modules_by_id[id(vm)] = vm
        return id(vm)

    # ═══════════════════════════════════════════════════════════
    # 帧执行：在独立的模块帧中执行字节码
    #
    # 保存当前 code/pc/vars/call_stack，切换到目标模块的帧，
    # 执行完毕后恢复。CALL_EXT 指令依赖此方法实现跨模块调用。
    # ═══════════════════════════════════════════════════════════
    def _exec_frame(self, code, start_pc, args: list | None = None) -> None:
        """在一个模块帧中执行字节码。

        保存当前的 code/pc/vars/call_stack，切换到目标帧执行，
        执行完毕后完整恢复。注意：vars 用 copy 隔离，避免内部修改
        污染外层变量（这是 JMP 循环 + 递归 CALL 能正常工作的关键）。
        """
        old_code = self.code
        old_pc = self.pc
        old_vars = self.vars  # 保存外层 vars 引用
        old_call_stack = list(self.call_stack)

        self.call_stack.clear()
        self.code = code
        self.pc = start_pc
        self.vars = list(old_vars)  # 使用独立副本执行
        if args:
            for val in args:
                self.stack.append(val)

        self._run_inner()

        # 完整恢复外层状态（关键：vars 回原来的引用，不保留内部修改）
        self.code = old_code
        self.pc = old_pc
        self.vars = old_vars
        self.call_stack = old_call_stack

    # ═══════════════════════════════════════════════════════════
    # 指令读取辅助方法
    # ═══════════════════════════════════════════════════════════
    def _read_i16(self) -> int:
        """读取有符号 16 位整数，pc 前进 2 字节"""
        val: int = struct.unpack_from('<h', self.code, self.pc)[0]
        self.pc += 2
        return val

    def _read_i32(self) -> int:
        """读取有符号 32 位整数，pc 前进 4 字节"""
        val: int = struct.unpack_from('<i', self.code, self.pc)[0]
        self.pc += 4
        return val

    # ═══════════════════════════════════════════════════════════
    # 指令分组执行方法
    #
    # 每个方法处理一类相关操作码，由 _run_inner 通过分派表调用。
    # 返回 True 表示继续执行，返回 False 表示停止（如 RET 弹出最后一帧）。
    # ═══════════════════════════════════════════════════════════

    def _exec_control_flow(self, op: int) -> bool:
        """控制流指令：RET, JMP, JMP32, JZ, JNZ, CALL"""
        if op == RET:
            if self.call_stack:
                pc, saved_vars, stack_base = self.call_stack.pop()
                # 安全检查：栈不应低于调用基线
                if len(self.stack) < stack_base:
                    raise VMError(f'栈下溢: stack={len(self.stack)} < base={stack_base}, func_return_pc={pc:#x}')
                ret_val = self.stack.pop() if len(self.stack) > stack_base else None
                del self.stack[stack_base:]
                if ret_val is not None:
                    self.stack.append(ret_val)
                self.pc = pc
                self.vars = saved_vars
            else:
                return False
        elif op == JMP:
            off = self._read_i16()
            self.pc += off
        elif op == JMP32:
            off = self._read_i32()
            self.pc += off
        elif op == JZ:
            off = self._read_i16()
            if self.stack.pop() == 0:
                self.pc += off
        elif op == JNZ:
            off = self._read_i16()
            if self.stack.pop() != 0:
                self.pc += off
        elif op == CALL:
            addr = self._read_i16()
            if addr != 0:
                # 从函数入口开始数连续 STORE = 参数个数
                # 函数入口 = JMP skip 之后的第一条指令
                arg_count = 0
                p = addr
                while p + 1 < len(self.code) and self.code[p] == STORE:
                    arg_count += 1
                    p += 2
                # base = 调用方推参数前的栈深
                caller_base = len(self.stack) - arg_count
                self.call_stack.append((self.pc, list(self.vars), caller_base))
                self.pc = addr
        return True

    def _exec_stack_ops(self, op: int) -> bool:
        """栈操作指令：PUSH_I, PUSH_STR, LOAD, STORE, PRINT"""
        if op == PUSH_I:
            self.stack.append(self._read_i32())
        elif op == PUSH_STR:
            length = self.code[self.pc]
            self.pc += 1
            chars = []
            for _ in range(length):
                lo = self.code[self.pc]
                hi = self.code[self.pc + 1]
                self.pc += 2
                chars.append(chr(lo | (hi << 8)))
            self.stack.append(''.join(chars))
        elif op == LOAD:
            idx = self.code[self.pc]
            self.pc += 1
            self.stack.append(self.vars[idx] if idx < len(self.vars) else 0)
        elif op == STORE:
            idx = self.code[self.pc]
            self.pc += 1
            if idx < len(self.vars):
                self.vars[idx] = self.stack.pop()
        elif op == PRINT:
            print(self.stack.pop())
        return True

    def _exec_arithmetic(self, op: int) -> bool:
        """算术运算指令：ADD, SUB, MUL, DIV, MOD"""
        b = self.stack.pop()
        a = self.stack.pop()
        if op == ADD:
            self.stack.append(a + b)
        elif op == SUB:
            self.stack.append(a - b)
        elif op == MUL:
            self.stack.append(a * b)
        elif op == DIV:
            self.stack.append(a // b if b else 0)
        elif op == MOD:
            self.stack.append(a % b if b else 0)
        return True

    def _exec_comparison(self, op: int) -> bool:
        """比较与逻辑运算指令：GT, LT, GTE, LTE, EQ, NE, NOT"""
        if op == NOT:
            a = self.stack.pop()
            self.stack.append(1 if a == 0 else 0)
        else:
            b = self.stack.pop()
            a = self.stack.pop()
            if op == GT:
                self.stack.append(1 if a > b else 0)
            elif op == LT:
                self.stack.append(1 if a < b else 0)
            elif op == GTE:
                self.stack.append(1 if a >= b else 0)
            elif op == LTE:
                self.stack.append(1 if a <= b else 0)
            elif op == EQ:
                self.stack.append(1 if a == b else 0)
            elif op == NE:
                self.stack.append(1 if a != b else 0)
        return True

    def _exec_type_check(self, op: int) -> bool:
        """类型检查指令：IS_NUM, IS_STR, IS_LIST, SAME"""
        if op == SAME:
            b = self.stack.pop()
            a = self.stack.pop()
            self.stack.append(1 if a == b else 0)
        else:
            v = self.stack.pop()
            if op == IS_NUM:
                self.stack.append(1 if isinstance(v, (int, float)) else 0)
            elif op == IS_STR:
                self.stack.append(1 if isinstance(v, str) else 0)
            elif op == IS_LIST:
                self.stack.append(1 if isinstance(v, (list, dict)) else 0)
        return True

    def _exec_string(self, op: int) -> bool:
        """字符串操作指令：STRLEN, STRSUB, STREQ, CONCAT, ORD"""
        if op == STRLEN:
            self.stack.append(len(str(self.stack.pop())))
        elif op == STRSUB:
            length = self.stack.pop()
            start = self.stack.pop()
            s = str(self.stack.pop())
            self.stack.append(s[start : start + length])
        elif op == STREQ:
            b = str(self.stack.pop())
            a = str(self.stack.pop())
            self.stack.append(1 if a == b else 0)
        elif op == CONCAT:
            b = str(self.stack.pop())
            a = str(self.stack.pop())
            self.stack.append(a + b)
        elif op == ORD:
            ch = str(self.stack.pop())
            self.stack.append(ord(ch[0]) if ch else 0)
        return True

    def _exec_container(self, op: int) -> bool:
        """容器操作指令：GET, SET_ELEMENT, LIST_NEW, LIST_CONCAT, SLICE, LIST_LEN"""
        if op == GET:
            idx = self.stack.pop()
            c = self.stack.pop()
            if isinstance(c, (list, str)):
                self.stack.append(c[idx] if 0 <= idx < len(c) else 0)
            elif isinstance(c, dict):
                self.stack.append(c.get(idx, 0))
            else:
                self.stack.append(0)
        elif op == SET_ELEMENT:
            val = self.stack.pop()
            idx = self.stack.pop()
            c = self.stack.pop()
            if isinstance(c, list) and 0 <= idx < len(c):
                c[idx] = val
            self.stack.append(c)
        elif op == LIST_NEW:
            n = self.stack.pop() if self.stack and isinstance(self.stack[-1], int) else 0
            if not isinstance(n, int):
                n = int(n) if str(n).lstrip('-').replace('.', '').isdigit() else 0
            lst: list = []
            for _ in range(n):
                lst.insert(0, self.stack.pop())
            self.stack.append(lst)
        elif op == LIST_CONCAT:
            b = self.stack.pop()
            a = self.stack.pop()
            self.stack.append((a if isinstance(a, list) else [a]) + (b if isinstance(b, list) else [b]))
        elif op == SLICE:
            # 支持 2 参数 (container, start) 和 3 参数 (container, start, end)
            a = self.stack.pop()
            b = self.stack.pop()
            if self.stack:
                # 3 参数：c start end
                end = a
                start = b
                c = self.stack.pop()
            else:
                # 2 参数：c start
                start = a
                c = b
                end = len(c) if isinstance(c, (list, str)) else 0
            # 确保索引为整数
            if not isinstance(start, int):
                start = int(start) if str(start).lstrip('-').isdigit() else 0
            if not isinstance(end, int):
                end = int(end) if str(end).lstrip('-').isdigit() else (len(c) if isinstance(c, (list, str)) else 0)
            self.stack.append(c[start:end] if isinstance(c, (list, str)) else [])
        elif op == LIST_LEN:
            c = self.stack.pop()
            self.stack.append(len(c) if isinstance(c, (list, str, dict)) else 0)
        return True

    def _exec_dict(self, op: int) -> bool:
        """字典操作指令：DICT, DICT_GET, DICT_SET, DICT_HAS, DICT_KEYS"""
        if op == DICT:
            n = self.stack.pop() if self.stack and isinstance(self.stack[-1], int) else 0
            if not isinstance(n, int):
                n = int(n) if str(n).lstrip('-').replace('.', '').isdigit() else 0
            d = {}
            for _ in range(n):
                v = self.stack.pop()
                k = self.stack.pop()
                d[k] = v
            self.stack.append(d)
        elif op == DICT_GET:
            key = self.stack.pop()
            d = self.stack.pop()
            self.stack.append(d.get(key, 0))
        elif op == DICT_SET:
            val = self.stack.pop()
            key = self.stack.pop()
            d = self.stack.pop()
            d[key] = val
            # 不 push 返回值——所有调用方都是纯副作用，push 会造成栈泄漏
        elif op == DICT_HAS:
            key = self.stack.pop()
            d = self.stack.pop()
            self.stack.append(1 if key in d else 0)
        elif op == DICT_KEYS:
            d = self.stack.pop()
            self.stack.append(list(d.keys()) if isinstance(d, dict) else [])
        return True

    def _exec_io(self, op: int) -> bool:
        """I/O 操作指令：IO_READ, IO_WRITE, WAIT, READ_FILE, WRITE_FILE, WRITE_BINARY"""
        if op == IO_READ:
            self.stack.pop()
            self.stack.append(0)
        elif op == IO_WRITE:
            self.stack.pop()
            self.stack.pop()
        elif op == WAIT:
            self.stack.pop()
        elif op == READ_FILE:
            path = str(self.stack.pop())
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    self.stack.append(f.read())
            except Exception:
                self.stack.append('')
        elif op == WRITE_FILE:
            data = str(self.stack.pop())
            path = str(self.stack.pop())
            try:
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(data)
                self.stack.append(1)
            except Exception:
                self.stack.append(0)
        elif op == WRITE_BINARY:
            data = self.stack.pop()
            path = str(self.stack.pop())
            try:
                if isinstance(data, list):
                    raw = bytes(b & 0xFF if isinstance(b, int) else 0 for b in data)
                    with open(path, 'wb') as f:
                        f.write(raw)
                self.stack.append(1)
            except Exception:
                self.stack.append(0)
        return True

    def _exec_module(self, op: int) -> bool:
        """模块操作指令：IMPORT, CALL_EXT"""
        if op == IMPORT:
            path = str(self.stack.pop())
            self.stack.append(self.import_module(path))
        elif op == CALL_EXT:
            # 栈顶到栈底: module_id, func_name, arg_count, args...
            mod_id = self.stack.pop()
            func_name = str(self.stack.pop())
            arg_count = self.stack.pop()
            target = self.modules_by_id.get(mod_id)
            if target and func_name in target.exports:
                args: list = []
                for _ in range(arg_count):
                    args.insert(0, self.stack.pop())
                self._exec_frame(target.code, target.exports[func_name], args)
            else:
                self.stack.append(0)
        return True

    # ═══════════════════════════════════════════════════════════
    # 操作码分派表（模块级，避免每次调用重建）
    #
    # 每个条目将操作码映射到对应的执行方法。
    # HALT 留在 _run_inner 中直接处理（需提前 return）。
    # ═══════════════════════════════════════════════════════════
    # 此处引用 VM 类的方法，需在类定义之后填充。
    # 实际分派表在类定义之后构建（见文件末尾 _DISPATCH）。

    # ═══════════════════════════════════════════════════════════
    # 主执行循环
    #
    # 设计原则:
    #   1. 每条指令 self.pc 始终指向"下一条指令的首字节"
    #   2. CALL 保存 (返回地址, vars快照) 到 call_stack，然后跳转
    #   3. RET 从 call_stack 弹出帧，恢复 pc 和 vars
    #   4. JMP/JZ/JNZ 使用有符号相对偏移（从指令末尾算起）
    #   5. 循环内的 CALL/RET 不干扰 JMP 跳转目标（call_stack 独立管理）
    # ═══════════════════════════════════════════════════════════
    def _run_inner(self) -> None:
        """内部执行循环。通过分派表将操作码路由到对应的执行方法。"""
        dispatch = _DISPATCH
        while not self.halted and self.pc < len(self.code):
            op = self.code[self.pc]
            self.pc += 1

            if op == HALT:
                self.halted = True
                return

            handler = dispatch.get(op)
            if handler is not None:
                if not handler(self, op):
                    break
            # 未知操作码 → 跳过（保持向后兼容）

    # ═══════════════════════════════════════════════════════════
    # from_bin: 从 .bin 文件加载并初始化
    #
    # .bin 文件结构:
    #   [0..3]   magic  "SAN0"
    #   [4]      ver    版本号
    #   [5]      vc     变量数
    #   [6..7]   sz     代码大小（小端 u16）
    #   [8..]    code   字节码
    #   [8+sz..]        导出表（count + entries）
    #
    # 加载后自动执行模块初始化代码（填充全局变量）。
    # ═══════════════════════════════════════════════════════════
    @classmethod
    def from_bin(cls, path: str) -> 'VM':
        with open(path, 'rb') as f:
            data = f.read()
        magic, ver, vc, sz = struct.unpack_from('<4sBBI', data, 0)
        if magic != b'SAN0':
            raise VMError(f'无效的字节码文件: magic={magic!r}')
        pos = 10
        code = bytearray(data[pos : pos + sz])
        pos += sz

        # 读取导出表
        exports = {}
        if len(data) > pos + 2:
            export_count = struct.unpack_from('<H', data, pos)[0]
            pos += 2
            for _ in range(export_count):
                name_len = struct.unpack_from('<H', data, pos)[0]
                pos += 2
                chars = []
                for _ in range(name_len):
                    lo = data[pos]
                    hi = data[pos + 1]
                    pos += 2
                    chars.append(chr(lo | (hi << 8)))
                name = ''.join(chars)
                addr = struct.unpack_from('<H', data, pos)[0]
                pos += 2
                exports[name] = addr

        vm = cls(code, max(vc, 256), exports)

        # 执行模块初始化代码（设置全局变量：操作码值、OP映射等）
        # 初始化代码从 PC=0 开始，执行到代码末尾自动退出
        vm._run_inner()
        vm.pc = 0
        vm.halted = False
        return vm

    def run(self) -> None:
        """执行字节码直到 HALT 或代码结束。"""
        self._run_inner()


# ═══════════════════════════════════════════════════════════════
# 操作码分派表（模块级常量）
#
# 将每个操作码映射到 VM 实例的对应执行方法。
# 使用 dict.get() 查找，未知操作码静默跳过（向后兼容）。
# ═══════════════════════════════════════════════════════════════
_DISPATCH: dict[int, 'Callable'] = {
    # 控制流
    RET:     VM._exec_control_flow,
    JMP:     VM._exec_control_flow,
    JMP32:   VM._exec_control_flow,
    JZ:      VM._exec_control_flow,
    JNZ:     VM._exec_control_flow,
    CALL:    VM._exec_control_flow,
    # 栈操作
    PUSH_I:  VM._exec_stack_ops,
    PUSH_STR: VM._exec_stack_ops,
    LOAD:    VM._exec_stack_ops,
    STORE:   VM._exec_stack_ops,
    PRINT:   VM._exec_stack_ops,
    # 算术
    ADD:     VM._exec_arithmetic,
    SUB:     VM._exec_arithmetic,
    MUL:     VM._exec_arithmetic,
    DIV:     VM._exec_arithmetic,
    MOD:     VM._exec_arithmetic,
    # 比较与逻辑
    GT:      VM._exec_comparison,
    LT:      VM._exec_comparison,
    GTE:     VM._exec_comparison,
    LTE:     VM._exec_comparison,
    EQ:      VM._exec_comparison,
    NE:      VM._exec_comparison,
    NOT:     VM._exec_comparison,
    # 类型检查
    IS_NUM:  VM._exec_type_check,
    IS_STR:  VM._exec_type_check,
    IS_LIST: VM._exec_type_check,
    SAME:    VM._exec_type_check,
    # 字符串
    STRLEN:  VM._exec_string,
    STRSUB:  VM._exec_string,
    STREQ:   VM._exec_string,
    CONCAT:  VM._exec_string,
    ORD:     VM._exec_string,
    # 容器
    GET:         VM._exec_container,
    SET_ELEMENT: VM._exec_container,
    LIST_NEW:    VM._exec_container,
    LIST_CONCAT: VM._exec_container,
    SLICE:       VM._exec_container,
    LIST_LEN:    VM._exec_container,
    # 字典
    DICT:      VM._exec_dict,
    DICT_GET:  VM._exec_dict,
    DICT_SET:  VM._exec_dict,
    DICT_HAS:  VM._exec_dict,
    DICT_KEYS: VM._exec_dict,
    # I/O
    IO_READ:      VM._exec_io,
    IO_WRITE:     VM._exec_io,
    WAIT:         VM._exec_io,
    READ_FILE:    VM._exec_io,
    WRITE_FILE:   VM._exec_io,
    WRITE_BINARY: VM._exec_io,
    # 模块
    IMPORT:   VM._exec_module,
    CALL_EXT: VM._exec_module,
}


def disassemble(code: bytearray) -> str:
    """反汇编字节码（调试用）。

    注意: CALL 使用绝对地址，反汇编中显示为相对偏移（仅供位置参考）。
    """
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
        elif op in (LOAD, STORE, GET, SET_ELEMENT):
            line += f' #{code[pc]}'
            pc += 1
        elif op in (LIST_NEW,):
            n = code[pc]
            line += f' {n}'
            pc += 1
        elif op in (JMP, JZ, JNZ, CALL):
            off = struct.unpack_from('<h', code, pc)[0]
            target = pc + 2 + off
            line += f' -> {target:04x}'
            pc += 2
        elif op == PUSH_STR:
            length = code[pc]
            pc += 1
            chars = []
            for _ in range(length):
                lo = code[pc]
                hi = code[pc + 1]
                pc += 2
                chars.append(chr(lo | (hi << 8)))
            line += f' {repr("".join(chars))}'
        elif op in (IMPORT, CALL_EXT):
            pass
        lines.append(line)
    return '\n'.join(lines)
