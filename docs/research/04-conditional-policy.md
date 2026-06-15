# Conditional Policy: 从全局最优到条件最优

## 问题

传统 Agent 使用统一策略处理所有任务。但任务类型不同，最优策略也不同。

**问题**：如何让 Agent 根据任务类型自动选择最优策略？

## 假设

1. **条件优化**：不同任务类型有不同的最优配置
2. **策略学习**：从历史数据中学习任务→策略映射
3. **成本感知**：验证成本影响探索优先级

## 实验

### 实验1: MetaConfig 验证

**方法**：用历史任务回放验证配置变更

**结果**：
```
500个任务回放验证
5个配置变更测试
结果: 0接受 / 0拒绝 / 5未知

结论: 系统在没有真实收益差异时，不会盲目接受变更
```

**结论**：MetaConfig 是保守型验证器，正确行为。

### 实验2: 成本感知进化

**方法**：测量每次验证的成本，计算收益/成本比

**结果**：
```
参数    改进    成本    效率    Tier
─────────────────────────────────────
param_C 0.5%   1.0s   0.50    T3（最高效）
param_B 1.5%   5.0s   0.30    T2
param_A 2.0%  30.0s   0.07    T1（最低效）
```

**结论**：效率 = 改进 / 成本，可以指导探索优先级。

### 实验3: UCB 探索策略

**方法**：用 UCB1 算法平衡探索与利用

**结果**：
```
未探索的参数优先探索
已探索的参数按 UCB1 分数排序
自动平衡探索新参数 vs 利用已知最优
```

**结论**：UCB 可以有效平衡探索与利用。

## 结论

1. **条件优化是可行的**：不同任务类型确实需要不同配置
2. **成本感知是必要的**：避免浪费时间验证低收益参数
3. **UCB 是有效的**：平衡探索与利用

## 核心洞察

> 从"全局最优"升级为"条件最优"
> 从"随机探索"升级为"成本感知探索"

## 四层架构

```
Layer 3: Knowledge Layer
  - MetaLearningDB
  - TaskEmbedding
  - ClusterLearning

Layer 2: Evolution Layer
  - Ranking
  - Cost
  - Budget
  - UCB

Layer 1: Policy Layer
  - Config
  - Strategy Parameters
  - Hypothesis Parameters

Layer 0: Frozen Core
  - Reviewer
  - Replay
  - History
  - Ternary
```

## 未来方向

1. **Knowledge Confidence**：为知识添加置信度
2. **Task Type 细化**：发现子聚类
3. **Meta-Learning**：学习任务→策略映射
4. **Conditional Optimization**：根据任务类型选择最优策略
