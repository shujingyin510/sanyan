"""三言 → 可执行文件 完整编译管线

用法:
    python -m llvmgen.build input.san [-o output] [--run]

流程:  .san → 糖解析 → AST → LLVM IR → .o → 链接 runtime → 可执行文件
"""

from __future__ import annotations

import os
import sys
import subprocess
import tempfile
from llvmgen.compiler import compile_source
from utils.compiler_tools import find_cc, find_llc, run_in_shell, win_to_posix


def _find_cc() -> str:
    """查找可用的 C 编译器。"""
    cc = find_cc()
    if cc:
        return cc
    raise RuntimeError('未找到 C 编译器 (gcc/clang/cc/MSYS2 mingw)。请安装后再试。')


def _find_llc() -> str | None:
    """查找 llc 工具。"""
    return find_llc()


def build(input_path: str, output_path: str | None = None, run: bool = False) -> str:
    """编译 .san 文件为可执行文件。"""
    name = os.path.splitext(os.path.basename(input_path))[0]
    if output_path is None:
        output_path = f'{name}.exe' if sys.platform == 'win32' else name

    rt_dir = os.path.dirname(os.path.abspath(__file__))
    rt_src = os.path.join(rt_dir, 'runtime.c')
    rt_obj = os.path.join(tempfile.gettempdir(), 'sanyan_rt.o')

    cc = _find_cc()

    # 1. 编译 runtime.o
    print(f'[1/3] 编译运行时 ({cc})...')
    subprocess.run([cc, '-c', rt_src, '-o', rt_obj, '-std=c99', '-O2'], check=True)

    # 2. .san → LLVM IR → .o
    print(f'[2/3] 编译 {input_path} → LLVM IR → .o ...')
    with open(input_path, 'r', encoding='utf-8') as f:
        source = f.read()
    ir_text, _cg = compile_source(source, name)

    ir_path = os.path.join(tempfile.gettempdir(), f'{name}.ll')
    obj_path = os.path.join(tempfile.gettempdir(), f'{name}.o')
    with open(ir_path, 'w', encoding='utf-8') as f:
        f.write(ir_text)

    # 用 llc/clang/gcc 编译 IR (优先 llc，无 Python 依赖)
    cc_ok = False
    llc = _find_llc()
    # 优先: llc（独立 LLVM 工具，无需 Python）
    if llc:
        try:
            subprocess.run([llc, '-filetype=obj', ir_path, '-o', obj_path], check=True, timeout=30)
            cc_ok = True
        except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            pass

    if not cc_ok:
        # 回退: clang 原生支持 .ll 文件
        try:
            subprocess.run(['clang', '-c', ir_path, '-o', obj_path], check=True)
            cc_ok = True
        except (FileNotFoundError, subprocess.CalledProcessError):
            pass

    if not cc_ok:
        # 最后回退: llvmlite（需要 Python）
        try:
            from llvmlite import binding

            binding.initialize_all_targets()
            binding.initialize_native_asmprinter()
            llvm_mod = binding.parse_assembly(ir_text)
            target = binding.Target.from_default_triple()
            tm = target.create_target_machine(reloc='static')
            obj_code = tm.emit_object(llvm_mod)
            with open(obj_path, 'wb') as f:
                f.write(obj_code)
            cc_ok = True
        except Exception:
            try:
                tm = target.create_target_machine(reloc='static', codemodel='large')
                asm = tm.emit_assembly(llvm_mod)
                asm_path = os.path.join(tempfile.gettempdir(), f'{name}.s')
                with open(asm_path, 'w') as f:
                    f.write(asm)
                subprocess.run([cc, '-c', asm_path, '-o', obj_path], check=True)
                cc_ok = True
            except Exception:
                pass

    if not cc_ok:
        raise RuntimeError(
            f'无法编译 LLVM IR。请安装 llc/clang 或运行 pip install llvmlite。\nIR 文件已保存至: {ir_path}'
        )

    # 3. 链接
    print(f'[3/3] 链接 → {output_path} ...')
    subprocess.run([cc, obj_path, rt_obj, '-o', output_path, '-lm'], check=True)

    # 清理
    os.unlink(ir_path)
    os.unlink(obj_path)

    print(f'✓ 编译完成: {output_path}')

    if run:
        print('--- 运行 ---')
        subprocess.run([output_path], check=False)

    return output_path


def main():
    if len(sys.argv) < 2:
        print('用法: python -m llvmgen.build input.san [-o output] [--run]')
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = None
    run = False

    i = 2
    while i < len(sys.argv):
        if sys.argv[i] == '-o' and i + 1 < len(sys.argv):
            output_path = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == '--run':
            run = True
            i += 1
        else:
            i += 1

    build(input_path, output_path, run)


if __name__ == '__main__':
    main()
