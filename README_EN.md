# Tri-State Cognitive Framework Sanyan v3.35.0

[![VS Code Extension](https://img.shields.io/badge/VS%20Code-Syntax%20Highlight-%23007ACC?logo=visualstudiocode)](sanyan-vscode/README.md)
[![CI](https://github.com/shujingyin510/sanyan/actions/workflows/test.yml/badge.svg)](https://github.com/shujingyin510/sanyan/actions)

> **One person. Six weeks. A compiler, a VM, a cognitive runtime, and an agent framework — built from scratch.** A cognitive computing framework for uncertainty-oriented decision making. The real world isn't binary — sensors glitch, users hesitate, code breaks. The Sanyan framework uses Kleene logic × Bayesian confidence × safety gating to let programs naturally express, propagate, and accumulate "not sure yet" — deferring decision until evidence is sufficient.

[中文版](README.md)

---

## Origin

In 1958, Moscow State University built a ternary computer called **Setun**. Each bit wasn't 0 or 1, but **positive, zero, or negative**. It ran reliably for thirty years at one-third the power consumption of binary computers of the same era. Then it was discontinued — not because the technology didn't work, but because Soviet industrial standards had fully shifted to binary.

In 2024, while building a smart home system on STM32, I noticed every sensor was feeding me three states: person detected, no person, signal unstable. But my code could only handle `if` and `else`. "Signal unstable" was forced into 0 or 1, and I added thresholds, state machines, and comments to patch the missing information.

**What if a programming language natively supported a third state?**

That's how Sanyan was born. From May 2026 to now — six weeks, one person — a full compiler, VM, cognitive runtime, and agent framework. What once required a team months now took one person weeks. AI helped write a lot of code, but the direction, the architecture, the judgment calls — the things AI can't figure out on its own — those were human.

---

## What is Sanyan?

Sanyan = **Ternary Language (DSL)** + **Ternary Engine (TernaryEngine)** + **Ternary Applications (Agent / IoT / Village)**.
The language is the interface — the core is the Kleene three-value logic propagation + Bayesian confidence decay + protection gating decision engine.

---

## What's New in v3.32

- **Agent Autonomous Loop**: `auto_verify.py` — commit triggers full test suite → auto-commit on pass / auto-rollback on fail. Three paths tested and verified.
- **Deep LLM Integration**: Upgraded to `deepseek-v4-pro` with explicit thinking control (`budget_tokens: 2048`). JSON tool call format. Cross-task experience library for learning from failures.
- **Cognitive Runtime**: Toggle detection, same-error-twice escalation, structured retry history — the Agent knows when it's going in circles.
- **Bootstrap Level 2–4**: Self-compiling compiler (fixpoint verified) → 318-line C seed VM → 617-line x86_64 NASM assembly VM. Zero external dependencies.
- **Full CI Green**: 1650+ tests, one-command preflight, multi-backend consistency verification.

---

## Why Ternary

Sanyan's native three-valued logic (`true` / `maybe` / `false`) is not a gimmick — it solves real problems that binary logic cannot. Four quantified case studies demonstrate this:

- **Circuit simulation** — 9-input truth tables prove ternary correctness by construction
- **Data cleaning** — `maybe` stops NULL propagation; binary `None` silently produces misleading 0
- **API health checks** — timeout ≠ down; binary aggregation triggers false alerts
- **Game NPCs** — hesitation is a legitimate behavior; binary needs extra state variables

See [Why Ternary](docs/ternary-logic.md) for the full comparison.

---

## Quick Start

```bash
git clone https://github.com/shujingyin510/sanyan.git
cd sanyan
python main.py
```

> **Performance tip**: For performance-sensitive programs, choose from easy to advanced:
> - [PyPy](https://pypy.org) — drop-in, 5-10x faster: `pypy main.py`
> - **LLVM native compilation** — machine code, orders of magnitude faster: `pip install llvmlite && python compile_llvmgen.py`
> - **C VM** — pure C bytecode interpreter, zero Python dependency: `gcc csrc/runtime.c -o vm && ./vm program.bin`

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
python main.py examples/circuit_sim.san     # Ternary truth tables
python main.py examples/data_cleaning.san   # NULL propagation safety
python main.py examples/health_check.san    # Timeout ≠ down
python main.py examples/npc_decision.san    # NPC hesitation behavior
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

## Features

### Language Core

| Feature | Description |
|---|---|
| **Ternary Logic** | Native `true`/`maybe`/`false` (Kleene strong logic), `maybe and maybe` = `maybe` |
| **Ternary Arithmetic** | Balanced ternary add/sub/mul/div/mod/pow/digit, `TernaryALU` at bit level |
| **Dual Syntax** | Sugar syntax (C-like) + S-expressions, shared evaluator, can be mixed |
| **Native Language** | Keywords switchable to any natural language (CN/EN skins), fullwidth symbol support |
| **Ternary Branch** | `judge (expr) { true → ..., maybe → ..., false → ... }` |
| **Gradual Typing** | Return type annotation `-> type`, optional type `?type`, runtime auto-validation |
| **Exception Handling** | `try { } catch (e) { }`, narrow exception catching |
| **Higher-Order Functions** | `map`/`filter`/`reduce`/`sort`/`reverse`/`unique`/`sum`/`join` |
| **Lambda** | `λ(x) { x * 2 }` or `function(x) { x * 2 }` |
| **Module System** | `import("path")`, `export name1 name2`, nested package import |
| **Line Comments** | `//` (halfwidth), `／／` (fullwidth), `#` — three comment syntaxes |

### Bytecode VM

| Feature | Description |
|---|---|
| **52 Opcodes** | Full instruction set: arithmetic/comparison/logic/container/string/dict/control/IO |
| **Self-Hosting** | `bytecode_compiler.san` compiles itself, VM output byte-identical to Python evaluator |
| **32-bit Code Size** | Supports >64KB bytecode (old 16-bit limit was 64KB) |
| **Standalone .bin** | sugar.bin (~10KB) and llvmgen.bin (~72KB) run independently on VM |
| **C VM** | `csrc/runtime.c` pure C implementation, 52 instructions, no Python dependency |
| **C VM Tests** | `csrc/test_runtime.c` 61 unit tests covering all instructions |
| **STM32 Firmware** | `sanyancc.py` cross-compile → `runtime_stm32.c`, Blue Pill hardware verified |

### LLVM Code Generation

| Feature | Description |
|---|---|
| **AST → LLVM IR** | `llvmgen/codegen.py` + `llvmgen/compiler.py`, ~1500 lines codegen |
| **63-bit Integers** | Tagged pointer upgraded to i64, range ±4.6×10^18 |
| **Float Support** | IEEE 754 double, `fadd`/`fmul`/`fdiv` inline, integer auto-promotion |
| **Import Static Linking** | Compile-time recursive dependency compilation, `san_{mod}__{fn}` name mangling |
| **try/catch** | `@g_error` LLVM visible global + manual stack unwinding |
| **Arena Allocator** | 64KB init, auto-grow, pointer bump替代 malloc |
| **Self-Hosted LLVM Compiler** | `llvmgen.san` compiled to .bin, V5 with all helpers inlined |

### Standard Library & Tools

| Feature | Description |
|---|---|
| **Standard Library** | `json.san` `http.san` `regex.san` `csv.san` `string.san` `list.san` `math.san` etc. |
| **LSP Language Server** | Formatting/reference/rename/document symbols/folding/semantic completion/hover |
| **DAP Debug Adapter** | VS Code breakpoint debugging protocol support |
| **Source Formatter** | `sanfmt.py` — black/prettier style `.san` formatter |
| **Profiling** | `--profile` flag + `:profile` REPL command |
| **AST JSON Export** | `--ast-json` exports parsed AST |
| **Package Manager** | `install("pkg")` / `list_packages()` / `load_package("pkg")` |
| **IoT Abstraction** | `register_device`/`write`/`read`/`query`/`context` sensor/actuator operations |

See [CHANGELOG.md](CHANGELOG.md) for the full version history.

---

### Agent: Readable Decision DSL (v5)

> See [ternary_agent/README.md](ternary_agent/README.md) — v5 architecture, three-phase design, patch catalog.

| Feature | Description |
|---|---|
| **Ternary Reasoning** | LLM cognitive states → ternary mapping → Kleene propagation → Bayesian confidence → safety gating |
| **Multi-Hypothesis** | Top-3 candidates explored in parallel, tournament selects best, early stop kills dead hypotheses |
| **Task Decomposition** | Auto-recursive task splitting, bounded context per layer (4000 token hard limit) |
| **Tool Dependency Graph** | P1: pre-validate tool chain legality, filter invalid combinations |
| **Capability Registry** | P9: task needs vs tool capability matching, -50% misselection rate |
| **Diversity Control** | P8: keyword clustering dedup, avoid 5≈1 pseudo-diversity |
| **Failure Classification** | P3: 6 FailureModes (empty/missing/schema/timeout/logic/loop), precise retry |
| **Adaptive Threshold** | P4: auto-tune from history after 50 rounds, eliminate hardcoded values |
| **Semantic Cache** | P5: similar tasks reused directly, ~15% hit rate |
| **Observability** | P7: full-chain metrics (early stop/cache hit/LLM compare/cost prediction) |
| **Cost Prediction** | P10: historical data model replaces LLM guessing, +20% accuracy |
| **Execution Replay** | P11: complete run log + diff comparison, +300% debug efficiency |
| **Experience Learning** | Tool success rate stats + time decay + module risk assessment |
| **Multi-Provider** | DeepSeek / OpenAI / Qwen / Gemini / Xiaomi MIMO / Token Plan / Ollama |
| **Declarative Policy** | `agent_policy.san` pure data + scene rules, hot-reload |

```bash
# Interactive mode (multi-turn, hot reload)
python -X utf8 run_agent.py

# Single-shot programming (LLM generates code → executes → returns result)
python -X utf8 run_agent.py "calculate sum from 1 to 1000"

# Autonomous (read → modify → test → fix → loop)
python -X utf8 run_agent.py "fix _test_verify.py so tests pass" --auto

# File operations
python -X utf8 run_agent.py "replace v0.3 with v0.4 in AGENTS.md"
```

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
├── ARCHITECTURE.md            # Architecture documentation
├── AGENTS.md                  # AI collaboration rules (self-hosting, tests, conventions)
├── CHANGELOG.md               # Changelog
├── CONTRIBUTING.md            # Contribution guide
├── README.md                  # Project README (Chinese)
├── README_EN.md               # Project README (English)
├── build_combined.py          # Build script: expand #include → combined .san
├── vm.py                      # Bytecode VM (self-hosting capable)
├── evaluator.py               # Tree-walking interpreter
├── lexer.py                   # S-expression tokenizer
├── parser.py                  # S-expression parser
├── ternary_core.py            # Balanced ternary arithmetic (simulated)
├── compile_bytecode.py        # .san → .bin compiler (supports #include)
├── compile_llvmgen.py         # llvmgen.san → llvmgen.bin (V5 self-hosted, no injection)
├── sanyancc.py                # Cross-compiler for STM32
├── main.py                    # Entry point / REPL
├── runtime.py                 # Runtime environment
├── preprocess.py              # #include preprocessor
├── sugar/                     # C-like sugar → S-expression converter
├── llvmgen/                   # LLVM code generator (split)
│   ├── codegen.py             # AST → LLVM IR
│   ├── compiler.py            # Compiler entry + source parsing
│   ├── ir_fixes.py            # IR post-processing (from compiler.py)
│   ├── ops_gen.py             # Main compilation entry
│   ├── ops_gen_control.py     # Control flow compilation (from ops_gen.py)
│   ├── ops_gen_helpers.py     # Arithmetic/container helpers (from ops_gen.py)
│   ├── ir_builder.py          # CodegenContext builder
│   ├── helpers.py             # Python helper functions
│   ├── runtime.c              # C runtime library
│   └── type_mapping.py        # Type mapping & runtime function specs
├── ops/                       # Built-in operations (30 modules)
├── lsp/                       # Language server protocol
├── csrc/                      # C VM (52 instructions, with #include preprocessing)
│   ├── runtime.c              # VM implementation
│   ├── test_runtime.c         # VM unit tests (61 tests)
│   └── dp.c                   # parse_sanyan native compile test
├── stdlib/                    # Standard library
│   ├── _bootstrap.san         # S-expression bootstrap parser
│   ├── bytecode_compiler.san  # Self-hosted bytecode compiler
│   ├── sugar.san              # Sugar parser (merged, from build_combined.py)
│   ├── llvmgen.san            # LLVM codegen (merged, from build_combined.py)
│   ├── llvmgen_src.san        # llvmgen split source (#include submodules)
│   ├── llvmgen/               # llvmgen submodules
│   │   ├── preamble.san       # Global vars + helper functions
│   │   ├── utils.san          # Utility functions
│   │   ├── compiler.san       # Main compilation function
│   │   ├── runtime_ir.san     # Runtime IR generation
│   │   └── entry.san          # Top-level entry + exports
│   ├── network.san            # Network library (TCP/UDP/connection pool)
│   ├── hardware.san           # Hardware abstraction (GPIO/I2C/SPI/sensors)
│   ├── math.san               # Math library (matrix/vector/statistics)
│   └── ...                    # More standard library modules
├── packages/                  # Package manager
│   ├── index.json             # Package index (6 packages)
│   ├── sample/                # Example package (greeting tool)
│   ├── math_extended/         # Extended math (complex/vector)
│   ├── logging/               # Structured logging
│   ├── web_utils/             # Web utilities (URL/HTML/Cookie)
│   ├── data_pipeline/         # Data pipeline (map/filter/aggregate)
│   └── config/                # Configuration management
├── examples/                  # Example programs
│   ├── sensor_fusion.san      # Three-value sensor fusion (Sanyan)
│   ├── sensor_fusion.py       # Sensor fusion (Python comparison)
│   ├── sensor_fusion.c        # Sensor fusion (C comparison)
│   ├── fault_tolerant_control.san # Fault-tolerant control
│   ├── iot_state_machine.san  # IoT device state machine
│   ├── greenhouse.san         # Smart greenhouse
│   └── stm32-blinky/          # STM32 embedded example
├── tests/                     # Automated tests (629+ tests)
├── docs/                      # Documentation
│   ├── manual.md              # User manual
│   ├── llvm.md                # LLVM documentation
│   └── package_development.md # Package development guide
└── benchmark/                 # Performance benchmarks
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
- [x] C VM unit tests (61 tests)
- [x] Auto-generated BUILTIN_OPS from language JSON
- [x] Core module docstrings
- [x] Architecture docs + contribution guide
- [x] llvmgen.san self-hosting V5 (helper functions inlined)
- [x] Package manager enhanced (uninstall/search/info)
- [x] Standard library expansion (network/hardware/math matrix)
- [x] Three-value IoT cases (sensor fusion, fault-tolerant control, state machine)
- [x] Three-value vs two-value comparison docs
- [x] Agent subsystem with file tools (read/write/list/replace) and programming capability (31 tests)
- [x] #include preprocessing full pipeline (Python + C VM)
- [ ] GPIO hardware control
- [ ] Web IDE
- [ ] Community ecosystem

---

## Limitations

- **Performance**: Python tree-walking interpreter. Use `--vm` (bytecode VM) or PyPy for speedups. LLVM backend compiles arithmetic directly to native instructions (`add i64`), achieving near-C performance on hot paths.
- **No stdin piping**: `input()` only supports interactive input, not pipe redirection.
- **Ternary is simulated**: The ternary arithmetic runs on Python integers, not hardware ternary logic. The LLVM backend bypasses this by generating native integer IR directly.

---

## Philosophy

Uncertainty is not a bug — it's a legitimate computational state.

---

## License

GNU General Public License v3.0 (GPL-3.0)
