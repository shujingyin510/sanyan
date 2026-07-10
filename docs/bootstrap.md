# 自举链（Bootstrap）

> 三言编译器可以编译自身——这是语言自举能力的核心证明。5 层自举链从 Python 宿主编译器一直延伸到零依赖的 x86-64 汇编虚拟机。

## 自举链总览

```
Level 0: Python Evaluator  →  宿主编译器（649行）
     ↓ 编译
Level 1: bytecode_compiler.san  →  编译器用三言写成（79行）
     ↓ 输出 A.bin
Level 2: 不动点验证  →  VM 加载 A → 编译 B → VM 加载 B → 编译 C → 验证 B == C
     ↓ 验证
Level 3: C 种子 VM  →  318 行纯 C，TCC 编译 ~2KB 可审计二进制
     ↓ 消除 C 编译器依赖
Level 4: x86-64 NASM VM  →  617 行汇编，零依赖
```

## Level 0 — Python 宿主编译器

**文件**：`core/evaluator.py` (649行)

Python 实现的求值器，是三言自举的起点。它直接解释执行三言源码，是唯一无法消除的"鸡"——所有自举链的起点。

```bash
python -X utf8 repl/main.py --eval program.san
```

## Level 1 — 自写编译器

**文件**：`stdlib/bytecode_compiler.san` (79行)

编译器**用三言自身写成**。这是自举的第一步——编译器用目标语言实现。

```sanyan
定义 编译字节码 (source)
    └── 双遍编译
        pass 1: 函数定义 → HALT
        pass 2: 主代码 → HALT
```

**输出**：`bytecode_compiler.bin` (7894 bytes)

## Level 2 — 不动点验证

```
Python 编译 bytecode_compiler.san → A.bin
VM 加载 A.bin → A 编译 bytecode_compiler.san → B.bin
VM 加载 B.bin → B 编译 bytecode_compiler.san → C.bin
验证 B.bin == C.bin 逐字节一致
```

**含义**：编译器输出是**确定性的**——相同源码永远产生相同二进制。这是对编译器正确性的形式化验证。如果插入后门，编译器的二进制产物必然改变，不动点会断裂。

**当前状态**：B == C，7894 bytes（v3.50 确认）

**验证命令**：
```bash
python -X utf8 tests/test_self_host.py -v
```

## Level 3 — C 种子 VM

**文件**：`csrc/sanyan_vm_seed.c` (318行)

仅 318 行纯 C，可通过 TCC 编译为 ~2KB 可审计二进制。

```bash
tcc -nostdlib csrc/sanyan_vm_seed.c -o sanyan_vm
```

- 支持 **65 个 opcode**（全量 ISA v2，v3.56.2）
- 零额外依赖（仅 libc）
- 可人工审计——2KB 二进制无法隐藏后门

**限制**：仅 Linux（TCC `-nostdlib` 不跨平台）。

## Level 4 — x86-64 NASM 汇编 VM

**文件**：`csrc/sanyan_vm_l4.asm` (617行)

零依赖——无需 C 编译器，纯 NASM 汇编 → 原生 x86-64 二进制。

```bash
nasm -f bin -o sanyan_vm csrc/sanyan_vm_l4.asm
./sanyan_vm program.bin
```

- 65 个 opcode（v3.56.2）
- 30+ 项安全加固
- 消除整个 C 编译器信任链

## 自举的意义

| 层级 | 消除的依赖 | 可审计性 |
|------|-----------|---------|
| L1 | 编译器逻辑不再依赖 Python | 79 行三言源码 |
| L2 | 证明编译器输出稳定 | B == C 逐字节 |
| L3 | C 编译器被简化为 TCC | 318 行 / ~2KB |
| L4 | C 编译器完全消除 | 617 行汇编 |

传统的 Ken Thompson "Trusting Trust" 攻击需要同时操纵 5 层二进制产出——每一层都在缩小攻击面。

## 相关文件

| 文件 | 说明 |
|------|------|
| `stdlib/bytecode_compiler.san` | 编译器源码（三言自写） |
| `stdlib/bytecode_compiler.bin` | 编译产物 |
| `csrc/sanyan_vm_seed.c` | Level 3 C 种子 VM |
| `csrc/sanyan_vm_l4.asm` | Level 4 x86-64 NASM VM |
| `tests/test_self_host.py` | 自举验证测试 |
| `llvmgen/` | LLVM 后端（编译器的第二后端） |
