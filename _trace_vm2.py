"""Minimal trace - just check stack contents before/after CALL_CLOSURE"""

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

# Set up: push arg
vm.stack = []
stack = vm.stack
stack.append('1 + 2 * 3')

pc = addr
code_len = len(code)

step = 0
while pc < code_len and step < 30:
    step += 1
    op = code[pc]
    pc += 1

    print(f'[{step}] PC={pc - 1}: op=0x{op:02X}, stack={[repr(str(x)[:30]) for x in stack]}')

    if op == 0x01:  # PUSH_I
        val = struct.unpack_from('<i', code, pc)[0]
        pc += 4
        stack.append(val)
    elif op == 0x07:  # LOAD
        idx = code[pc]
        pc += 1
        stack.append(vars_[idx] if idx < len(vars_) else 0)
    elif op == 0x08:  # STORE
        idx = code[pc]
        pc += 1
        val = stack.pop() if stack else 0
        if idx < len(vars_):
            vars_[idx] = val
        print(f'  STORE[{idx}] = {repr(str(val)[:40])}')
    elif op == 0xFF:  # HALT
        print('HALT')
        break
    elif op == 0x0D:  # RET
        if vm.call_stack:
            frame = vm.call_stack.pop()
            ret_pc, saved_vars, stack_base = frame[0], frame[1], frame[2]
            closure = frame[3] if len(frame) > 3 else None
            if closure and isinstance(closure, list) and len(closure) >= 3:
                for i in range(1, len(closure), 2):
                    i2 = closure[i]
                    if i2 < len(vars_):
                        closure[i + 1] = vars_[i2]
            ret_val = stack.pop() if len(stack) > stack_base else None
            del stack[stack_base:]
            if ret_val is not None:
                stack.append(ret_val)
            pc = ret_pc
            vars_ = saved_vars
            print(f'  RET: val={repr(str(ret_val)[:40])}')
        else:
            print('  RET empty, BREAK')
            break
    elif op == 0x4C:  # CALL_CLOSURE
        print(f'  BEFORE pop: stack depth={len(stack)}')
        closure = stack.pop() if stack else []
        print(f'  AFTER pop: stack depth={len(stack)}, closure type={type(closure).__name__}')
        print(f'  closure is list: {isinstance(closure, list)}')
        if isinstance(closure, list):
            print(f'  closure len={len(closure)}, first={repr(str(closure[0])[:30])}')
        if isinstance(closure, list) and len(closure) >= 3 and len(closure) % 2 == 1:
            addr2 = closure[0]
            vm.call_stack.append((pc, list(vars_), 0, closure))
            for i in range(1, len(closure), 2):
                i2 = closure[i]
                if i2 < len(vars_):
                    vars_[i2] = closure[i + 1]
            pc = addr2
            print(f'  CALL to addr={addr2}, stack now={[repr(str(x)[:30]) for x in stack]}')
        else:
            print('  NOT a valid closure!')
    elif op == 0x0A:  # JZ
        off = struct.unpack_from('<h', code, pc)[0]
        pc += 2
        v = stack.pop() if stack else 0
        if not (isinstance(v, int) and v > 0):
            pc += off
    elif op == 0x09:  # JMP
        off = struct.unpack_from('<h', code, pc)[0]
        pc += 2
        pc += off
    elif op == 0x33:  # JMP32
        off = struct.unpack_from('<i', code, pc)[0]
        pc += 4
        pc += off
    elif op == 0x27:  # LIST_NEW
        stack.append([])
    elif op == 0x1A:  # STRLEN
        c = stack.pop() if stack else 0
        stack.append(len(c) if isinstance(c, (list, str, dict)) else 0)
    elif op == 0x32:  # DICT_KEYS
        d = stack.pop() if stack else {}
        if isinstance(d, dict):
            stack.append(list(d.keys()))
        elif isinstance(d, str):
            stack.append(list(d))
        else:
            stack.append([])
    elif op == 0x2A:  # LIST_LEN
        c = stack.pop() if stack else 0
        stack.append(len(c) if isinstance(c, (list, str, dict)) else 0)
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
    elif op == 0x2D:  # PUSH_STR
        end = code.index(0, pc)
        s = code[pc:end].decode('utf-8', errors='replace')
        stack.append(s)
        pc = end + 1
    elif op == 0x28:  # LIST_CONCAT
        b = stack.pop() if stack else []
        a = stack.pop() if stack else []
        stack.append(a + b)
    elif op == 0x25:  # GET
        idx_g = stack.pop() if stack else 0
        container = stack.pop() if stack else ''
        if isinstance(container, (list, str)) and isinstance(idx_g, int) and 0 <= idx_g < len(container):
            stack.append(container[idx_g])
        elif isinstance(container, dict):
            stack.append(container.get(idx_g, 0))
        else:
            stack.append(0)
    else:
        pass

if stack:
    print(f'\nFinal stack: {[repr(str(x)[:40]) for x in stack]}')
    print(f'Result: {repr(str(stack[-1])[:100])}')
