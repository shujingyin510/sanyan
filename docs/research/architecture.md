# Evolution Runtime Architecture

## 四层架构

```
Layer 3: Knowledge Layer（知识层）
  │
  │  MetaLearningDB（项目经验数据库）
  │  TaskEmbedding（任务向量化）
  │  ClusterLearning（自动聚类）
  │  目标：不同任务→不同策略（条件最优）
  │
  ▼
Layer 2: Evolution Layer（进化层）
  │
  │  ParameterRanker（参数影响力排名）
  │  CostAwareRanker（收益/成本排名）
  │  ExplorationBudget（探索预算）
  │  UCBExploration（UCB探索策略）
  │
  ▼
Layer 1: Policy Layer（策略层）
  │
  │  ConfigSchema（可进化配置参数）
  │  StrategySchema（策略参数化）
  │  HypothesisSchema（候选参数）
  │
  ▼
Layer 0: Frozen Core（冰冻核心，不可修改）
  │
  │  Reviewer（代码审查）
  │  TernaryEngine（三态决策）
  │  PatchHistory（历史记录）
  │  TaskReplay（任务回放）
```

## 三层知识体系

```
Layer 3: Global Knowledge（云端）
  │
  │  共享元知识：任务模式→策略模式
  │  不共享具体Patch历史
  │  新用户开箱即用
  │
  ▼
Layer 2: Project Memory（项目）
  │
  │  项目专属经验
  │  sanyan.db = 项目大脑
  │  最有价值的一层
  │
  ▼
Layer 1: Personal Memory（个人）
  │
  │  用户偏好/习惯
  │  绝不共享
```

## 数据流

```
Task
  ↓
TaskClassifier → Task Type
  ↓
MetaLearningDB → 最优配置
  ↓
ConfigSchema → 应用配置
  ↓
Patch Evolution → 生成补丁
  ↓
Reviewer → 审查
  ↓
TaskReplay → 验证
  ↓
TernaryVerdict → TRUE/FALSE/UNKNOWN
  ↓
PatchHistory → 记录
  ↓
KnowledgeConfidence → 更新知识
```

## Frozen Core（不可修改）

| 组件 | 职责 | 为什么不可修改 |
|------|------|----------------|
| Reviewer | 代码审查 | 免疫系统 |
| TernaryEngine | 三态决策 | 决策核心 |
| PatchHistory | 历史记录 | 记忆系统 |
| TaskReplay | 任务回放 | 验证系统 |

## Evolution Surface（可进化）

| 组件 | 职责 | 风险 |
|------|------|------|
| Config | 配置参数 | 低 |
| Strategy | 策略参数 | 中 |
| Hypothesis | 候选参数 | 中 |

## 核心公式

### Knowledge Confidence
```
confidence = sample_factor × 0.4 + sr_factor × 0.3 + consistency_factor × 0.3
```

### Cost-Aware Efficiency
```
efficiency = improvement / cost
cost = verification_time + tokens/1000
```

### UCB1 Exploration
```
UCB_score = avg_value + c × sqrt(ln(total_plays) / n_plays)
```

## 核心洞察

> LLM知识 = Prior（推测）
> Agent知识 = Evidence（证据）

> LLM解决"我知道什么"
> Agent知识库解决"在这个项目里什么真的有效"

> 从"Agent改代码"升级为"可验证的局部自改进系统"
> 从"全局最优"升级为"条件最优"
> 从"静态Agent"升级为"情境Agent"
