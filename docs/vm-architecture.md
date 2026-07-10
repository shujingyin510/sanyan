# VM 多后端架构

> 三言的虚拟机架构——同一套 ISA v2（65 opcode）在五个后端的实现对比。

## 后端总览

| 后端 | 文件 | 行数 | opcode | 用途 |
|------|------|------|--------|------|
| Python | `vm/__init__.py` | 1041 | 65 | 开发、测试 |
| C | `csrc/runtime.c` | 1695 | 65 | 生产部署 |
| LLVM | `llvmgen/` | ~3500 | 65 | JIT 高性能 |
| C 种子 | `csrc/sanyan_vm_seed.c` | 318 | 65 | 自举 Level 3 |
| NASM | `csrc/sanyan_vm_l4.asm` | 617 | 65 | 零依赖裸机 |
| STM32 | `examples/stm32-blinky/` | 205 | 65 | 嵌入式 |

## Python VM

**文件**：`vm/__init__.py` (1041行)

主开发和测试目标。完整实现所有 65 opcode + 闭包支持。

**核心机制**：
- **栈隔离**：CALL 记录 `stack_base`，RET 执行 `del stack[base:]`，消除栈泄漏
- **STORE 扫描**：调用时自动推算函数参数个数
- **三态逻辑**：比较返回 1/-1（非 1/0），JZ/JNZ 用 `>0` 判断
- **闭包**：`CLOSURE (0x4B)` / `CALL_CLOSURE (0x4C)` 操作码

```bash
python -X utf8 repl/main.py --vm program.san
```

## C VM

**文件**：`csrc/runtime.c` (1695行)

生产级实现，使用**标记指针**值系统：

```c
// LSB=0 → 堆对象  /  LSB=1 → 内联整数 63-bit
#define MAKE_INT(n) ((void*)(((intptr_t)(n) << 1) | 1))
```

- FNV-1a 哈希字典 + 开放寻址
- UTF-8 字符串支持（按字符边界切片，非按字节）
- IEEE 754 double 浮点支持

```bash
gcc -o sanyan_vm csrc/runtime.c
./sanyan_vm program.bin
```

## LLVM 后端

**文件**：`llvmgen/` (3500+ 行)

将三言源码编译为 LLVM IR，经优化 passes 生成机器码。

**优化 passes**：mem2reg + instcombine + reassociate + GVN + simplifycfg

**Arena 分配器**：64KB 预分配，auto-grow ×2，程序结束一次性释放。

**标记指针**（i64）：
- LSB=1 → 63-bit 整数 (±4.6×10^18)
- LSB=0 → 堆对象指针

## C 种子 VM (Level 3)

**文件**：`csrc/sanyan_vm_seed.c` (318行)

自举链的最小 C 实现。仅 318 行，~2KB 可审计二进制。TCC 编译。

## NASM VM (Level 4)

**文件**：`csrc/sanyan_vm_l4.asm` (617行)

零依赖——不依赖 C 编译器。NASM 汇编 → 原生 x86-64。30+ 安全加固。

## STM32 嵌入式

**文件**：`examples/stm32-blinky/` (205行)

Blue Pill (STM32F103C8T6) 固件。三言源码 → 编译器 → .bin → 固件烧录。PC13 LED 200ms 闪烁验证。

## 差分验证

四后端一致性通过差分模糊测试保证：

```bash
python -X utf8 tests/test_diff_fuzz.py
```

## 相关文件

| 文件 | 后端 |
|------|------|
| `vm/__init__.py` | Python VM |
| `csrc/runtime.c` | C VM |
| `llvmgen/` | LLVM 后端 |
| `csrc/sanyan_vm_seed.c` | C 种子 (L3) |
| `csrc/sanyan_vm_l4.asm` | NASM (L4) |
| `examples/stm32-blinky/` | STM32 嵌入式 |
| `tests/test_diff_fuzz.py` | 四后端差分测试 |
