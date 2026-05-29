#!/usr/bin/env bash
# 无 Python 依赖的编译管线
# 用法: bash scripts/compile_native.sh <input.san> [-o output.exe]
#
# 管线:
#   1. C VM 运行 sugar.bin → 解析源码 → AST (临时文件)
#   2. C VM 运行 llvmgen.bin → 编译 AST → LLVM IR (临时文件)
#   3. llc → 目标文件
#   4. gcc → 可执行文件
#
# 依赖: csrc/runtime.exe, llvmgen/sugar.bin, llvmgen/llvmgen.bin, llc, gcc
set -e

INPUT="${1:?用法: $0 <input.san> [-o output.exe]}"
OUTPUT="output.exe"
if [ "$2" = "-o" ] && [ -n "$3" ]; then
    OUTPUT="$3"
fi

VM="csrc/runtime.exe"
SUGAR_BIN="stdlib/sugar.bin"
LLVMGEN_BIN="stdlib/llvmgen.bin"
TMPDIR="/tmp/sanyan_build_$$"
mkdir -p "$TMPDIR"

echo "=== 无 Python 编译管线 ==="

# 检查依赖
for f in "$VM" "$SUGAR_BIN" "$LLVMGEN_BIN"; do
    if [ ! -f "$f" ]; then echo "错误: 缺少 $f"; exit 1; fi
done

# 添加 MSYS2 路径
export PATH="/d/msys64/ucrt64/bin:/d/msys64/mingw64/bin:$PATH"

if ! command -v llc &>/dev/null && ! command -v clang &>/dev/null; then
    echo "错误: 需要 llc 或 clang"; exit 1
fi
if ! command -v gcc &>/dev/null; then
    echo "错误: 需要 gcc"; exit 1
fi

# 步骤 1: 解析源码 → AST
echo "[1/4] 解析源码..."
"$VM" "$SUGAR_BIN" "$INPUT" > "$TMPDIR/ast.txt" 2>/dev/null || true

if [ ! -s "$TMPDIR/ast.txt" ]; then
    echo "警告: AST 为空，尝试直接编译"
fi

# 步骤 2: AST → LLVM IR
echo "[2/4] 编译 LLVM IR..."
"$VM" "$LLVMGEN_BIN" "$TMPDIR/ast.txt" > "$TMPDIR/output.ll" 2>/dev/null || true

if [ ! -s "$TMPDIR/output.ll" ]; then
    echo "错误: IR 生成失败"
    exit 1
fi

echo "  IR 大小: $(wc -c < "$TMPDIR/output.ll") 字节"

# 步骤 3: IR → 目标文件
echo "[3/4] 编译目标文件..."
if command -v llc &>/dev/null; then
    llc -filetype=obj "$TMPDIR/output.ll" -o "$TMPDIR/output.o" 2>/dev/null
elif command -v clang &>/dev/null; then
    clang -c "$TMPDIR/output.ll" -o "$TMPDIR/output.o" 2>/dev/null
fi

if [ ! -f "$TMPDIR/output.o" ]; then
    echo "错误: 目标文件生成失败"
    exit 1
fi

# 步骤 4: 链接
echo "[4/4] 链接..."
gcc "$TMPDIR/output.o" llvmgen/runtime.c -o "$OUTPUT" -lm 2>/dev/null

rm -rf "$TMPDIR"
echo "✓ 编译完成: $OUTPUT"
