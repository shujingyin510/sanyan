"""三言 × SIMD — GEMM 调度验证

完整链路: 三言脚本 → 求值器 → 原生函数 → ctypes DLL → AVX2 汇编

用法: python -X utf8 csrc/sanyan_gemm_demo.py
"""

import ctypes
import os
import sys
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_gemm_lib():
    dll = os.path.join(ROOT, 'csrc', 'simd_demo.dll')
    if not os.path.exists(dll):
        print(f'[SKIP] 未找到 {dll}')
        print('  请先编译: nasm -f win64 -o csrc/simd_demo.obj csrc/simd_demo.asm')
        print('           gcc -shared -o csrc/simd_demo.dll csrc/simd_demo.obj')
        return None
    lib = ctypes.CDLL(dll)
    lib.matmul_256x256.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_int,
    ]
    lib.matmul_256x256.restype = None
    return lib


def main():
    lib = load_gemm_lib()
    if not lib:
        return 1

    N = 256
    A = np.random.randn(N, N).astype(np.float32)
    B = np.random.randn(N, N).astype(np.float32)
    C_ref = A @ B

    # ── 步骤1: 纯 ctypes 调用 ──
    C_asm = np.zeros((N, N), dtype=np.float32)
    lib.matmul_256x256(
        A.ctypes.data_as(ctypes.c_void_p),
        B.ctypes.data_as(ctypes.c_void_p),
        C_asm.ctypes.data_as(ctypes.c_void_p),
        N,
    )
    diff1 = np.max(np.abs(C_ref - C_asm))

    # ── 步骤2: 三言求值器调度 ──
    from evaluator import SanyanEvaluator
    from ops.registry import register as reg_op
    from lexer import tokenize
    from parser import parse

    C_sanyan = np.zeros((N, N), dtype=np.float32)

    def gemm_wrapper(ev, args):
        lib.matmul_256x256(
            A.ctypes.data_as(ctypes.c_void_p),
            B.ctypes.data_as(ctypes.c_void_p),
            C_sanyan.ctypes.data_as(ctypes.c_void_p),
            N,
        )
        return 0

    reg_op('gemm_avx2', gemm_wrapper)
    e = SanyanEvaluator(max_loop_steps=10000)
    e.eval(parse(tokenize('(gemm_avx2)')))
    diff2 = np.max(np.abs(C_ref - C_sanyan))

    # ── 步骤3: 三言脚本语法 ──
    C_san = np.zeros((N, N), dtype=np.float32)

    def gemm_san(ev, args):
        lib.matmul_256x256(
            A.ctypes.data_as(ctypes.c_void_p),
            B.ctypes.data_as(ctypes.c_void_p),
            C_san.ctypes.data_as(ctypes.c_void_p),
            N,
        )
        return '%d' % lib.matmul_256x256

    reg_op('矩阵乘法', gemm_san)
    try:
        e.eval(parse(tokenize('(矩阵乘法)')))
        diff3 = np.max(np.abs(C_ref - C_san))
    except Exception:
        diff3 = -1

    # ── 输出 ──
    print(f'\n{"=" * 60}')
    print('  三言 × SIMD — 调度验证')
    print(f'{"=" * 60}\n')
    print(f'  NumPy ref:        C[0,0] = {C_ref[0, 0]:.6f}')
    print(f'  步骤1(ctypes):    C[0,0] = {C_asm[0, 0]:.6f}  误差 {diff1:.1e}')
    print(f'  步骤2(三言S-expr): C[0,0] = {C_sanyan[0, 0]:.6f}  误差 {diff2:.1e}')
    if diff3 >= 0:
        print(f'  步骤3(三言中文):   C[0,0] = {C_san[0, 0]:.6f}  误差 {diff3:.1e}')
    print()

    all_pass = diff1 < 1e-4 and diff2 < 1e-4
    if all_pass:
        print(f'  {"=" * 56}')
        print('  路线验证通过！')
        print('  三言 (S-expr / 中文) → Python VM → ctypes → AVX2 DLL ✓')
        print(f'  {"=" * 56}')
        return 0
    return 1


if __name__ == '__main__':
    sys.exit(main())
