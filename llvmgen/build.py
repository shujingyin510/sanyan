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


def _find_cc() -> str:
    """查找可用的 C 编译器。"""
    candidates = ['gcc', 'clang', 'cc']
    for cc in candidates:
        try:
            subprocess.run([cc, '--version'], capture_output=True, timeout=5, check=False)
            return cc
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    # Windows/MSYS2
    msys2_paths = [
        r'C:\msys64\mingw64\bin\gcc.exe',
        r'C:\msys64\ucrt64\bin\gcc.exe',
        r'C:\msys32\mingw32\bin\gcc.exe',
    ]
    for p in msys2_paths:
        if os.path.exists(p):
            return p
    raise RuntimeError('未找到 C 编译器 (gcc/clang/cc/MSYS2 mingw)。请安装后再试。')


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

    # 用 clang/gcc 编译 IR (需要 LLVM 工具链)
    # 如果没有 clang，尝试用 llc 编译 IR → .s → as
    try:
        subprocess.run([cc, '-c', ir_path, '-o', obj_path], check=True)
    except subprocess.CalledProcessError:
        # 回退: 尝试 llc
        try:
            subprocess.run(['llc', '-filetype=obj', ir_path, '-o', obj_path], check=True)
        except FileNotFoundError:
            raise RuntimeError(f'无法编译 LLVM IR。请安装 clang (推荐) 或 llc。\nIR 文件已保存至: {ir_path}') from None

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
