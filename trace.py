# ruff: noqa: E402
import sys
import os

sys.path.insert(0, '.')
os.environ['VM_MAX_STEPS'] = '500000'
import importlib
import vm
import ops.file_ops

importlib.reload(vm)
importlib.reload(ops.file_ops)

mod = ops.file_ops._load_sugar_from_bin('stdlib/sugar.bin')
v = mod.vars['__sugar_vm__']
v.pc = 0
v._run_inner()

# Direct trace: patch just the STR_FIND handler
import vm as vm_mod

orig_exec_string = vm_mod.VM._exec_string


def traced_exec_string(self, op):
    if op == vm_mod.STR_FIND:
        a = self.stack[-1] if self.stack else None
        b = self.stack[-2] if len(self.stack) > 1 else None
        result = orig_exec_string(self, op)
        # Check if this is the digit check
        if b == '0123456789':
            print(f'STR_FIND(b="{b}", a="{a}") = {self.stack[-1]}')
        return result
    return orig_exec_string(self, op)


vm_mod.VM._exec_string = traced_exec_string

# Also trace JZ in the 1500-2050 range
orig_control = vm_mod.VM._exec_control_flow


def traced_control(self, op):
    if op in (vm_mod.JZ, vm_mod.JNZ, vm_mod.JMP):
        old_pc = self.pc
        result = orig_control(self, op)
        if 1530 <= old_pc <= 2050:
            name = {vm_mod.JZ: 'JZ', vm_mod.JNZ: 'JNZ', vm_mod.JMP: 'JMP'}.get(op, '???')
            print(f'  FLOW {name} at {old_pc}')
        return result
    return orig_control(self, op)


vm_mod.VM._exec_control_flow = traced_control

# Also trace CALL_CLOSURE
orig_stack = vm_mod.VM._exec_stack_ops


def traced_stack(self, op):
    if op == vm_mod.PUSH_STR and 1530 <= self.pc <= 2050:
        length = self.code[self.pc]
        chars = []
        pc_tmp = self.pc + 1
        for _ in range(length):
            lo = self.code[pc_tmp]
            hi = self.code[pc_tmp + 1]
            pc_tmp += 2
            chars.append(chr(lo | (hi << 8)))
        s = ''.join(chars)
        if s:
            print(f'  PUSH_STR at {self.pc}: {repr(s)}')
    return orig_stack(self, op)


vm_mod.VM._exec_stack_ops = traced_stack

print('=== CALL 词法分析 ===')
v.stack = []
v.call_stack.clear()
v._exec_frame(v.code, v.exports.get('词法分析'), ['1 + 2 * 3'])
print(f'\nFinal result: {repr(str(v.stack)[:200])}')
