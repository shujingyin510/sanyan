import sys
import os
import struct

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ['VM_MAX_STEPS'] = '50000'
import vm as vm_mod

v = vm_mod.VM.from_bin('stdlib/sugar.bin')


def make_traced_run():
    dispatch = vm_mod._DISPATCH
    max_steps = vm_mod.VM_MAX_STEPS

    def traced_run(self):
        trace_active = getattr(self, '_trace_active', False)
        if not trace_active:
            vm_mod.VM._run_inner(self)
            return

        steps = 0
        code = self.code
        stack = self.stack
        vars_ = self.vars
        pc = self.pc
        code_len = len(code)
        stack_pop = stack.pop

        while pc < code_len:
            if steps >= max_steps:
                self.pc = pc
                raise vm_mod.VMError(f'max steps {max_steps}')
            steps += 1
            op = code[pc]
            old_pc = pc
            pc += 1

            if op == 0x01:  # PUSH_I
                val = struct.unpack_from('<i', code, pc)[0]
                pc += 4
                stack.append(val)
            elif op == 0x07:  # LOAD
                idx = code[pc]
                pc += 1
                val = vars_[idx] if idx < len(vars_) else 0
                if idx in (20, 27):
                    print(f'  [{old_pc}] LOAD var[{idx}]={repr(str(val)[:15])}')
                stack.append(val)
            elif op == 0x08:  # STORE
                idx = code[pc]
                pc += 1
                val = stack_pop() if stack else 0
                if idx in (15, 16, 17, 18, 19, 20, 27):
                    print(f'  [{old_pc}] STORE var[{idx}]={repr(str(val)[:15])}')
                if idx < len(vars_):
                    vars_[idx] = val
            elif op == 0x09:  # JMP
                off = struct.unpack_from('<h', code, pc)[0]
                target = pc + 2 + off
                print(f'  [{old_pc}] JMP -> {target}')
                pc += 2 + off
            elif op == 0x0A:  # JZ
                off = struct.unpack_from('<h', code, pc)[0]
                pc += 2
                v = stack_pop() if stack else 0
                do_jump = False
                if isinstance(v, str):
                    do_jump = v == '\u5047'
                elif not (isinstance(v, int) and v > 0):
                    do_jump = True
                target = pc + off if do_jump else pc
                print(f'  [{old_pc}] JZ v={repr(str(v))} -> {target}' + (' JUMP!' if do_jump else ' fallthrough'))
                if do_jump:
                    pc += off
            elif op == 0x0B:  # JNZ
                off = struct.unpack_from('<h', code, pc)[0]
                pc += 2
                v = stack_pop() if stack else 0
                do_jump = False
                if isinstance(v, str):
                    do_jump = v == '\u771f'
                elif isinstance(v, int) and v > 0:
                    do_jump = True
                target = pc + off if do_jump else pc
                print(f'  [{old_pc}] JNZ v={repr(str(v))} -> {target}' + (' JUMP!' if do_jump else ' fallthrough'))
                if do_jump:
                    pc += off
            elif op == 0x0D:  # RET
                print(f'  [{old_pc}] RET stack_top={repr(str(stack[-1])[:20] if stack else "<empty>")}')
                self.pc = pc
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
                continue
            elif op == 0x11:  # EQ
                b = stack_pop() if stack else 0
                a = stack_pop() if stack else 0
                stack.append(1 if a == b else -1)
            elif op == 0x14:  # LT
                b = stack_pop() if stack else 0
                a = stack_pop() if stack else 0
                stack.append(1 if a < b else -1)
            elif op == 0x15:  # GTE
                b = stack_pop() if stack else 0
                a = stack_pop() if stack else 0
                stack.append(1 if a >= b else -1)
            elif op == 0x17:  # NOT
                a = stack_pop() if stack else 0
                if isinstance(a, str):
                    a = 1 if a == '\u771f' else 0
                if isinstance(a, int):
                    stack.append(-1 if a > 0 else (1 if a < 0 else 0))
                else:
                    stack.append(0)
            elif op == 0x02:  # ADD
                b = stack_pop() if stack else 0
                a = stack_pop() if stack else 0
                if isinstance(a, str) or isinstance(b, str):
                    stack.append(str(a) + str(b))
                else:
                    stack.append(a + b)
            elif op == 0x03:  # SUB
                b = stack_pop() if stack else 0
                a = stack_pop() if stack else 0
                stack.append(a - b)
            elif op == 0x1A:  # STRLEN
                s = stack_pop() if stack else ''
                stack.append(len(str(s)))
            elif op == 0x1B:  # STRSUB
                end = stack_pop()
                start = stack_pop()
                s = stack_pop()
                stack.append(s[start:end] if isinstance(s, str) else '')
            elif op == 0x19:  # CONCAT
                b = str(stack_pop() if stack else '')
                a = str(stack_pop() if stack else '')
                stack.append(a + b)
            elif op == 0x36:  # STR_FIND
                a = stack_pop() if stack else ''
                b = stack_pop() if stack else ''
                result = b.find(a) if isinstance(a, str) and isinstance(b, str) else -1
                print(f'  [{old_pc}] STR_FIND a={repr(a)} b={repr(b)} -> {result}')
                stack.append(result)
            elif op == 0x1C:  # STREQ
                b = stack_pop() if stack else ''
                a = stack_pop() if stack else ''
                stack.append(1 if isinstance(a, str) and isinstance(b, str) and a == b else -1)
            elif op == 0x2D:  # PUSH_STR
                length = code[pc]
                pc += 1
                chars = []
                for _ in range(length):
                    lo = code[pc]
                    hi = code[pc + 1]
                    pc += 2
                    chars.append(chr(lo | (hi << 8)))
                s = ''.join(chars)
                print(f'  [{old_pc}] PUSH_STR {repr(s)}')
                stack.append(s)
            elif op == 0x27:  # LIST_NEW
                n = stack_pop() if stack else 0
                if not isinstance(n, (int, float)):
                    try:
                        n = int(n)
                    except (ValueError, TypeError):
                        n = 0
                n = max(0, min(int(n), len(stack)))
                if n == 0:
                    result = []
                else:
                    items = stack[-n:]
                    del stack[-n:]
                    result = items
                print(f'  [{old_pc}] LIST_NEW n={n}')
                stack.append(result)
            elif op == 0x28:  # LIST_CONCAT
                b = stack_pop() if stack else 0
                a = stack_pop() if stack else 0
                result = (a if isinstance(a, list) else [a]) + (b if isinstance(b, list) else [b])
                print(f'  [{old_pc}] LIST_CONCAT')
                stack.append(result)
            elif op == 0x4C:  # CALL_CLOSURE
                closure = stack_pop() if stack else None
                if closure and isinstance(closure, list) and len(closure) >= 2:
                    target = closure[0]
                    nargs = closure[1]
                    args = []
                    for _ in range(nargs):
                        args.insert(0, stack_pop() if stack else 0)
                    print(f'  [{old_pc}] CALL_CLOSURE target={target} nargs={nargs} args={args}')
                    self.call_stack.append((pc, list(vars_), len(stack), closure))
                    vars_ = list(vars_)
                    self.vars = vars_
                    pc = target
                    continue
                else:
                    stack.append(0)
            elif op == 0x25:  # GET
                idx = stack_pop() if stack else 0
                c = stack_pop() if stack else 0
                if isinstance(c, (list, str)):
                    result = c[idx] if 0 <= idx < len(c) else 0
                elif isinstance(c, dict):
                    result = c.get(idx, 0)
                else:
                    result = 0
                if old_pc in (669, 798, 839, 916, 1242):
                    print(
                        f'  [{old_pc}] GET c type={type(c).__name__} len={len(c) if isinstance(c, (list, str, dict)) else "?"} idx={idx}'
                    )
                stack.append(result)
            elif op == 0xFF:  # HALT
                print(f'  [{old_pc}] HALT')
                self.halted = True
                self.pc = pc
                return
            else:
                # Dispatch
                self.pc = pc
                handler = dispatch[op]
                if handler is not None:
                    if not handler(self, op):
                        break
                    pc = self.pc
                continue

            self.pc = pc

        self.pc = pc

    return traced_run


# Replace _run_inner
vm_mod.VM._run_inner = make_traced_run()

print('=== CALL \u8bcd\u6cd5\u5206\u6790 ===')
v.stack = []
v.call_stack.clear()
v._trace_active = True
v._exec_frame(v.code, v.exports.get('\u8bcd\u6cd5\u5206\u6790'), ['1 + 2 * 3'])
v._trace_active = False
print()
print(f'Result: {repr(str(v.stack)[:200])}')
