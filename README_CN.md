# 三言（Sanyan）— LLM 退化检测的通用阈值

[![CI](https://github.com/shujingyin510/sanyan/actions/workflows/test.yml/badge.svg)](https://github.com/shujingyin510/sanyan/actions)
![Tests](https://img.shields.io/badge/tests-1634%20passing-brightgreen)
![Models](https://img.shields.io/badge/models-GPT--2%20%7C%20Qwen2.5%20%7C%20TinyStories-blue)
![UR](https://img.shields.io/badge/threshold-UR%E2%89%880.30-orange)

> **UR ≈ 0.30 在 4 个模型、3 种架构、3 个数量级的参数跨度上，可靠区分退化生成与连贯生成。**

[English](README.md) | [快速开始](QUICK_START.md) | [结果](RESULTS_CN.md) | [研究](docs/research/) | [路线图](ROADMAP.md)

---

## 核心发现

滑动 32-token 窗口内的 **unique_ratio（独特词比例）阈值 0.30**，能在模型退化为循环重复时准确检测：

| 模型 | 架构 | 参数 | 行为 | UR=0.30 结果 |
|------|------|------|------|-------------|
| TinyStories 3.6M | GPT-Neo | 3.6M | 退化 | 真阳性 98% |
| TinyStories 28M | GPT-Neo | 28M | 退化 | 真阳性 100% |
| GPT-2 124M | GPT-2 | 124M | 退化 | 真阳性 100% |
| Qwen2.5-0.5B | Qwen2 | 494M | 连贯 | 假阳性 0.4% |

**关键结论**：阈值在退化模型上真阳性 98-100%，在正常模型上假阳性仅 0.4%（p < 0.05）。消融实验证明仅 UR 一个信号即可达到完整轨迹检测的效果。

---

## 为什么重要

小语言模型经常陷入循环重复，但 **softmax 置信度始终维持在 0.97-1.00**——模型以为自己输出很好。传统停止策略完全失效。

**三态门控 vs 传统策略（1000 prompt 基准）：**

| 策略 | 平均长度 | 停止率 |
|------|---------|--------|
| UR < 0.30 | 12-20 tokens | **98-100%** |
| EOS-only | 64 tokens | 0% |
| 重复惩罚 | 64 tokens | 0% |

100 prompt 盲评：**三元门控 79.7% vs EOS-only 8.3%**（平局 12%）。

---

## 系统架构

```
三言语言（决策 DSL）
    ↓
Python / C VM
    ↓
Native FFI（reg_op 机制）
    ↓
AVX2 GEMM + C LayerNorm/GELU/Softmax
    ↓
GPT-2 / GPT-Neo / Qwen2 Transformer
    ↓
KV Cache 推理
    ↓
UR 退化检测（UR_TH = 0.30）
```

---

## 快速开始

```bash
# 三态门控基准测试（GPT-2 124M, 1000 prompts）
python -X utf8 csrc/gpt2_scale.py

# 三言语言验证 Demo（.san → reg_op → C DLL → GPT-2）
python -X utf8 csrc/sanyan_run.py csrc/infer_demo.san

# 编译 C 算子
gcc -shared -O2 -o csrc/transformer_c.dll csrc/transformer_c.c -lm
```

---

## 文档

| 文档 | 说明 |
|------|------|
| [RESULTS_CN.md](RESULTS_CN.md) | 全部实验数据 |
| [ROADMAP.md](ROADMAP.md) | 已完成和计划中 |
| [docs/research/ternary_gating_report.md](docs/research/ternary_gating_report.md) | 完整研究报告 |
| [csrc/README.md](csrc/README.md) | C 源码和推理引擎文档 |
| [AGENTS.md](AGENTS.md) | 开发规范 |
