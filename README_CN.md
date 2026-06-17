# 三言（Sanyan）— 小语言模型的惊人稳定退化阈值

[![CI](https://github.com/shujingyin510/sanyan/actions/workflows/test.yml/badge.svg)](https://github.com/shujingyin510/sanyan/actions)
![Tests](https://img.shields.io/badge/tests-1650%2B%20passing-brightgreen)
![Models](https://img.shields.io/badge/models-GPT--2%20%7C%20Qwen2.5%20%7C%20TinyStories-blue)
![UR](https://img.shields.io/badge/threshold-UR%E2%89%880.30-orange)

> **UR ≈ 0.30 在 4 个小型模型、3 种架构、3 个数量级的参数跨度上，可靠区分退化生成与连贯生成。**

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

### 经验验证

**UR 轨迹呈现相变特征**，而非简单统计下降——UR 从 ~0.70 单调下降至 ~0.10，在 t=18–28 穿越 0.30，且**评估窗口内（≤64 token）未观察到恢复**：

| 步数 | "Once upon a time" | "The little boy" | "A big dog" |
|------|--------------------|-------------------|-------------|
| t=9 | 0.62 | 0.88 | 0.50 |
| t=18 | 0.35 | 0.41 | **0.24** |
| t=28 | 0.26 | **0.26** | 0.19 |
| t=48 | 0.16 | 0.03 | 0.06 |

**人类文本 vs 退化文本分离度**（window=32）：

| 文本类型 | 平均 UR | UR < 0.30 |
|-----------|--------|-----------|
| 人类（文学） | **0.704** | **0.0%** |
| 退化（GPT-2） | **0.101** | **99.7%** |

**采样策略对比**（GPT-2 124M）：

| 策略 | 退化率 | 平均 UR |
|------|--------|---------|
| nucleus (top_p=0.9) | **0%** | **0.867** |
| greedy | 25% | 0.336 |
| rep_penalty=1.15 | **100%** | 0.117 |

> **反直觉发现**：repetition_penalty 在 GPT-2 上*加剧*了模型坍缩——缩小有效采样空间迫使模型循环。UR 作为机制无关的后验信号，正确反映每种策略的实际退化程度。

**GPT-2 跨规模 UR 稳定性**（nucleus sampling, top_p=0.9）：

| 模型 | 参数 | 平均 UR | UR < 0.30 |
|------|------|--------|-----------|
| GPT-2 | 124M | 0.711 | 0% |
| GPT-2 Medium | 355M | 0.714 | 0% |
| GPT-2 Large | 774M | 0.797 | 0% |

> UR 跨 6× 参数规模的波动仅 ±0.043。模型越大，UR 越高（0.71→0.80），生成多样性递增。UR 不仅是退化检测器，更是稳定的生成多样性度量。

**阈值敏感性**：UR 从 0.20–0.40 滑动扫描，TPR/FPR 完全相同——两类分布在 0.20–0.40 间存在宽分离带。选择 0.30（比中点 0.402 更保守），最小化假阳性风险。

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

## 已知边界

当前发现（UR ≈ 0.30 作为退化检测阈值）是经验性的，应在以下约束内解读：

### 1. 窗口化词法度量

`unique_ratio` 在固定滑动 token 窗口上计算。所有报告结果使用 32 token 窗口，步长 = 1。阈值在中等窗口大小（32–64）下稳定，但不保证在任意尺度下不变。

### 2. 区间定义（非质量分类）

UR 度量的是**重复主导的生成区间**，而非语义正确性或整体输出质量。因此：

- 结构化输出（代码、列表、枚举）
- 诗歌或文体约束文本

可能呈现低 UR 但内容有效。这些情况不被视为假阳性，而是检测器目标域之外的不同生成区间。

### 3. prompt 诱导重复是独立区间

输入 prompt 中显式存在的重复（如 "cat cat cat"）被视为输入条件行为，而非模型内部退化。检测器设计用于检测生成过程中的**涌现式重复**，而非回显输入结构。

### 4. 经验性模型覆盖

当前评估包括：
- TinyStories（3.6M, 28M）
- GPT-2（124M）
- Qwen2.5-0.5B

结果在这些模型间一致，但应解读为*测试区间内的经验性跨模型稳定性*，而非所有架构的完全模型无关性。

### 5. 规模限制

未在以下模型上评估：
- 7B+ 参数模型（如 LLaMA-3、Qwen2.5-7B）
- 指令微调大模型在开放对话区间中的表现

向大规模模型的泛化仍是一个开放问题。

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
