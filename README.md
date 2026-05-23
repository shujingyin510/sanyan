# Sanyan v3.14.0

[![VS Code Marketplace](https://img.shields.io/badge/VS%20Code-Marketplace-%23007ACC?logo=visualstudiocode)](https://marketplace.visualstudio.com/items?itemName=sanyan-lang.sanyan-language)
[![CI](https://github.com/shujingyin510/sanyan/actions/workflows/ci.yml/badge.svg)](https://github.com/shujingyin510/sanyan/actions)

> **A programming language built for the real world.** Sensors glitch. Users hesitate. Networks fluctuate. The real world was never binary to begin with.

[中文版](README_CN.md)

---

## What is Sanyan?

Sanyan is a programming language with native three-valued logic. The real world is full of uncertainty — Sanyan expresses it with "maybe" instead of forcing a binary yes-or-no.

Keywords can switch to any natural language. It's not just Chinese programming — it's native-language programming.

---

## Origin

In 1958, Moscow State University built a ternary computer called **Setun**. Each bit wasn't 0 or 1, but **positive, zero, or negative**. It ran reliably for thirty years at one-third the power consumption of binary computers of the same era. Then it was discontinued — not because the technology didn't work, but because Soviet industrial standards had fully shifted to binary.

In 2024, while building a smart home system on STM32, I noticed every sensor was feeding me three states: person detected, no person, signal unstable. But my code could only handle `if` and `else`. "Signal unstable" was forced into 0 or 1, and I added thresholds, state machines, and comments to patch the missing information.

**What if a programming language natively supported a third state?**

That's how Sanyan was born.

---

## Quick Start

```bash
git clone https://github.com/shujingyin510/sanyan.git
cd sanyan
python main.py
```

> **Performance tip**: Run with [PyPy](https://pypy.org) for 5-10x speedup: `pypy main.py`

Once in the REPL, try:

```text
sanyan> set a = 10
sanyan> print(a ^ 2)
  => 100  (ternary: ++-0+)

sanyan> set state = maybe
sanyan> print(state)
  => 0  (ternary: 0)
```

Run example files:

```bash
python main.py examples/greenhouse.san
python main.py examples/sensor_pipeline_simple.san
```

---

## Key Features

### Ternary Logic

Sanyan's ternary system is simulated on Python integers (TritValue wraps +1/0/-1). The semantics follow Kleene strong logic:

| A | B | A AND B | A OR B |
|---|---|---|---|
| True | Maybe | Maybe | True |
| False | Maybe | False | Maybe |
| Maybe | Maybe | Maybe | Maybe |

`Maybe AND Maybe` is still `Maybe`. Stack uncertainty on uncertainty, and the result remains uncertain.

### Dual Syntax

Sanyan has two equivalent syntaxes: **Sugar** (C-like) and **S-Expressions** (Lisp-like). Both compile to the same evaluator.

**Sugar:**
```c
set x = 10
if (x > 5) {
    print("large")
} else {
    print("small")
}
```

**S-Expression:**
```lisp
(set x 10)
(if (> x 5)
    (print "large")
    (print "small"))
```

### Native-Language Keywords

Switch keywords to any language via the skin system. Chinese, English, or any other language — the semantics don't change.

### IoT & Sensor Abstraction

Register virtual devices, read/write sensors with ternary values. Perfect for smart home, robotics, and industrial control where uncertainty is the default state.

---

## What's New in v3.14.0

| Feature | Description |
|---|---|
| 🔄 **Full Self-Hosting VM** | VM-compiled `bytecode_compiler.bin` is byte-identical to the evaluator output (5442 bytes, 5406 bytecodes) |
| 🛡️ **Stack Isolation** | CALL records `stack_base`, RET executes `del stack[base:]` — eliminates stack pollution from recursive CALL + JMP loops |
| 📝 **Line Comments** | `//` and `／／` line comments supported in the S-expression lexer |
| 🆕 **DICT_KEYS Opcode** | New 0x32 opcode returns dict keys as a list |
| 🐛 **String Quote Detection Fix** | Uses `(ord (substr n 0 1))` instead of unreliable `str_equals "\""` |

See [CHANGELOG.md](CHANGELOG.md) for the full list.

---

## Architecture

```
Source (.san) → Sugar Parser or S-Expression Parser → AST
  → Evaluator (interpreted) or Compiler → Bytecode (.bin) → VM
  → LLVM Codegen → Native Binary (optional)
```

The evaluator path is the primary execution mode. The bytecode VM (vm.py) can compile and run .bin files — and has achieved full self-hosting: the VM can compile its own compiler source to produce an identical .bin.

The LLVM codegen (llvmgen/) compiles to native binaries via C runtime linkage.

---

## Project Structure

```
sanyan/
├── vm.py                    # Bytecode VM (self-hosting capable)
├── evaluator.py             # Tree-walking interpreter
├── lexer.py                 # S-expression tokenizer (supports // comments)
├── parser.py                # S-expression parser
├── ternary_core.py          # Balanced ternary arithmetic (simulated)
├── compile_bytecode.py      # .san → .bin compiler entry
├── sanyancc.py              # Cross-compiler for STM32
├── main.py                  # Entry point / REPL
├── runtime.py               # Runtime environment
├── sugar/                   # C-like sugar → S-expression converter
├── ops/                     # Built-in operations (28 modules)
├── llvmgen/                 # LLVM code generator
├── lsp/                     # Language server protocol
├── stdlib/                  # Standard library
├── tests/                   # 41 integration tests + unit tests
├── examples/                # Example programs
├── docs/                    # Manual, syntax guide, LLVM docs
├── benchmark/               # Performance benchmarks
├── packages/                # Package manager cache
└── sanyan-vscode/           # VS Code extension
```

---

## Roadmap

- [x] Balanced ternary arithmetic & three-valued logic
- [x] Custom functions, lambdas, higher-order functions
- [x] C-like sugar + S-expression dual syntax
- [x] Exception handling (try/catch)
- [x] Internationalizable keywords (skin system)
- [x] Full-width symbol compatibility
- [x] LLVM native code generation
- [x] Bytecode VM + full self-hosting
- [ ] GPIO hardware control
- [ ] Web IDE
- [ ] Expanded standard library

---

## Limitations

- **Performance**: Python-based tree-walking interpreter. Use PyPy for 5-10x speedup.
- **No stdin piping**: `input()` only supports interactive input, not pipe redirection.
- **Ternary is simulated**: The ternary arithmetic runs on Python integers, not hardware ternary logic.

---

## Philosophy

Uncertainty is not a bug — it's a legitimate computational state.

---

## License

GNU General Public License v3.0 (GPL-3.0)
