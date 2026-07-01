# ruff: noqa: E402
"""Test: update dispatch list to use new DICT_KEYS handler"""

import sys

sys.path.insert(0, '.')
import vm as vm_module

# Get the actual DICT_KEYS handler source
# The issue: _DISPATCH_LIST stores the old reference
# We need to make sure our changes are in the live dispatch list

print(f'Dispatch[50] = {vm_module._DISPATCH_LIST[50]}')
print(f'VM._exec_dict = {vm_module.VM._exec_dict}')
print(f'Same? {vm_module._DISPATCH_LIST[50] == vm_module.VM._exec_dict}')

# If they differ, the dispatch table has stale references
if vm_module._DISPATCH_LIST[50] != vm_module.VM._exec_dict:
    print('DISPATCH TABLE IS STALE! Updating...')
    vm_module._DISPATCH_LIST[50] = vm_module.VM._exec_dict
    # Also update RET (0x0D) and CALL_CLOSURE (0x4C)
    from vm import RET, CALL_CLOSURE, MAKE_CLOSURE

    vm_module._DISPATCH_LIST[RET] = vm_module.VM._exec_control_flow
    vm_module._DISPATCH_LIST[CALL_CLOSURE] = vm_module.VM._exec_control_flow
    vm_module._DISPATCH_LIST[MAKE_CLOSURE] = vm_module.VM._exec_control_flow
else:
    print('Dispatch table is up-to-date')

import importlib
import ops.file_ops

importlib.reload(ops.file_ops)
from ops.file_ops import _load_sugar_from_bin

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
print(f'Result type: {type(result).__name__}')
print(f'Result: {repr(str(result)[:200])}')
if isinstance(result, list) and len(result) > 0:
    print(f'First few: {[str(x)[:30] for x in result[:3]]}')
