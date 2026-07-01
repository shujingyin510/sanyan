# Roadmap

## Completed

| Milestone | Details |
|-----------|---------|
| **C VM (ISA v2)** | 16-bit LOAD/STORE, 32-bit CALL, CLOSURE, PUSH_STR16 |
| **Level 3 Bootstrap** | 318-line C seed VM → TCC-compiled binary |
| **Level 4 Bootstrap** | 617-line x86_64 NASM assembly VM |
| **Sanyan → C FFI Demo** | .san → reg_op → C DLL → GPT-2 end-to-end |
| **Agent Safety Benchmarks** | 49 bug injections, 100% detection rate (49/49) |
| **Agent Honesty Benchmarks** | 100 questions × 5 categories, Truth Calibration -16.7% overreach (50.0%→33.3%) |
| **Agent Evolution Runtime** | 5-layer architecture, knowledge→calibration→selection→success chain（合成模拟·机制演示，见 README 核心实验说明） |

> **三态门控 / 神经推理工作已迁移到独立 UR 仓库。**
> AVX2 GEMM（66 GFLOPS）、C 算子库、TinyStories/GPT-2 推理、UR 阈值校准（0.30）、Qwen 误报率（0.4%）、人类盲评（ternary 79.7% preferred）、消融实验、统计显著性（p = 0.0287）等成果不再在本仓 ROADMAP 维护。
> 详见 [`docs/research/ternary_gating_report.md`](research/ternary_gating_report.md) 及独立 UR 仓库 <https://github.com/shujingyin510/UR>。

---

## Next

| Priority | Item | Notes |
|----------|------|-------|
| 🔴 | **TinyLlama-1.1B validation** | Test if UR≈0.30 holds for Llama architecture |
| 🔴 | **Paper draft** | Ternary gating + UR threshold as main contribution |
| 🟡 | **GGUF format support** | Quantized model loading (INT8/FP16) |
| 🟡 | **Semantic loop detection** | Embedding-distance based detection for subtle loops |
| 🟡 | **GPU inference** | CUDA kernels for GEMM/Attention |
| 🟢 | **More architectures** | SmolLM, Phi, Mistral |
| 🟢 | **Larger models** | 1B-7B range for stress-testing false positive rate |
| 🟢 | **Streaming token-level gate** | Real-time UR check during token generation |
