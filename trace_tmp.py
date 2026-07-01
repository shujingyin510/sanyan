import sys
import os
import struct

sys.path.insert(0, r'D:\Test\sanyan')
os.environ['VM_MAX_STEPS'] = '500000'

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import vm as vm_mod
import importlib

importlib.reload(vm_mod)


class TracingVM(vm_mod.VM):
    def _run_inner(self):
        dispatch = vm_mod._DISPATCH_LIST
        max_steps = vm_mod.VM_MAX_STEPS
        steps = 0
        code = self.code
        stack = self.stack
        vars_ = self.vars
        pc = self.pc
        code_len = len(code)
        stack_append = stack.append
        stack_pop = stack.pop

        while pc < code_len:
            if steps >= max_steps:
                self.pc = pc
                raise vm_mod.VMError(f'VM max steps ({max_steps})')
            steps += 1
            op = code[pc]
            old_pc = pc
            pc += 1

            if op == vm_mod.PUSH_I:
                val = struct.unpack_from('<i', code, pc)[0]
                pc += 4
                stack.append(val)
                self.pc = pc
                continue
            if op == vm_mod.LOAD:
                idx = code[pc]
                pc += 1
                stack.append(vars_[idx] if idx < len(vars_) else 0)
                self.pc = pc
                continue
            if op == vm_mod.STORE:
                idx = code[pc]
                pc += 1
                if idx < len(vars_):
                    vars_[idx] = stack_pop() if stack else 0
                self.pc = pc
                continue
            if op == vm_mod.HALT:
                self.halted = True
                self.pc = pc
                return
            if op == vm_mod.ADD:
                b = stack_pop() if stack else 0
                a = stack_pop() if stack else 0
                stack_append(str(a) + str(b)) if isinstance(a, str) or isinstance(b, str) else stack_append(a + b)
                self.pc = pc
                continue
            if op == vm_mod.SUB:
                b = stack_pop() if stack else 0
                a = stack_pop() if stack else 0
                stack_append(a - b)
                self.pc = pc
                continue
            if op == vm_mod.LT:
                b = stack_pop() if stack else 0
                a = stack_pop() if stack else 0
                stack_append(1 if a < b else -1)
                self.pc = pc
                continue
            if op == vm_mod.GT:
                b = stack_pop() if stack else 0
                a = stack_pop() if stack else 0
                stack_append(1 if a > b else -1)
                self.pc = pc
                continue
            if op == vm_mod.EQ:
                b = stack_pop() if stack else 0
                a = stack_pop() if stack else 0
                stack_append(1 if a == b else -1)
                self.pc = pc
                continue
            if op == vm_mod.GTE:
                b = stack_pop() if stack else 0
                a = stack_pop() if stack else 0
                stack_append(1 if a >= b else -1)
                self.pc = pc
                continue
            if op == vm_mod.STRLEN:
                stack_append(len(str(stack_pop() if stack else '')))
                self.pc = pc
                continue
            if op == vm_mod.STRSUB:
                end = stack_pop()
                start = stack_pop()
                s = stack_pop()
                stack_append(s[start:end] if isinstance(s, str) else '')
                self.pc = pc
                continue
            if op == vm_mod.PUSH_STR:
                length = code[pc]
                pc += 1
                chars = []
                for _ in range(length):
                    lo = code[pc]
                    hi = code[pc + 1]
                    pc += 2
                    chars.append(chr(lo | (hi << 8)))
                stack_append(''.join(chars))
                self.pc = pc
                continue
            if op == vm_mod.LIST_NEW:
                n = stack_pop() if stack else 0
                if not isinstance(n, (int, float)):
                    try:
                        n = int(n)
                    except (ValueError, TypeError):
                        n = 0
                n = max(0, min(int(n), len(stack)))
                if n == 0:
                    stack_append([])
                else:
                    items = stack[-n:]
                    del stack[-n:]
                    stack_append(items)
                self.pc = pc
                continue
            if op == vm_mod.LIST_CONCAT:
                b = stack_pop() if stack else 0
                a = stack_pop() if stack else 0
                stack_append((a if isinstance(a, list) else [a]) + (b if isinstance(b, list) else [b]))
                self.pc = pc
                continue
            if op == vm_mod.CONCAT:
                b = str(stack_pop() if stack else '')
                a = str(stack_pop() if stack else '')
                stack_append(a + b)
                self.pc = pc
                continue
            if op == vm_mod.NOT:
                a = stack_pop() if stack else 0
                a = vm_mod.VM._to_bool(a) if isinstance(a, str) else a
                if isinstance(a, int):
                    stack_append(-1 if a > 0 else (1 if a < 0 else 0))
                else:
                    stack_append(0)
                self.pc = pc
                continue
            if op == vm_mod.LIST_LEN:
                c = stack_pop() if stack else 0
                stack_append(len(c) if isinstance(c, (list, str, dict)) else 0)
                self.pc = pc
                continue

            # Control flow with TRACE
            if op == vm_mod.JMP:
                off = struct.unpack_from('<h', code, pc)[0]
                target = pc + 2 + off
                if 600 <= old_pc <= 2500:
                    print(f'  TRACE[{old_pc}] JMP -> {target}')
                pc += 2 + off
                self.pc = pc
                continue
            if op == vm_mod.JZ:
                off = struct.unpack_from('<h', code, pc)[0]
                pc += 2
                v = stack_pop() if stack else 0
                do_jump = False
                if isinstance(v, str):
                    do_jump = v == '假'
                elif not (isinstance(v, int) and v > 0):
                    do_jump = True
                target = pc + off if do_jump else pc
                if 600 <= old_pc <= 2500:
                    print(f'  TRACE[{old_pc}] JZ v={repr(str(v)[:15])} do_jump={do_jump} -> {target}')
                if do_jump:
                    pc += off
                self.pc = pc
                continue
            if op == vm_mod.JNZ:
                off = struct.unpack_from('<h', code, pc)[0]
                pc += 2
                v = stack_pop() if stack else 0
                do_jump = False
                if isinstance(v, str):
                    do_jump = v == '真'
                elif isinstance(v, int) and v > 0:
                    do_jump = True
                target = pc + off if do_jump else pc
                if 600 <= old_pc <= 2500:
                    print(f'  TRACE[{old_pc}] JNZ v={repr(str(v)[:15])} do_jump={do_jump} -> {target}')
                if do_jump:
                    pc += off
                self.pc = pc
                continue
            if op == vm_mod.RET:
                if self.call_stack:
                    frame = self.call_stack.pop()
                    ret_pc, saved_vars, stack_base = frame[0], frame[1], frame[2]
                    ret_val = stack_pop() if len(stack) > stack_base else None
                    del stack[stack_base:]
                    if ret_val is not None:
                        stack.append(ret_val)
                    pc = ret_pc
                    vars_ = saved_vars
                    self.vars = vars_
                else:
                    break
                self.pc = pc
                continue

            # Dispatch fallthrough
            handler = dispatch[op]
            if handler is not None:
                self.pc = pc
                if not handler(self, op):
                    break
                pc = self.pc
            self.pc = pc

        self.pc = pc


# Load sugar.bin
with open('stdlib/sugar.bin', 'rb') as f:
    data = f.read()
magic, ver, vc, sz = struct.unpack_from('<4sBBI', data, 0)
pos = 10
code = bytearray(data[pos : pos + sz])
v = TracingVM(code, max(vc, 256), {})
v.run_init()

print('=== CALL 词法分析 ===')
v.stack = []
v.call_stack.clear()
v._exec_frame(v.code, v.exports.get('词法分析'), ['1 + 2 * 3'])
print(f'\nFinal result: {repr(str(v.stack)[:200])}')
