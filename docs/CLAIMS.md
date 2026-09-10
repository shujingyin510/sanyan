# Agent 量化声明清账表（阶段 0 产物）

> 目的：把散落在 README / ROADMAP / `docs/research/` 的每个数字归账，
> 标注**来源、产生模块、性质、是否可复现、冲突点**，作为阶段 1（让每条可复现）的输入。
> 生成方式：静态分析（grep + 读源码）。**未实跑**——运行环境当时不可用，标 ⚠️ 处需本地跑确认。
> **2026-09-10 更新**：Agent 子系统已拆至 [sanyan-agent](https://github.com/shujingyin510/sanyan-agent)（自更新线冻结）。
> 本表中与 Agent 评测相关的「可复现入口」不再在本仓执行；冲突项已按下列权威源归账。

---

## ⭐ 最重要的发现：多数 agent 头条数字是「模拟产物」，非实证

`agent_causal_chain.py` 的 `run_experiment()` 不调用真实 LLM、不执行真实任务。它的「成功率」是：

```python
base_sr = match_score * (1 - difficulty * 0.3)  # match_score 来自硬编码 best_params
success = random.random() < (base_sr + 高斯噪声)
```

即：先定义「策略-任务匹配度」公式，再奖励匹配高的策略。于是 Knowledge Agent（挑接近
`best_params` 的策略）必然赢过 Baseline（固定策略）。**这个 40.9%→82.5% 的差距是模拟器
设计决定的，属于循环论证**，不能支撑「Knowledge → Success 因果链」这一实证主张。

同源报告 `agent_evolution_report.md` 自述方法为「生成 1000 个任务，用随机配置执行」，
故其下的知识迁移、任务分类、参数影响力、知识置信度等表**大概率同属合成模拟**。

> 含义：这些数字可以作为「设计意图 / 机制演示」展示，但**不能用「成功率」「因果链」
> 「+43.6%」这种实证措辞**。要变成真主张，需在真实任务上重做（见阶段 1）。

---

## 分类总览

| 类 | 含义 | 处理方向 |
|----|------|----------|
| 🟥 模拟产物（循环/合成） | 由合成模拟器产生，结论被其设计决定 | 改措辞为「机制演示」，或在真实任务上重做 |
| 🟩 有实证基础 | 注入/执行真实代码，真实工具链验证 | 补固定种子 + 提交结果工件即可定稿 |
| 🟨 半实证 / 低样本 | 需真实 LLM，但 N 小、单次、自设题库 | 提交原始逐题数据 + 多次重跑 |
| 🟦 已迁移 UR 仓库 | 属三态门控/LLM 推理工作，已独立成新仓库 | 从本仓 ROADMAP 移除，改链接 |
| ⬛ 冲突 / 待核 | 同一指标多处取值不一致 | 重跑定真值，统一全仓 |

---

## 清账明细

### 🟥 模拟产物（循环论证，最需改措辞）

| 声明 | 值 | 出现处 | 产生模块（历史路径，已迁 sanyan-agent） | 复现入口 |
|------|----|--------|----------|----------|
| 因果链成功率 | 40.9% → 82.5% → 84.5%（+43.6%） | README 实验1；evolution_report L595-605 | `agent_causal_chain.py` `run_experiment()` | ⚠️ 无 `__main__`，需自写驱动 |
| 知识迁移 | 配置 -4.6% / 规律 +27.9% | README 实验2；evolution_report L632-640 | `agent_meta_knowledge.py` / `agent_generalization.py` | ⚠️ 待确认 |
| 任务分类成功率 | test 72.2% … analysis 42.5% | README 实验4；evolution_report L689-695 | `agent_task_taxonomy.py` | ⚠️ 待确认 |
| 参数影响力 | max_auto_fix 48.8% … cooldown 7.0% | evolution_report L271-290 | `agent_param_importance.py` | ⚠️ 待确认 |
| 知识置信度 | documentation 151/90.0%/0.92 … refactor 87/66.1%/0.69 | README 实验3；evolution_report L335-343, L658-666 | `agent_knowledge_confidence.py` | ⚠️ 待确认 |
| 进化接受率/提升 | 接受 86%→100%，平均 +7.7%/+7.88% | evolution_report L166-208 | `agent_evolution.py` / `agent_validation.py` | ⚠️ 待确认 |

### 🟩 有实证基础（最接近可定稿）

| 声明 | 值 | 出现处 | 产生模块 | 复现入口 |
|------|----|--------|----------|----------|
| 安全 bug 检出 | 49 注入 / 检出 49（100%，7 类全满分） | benchmark_report L55-64 | `tests/test_agent_safety.py`（故障注入框架，注入真实 vm.py/evaluator.py 跑真实 ruff+pytest） | `python -X utf8 tests/test_agent_safety.py` ⚠️本地确认 |
| Reviewer 拦截 | Precision 66.7% / Recall 100% / 对抗 4/4 | evolution_report L179-181 | `agent_review.py` | ⚠️ 待确认是否真实补丁 |

### 🟨 半实证 / 低样本（需原始数据 + 多次重跑）

| 声明 | 值 | 出现处 | 产生模块 | 复现入口 |
|------|----|--------|----------|----------|
| 诚实度正确率 | 66.7% → 68.3% | benchmark_report L108 | honesty bench（需真实 LLM，N=100，单次，自设题库） | `sanyan bench --type honesty` ⚠️本地确认 |
| 校准 ECE | 0.336 → 0.251 | benchmark_report L109 | 同上 | 同上 |
| 认知越界率 | 50.0% → 33.3% | benchmark_report L110 | 同上 | 同上 |

### 🟦 已迁移 UR 仓库（2026-09-10：本仓 ROADMAP 已移除；本表仅作历史账）

| 声明 | 值 | 现状 |
|------|----|------|
| 人类盲评偏好 | ternary 79.7% preferred | **见 UR 仓** `docs/RESULTS` / README |
| 统计显著性 | p = 0.0287, 95% CI [0.01%, 0.79%] | **见 UR 仓** |
| Qwen 误报 | 1000-prompt FP 0.4% | **见 UR 仓** |
| GEMM / 推理性能 | 66 GFLOPS、4ms/token 等 | **见 UR 仓** |
| UR≈0.30 叙事 | 单一阈值 | **已升级**：UR 仓主叙事为 R1–R4 周期谱；0.30=短波子带特例 |

### ⬛ 冲突 / 待核（同指标多值）

| 指标 | 权威值（已归账） | 过时值 | 状态 |
|------|------------------|--------|------|
| 安全检出率 | **100%（49/49）** — `docs/research/agent_benchmark_report.md` | 旧 ROADMAP 的 98% | ✅ **已消**：旧 ROADMAP 已重写且不再含该数字；本仓不再重跑（入口在 sanyan-agent） |
| 认知越界改善 | **-16.7%（50.0%→33.3%）** — 同报告 | 旧 ROADMAP 的 -11.5% | ✅ **已消**：同上 |
| 迁移 baseline | 见 sanyan-agent / 知识库（合成模拟） | evolution_report 同文两值 | ⚠️ **挂起**：自更新线冻结，解冻后在 sanyan-agent 归账 |
| 因果链命名分层 | **五层架构**为全仓唯一叙事 | 历史「四层进化」 | ✅ **已消**：README 已删 Agent 进化正文，只留迁出指针 |

---

## 给阶段 1 的优先动作（按性价比）

1. **先修措辞，零成本最高收益**：把 🟥 类的「成功率/因果链/+43.6%」改成「机制演示（合成模拟）」，
   README 实验1 顶部加一句「本实验为合成模拟，用于展示机制，非真实任务实测」。这一步立刻消除最大的可信度风险。→ **README 已加警告（完成）**
2. **统一 ⬛ 冲突**：安全/越界冲突已按 research 报告权威值归账（98%/-11.5% 来自已删除的旧 ROADMAP）。迁移 baseline 冲突挂起至 Agent 解冻后在 sanyan-agent 处理。→ **本仓完成**
3. **移走 🟦 UR 内容**：ROADMAP 的盲评/p 值/GFLOPS 改为「见 UR 仓库」链接。→ **2026-09-10 完成**（`docs/roadmap.md` 重写）
4. **定稿 🟩 安全基准**：给 `test_agent_safety.py` 固定种子 + 提交 `results/safety.json`，文档引用工件。
5. **补 🟨 原始数据**：诚实度基准提交逐题打分表 + 题库，支持从数据重算。
6. **真正的实证实验（最大工程量，最高价值）**：在真实任务上做「三态门控 vs 二值基线」的
   自信错误率对照——这是把 🟥 的机制演示升级成真主张的唯一路径。
   **2026-09-10 起归属 sanyan-agent；自更新线冻结，解冻后再议。**

> 注：所有 ⚠️ 复现入口均未实跑验证（环境不可用）。阶段 1 第一件事即本地逐条跑通。
