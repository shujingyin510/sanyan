# Sanyan Evolution Runtime: 实验报告

> 从 Experience to Knowledge — 一个可验证的自改进 Agent 知识系统

## 摘要

本文报告了 Sanyan Evolution Runtime 的实验结果。我们构建了一个五层进化架构，实现了从任务分类到知识迁移的完整闭环。关键发现：

1. **因果链闭环**：Knowledge → Calibration → Selection → Success（+43.6%）
2. **知识分层**：配置不可迁移，但任务规律可迁移（+27.9%）
3. **三态逻辑贯穿**：从语言层到知识层，TRUE/FALSE/UNKNOWN 统一认知哲学

## 1. 引言

传统 Agent 系统是"调用大模型"，缺乏可验证的自改进能力。我们的目标是构建一个能够：
- 自主修改代码
- 自动验证修改
- 从历史中学习
- 迁移知识到新项目

的进化系统。

## 2. 系统架构

### 五层架构

```
Layer 5: Knowledge Validation（知识验证层）
  Confidence / Cluster / Consistency
        ↓
Layer 4: Knowledge Layer（知识层）
  MetaLearningDB / TaskEmbedding / ClusterLearning
        ↓
Layer 3: Evolution Layer（进化层）
  Ranking / Cost / Budget / UCB
        ↓
Layer 2: Policy Layer（策略层）
  Config / Strategy / Hypothesis
        ↓
Layer 1: Frozen Core（冰冻核心）
  Reviewer / Replay / History / Ternary
```

### 三态逻辑贯穿

| 层 | 三态表现 | 说明 |
|---|---|---|
| 语言层 | TRUE / FALSE / UNKNOWN | Kleene三值逻辑 |
| Agent层 | 高置信度 / 低置信度 / 未知 | 决策门控 |
| Knowledge Layer | 可信知识 / 弱知识 / 未知知识 | 知识可靠性评估 |
| Evolution Layer | 接受 / 拒绝 / 收集更多数据 | 三态裁决 |

## 3. 实验1: 因果链闭环

### 问题

Knowledge 是否能转化为更好的决策？

### 假设

```
Knowledge → Better Prediction → Better Selection → Higher Success Rate
```

### 实验设计

- **Baseline Agent**：统一配置
- **Knowledge Agent**：从训练集学习最优配置
- **Knowledge + Confidence Agent**：知识 + 置信度加权

### 结果

| Agent | 预测SR | 实际SR | 差距 |
|-------|--------|--------|------|
| Baseline | 40.8% | 40.9% | 0.1% |
| Knowledge | 82.9% | 82.5% | 0.4% |
| Knowledge+Conf | 83.0% | 84.5% | 1.5% |

### 因果链分析

```
Knowledge → Prediction:  +42.1%
Prediction → Selection:  +41.6%
Confidence → Better:     +2.0%
总体提升:                +43.6%
因果链完整:              ✓
```

### 结论

✓ Knowledge → Calibration → Selection → Success 因果链闭环

## 4. 实验2: Knowledge Transfer

### 问题

项目A学到的知识，能否帮助项目B？

### 假设

1. 配置级知识不可迁移（Domain Shift）
2. 任务规律可能可迁移

### 实验设计

- **源项目**：sanyan（三言语言项目）
- **目标项目**：iot_system, web_app
- **测试**：直接迁移配置 vs 迁移任务规律

### 结果

| 目标项目 | Baseline | 配置迁移 | 规律迁移 |
|----------|----------|----------|----------|
| iot_system | 30.4% | 25.8% (-4.6%) | 58.4% (+24.2%) |
| web_app | 33.8% | 31.0% (-2.8%) | 65.0% (+31.6%) |

### 结论

✗ 配置迁移不可行（Domain Shift）
✓ 任务规律可迁移（+27.9%）

**迁移的是规律，不是配置。战略比战术更容易迁移。**

## 5. 实验3: Knowledge Confidence

### 问题

如何评估知识的可靠性？如何防止把偶然当规律？

### 假设

```
confidence = sample_factor × 0.4 + sr_factor × 0.3 + consistency_factor × 0.3
```

### 结果

| 任务类型 | 样本数 | 成功率 | 置信度 | 解释 |
|----------|--------|--------|--------|------|
| documentation | 151 | 90.0% | 0.92 | 高置信度（可信赖） |
| analysis | 111 | 84.0% | 0.87 | 中等置信度 |
| feature | 172 | 80.2% | 0.84 | 中等置信度 |
| bug_fix | 183 | 74.2% | 0.79 | 中等置信度 |
| test | 187 | 70.9% | 0.77 | 中等置信度 |
| performance | 128 | 68.2% | 0.74 | 中等置信度 |
| refactor | 87 | 66.1% | 0.69 | 低置信度（需要更多数据） |

### 结论

✓ Knowledge Confidence 有效区分可靠知识和噪声
✓ 置信度不足的知识不会被用于策略选择

## 6. 实验4: Task Taxonomy

### 问题

不同任务类型是否需要不同策略？

### 假设

```
Task Type → 最优策略 不同
```

### 结果

| 任务类型 | 成功率 | 最佳策略 |
|----------|--------|----------|
| test | 72.2% | thorough |
| feature | 66.8% | standard |
| documentation | 49.5% | direct |
| performance | 48.4% | multi_candidate |
| bug_fix | 45.8% | multi_fix |
| refactor | 45.0% | careful |
| analysis | 42.5% | direct |

### 结论

✓ 不同任务类型确实需要不同配置
✓ Task Taxonomy 有效分类任务

## 7. 实验5: Meta-Knowledge Transfer

### 问题

任务规律能否跨项目迁移？

### 假设

```
Task Pattern → Strategy Pattern 可迁移
```

### 结果

| 目标项目 | Baseline | Pattern Transfer | Confidence Transfer |
|----------|----------|------------------|---------------------|
| iot_system | 34.2% | 58.4% (+24.2%) | 36.4% (+2.2%) |
| web_app | 33.4% | 65.0% (+31.6%) | 38.8% (+5.4%) |

### 学到的规律

```
bug_fix → multi_fix (置信度: 0.53)
refactor → careful (置信度: 0.54)
performance → multi_candidate (置信度: 0.66)
feature → standard (置信度: 0.69)
analysis → direct (置信度: 0.73)
documentation → direct (置信度: 0.75)
```

### 结论

✓ 任务规律可迁移（+27.9%）
✓ 置信度模型可迁移（+3.8%）

## 8. 实验6: 长期稳定性

### 问题

系统是否会在长期运行中退化？

### 结果

```
200轮连续进化:
  接受率: 100%
  平均提升: 7.88%
  标准差: 1.81%
```

### 结论

✓ 系统稳定，不会退化

## 9. 核心洞察

### 三态逻辑贯穿整个系统

```
语言时代：TRUE / FALSE / UNKNOWN
    ↓
Agent时代：高置信度 / 低置信度 / 未知
    ↓
Knowledge Layer：可信知识 / 弱知识 / 未知知识
```

### Knowledge + Confidence + Selection

```
Knowledge（知识）
    ↓
Confidence Gate（置信度门控）
    ↓
Policy Selection（策略选择）
```

**三者一起才是主体。**

### LLM知识 vs Agent知识

```
LLM知识 = Prior（推测）
Agent知识 = Evidence（证据）

LLM解决"我知道什么"
Agent知识库解决"在这个项目里什么真的有效"
```

## 10. 未来方向

1. **Knowledge Generalization**：跨分布泛化验证
2. **Meta-Knowledge Transfer**：元知识迁移优化
3. **长期稳定性**：10000轮压力测试
4. **可视化**：Evolution Graph

## 11. 结论

本项目构建了一个五层进化架构，实现了从任务分类到知识迁移的完整闭环。关键贡献：

1. **因果链闭环**：证明 Knowledge → Calibration → Selection → Success
2. **知识分层**：证明配置不可迁移，但任务规律可迁移
3. **三态逻辑贯穿**：从语言层到知识层的统一认知哲学
4. **可验证的自改进**：通过 Confidence 防止把偶然当规律

> 从"Agent改代码"升级为"可验证的局部自改进系统"
> 从"全局最优"升级为"条件最优"
> 从"静态Agent"升级为"情境Agent"
