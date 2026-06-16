# Sanyan — A Universal Degeneration Threshold for LLMs

[![CI](https://github.com/shujingyin510/sanyan/actions/workflows/test.yml/badge.svg)](https://github.com/shujingyin510/sanyan/actions)
![Tests](https://img.shields.io/badge/tests-1634%20passing-brightgreen)
![Models](https://img.shields.io/badge/models-GPT--2%20%7C%20Qwen2.5%20%7C%20TinyStories-blue)
![UR](https://img.shields.io/badge/threshold-UR%E2%89%880.30-orange)

> **UR ≈ 0.30 reliably separates degenerative from coherent text generation across 4 models, 3 architectures, and 3 orders of magnitude in parameter count.**

[中文](README_CN.md) | [Quick Start](QUICK_START.md) | [Results](RESULTS.md) | [Research](docs/research/) | [Roadmap](ROADMAP.md)

---

## Main Finding

A single **uniqueness-ratio threshold of 0.30** — the fraction of unique tokens in a sliding 32-token window — detects when a language model has collapsed into repetitive degeneration:

| Model | Architecture | Params | Behavior | UR=0.30 Result |
|-------|-------------|--------|----------|----------------|
| TinyStories 3.6M | GPT-Neo | 3.6M | Degenerates | True Positive 98% |
| TinyStories 28M | GPT-Neo | 28M | Degenerates | True Positive 100% |
| GPT-2 124M | GPT-2 | 124M | Degenerates | True Positive 100% |
| Qwen2.5-0.5B | Qwen2 | 494M | Coherent | False Positive 0.4% |

**Key result**: The threshold has a 98-100% true positive rate on degenerating models and a 0.4% false positive rate on coherent ones (p < 0.05, binomial test). Ablation shows UR alone achieves the same performance as the full trajectory detection system — cycle detection, function-word density, and no-new-word signals are entirely redundant.

---

## Why It Matters

Small language models frequently collapse into repetitive loops ("was was was...", "and and and...") with **confidence scores remaining at 0.97-1.00** — the model believes it's producing high-quality output while generating garbage. Standard stopping strategies (EOS token, max token limit, repetition penalty) fail to detect this.

**Sanyan's UR-based stopping** catches degeneration the moment it happens:

| Strategy | Avg Length | Stop Rate |
|----------|-----------|-----------|
| UR < 0.30 (Sanyan) | 12-20 tokens | **98-100%** |
| EOS-only | 64 tokens | 0% |
| Repetition Penalty | 64 tokens | 0% |

Human blind evaluation across 100 prompts: **ternary gating preferred 79.7% vs. EOS-only 8.3%** (12% ties).

---

## Architecture

```
Sanyan Language (决策 DSL)
    ↓
Python / C VM
    ↓
Native FFI (reg_op)
    ↓
AVX2 GEMM + C LayerNorm/GELU/Softmax
    ↓
GPT-2 / GPT-Neo / Qwen2 Transformer
    ↓
KV Cache Inference
    ↓
UR-based Degeneration Detection (UR_TH = 0.30)
```

---

## Quick Start

```bash
# Run ternary gating benchmark (GPT-2 124M, 1000 prompts)
python -X utf8 csrc/gpt2_scale.py

# Run Sanyan language demo (.san → reg_op → C DLL → GPT-2)
python -X utf8 csrc/sanyan_run.py csrc/infer_demo.san

# Compile C kernels
gcc -shared -O2 -o csrc/transformer_c.dll csrc/transformer_c.c -lm
```

---

## Repository Layout

```
sanyan/
├── README.md                    ← this file
├── README_CN.md                 ← Chinese version
├── RESULTS.md                   ← all benchmark results
├── ROADMAP.md                   ← future plans
│
├── csrc/                        ← C kernels + inference engines
│   ├── README.md                ←   csrc documentation
│   ├── transformer_c.c/dll      ←   C LayerNorm/GELU
│   ├── softmax_c.c/dll          ←   C Softmax
│   ├── simd_demo.asm/dll        ←   AVX2 GEMM kernel
│   ├── gpt2_scale.py            ←   1000-prompt benchmark
│   └── qwen25_bench.py          ←   Qwen2.5 validation
│
├── docs/
│   ├── research/                ← research reports
│   │   ├── ternary_gating_report.md
│   │   ├── agent_benchmark_report.md
│   │   └── agent_evolution_report.md
│   ├── architecture.md          ← system architecture (TBD)
│   └── vm.md                    ← VM design (TBD)
│
├── benchmarks/                  ← benchmark result JSONs
├── agent_system/                ← Agent decision runtime
├── ops/                         ← Sanyan language builtins
├── sugar/                       ← Sugar syntax parser
└── tests/                       ← 1634 passing tests
```

---

## Current Status

| Component | Status |
|-----------|--------|
| UR=0.30 validation (4 models, 3 architectures) | ✅ |
| 1000-prompt benchmark per model | ✅ |
| Human blind evaluation (100 prompts) | ✅ |
| Ablation: UR-only vs full trajectory | ✅ |
| Statistical significance (p < 0.05) | ✅ |
| AVX2 GEMM kernel (66 GFLOPS) | ✅ |
| C LayerNorm/GELU/Softmax kernels | ✅ |
| KV Cache inference | ✅ |
| Sanyan → C FFI demo (.san → reg_op → C DLL) | ✅ |
| GGUF / quantization | ⬜ |
| Larger models (TinyLlama, SmolLM) | ⬜ |
| Paper submission | ⬜ |

---

## Documentation

| Document | Description |
|----------|-------------|
| [RESULTS.md](RESULTS.md) | All benchmark results with tables |
| [ROADMAP.md](ROADMAP.md) | Completed and planned work |
| [docs/research/ternary_gating_report.md](docs/research/ternary_gating_report.md) | Full research report (Chinese + English abstract) |
| [docs/research/agent_benchmark_report.md](docs/research/agent_benchmark_report.md) | Agent safety & honesty benchmarks |
| [docs/research/agent_evolution_report.md](docs/research/agent_evolution_report.md) | Agent evolution runtime experiments |
| [csrc/README.md](csrc/README.md) | C source and inference engine docs |
| [CHANGELOG.md](CHANGELOG.md) | Version history |
| [AGENTS.md](AGENTS.md) | Development conventions |
