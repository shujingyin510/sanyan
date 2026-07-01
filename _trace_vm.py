# ruff: noqa: E402
"""Trace VM execution of sugar parser"""

import sys

sys.path.insert(0, '.')
import struct

from ops.file_ops import _load_sugar_from_bin

mod = _load_sugar_from_bin('stdlib/sugar.bin')
vm = mod.vars['__sugar_vm__']
addr = vm.exports.get('解析')

code = vm.code
stack = vm.stack
vars_ = vm.vars
pc = addr
code_len = len(code)

print(f'Parsing with addr={addr}, code_len={code_len}')
print(f'Initial vars count: {len(vars_)}')

# Override _run_inner - we'll run manually
vm.pc = addr
vm.stack = []
vm.stack.append('1 + 2 * 3')

import io
import sys as sys_mod

old_stdout = sys_mod.stdout
sys_mod.stdout = io.StringIO()

step = 0
max_steps = 500
while pc < code_len and step < max_steps:
    step += 1
    op = code[pc]
    pc += 1

    if step <= 200 or op == 0x0D or op == 0x4C or op == 0xFF:  # Trace first 200 + RET/CALL_CLOSURE/HALT
        print(f'  [{step}] PC={pc - 1}, op=0x{op:02X}, stack_depth={len(stack)}', file=sys_mod.stderr)

    if op == 0x01:  # PUSH_I
        val = struct.unpack_from('<i', code, pc)[0]
        pc += 4
        stack.append(val)
    elif op == 0x07:  # LOAD
        idx = code[pc]
        pc += 1
        val = vars_[idx] if idx < len(vars_) else 0
        stack.append(val)
        if step <= 200:
            print(f'    LOAD var[{idx}] = {repr(str(val)[:40])}', file=sys_mod.stderr)
    elif op == 0x08:  # STORE
        idx = code[pc]
        pc += 1
        val = stack.pop() if stack else 0
        if idx < len(vars_):
            vars_[idx] = val
        if step <= 200:
            print(f'    STORE var[{idx}] = {repr(str(val)[:40])}', file=sys_mod.stderr)
    elif op == 0xFF:  # HALT
        print(f'HALT at step {step}', file=sys_mod.stderr)
        break
    elif op == 0x0D:  # RET
        if vm.call_stack:
            frame = vm.call_stack.pop()
            ret_pc, saved_vars, stack_base = frame[0], frame[1], frame[2]
            closure = frame[3] if len(frame) > 3 else None
            if closure and isinstance(closure, list) and len(closure) >= 3:
                for i in range(1, len(closure), 2):
                    idx2 = closure[i]
                    if idx2 < len(vars_):
                        closure[i + 1] = vars_[idx2]
            ret_val = stack.pop() if len(stack) > stack_base else None
            del stack[stack_base:]
            if ret_val is not None:
                stack.append(ret_val)
            pc = ret_pc
            vars_ = saved_vars
            print(f'  RET: depth={len(vm.call_stack)}, ret_val={repr(str(ret_val)[:60])}', file=sys_mod.stderr)
        else:
            print('  RET (empty call_stack) - exiting', file=sys_mod.stderr)
            break
    elif op == 0x4C:  # CALL_CLOSURE
        closure = stack.pop() if stack else []
        print(f'  CALL_CLOSURE: stack_after_pop_len={len(stack)}', file=sys_mod.stderr)
        if isinstance(closure, list) and len(closure) >= 3 and len(closure) % 2 == 1:
            addr2 = closure[0]
            arg_count = 0
            p = addr2
            while p + 1 < len(code) and code[p] == 0x08:
                arg_count += 1
                p += 2
            vm.call_stack.append((pc, list(vars_), 0, closure))
            for i in range(1, len(closure), 2):
                idx2 = closure[i]
                if idx2 < len(vars_):
                    vars_[idx2] = closure[i + 1]
            pc = addr2
            print(
                f'    -> closure addr={addr2}, arg_count={arg_count}, depth={len(vm.call_stack)}', file=sys_mod.stderr
            )
        elif isinstance(closure, int) and closure != 0:
            addr2 = closure
            arg_count = 0
            p = addr2
            while p + 1 < len(code) and code[p] == 0x08:
                arg_count += 1
                p += 2
            vm.call_stack.append((pc, list(vars_), 0))
            pc = addr2
            print(f'    -> int addr={addr2}, arg_count={arg_count}', file=sys_mod.stderr)
        else:
            print(
                f'    WARN: not a valid closure: type={type(closure).__name__}, val={repr(str(closure)[:50])}',
                file=sys_mod.stderr,
            )
    elif op == 0x09:  # JMP
        off = struct.unpack_from('<h', code, pc)[0]
        pc += 2
        pc += off
    elif op == 0x0A:  # JZ
        off = struct.unpack_from('<h', code, pc)[0]
        pc += 2
        v = stack.pop() if stack else 0
        if not (isinstance(v, int) and v > 0):
            pc += off
    elif op == 0x0B:  # JNZ
        off = struct.unpack_from('<h', code, pc)[0]
        pc += 2
        v = stack.pop() if stack else 0
        if isinstance(v, int) and v > 0:
            pc += off
    elif op == 0x33:  # JMP32
        off = struct.unpack_from('<i', code, pc)[0]
        pc += 4
        pc += off
    elif op == 0x2D:  # PUSH_STR
        end = code.index(0, pc)
        s = code[pc:end].decode('utf-8', errors='replace')
        stack.append(s)
        pc = end + 1
        if step <= 200:
            print(f'    PUSH_STR {repr(s[:40])}', file=sys_mod.stderr)
    elif op == 0x2A:  # LIST_LEN
        c = stack.pop() if stack else 0
        stack.append(len(c) if isinstance(c, (list, str, dict)) else 0)
    elif op == 0x27:  # LIST_NEW
        stack.append([])
    elif op == 0x28:  # LIST_CONCAT
        b = stack.pop() if stack else []
        a = stack.pop() if stack else []
        stack.append(a + b)
    elif op == 0x11:  # EQ
        b = stack.pop() if stack else 0
        a = stack.pop() if stack else 0
        stack.append(1 if a == b else -1)
    elif op == 0x13:  # GT
        b = stack.pop() if stack else 0
        a = stack.pop() if stack else 0
        stack.append(1 if a > b else -1)
    elif op == 0x14:  # LT
        b = stack.pop() if stack else 0
        a = stack.pop() if stack else 0
        stack.append(1 if a < b else -1)
    elif op == 0x15:  # GTE
        b = stack.pop() if stack else 0
        a = stack.pop() if stack else 0
        stack.append(1 if a >= b else -1)
    elif op == 0x16:  # LTE
        b = stack.pop() if stack else 0
        a = stack.pop() if stack else 0
        stack.append(1 if a <= b else -1)
    elif op == 0x12:  # NE
        b = stack.pop() if stack else 0
        a = stack.pop() if stack else 0
        stack.append(1 if a != b else -1)
    elif op == 0x17:  # NOT
        a = stack.pop() if stack else 0
        stack.append(-1 if isinstance(a, int) and a > 0 else (0 if isinstance(a, int) and a == 0 else 1))
    elif op == 0x23:  # IS_LIST
        a = stack.pop() if stack else 0
        stack.append(1 if isinstance(a, (list, dict)) else -1)
    elif op == 0x22:  # IS_STR
        a = stack.pop() if stack else 0
        stack.append(1 if isinstance(a, str) else -1)
    elif op == 0x21:  # IS_NUM
        a = stack.pop() if stack else 0
        stack.append(1 if isinstance(a, (int, float)) else -1)
    elif op == 0x25:  # GET
        idx_g = stack.pop() if stack else 0
        container = stack.pop() if stack else ''
        if isinstance(container, (list, str)) and isinstance(idx_g, int) and 0 <= idx_g < len(container):
            stack.append(container[idx_g])
        elif isinstance(container, dict):
            stack.append(container.get(idx_g, 0))
        else:
            stack.append(0)
    elif op == 0x1C:  # STREQ
        b = stack.pop() if stack else ''
        a = stack.pop() if stack else ''
        stack.append(1 if a == b else -1)
    elif op == 0x1D:  # DICT
        n = stack.pop() if stack else 0
        if not isinstance(n, int):
            n = 0
        d = {}
        for _ in range(n):
            if len(stack) < 2:
                d = {}
                break
            val = stack.pop()
            key = stack.pop()
            d[key] = val
        stack.append(d)
    elif op == 0x1E:  # DICT_GET
        key = stack.pop() if stack else ''
        d = stack.pop() if stack else {}
        if isinstance(d, dict):
            stack.append(d.get(key, 0))
        else:
            stack.append(0)
    elif op == 0x1F:  # DICT_SET
        val = stack.pop() if stack else 0
        key = stack.pop() if stack else ''
        d = stack.pop() if stack else {}
        if isinstance(d, dict):
            d[key] = val
        stack.append(d)
    elif op == 0x20:  # DICT_HAS
        key = stack.pop() if stack else ''
        d = stack.pop() if stack else {}
        stack.append(1 if isinstance(d, dict) and key in d else -1)
    elif op == 0x29:  # SLICE
        a = stack.pop() if stack else 0
        b = stack.pop() if stack else 0
        if isinstance(b, (list, str, dict, tuple)):
            c = b
            start = a
            end = len(c)
        elif stack and isinstance(stack[-1], (list, str, dict, tuple)):
            end = a
            start = b
            c = stack.pop()
        else:
            c = b
            start = a
            end = len(c)
        if isinstance(c, (list, str)):
            stack.append(c[start:end])
        else:
            stack.append([])
    elif op == 0x32:  # DICT_KEYS
        d = stack.pop() if stack else {}
        if isinstance(d, dict):
            stack.append(list(d.keys()))
        elif isinstance(d, str):
            stack.append(list(d))
        else:
            stack.append([])
    elif op == 0x02:  # ADD
        b = stack.pop() if stack else 0
        a = stack.pop() if stack else 0
        stack.append(a + b)
    elif op == 0x03:  # SUB
        b = stack.pop() if stack else 0
        a = stack.pop() if stack else 0
        stack.append(a - b)
    elif op == 0x04:  # MUL
        b = stack.pop() if stack else 0
        a = stack.pop() if stack else 0
        stack.append(a * b)
    elif op == 0x05:  # DIV
        b = stack.pop() if stack else 1
        a = stack.pop() if stack else 0
        stack.append(a // b if b != 0 else 0)
    elif op == 0x0C:  # CALL
        call_addr = struct.unpack_from('<h', code, pc)[0]
        pc += 2
        if call_addr != 0:
            arg_count = 0
            p = call_addr
            while p + 1 < len(code) and code[p] == 0x08:
                arg_count += 1
                p += 2
            vm.call_stack.append((pc, list(vars_), 0))
            pc = call_addr
        print(f'  CALL -> addr={call_addr}, depth={len(vm.call_stack)}', file=sys_mod.stderr)
    elif op == 0x06:  # MOD
        b = stack.pop() if stack else 1
        a = stack.pop() if stack else 0
        stack.append(a % b if b != 0 else 0)
    elif op == 0x19:  # CONCAT
        b = stack.pop() if stack else ''
        a = stack.pop() if stack else ''
        stack.append(a + b)
    elif op == 0x34:  # OR
        b = stack.pop() if stack else 0
        a = stack.pop() if stack else 0
        stack.append(1 if a > 0 or b > 0 else (-1 if a == -1 or b == -1 else 0))
    elif op == 0x35:  # AND
        b = stack.pop() if stack else 0
        a = stack.pop() if stack else 0
        stack.append(1 if a > 0 and b > 0 else (-1 if a == -1 or b == -1 else -1 if a < 1 or b < 1 else 0))
    elif op == 0x31:  # ORD
        s = stack.pop() if stack else ''
        stack.append(ord(s[0]) if isinstance(s, str) and len(s) > 0 else 0)
    else:
        if step <= 200:
            print(f'  UNHANDLED op=0x{op:02X}', file=sys_mod.stderr)

stdout_output = sys_mod.stdout.getvalue()
sys_mod.stdout = old_stdout

result = stack[-1] if stack else None
print(f'\nSteps executed: {step}')
print(f'Final stack: {[repr(str(x)[:40]) for x in stack]}')
print(f'Result: {repr(str(result)[:100])}')

if stdout_output.strip():
    print(f'VM stdout: {stdout_output[:500]}')
