# Roadmap

## Completed

| Milestone | Details |
|-----------|---------|
| **C VM (ISA v2)** | 16-bit LOAD/STORE, 32-bit CALL, CLOSURE, PUSH_STR16 |
| **Level 3 Bootstrap** | 318-line C seed VM → TCC-compiled binary |
| **Level 4 Bootstrap** | 617-line x86_64 NASM assembly VM |
| **AVX2 GEMM Kernel** | FMA instructions, 256×256, 66 GFLOPS, zero error vs NumPy |
| **C Operator Library** | LayerNorm (err e-07), Softmax (err e-09), GELU (err e-08) |
| **TinyStories 3.6M** | GPT-Neo inference, KV Cache, 4ms/token |
| **TinyStories 28M** | GPT-Neo inference, 1000-prompt benchmark |
| **GPT-2 124M** | GPT-2 inference (Conv1D + pre-norm), KV Cache, 1000-prompt benchmark |
| **UR Threshold Calibration** | Auto-calibrated to 0.30 across 3.6M and 28M |
| **Qwen2.5-0.5B Validation** | 1000-prompt false positive check (0.4%) |
| **Human Blind Evaluation** | 100 prompts × 3 dimensions, ternary 79.7% preferred |
| **Ablation Study** | UR-only = full trajectory (all other signals redundant) |
| **Statistical Significance** | p = 0.0287, 95% CI [0.01%, 0.79%] |
| **Sanyan → C FFI Demo** | .san → reg_op → C DLL → GPT-2 end-to-end |
| **Agent Safety Benchmarks** | 49 bug injections, 98% detection rate |
| **Agent Honesty Benchmarks** | 100 questions × 5 categories, Truth Calibration -11.5% overreach |
| **Agent Evolution Runtime** | 4-layer architecture, knowledge→calibration→selection→success chain |

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
