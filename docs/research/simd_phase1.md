# Phase 1 — SIMD GEMM 验证通过

> 日期: 2026-06-16 | 状态: ✅ 已通过

## 结果

```
三言脚本 (矩阵乘法)
  → SanyanEvaluator (reg_op)
  → ctypes CDLL
  → AVX2 汇编 matmul_256x256
  → 与 NumPy 对比: 误差 0.00e+00
```

## 关键文件

| 文件 | 内容 |
|------|------|
| `csrc/simd_demo.asm` | AVX2 GEMM 内核 (256×256, FMA, 4行×8列分块) |
| `csrc/simd_test.py` | Python ctypes 测试驱动 + NumPy 对比 |
| `csrc/sanyan_gemm_demo.py` | 三言语言层调度验证 |

## 下一步

- [ ] Softmax AVX2 核 (已写, ABI调试中)
- [ ] LayerNorm
- [ ] Tiny Attention (seq=8, dim=32, heads=1)
- [ ] 加载 TinyStories-1M
