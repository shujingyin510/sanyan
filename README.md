# Sanyan — A Surprisingly Stable Degeneration Threshold for Small LLMs

[![CI](https://github.com/shujingyin510/sanyan/actions/workflows/test.yml/badge.svg)](https://github.com/shujingyin510/sanyan/actions)
![Tests](https://img.shields.io/badge/tests-1650%2B%20passing-brightgreen)
![Models](https://img.shields.io/badge/models-GPT--2%20%7C%20Qwen2.5%20%7C%20TinyStories-blue)
![UR](https://img.shields.io/badge/threshold-UR%E2%89%880.30-orange)

> **UR ≈ 0.30 reliably separates degenerative from coherent text generation across 4 small models, 3 architectures, and 3 orders of magnitude in parameter count.**

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

### Empirical Validation

**UR trajectories show a phase transition**, not just a statistical drop — UR declines monotonically from ~0.70 to ~0.10, crosses 0.30 at t=18–28, and **no recovery is observed within the evaluated horizon** (≤64 tokens):

| Step | "Once upon a time" | "The little boy" | "A big dog" |
|------|--------------------|-------------------|-------------|
| t=9 | 0.62 | 0.88 | 0.50 |
| t=18 | 0.35 | 0.41 | **0.24** |
| t=28 | 0.26 | **0.26** | 0.19 |
| t=48 | 0.16 | 0.03 | 0.06 |

**Human vs. degenerative text separation** (window=32):

| Text Type | Avg UR | UR < 0.30 |
|-----------|--------|-----------|
| Human (literature) | **0.704** | **0.0%** |
| Human (WikiText-2, n=60) | **0.849** | **0.2%** |
| Degenerative (GPT-2) | **0.101** | **99.7%** |

**Decoding strategy comparison** on GPT-2 124M:

| Strategy | Degeneration Rate | Avg UR |
|----------|-------------------|--------|
| nucleus (top_p=0.9) | **0%** | **0.867** |
| greedy | 25% | 0.336 |
| rep_penalty=1.15 | **100%** | 0.117 |

> **Counterintuitive**: repetition penalty *amplifies* collapse on GPT-2 by narrowing the effective sampling space. UR correctly reflects each strategy's actual degeneration level independent of the strategy's assumptions.

**GPT-2 cross-size UR stability** (nucleus sampling, top_p=0.9):

| Model | Params | Avg UR | UR < 0.30 |
|-------|--------|--------|-----------|
| GPT-2 | 124M | 0.711 | 0% |
| GPT-2 Medium | 355M | 0.714 | 0% |
| GPT-2 Large | 774M | 0.797 | 0% |

> UR varies only ±0.043 across 6× scale. Larger models → higher UR → more diverse output. UR functions as a stable generation diversity metric, not just a degeneration detector.

**Cross-language stability**: Qwen2.5-0.5B on Chinese (n=1000): FP=**0.6%**, avg min_UR=**0.714** — vs English FP=0.4%, avg=0.717. UR threshold is language-agnostic at scale.

**Threshold selection** (real-data ROC, 1214 samples): Youden's J optimum = 0.32. We chose **0.30** — the TPR "knee point" where detection jumps from 0.847→0.993. Conservative relative to the optimum, minimizing FPR.

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

## Known Boundaries

The current findings (UR ≈ 0.30 as a degeneration threshold) are empirical and should be interpreted within the following constraints:

### 1. Windowed lexical measurement

`unique_ratio` is computed over a fixed sliding window of tokens. All reported results use a window size of 32 tokens, stride = 1. The threshold is stable under moderate window sizes (32–64), but is not invariant across arbitrary scales.

### 2. Regime definition (not quality classification)

UR measures **repetition-dominated generation regimes**, not semantic correctness or overall output quality. Therefore:

- Structured outputs (code, lists, enumerations)
- Poetic or stylistically constrained text

may exhibit low UR while remaining valid. These cases are not considered false positives, but a different generation regime outside the detector's target domain.

### 3. Prompt-induced repetition is a separate regime

Repetition explicitly present in the input prompt (e.g., "cat cat cat") is treated as input-conditioned behavior, not model-internal degeneration. The detector is designed for emergent repetition during generation, not echoing input structure.

### 4. Empirical model coverage

The current evaluation includes:
- TinyStories (3.6M, 28M)
- GPT-2 (124M)
- Qwen2.5-0.5B

Results are consistent across these models, but this should be interpreted as *empirical cross-model stability within tested regimes*, not full model-invariance across all architectures.

### 5. Scale limitation

No evaluation has been performed on:
- 7B+ parameter models (e.g., LLaMA-3, Qwen2.5-7B)
- Instruction-tuned large chat models in open-ended dialogue regimes

Generalization to large-scale models remains an open question.

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
