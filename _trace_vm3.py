# ruff: noqa: E402
"""Trace _run_inner"""

import sys

sys.path.insert(0, '.')
import vm as vm_module

_orig_run_inner = vm_module.VM._run_inner


def traced_run_inner(self):
    with open('vm_trace_inner.log', 'a', encoding='utf-8') as f:
        f.write(f'_run_inner START, pc={self.pc}, stack={repr([str(x)[:30] for x in self.stack])}\n')
    _orig_run_inner(self)
    with open('vm_trace_inner.log', 'a', encoding='utf-8') as f:
        f.write(
            f'_run_inner END, pc={self.pc}, stack={repr([str(x)[:30] for x in self.stack])}, call_stack={len(self.call_stack)}\n'
        )


vm_module.VM._run_inner = traced_run_inner

import importlib
import ops.file_ops

importlib.reload(ops.file_ops)
from ops.file_ops import _load_sugar_from_bin

with open('vm_trace_inner.log', 'w', encoding='utf-8') as f:
    f.write('LOG START\n')

mod = _load_sugar_from_bin('stdlib/sugar.bin')
vm = mod.vars['__sugar_vm__']
addr = vm.exports.get('解析')

old_pc = vm.pc
old_vars = list(vm.vars)
vm.call_stack.clear()
vm.pc = addr
vm.vars = list(old_vars)
vm.stack = ['1 + 2 * 3']
vm._run_inner()

result = vm.stack[-1] if vm.stack else None
print(f'Result: {repr(str(result)[:100])}')

with open('vm_trace_inner.log', 'r', encoding='utf-8') as f:
    print(f'Log: {f.read()}')
