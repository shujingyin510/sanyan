"""sanyanc — 三言编译器驱动程序

用法:
    python sanyanc.py input.san -o output.bin
    python sanyanc.py input.san               # → input.bin
    python sanyanc.py -x "输出(加(1,2))"      # 直接执行

原理:
    sugar.bin (解析器) + bytecode_compiler.bin (编译器) → .bin → VM 执行

    agent 可以直接修改本文件——只有 50 行的胶水代码
"""

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
STDLIB = ROOT / 'stdlib'
SUGAR_BIN = STDLIB / 'sugar.bin'
COMPILER_BIN = STDLIB / 'bytecode_compiler.bin'


def _vm_to_python(val):
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return val
    if hasattr(val, 'to_int'):
        return val.to_int() if not val.is_string() else val.to_payload()
    if isinstance(val, str):
        return val
    if isinstance(val, list):
        return [_vm_to_python(v) for v in val]
    if isinstance(val, dict):
        return {_vm_to_python(k): _vm_to_python(v) for k, v in val.items()}
    return str(val)


def _call_vm_export(bin_path, export_name, *args):
    from vm import VM

    vm = VM.from_bin(str(bin_path))
    addr = vm.exports.get(export_name)
    if addr is None:
        raise RuntimeError(f'{bin_path} no export {export_name}')
    for a in args:
        vm.stack.append(a)
    vm.code.append(0xFF)
    halt_addr = len(vm.code) - 1
    vm.code_len = len(vm.code)
    caller_base = max(0, len(vm.stack) - len(args))
    vm.call_stack.append((halt_addr, list(vm.vars), caller_base))
    vm.pc = addr
    vm.halted = False
    vm._run_inner()
    return _vm_to_python(vm.stack[-1]) if vm.stack else None


def parse_sugar(source):
    """解析 sugar 语法源码为 AST（Python sugar parser）"""
    from sugar.parser import parse_code

    ast, errors = parse_code(source)
    if not ast:
        raise SyntaxError(f'sugar 解析失败: {errors[:3]}')
    return ast


def compile_san(source: str, output_path: str, use_sugar: bool = True) -> bytes:
    """编译 Sanyan 源码为 .bin 字节码。

    管道: sugar.san 解析 → bytecode_compiler.san 编译 → .bin
    两个模块都是独立 .bin 文件，通过 VM 加载并调用导出函数。
    """
    from vm import VM

    # 1. 用 S-表达式解析器 (Python 内建，无需 sugar.bin)
    if not use_sugar or source.strip().startswith('('):
        from lexer import tokenize
        from parser import parse

        ast = parse(tokenize(source))
        if ast is None:
            raise SyntaxError('S-表达式解析失败')
        if isinstance(ast, list) and ast[0] == '做':
            ast = ['do'] + ast[1:]
        elif isinstance(ast, list):
            ast = ['do', ast]
        else:
            ast = ['do', ast]
    else:
        # sugar 语法：加载 sugar.bin 解析
        ast = parse_sugar(source)
        if isinstance(ast, list) and len(ast) > 0 and ast[0] == 'do':
            pass
        elif isinstance(ast, list):
            ast = ['do', ast]
        else:
            ast = ['do', ast]

    if not COMPILER_BIN.exists():
        raise FileNotFoundError(f'编译器不存在: {COMPILER_BIN}')

    vm = VM.from_bin(str(COMPILER_BIN))
    addr = vm.exports.get('编译字节码')
    if addr is None:
        raise RuntimeError('编译器没有 编译字节码 导出')

    # 推参数：编译字节码(ast, output_path, vars_dict)
    vm.stack.append(ast)
    vm.stack.append(output_path)
    vm.stack.append({})

    # 在字节码末尾加 HALT 返回点
    vm.code.append(0xFF)
    halt_addr = len(vm.code) - 1
    vm.code_len = len(vm.code)

    # 构造调用帧
    arg_count = 3
    caller_base = max(0, len(vm.stack) - arg_count)
    vm.call_stack.append((halt_addr, list(vm.vars), caller_base))

    vm.pc = addr
    vm.halted = False
    vm._run_inner()

    if not os.path.exists(output_path):
        raise RuntimeError(f'编译未产出 {output_path}')
    with open(output_path, 'rb') as f:
        return f.read()


def run_bin(bin_path: str):
    """执行 .bin 文件"""
    from vm import VM

    vm = VM.from_bin(bin_path)
    vm.run()


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    # -x 直接执行
    if sys.argv[1] == '-x':
        source = sys.argv[2]
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, 'out.bin')
            compile_san(source, out)
            run_bin(out)
        return

    # 编译文件
    input_path = sys.argv[1]
    output_path = None
    for i, arg in enumerate(sys.argv):
        if arg == '-o' and i + 1 < len(sys.argv):
            output_path = sys.argv[i + 1]

    if output_path is None:
        output_path = os.path.splitext(input_path)[0] + '.bin'

    if not os.path.exists(input_path):
        # 可能是内联表达式
        compile_san(input_path, output_path)
    else:
        with open(input_path, 'r', encoding='utf-8') as f:
            source = f.read()
        compile_san(source, output_path)

    print(f'[OK] {input_path} → {output_path}: {os.path.getsize(output_path)} 字节')

    # --run 标志
    if '--run' in sys.argv:
        run_bin(output_path)


if __name__ == '__main__':
    main()
