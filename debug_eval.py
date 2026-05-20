"""调试辅助模块：从 evaluator.py 提取的调试相关方法"""

from __future__ import annotations
import sys
from typing import Any


def debug_before(evaluator, internal: str, op: str, args: list) -> None:
    """操作执行前的调试检查"""
    if not evaluator.debug_mode:
        return
    if not evaluator._break_all and op not in evaluator._break_ops and internal not in evaluator._break_ops:
        return
    debug_prompt(evaluator, internal or op, args)


def debug_after(evaluator, internal: str, op: str, args: list) -> None:
    """操作执行后的监视变量检查"""
    if not evaluator._watched_vars:
        return
    name = internal or op
    if name not in evaluator._watched_vars:
        return
    for v in evaluator._watched_vars:
        if evaluator.has_var(v):
            print(f'  [监视] {v} = {evaluator.get_var(v)}')


def debug_prompt(evaluator, cur_op: str, args: list) -> None:
    """调试断点交互提示"""
    from ops.io_ops import IOOps

    fargs = ', '.join(IOOps.format_value(a) if not isinstance(a, str) else a for a in args)
    print(f'\n⏸ [断点] {cur_op}({fargs})')
    while True:
        try:
            cmd = input('调试> ').strip()
        except (KeyboardInterrupt, EOFError):
            print()
            evaluator.debug_mode = False
            return
        if cmd in ('', 'n', 'next'):
            return
        if cmd in ('c', 'continue'):
            evaluator.debug_mode = False
            return
        if cmd.startswith('p ') or cmd.startswith('print '):
            var = cmd.split(maxsplit=1)[1].strip()
            if evaluator.has_var(var):
                val = evaluator.get_var(var)
                print(f'  {var} = {IOOps.format_value(val) if not isinstance(val, str) else val}')
            else:
                print(f'  {var}: 未定义')
        elif cmd == 'bt':
            print('\n  === 调用栈 ===')
            for oname, oargs in evaluator.call_stack:
                fa = ', '.join(str(a) for a in oargs)
                print(f'    at {oname}({fa})')
            print('  =============')
        elif cmd == 'q':
            sys.exit(0)
        else:
            print('  命令: [Enter]/n=下一步  c=继续  p 变量  bt=调用栈  q=退出')
