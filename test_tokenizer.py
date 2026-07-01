"""Test the tokenizer fix"""

import sys

sys.path.insert(0, '.')
from vm import VM
import struct

OLD_RUN = VM._run_inner


def traced_run(self):
    MAX_STEPS = 20000
    step = 0
    old_code = self.code
    while self.pc < len(self.code) and not self.halted and step < MAX_STEPS:
        op = self.code[self.pc]
        self.pc += 1

        if op == 0xFF:  # HALT
            self.halted = True
            break
        elif op == 0x0D:  # RET
            if self.call_stack:
                frame = self.call_stack.pop()
                self.code, self.pc, self.vars = frame
            else:
                self.halted = True
            break
        elif op == 0x09:  # JMP
            off = struct.unpack_from('<h', self.code, self.pc)[0]
            self.pc += 2
            self.pc += off
        elif op == 0x0A:  # JZ
            off = struct.unpack_from('<h', self.code, self.pc)[0]
            self.pc += 2
            v = self.stack.pop() if self.stack else 0
            if v == 0 or v == -1:
                self.pc += off
        elif op == 0x0B:  # JNZ
            off = struct.unpack_from('<h', self.code, self.pc)[0]
            self.pc += 2
            v = self.stack.pop() if self.stack else 0
            if v != 0 and v != -1:
                self.pc += off
        elif op in (0x07, 0x08):
            idx = self.code[self.pc]
            self.pc += 1
            if op == 0x07:  # LOAD
                val = self.vars[idx] if idx < len(self.vars) else 0
                self.stack.append(val)
            else:  # STORE
                val = self.stack.pop() if self.stack else 0
                if idx < len(self.vars):
                    self.vars[idx] = val
        elif op == 0x01:  # PUSH_I
            val = struct.unpack_from('<i', self.code, self.pc)[0]
            self.pc += 4
            self.stack.append(val)
        elif op == 0x2D:  # PUSH_STR
            length = self.code[self.pc]
            self.pc += 1
            chars = []
            for _ in range(length):
                lo = self.code[self.pc]
                hi = self.code[self.pc + 1]
                self.pc += 2
                chars.append(chr(lo | (hi << 8)))
            self.stack.append(''.join(chars))
        elif op == 0x25:  # GET
            idx = self.stack.pop() if self.stack else 0
            c = self.stack.pop() if self.stack else 0
            if isinstance(c, (list, str)):
                r = c[idx] if 0 <= idx < len(c) else 0
            elif isinstance(c, dict):
                r = c.get(idx, 0)
            else:
                r = 0
            self.stack.append(r)
        elif op == 0x1C:  # STREQ
            b = self.stack.pop() if self.stack else ''
            a = self.stack.pop() if self.stack else ''
            self.stack.append(1 if str(a) == str(b) else -1)
        elif op == 0x17:  # NOT
            a = self.stack.pop() if self.stack else 0
            self.stack.append(1 if (a == 0 or a == -1) else -1)
        elif op == 0x14:  # LT
            b = self.stack.pop() if self.stack else 0
            a = self.stack.pop() if self.stack else 0
            self.stack.append(1 if a < b else -1)
        elif op == 0x15:  # GTE
            b = self.stack.pop() if self.stack else 0
            a = self.stack.pop() if self.stack else 0
            self.stack.append(1 if a >= b else -1)
        elif op == 0x02:  # ADD
            b = self.stack.pop() if self.stack else 0
            a = self.stack.pop() if self.stack else 0
            self.stack.append(a + b)
        elif op == 0x03:  # SUB
            b = self.stack.pop() if self.stack else 0
            a = self.stack.pop() if self.stack else 0
            self.stack.append(a - b)
        elif op == 0x04:  # MUL
            b = self.stack.pop() if self.stack else 0
            a = self.stack.pop() if self.stack else 0
            self.stack.append(a * b)
        elif op == 0x05:  # DIV
            b = self.stack.pop() if self.stack else 0
            a = self.stack.pop() if self.stack else 0
            self.stack.append(a // b)
        elif op == 0x27:  # LIST_NEW
            n = self.stack.pop() if self.stack else 0
            if not isinstance(n, int):
                try:
                    n = int(n)
                except (ValueError, TypeError):
                    n = 0
            lst = []
            for _ in range(n):
                if self.stack:
                    lst.insert(0, self.stack.pop())
            self.stack.append(lst)
        elif op == 0x28:  # LIST_CONCAT
            b = self.stack.pop() if self.stack else []
            a = self.stack.pop() if self.stack else []
            if not isinstance(a, list):
                a = [a]
            if not isinstance(b, list):
                b = [b]
            self.stack.append(a + b)
        elif op == 0x32:  # DICT_KEYS (with string support)
            d = self.stack.pop() if self.stack else {}
            if isinstance(d, dict):
                self.stack.append(list(d.keys()))
            elif isinstance(d, str):
                self.stack.append(list(d))
            else:
                self.stack.append([])
        elif op == 0x36:  # STR_FIND
            a = str(self.stack.pop() if self.stack else '')
            b = str(self.stack.pop() if self.stack else '')
            self.stack.append(b.find(a))
        elif op == 0x1A:  # STRLEN
            s = self.stack.pop() if self.stack else ''
            self.stack.append(len(s))
        elif op == 0x1B:  # STRSUB
            end = self.stack.pop() if self.stack else 0
            start = self.stack.pop() if self.stack else 0
            s = self.stack.pop() if self.stack else ''
            if isinstance(s, str):
                self.stack.append(s[start:end])
            else:
                self.stack.append('')
        elif op == 0x19:  # CONCAT
            b = str(self.stack.pop() if self.stack else '')
            a = str(self.stack.pop() if self.stack else '')
            self.stack.append(a + b)
        elif op == 0x4C:  # CALL_CLOSURE
            closure = self.stack.pop() if self.stack else None
            if isinstance(closure, (list, tuple)) and len(closure) == 2:
                code_offset, closed_vars = closure
                saved_code = self.code
                saved_pc = self.pc
                self.code = old_code
                self.pc = code_offset
                while self.pc < len(self.code) and not self.halted:
                    if self.code[self.pc] == 0x0D:
                        self.pc += 1
                        break
                    if self.code[self.pc] == 0xFF:
                        self.halted = True
                        break
                    self.pc += 1
                self.code = saved_code
                self.pc = saved_pc
        elif op == 0x11:  # EQ
            b = self.stack.pop() if self.stack else 0
            a = self.stack.pop() if self.stack else 0
            self.stack.append(1 if a == b else -1)
        elif op == 0x13:  # GT
            b = self.stack.pop() if self.stack else 0
            a = self.stack.pop() if self.stack else 0
            self.stack.append(1 if a > b else -1)
        elif op == 0x16:  # LTE
            b = self.stack.pop() if self.stack else 0
            a = self.stack.pop() if self.stack else 0
            self.stack.append(1 if a <= b else -1)
        elif op == 0x23:  # IS_LIST
            v = self.stack.pop() if self.stack else 0
            self.stack.append(1 if isinstance(v, list) else -1)
        elif op == 0x26:  # SET_ELEMENT
            val = self.stack.pop() if self.stack else 0
            idx = self.stack.pop() if self.stack else 0
            c = self.stack.pop() if self.stack else 0
            if isinstance(c, list) and isinstance(idx, int) and 0 <= idx < len(c):
                c[idx] = val
        elif op == 0x0C:  # CALL
            addr = struct.unpack_from('<H', self.code, self.pc)[0]
            self.pc += 2
            frame = (self.pc, list(self.vars), len(self.stack))
            self.call_stack.append(frame)
            self.pc = addr
        elif op == 0x3F:  # CLOSURE
            body_addr = struct.unpack_from('<H', self.code, self.pc)[0]
            self.pc += 2
            closed_vars = []
            self.stack.append((body_addr, closed_vars))
        elif op == 0x17:  # NOT_OP
            a = self.stack.pop() if self.stack else 0
            self.stack.append(1 if (a == 0 or a == -1) else -1)
        elif op == 0x3B:  # LOAD16
            idx = struct.unpack_from('<H', self.code, self.pc)[0]
            self.pc += 2
            val = self.vars[idx] if idx < len(self.vars) else 0
            self.stack.append(val)
        elif op == 0x3C:  # STORE16
            idx = struct.unpack_from('<H', self.code, self.pc)[0]
            self.pc += 2
            val = self.stack.pop() if self.stack else 0
            if idx < len(self.vars):
                self.vars[idx] = val
        step += 1

    if step >= MAX_STEPS:
        print(f'TRACE: max steps, pc={self.pc}, stack={len(self.stack)}')


VM._run_inner = traced_run

vm = VM.from_bin('stdlib/sugar.bin')
print(f'Exports: {list(vm.exports.keys())}')
addr = vm.exports.get(list(vm.exports.keys())[0])
print(f'Calling export at {addr}')

vm.stack.append('1 + 2 * 3')
vm.code.append(0xFF)
vm.call_stack.append((len(vm.code) - 1, list(vm.vars), 0))
vm.pc = addr
vm.halted = False
vm._run_inner()

result = vm.stack[-1] if vm.stack else None
print(f'\nResult: {result}')
if isinstance(result, list):
    print(f'Token count: {len(result)}')
    for t in result:
        print(f'  {t}')
