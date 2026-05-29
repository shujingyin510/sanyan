#!/usr/bin/env bash
# 无 Python 依赖的编译管线（使用 C VM --compile 模式）
# 用法: bash scripts/compile_native.sh <input.san> [-o output.exe]
#
# 管线:
#   1. C VM 加载 sugar.bin → 解析源码 → AST
#   2. C VM 加载 llvmgen.bin → 编译 AST → LLVM IR
#   3. llc/clang → 目标文件
#   4. gcc → 可执行文件
#
# 依赖: csrc/runtime.exe, stdlib/sugar.bin, stdlib/llvmgen.bin, llc/clang, gcc
set -e

INPUT="${1:?用法: $0 <input.san> [-o output.exe]}"
OUTPUT="output.exe"
if [ "$2" = "-o" ] && [ -n "$3" ]; then
    OUTPUT="$3"
fi

VM="csrc/runtime.exe"

echo "=== 无 Python 编译管线 ==="

# 检查依赖
if [ ! -f "$VM" ]; then
    echo "错误: 缺少 $VM（先编译 C VM: gcc -o csrc/runtime.exe csrc/runtime.c -std=c99）"
    exit 1
fi

# 添加 MSYS2 路径
export PATH="/d/msys64/ucrt64/bin:/d/msys64/mingw64/bin:$PATH"

# 使用 C VM 的 --compile 模式（完整管线）
"$VM" --compile "$INPUT" -o "$OUTPUT"

echo "✓ 编译完成: $OUTPUT"
