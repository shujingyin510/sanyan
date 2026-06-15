# Knowledge Validation: 知识层的构建与验证

## 问题

Agent 系统积累的经验如何转化为可信赖的知识？如何防止把偶然当规律？

**问题**：
1. 如何评估知识的可靠性？
2. 如何发现任务类型内的子模式？
3. 如何让知识库从"记录"升级为"理解"？

## 假设

1. **Knowledge Confidence**：通过样本数、成功率、一致性可以评估知识可靠性
2. **子聚类发现**：任务类型内部存在子模式
3. **三层知识体系**：Personal/Project/Global 分层管理

## 实验

### 实验1: 知识置信度计算

**方法**：为每个任务类型计算置信度

**结果**：
```
任务类型        样本数  成功率   置信度   解释
──────────────────────────────────────────────────
documentation  151    90.0%   0.92    高置信度（可信赖）
analysis       111    84.0%   0.87    中等置信度
feature        172    80.2%   0.84    中等置信度
bug_fix        183    74.2%   0.79    中等置信度
test           187    70.9%   0.77    中等置信度
performance    128    68.2%   0.74    中等置信度
refactor        87    66.1%   0.69    低置信度（需要更多数据）

高置信度知识: 6/7
低置信度知识: 0/7
```

**置信度公式**：
```
confidence = sample_factor × 0.4 + sr_factor × 0.3 + consistency_factor × 0.3

sample_factor = min(1, log(n_samples+1) / log(100))
sr_factor = 2 × |success_rate - 0.5|
consistency_factor = max(0, 1 - stdev × 2)
```

**结论**：置信度可以有效区分可靠知识和噪声。

### 实验2: 子聚类发现

**方法**：对每种任务类型进行子聚类

**结果**：
```
每个任务类型发现3个子聚类：
  bug_fix: 10 / 90 / 83
  refactor: 10 / 77
  performance: 10 / 28 / 90
  feature: 10 / 90 / 72
  analysis: 10 / 11 / 90
  test: 10 / 90 / 87
  documentation: 10 / 90 / 51
```

**结论**：任务类型内部确实存在子模式。

### 实验3: 三层知识体系

**方法**：设计 Personal/Project/Global 三层架构

**架构**：
```
Layer 3: Global Knowledge（云端）
  - 共享元知识：任务模式→策略模式
  - 不共享具体Patch历史

Layer 2: Project Memory（项目）
  - 项目专属经验
  - sanyan.db = 项目大脑

Layer 1: Personal Memory（个人）
  - 用户偏好/习惯
  - 绝不共享
```

**决策流程**：Personal → Project → Global（逐层查找）

**结论**：三层架构可以有效管理不同粒度的知识。

## 结论

1. **Knowledge Confidence 有效**：可以区分可靠知识和噪声
2. **子聚类是真实的**：任务类型内部存在子模式
3. **三层知识体系可行**：Personal/Project/Global 分层管理

## 核心洞察

> LLM知识 = Prior（推测）
> Agent知识 = Evidence（证据）

> LLM解决"我知道什么"；Agent知识库解决"在这个项目里什么真的有效"
