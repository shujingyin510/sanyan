# 三言 Agent 架构重构计划

目标：把"清单庞大但真实运行路径很小"的现状，收敛成**薄核心 + 能力插件**，
同时**保留所有做得好或有潜力的部分**，而不是删功能。

## 原则

1. **保留，不删除。** 实验性子系统（进化、淘汰赛、多 Agent、模型路由、metaconfig、
   并行执行……）一律保留为"能力插件"，只是改成按需懒加载，不在 `__init__` 里全建。
2. **每一步都跑得过测试。** 每个阶段是一个独立、可回滚的小改动，合并前必须
   `pytest` 全绿。架构动到哪，测试覆盖到哪。
3. **一次只动一个 seam。** 先立契约（类型边界），再迁移调用方，最后删旧路径。
4. **净模块数应当下降。** 新增的只有少量"脊梁"模块（契约、存储、注册表）；
   它们落地后，重复实现（两条 LLM 路径、5 套学习存储、3 处淘汰赛）逐步合并。

## 目标形状

```
core (薄、必跑、全测)
  ├─ contracts.py      ToolResult / LLMProvider          ← 已建
  ├─ store.py          单一 SQLite + 路径解析 + 迁移        ← 阶段 2
  ├─ loop.py           agent 主循环（停止条件、记忆、规则/模板快捷路径）
  └─ registry.py       能力注册表（懒加载 + feature flag） ← 阶段 1

capabilities (可选、懒加载、保留的潜力件)
  ├─ tournament/       HypothesisGenerator / TournamentFallback
  ├─ evolution/        ConstrainedEvolutionSystem / AgentCodeModifier
  ├─ routing/          ModelRouter（多模型 + 成本降级）
  ├─ multi_agent/      AgentCoordinator
  └─ learning/         经验 / 领域知识 / 规则学习（合并为一套）
```

## 现状对照（为什么这么改）

- `AgentRuntime.__init__` 一次实例化约 30 个子系统 → God Object，构造慢、难单测。
- 约 19 个 `.db`，各模块各开各的、路径规则不一（根目录 vs `agent_system/`）→ 状态分裂。
- 控制流靠扫中文子串（`'未找到'`/`'失败'`/`'真'`/`'假'`）→ 脆弱。
- 重复实现：2 条 LLM 路径、5+ 套学习/记忆、3 处 tournament。

## 分阶段

### 阶段 0 —— 已完成（安全清理 + 脊梁）
- 删除 `_run_core` 不可达分支；移除重复的 `tool_learner` 写入与未接线的
  `ModelRouter` 实例化；删掉孤儿 `_execute_hypothesis` / `_run_tournament_fallback`
  方法。**注意：只删了死接线，能力类（HypothesisGenerator/Tournament/ModelRouter）
  全部保留。**
- 修复 CI mypy 报错（`research/tokenizer_dsl/*`）。
- 新增 `contracts.py`（`ToolResult` / `LLMProvider`）+ 单元测试。
- `LLMHandler` 与 `ModelRouter` 各加 `complete()`，双双满足 `LLMProvider`。
- 验证：`pytest tests/test_contracts.py -q`、`mypy .`。

### 阶段 1 —— 能力注册表 + God Object 瘦身
- 新增 `core/registry.py`：`register(name, factory, *, flag=None)`，懒加载。
- 把**非热路径**子系统从 `__init__` 移到注册表（懒加载）：evolution、tournament、
  metaconfig、parallel、multi_agent、routing、git_batch_learner……
- 用 `@property`/`__getattr__` 维持 `rt.<name>` 访问不变（`test_agent_v5` 里
  `assertIsNotNone(rt.hypothesis_generator/tournament/failure_classifier)` 仍过）。
- 风险：中（改构造语义）。验证：全量 `pytest`，重点 `test_agent_v5.py`。

**进度（2026-06-30）—— 已完成：**
- 注意：实测构造仅 3ms（多数 DB 类按操作开/关连接，不在 `__init__` 连），故本阶段价值
  在**收敛机制 / 可测性**，而非提速。
- 新增 `agent_system/registry.py` 的 `LazyRegistry`：`register(name, factory, *, flag=)`，
  首次 `get` 构造并缓存；`flag` 为可选 `()->bool` 开关（关时抛错，供 feature flag 启停）。
- `AgentRuntime` 把 13 个非热路径能力（tournament、parallel_executor、hypothesis_paraller、
  evolution、coordinator、pipeline、composer、conditional、shared_context、shared_symbols、
  progress_display、prompt_evolver、ab_rollout）从「`self._x=None` + `@property`」样板
  收敛进一处声明式注册；新增 `__getattr__` 路由 `rt.<name>`（仅常规查找失败时触发，
  用 `self.__dict__.get('_caps')` 防递归；未知属性仍 `AttributeError`）。净删 71 行、
  消掉 11 段 @property + 2 个急切但未用的构造（tournament/parallel_executor）。
- 守护：`tests/test_registry.py`（懒构造+缓存、未知 KeyError、flag 门控、runtime 路由）。
  验证：238 passed（含 `test_agent_v5` 的 `assertIsNotNone(rt.tournament)` 等仍过）、零回归。

**进度（2026-07-01）—— 阶段 1 续：构造侧诚实结论 + 测试密封：**
- 复核构造：`AgentRuntime.__init__` 实测 3ms（DB 类按操作开/关连接、不在构造期连），残余 eager
  子系统多为廉价或热路径必用；再往注册表搬只是**增间接、无实测收益**，故**不为搬而搬**
  （原则 #4「不加投机层」）。真正的可测性痛点在别处 ⬇。
- 测试密封（真痛点）：此前 5 个构造/运行 `AgentRuntime` 的测试（test_agent_v5 / agent_runtime /
  contracts / fallback / registry）**未隔离 `AGENT_DATA_DIR`**，会在真实 `agent_system/` 里生成并
  改写 `agent.db`、污染开发者数据、且各测试共享同一 DB（非密封）——整轮开发我都在手工 `rm agent.db`。
  现加 `tests/conftest.py` 的 **autouse 夹具**：每个测试独享 tmp 数据目录。
- 验证：8 个 agent 套件 235 passed；混跑 agent+非 agent 71 passed；**运行后 `agent_system/agent.db`
  不再生成**（密封成功、零污染、无需手工清理）；对非 agent 测试无影响（仅设一个它们不读的环境变量）。

### 阶段 2 —— 单一存储层
- 新增 `core/store.py`：规范数据目录（`AGENT_DATA_DIR` 环境变量，缺省
  `agent_system/`），`db_path(name)`，`schema_version` 表 + 迁移钩子。
- 先**统一路径**（消灭根目录 vs `agent_system/` 重复 db、状态分裂），各模块仍
  各自建表；再逐步**并表**进单一 `agent.db`。附数据迁移脚本。
- 风险：中高（持久化）。验证：针对每个 store 写读写往返测试后再迁。

**进度（2026-06-30）—— 路径统一已完成：**
- `paths.py`（`data_dir()` / `db_path()`，认 `AGENT_DATA_DIR`）已建。
- 全部 12 个 agent_system 模块的 `DB_PATH`/`db_path` 改走 `paths.db_path('x.db')`：
  cost_aware、knowledge_confidence、metaconfig(×2)、param_importance(×2)、
  review(×2)、task_taxonomy、strategy(×2)、domain、learning、extract_git_tasks，
  外加先前已转的 evolution_v2、knowledge。`grep` 零残留旧式 `os.path.join(ROOT,'*.db')`。
  命名冲突的 domain / learning（局部 `db_path`）改用 `from agent_system import paths`
  + `paths.db_path(...)`。默认目录不变（均为 `agent_system/`），故**无需数据迁移**；
  收益是 `AGENT_DATA_DIR` 现对所有 DB 一致生效，且为后续并库扫清入口分裂。
- 验证：`pytest tests/test_contracts.py tests/test_agent_v5.py tests/test_agent_safety.py`
  → 167 passed；全量 agent 相关测试 0 失败。
- 遗留：仓库根的 `agent_evolution_memory.db` 是 evolution_v2 切到 `agent_system/`
  之前的**陈旧副本**，现已无人写入，可由用户确认后删除（属数据文件，未擅自删）。
  `run_agent.py` 仍在根目录写 `agent_state.db`（顶层脚本，按设计在根，未纳入本次）。
**进度（2026-07-01）—— 单一 `agent.db` 已落地（非破坏迁移）：**
- 新增 `agent_system/store.py`：`connect(name='agent.db')`（认 `AGENT_DATA_DIR`、保证
  `_schema_version` 表）、`get_version/set_version(conn, component, v)`（各子系统独立版本号）、
  `adopt_legacy(conn, legacy_db, tables)` —— `ATTACH` 旧独立库，**仅当目标表为空**时
  `INSERT ... SELECT` 拷入，**不删旧库**（可回滚），返回实际迁移表数。
- `ExperienceStore` 默认库由 `agent_experience.db` 改为并入单一 `store.AGENT_DB`（`agent.db`）：
  `_init_db` 建表后，若 basename==agent.db 则 `adopt_legacy('agent_experience.db', _TABLES)`
  一次性搬入历史经验并 `set_version(conn,'experience',1)`；显式传 `db_path=` 时不触发迁移
  （测试与旧库读写仍可点名旧路径）。
- 非破坏性实测确认：集中跑 `test_agent_v5` 构造 `AgentRuntime→ExperienceStore`（默认路径、
  未隔离 `AGENT_DATA_DIR`）后，`agent_system/agent.db` 自动生成、含 4 表 + `_schema_version`
  (`experience`=1) + 旧库 `tool_stats` 9 行如数搬入；旧 `agent_experience.db`（81920B）
  字节未动、保留可回滚。`agent_system/*.db` 已被 `.gitignore`（第 226 行）覆盖，不污染仓库。
- 守护：`tests/test_store.py`（4 测：版本往返、非破坏拷贝、目标非空跳过、ExperienceStore
  端到端并库 + 版本已记）；`test_learning_store.py`（7 测）继续全过。
- 验证：`test_agent_v5 + test_agent_runtime + test_agent_safety + test_store + test_learning_store`
  → **210 passed、零回归**；`test_store + test_learning_store` 单跑 11 passed。
- 遗留（后续随阶段 1 注册表懒加载逐个并入）：其余各自独立库的 store（domain / strategy /
  review / param_importance / task_taxonomy / cost_aware / knowledge* / metaconfig……）尚未并入
  `agent.db`，按原则 #1「保留不删除」暂留独立表；`store.adopt_legacy` 已备好非破坏并库入口，
  可逐个迁移。根目录陈旧副本 `agent_evolution_memory.db` 仍待用户确认后删除（属数据文件）。

**进度（2026-07-01）—— 选择性并库：DomainKnowledgeLayer 也并入 agent.db：**
- 原则：不为并而并——只并**活读路径 + eager 构造**的 store。经清点，除已并的 `ExperienceStore`
  外，`AgentRuntime.__init__` 里 eager 且每任务读的只有 `DomainKnowledgeLayer`（领域分类
  缓存 → 置信度反馈）。其余（strategy/prompt_evolution 懒加载、git_task/task_replay 仅 CLI、
  各实验件）按原则 #1 暂留独立库，`adopt_legacy` 入口已就绪、可后续逐个并。
- 改动：`agent_domain.py` 默认库 `domain_knowledge.db` → `store.AGENT_DB`；`_init_db` 建
  `domain_cache` 表后，若 basename==agent.db 则 `adopt_legacy('domain_knowledge.db',('domain_cache',))`
  + `set_version(conn,'domain',1)`。表名与 experience 4 表无冲突，同库共存。
- 非破坏实测：`test_agent_v5` 构造 runtime 后 `agent.db` 同时含 `domain_cache`(10 行) 与
  experience 4 表，`_schema_version`={domain:1, experience:1}；旧 `domain_knowledge.db`
  10 行 `integrity_check=ok` 完好保留。
- 守护：`test_store.py` 增 `test_domain_layer_merges_into_agent_db`。验证：`test_store +
  test_learning_store + test_agent_v5` → 170 passed、零回归。

### 阶段 3 —— 工具层结构化
- 工具返回 `ToolResult`，停止 `路径|内容` 管道编码与子串嗅探。
- `TernaryEngine` 改吃 `result.trit`，不再扫文本。
- 风险：中。验证：工具单测 + `test_agent_safety.py`。

**进度（2026-06-30）—— 输出 seam 已完成：**
- 生产侧：`agent_tools.py` 的文件/测试/git 类工具（analyze、find_symbol、read_file、
  search_code、replace_in_file、replace_all、write_file、list_files、run_test、
  run_shell、git_diff/status/stash/reset/commit、run_assembly）改返回 `ToolResult`，
  状态由工具自报（成败由 `rc`/命中与否决定，不再靠输出文本里有没有 '失败'/'错误'）。
  新增 `_ok/_err/_missing/_empty` 构造器，保证 `str(result)` 与旧返回**字节级一致**
  （OK/NOT_FOUND/EMPTY 入 data，ERROR 入 error，`__str__` 返回 data or error）。
  多 Agent 工具（`_spawn_*`/`_agent_*`/`_vote_spawn`）**不迁移**——它们的返回被字符串
  拼接消费；`done` 仍返回字符串（最终答案抽取）。
- 消费侧：`ternary_engine.classify` 加 duck-typed 状态快路径（status→cog），不 import
  契约、保持引擎对 IoT/Village 独立；`FailureClassifier.classify` 对 OK/NOT_FOUND/EMPTY
  短路，ERROR/BLOCKED 仍落到文本逻辑细分 SCHEMA_ERROR/TIMEOUT。两者对**字符串**输入
  行为不变（纯超集）。`agent_execution.py` 的 `ternary.step(tool, str(result))` 改传原始
  `result`，使 RuleExecutor 路径也读结构化状态。
- 修掉的真 bug：`search_code('失败')` 命中结果旧逻辑判 NEGATE（成功被当失败）；成功的
  `run_shell` 若输出含 'error'/'失败' 字样也被误判。现按 status/rc 判，已 smoke 验证。
- 验证：`pytest tests/test_agent_runtime.py tests/test_contracts.py tests/test_agent_v5.py`
  全绿（新增 2 个测试：not_found 状态、命中即 AFFIRM）；全量套件失败数与改前持平（41，
  全部为既有 sugar/编译器工作区改动 + 缺 llvmlite，与本次无关）。
- 未做（留后续）：输入侧 `路径|旧|新` 管道编码仍在（动它要改 LLM 工具调用契约/parser，
  风险更高，单列）；工具结果尚未带 `meta`（行号/计数等）供更细决策。

**进度（2026-07-01）—— 收尾：消灭 runtime 残存文本嗅探 + 停止条件抽出：**
- 承接输出 seam：Phase 3 只接了 `ternary.classify`/`FailureClassifier` 两个消费方，**runtime
  自身的裁决仍在嗅子串**。现补齐：
  * `run_test` 工具**自报** `meta['passed']`（`_ok/_err` 加 `**meta`）；`_run_legacy` 的重试
    判定由 `'FAIL'/'失败' in str(result)` 改走 `AgentRuntime._test_failed(result)`（meta['passed']
    → 结构化 status → 仅旧裸串才回退文本）。修掉与 `search_code('失败')` 同类的**假重试**：
    成功结果文本里恰含"失败"二字不再误判。
  * `agent_hypothesis.FailureClassifier._looks_logically_wrong`、`agent_parallel._validate_one`
    同样改**结构化优先**（读 meta['passed'] / `.failed`，旧串回退文本）。
  * `_update_confidence` 原读死键 `result['ternary']`（主循环从不设置）→ 领域置信度反馈在
    主路径**恒为 no-op**（'真'/'假'/'不确定' 三分支实为死代码）。现抽纯函数 `_confidence_delta`，
    改读主循环**确实产出**的结构化 memory（history 各步 trit / modified / failures），增量幅度
    沿用原作者取值——**修好一条静默失效的反馈回路**，非仅删死码。`_pre_analyze` 的 `find_symbol`
    结果门也由 `'未找到' not in str(r)` 改读 `.ok`。ternary/hypothesis 的文本分支保留为旧裸串
    兜底（ToolResult 早被 status 快路径短路、不再触达）。
- 停止条件抽出（target-shape 的 core/loop.py 之「停止条件」）：把 `_run_legacy` 里**内联、
  无法单测**的退化判定抽成 `agent_system/loop_policy.py` 纯函数——`results_degenerate`（连续
  同输出）、`llm_output_ur`（LLM 字符级唯一率退化）、`context_too_large`（超长压缩）。循环 3 处
  内联表达式改调纯函数，**逐位等价**、热循环更薄。当时**暂缓**整体搬 `_run_legacy`（依赖
  ~20 个 rt.* 属性、属最高风险），留待提交检查点后单独进行——见下方「loop.py 抽出」。
- 守护：`tests/test_structured_verdict.py`（8 测：meta 自报、成功含"失败"不误判、status 兜底、
  旧串回退、`_confidence_delta` 捷径+结构化信号）、`tests/test_loop_policy.py`（6 测：退化/边界/UR）。
- 验证：14 个 agent 相关套件（含 `test_deadloop` 循环退化） → **287 passed、零回归**。
- 关于阶段 4 provider 命名撞车（`contracts.LLMProvider` 协议 vs `agent_llm.LLMProvider` 具象基类
  + 11 子类）：二者分居不同模块、**运行时无冲突**，改名要动 11 子类且零功能收益 = 纯 churn，
  按计划判断**不做**；LLM seam 本身已在阶段 4 收口（runtime 单漏斗走 `llm_provider.complete`）。

**进度（2026-07-01）—— loop.py 抽出（在提交检查点 `95cc000` 之后）：**
- 把 `AgentRuntime._run_legacy`（176 行、最长的编排方法：规则快捷路径 → LLM 多轮 → 退化/超时/UR
  停止 → 工具执行 → 反思重试）整体搬到 `agent_system/loop.py` 的 `run_legacy(rt, ...)`，runtime 侧
  变 5 行薄委托。用脚本机械抽取（`self.`→`rt.` + **裸 self 安全检查**），**行为逐位一致**。
- 收益：God Object 文件 `agent_runtime.py` 1115 → 969 行；主循环有了独立模块边界，且**可脱离完整
  runtime 单测**——`tests/test_loop.py` 用最小 mock rt 驱动 dry_run 三分支（这是抽出真正兑现的可测性）。
- 诚实定性：当前仍属**「位移建模」**——`run_legacy` 还依赖 rt 约 20 个属性/私有方法，是"把 loop
  放进 loop.py"而非"把 loop 与 runtime 解耦"。后续可随阶段 1 能力注入逐步收窄 rt 接口。
- 验证：15 个 agent 套件（含 test_loop / test_deadloop / 跑真实任务的 test_agent_v5）→ **290 passed、零回归**。

### 阶段 4 —— 合并重复实现
- LLM：调用方统一走 `LLMProvider`；`ModelRouter` 作为多 provider 实现接入。
- 学习/记忆：合并为一套有明确**读路径**的存储（删掉只写不读的）。
- 淘汰赛：以 `agent_execution.TournamentFallback` 为唯一实现，接到失败兜底。
- 风险：中。验证：全量 `pytest`。

**进度（2026-06-30）—— 学习/记忆：单一写入路径已收敛：**
- 审计结论：DB 落盘的「学习」类里，真正接到**活路径**的只有 `ExperienceStore`
  （读路径 = `AdaptiveToolSelector.recommend/should_avoid`）、`DomainKnowledgeLayer`、
  `git_batch_learner`、`PromptEvolver`(懒)、`TaskReplay`(CLI)。其余（CostTracker、
  EvolutionMemory、ClusterLearning、TaskSimilarity、ConfidenceAwareKnowledge、
  ConfigPatch、ParameterRanker、StrategySchema、ToolSelectionLearner、MetaLearningDB…）
  只在各自模块 `__main__`/测试里实例化 —— 属**实验能力件**，按原则 #1「保留不删除」，
  本次**不删**，留作懒加载能力（阶段 1 注册表落地后归位）。
- 真 bug 修复：`LearningHandler`（Phase 0/1 抽出）一直**未接线** ——`AgentRuntime`
  仍内联了逐字重复的 `_save_experience/_lookup_style/_learn_from_task/_collect_change_details/
  _infer_style_from_task/_save_style_rule`（共 ~224 行），且 `run()` 每次重绑 `self.memory`，
  而 handler 在构造期捕获的是**过期空 memory**（这正是当年放弃接线的原因）。
  现：handler 三个公开方法改**按次接收 memory 参数**（消除捕获陷阱），`run()` 直接委托
  `self.learning_handler.{lookup_style,save_experience,learn_from_task}(..., self.memory)`，
  runtime 内联副本全部删除；`batch_learn_from_git` 留薄壳供 CLI。净删 224 行。
- 守护：新增 `tests/test_learning_store.py`（5 个）——`ExperienceStore` 读写往返
  （可靠度/失败模式/相似任务）+ handler 按传入 memory 落库 + lookup_style 安全空返回。
- 验证：聚焦套件 244 passed；全量失败数仍 41（全为既有 sugar/self_host/llvm，与本次无关），
  通过数 +5（恰为新测试）→ 零回归。
- 双计数 bug 已修复：`tool_selector.record_outcome`（每步，仅主循环触发）与
  `save_experience`（收尾，遍历 `memory['history']`）过去**都**调 `record_tool_use` →
  主循环工具被记两次。定调：`save_experience` 为**唯一** tool_use 记录源（每次执行一条、
  覆盖主循环/验证/干跑三条 history 写入路径，恰好一次）；`record_outcome` 去掉
  `record_tool_use`、只保留 `update_recommendation`（推荐表，唯一且需每步）。
  守护：`test_learning_store.py` 增 2 测（record_outcome 不计 tool_use；端到端 success 计数=1）。
  验证：全量 41 失败不变 / 2307 通过（+2 新测试）→ 零回归。

**进度（2026-06-30）—— LLM seam 已收尾：**
- 现状核对：runtime 早已**单一漏斗**（所有子系统注入 `self._llm_call`），但 `_llm_call`
  直接调具体的 `llm_handler.llm_call()`，未走契约。
- 改动：新增 `self.llm_provider: LLMProvider = self.llm_handler`（可替换句柄）；`_llm_call`
  改走 `self.llm_provider.complete(prompt, system=…)`，`system` 显式传入（override 优先，
  否则用 `self._system_prompt`）——与旧「先 mutate handler._system_prompt 再 llm_call」
  逐位等价，但不再 mutate provider，故对任意满足协议者（LLMHandler / ModelRouter）成立。
  `parse_tool` 等 handler 专有方法仍走 `self.llm_handler`。**没有**把未接线的 ModelRouter
  设为默认（不引入只写不读的投机路径）——它现在是「可一行替换」的候选实现。
- 守护：`test_contracts.py` 增 `test_runtime_routes_llm_through_provider_seam`（替换 provider
  后 `_llm_call` 走其 complete、token 追踪、override 优先）。验证：168 passed；全量 +1、零回归。
- 遗留命名撞车（未改，单列）：`contracts.LLMProvider`（协议）与 `agent_llm.LLMProvider`
  （旧的具体基类，10+ provider 子类继承它）同名。重命名基类要动 10+ 子类，纯属表层、
  风险>收益，留待 provider 体系整体归并时一并处理。

**结论（2026-06-30）—— 淘汰赛：前提不成立，不做强行合并：**
- 审计后「3 处 tournament 重复」并不成立——它们是**不同层的不同东西**：
  `Tournament`(agent_hypothesis) = 候选两两比较算法（ThresholdTuner + `_compare`）；
  `TournamentFallback`(agent_execution) = 失败兜底**编排**（生成→并行验证→执行最优）；
  `CandidateTournament`(agent_evolution_v2) = 进化补丁候选打分。三者签名/职责各异，
  且 `parallel_validate` vs `Tournament._parallel_phase` 返回类型都不同，非复制粘贴。
- 失败兜底路径在**阶段 0 已被有意拆线**（删了 `_execute_hypothesis`/`_run_tournament_fallback`）。
  `TournamentFallback` 正因依赖被删的 `_execute_hypothesis` 而**搁浅**（全仓零实例化）；
  `self.tournament`(Tournament) 仅构造、`test_agent_v5` 断言非空，并无活调用。
- 据原则 #1「保留不删除」+ 不加投机路径：**不删**这些能力类，也**不**重新接线兜底
  （那是 feature，不是去重）。可选的真去重为零。若日后要恢复兜底，规范实现取
  `TournamentFallback`；若要瘦身构造，把 `self.tournament` 改懒加载属于**阶段 1**。

**进度（2026-06-30）—— 失败兜底已按用户要求恢复（feature）：**
- 规范实现取 `agent_execution.TournamentFallback`（计划指定）。在 `_run_core` 末尾**显式**
  触发（非死分支）：`_run_legacy` 跑完后，`_should_fallback` 判定「未兜底过 + 无文件产出 +
  失败累计≥3」则启动；`tournament_used` 标志防递归。
- `_execute_hypothesis` 不照搬旧版（旧版依赖已漂移的 ctx 对象架构 + 未导入的 FailureMode）：
  改为把择优假设的描述/建议工具链作为提示，**复用已测的 `_run_legacy`** 跑一轮，行为可控可测。
- 守护：`tests/test_fallback.py`（4 测）——should_fallback 逻辑、单假设择优执行并注入提示、
  无假设优雅返回、execute_hypothesis 只委托不递归。验证：234 passed、零回归。

### 阶段 5 —— 配置/密钥集中
- 一个 typed config 加载一次；密钥只走环境/密钥管理，禁止写入 `.san` 源码或
  `str.replace` 注入。
- 风险：低。验证：启动冒烟 + `mypy`。

**进度（2026-06-30）—— 已完成：**
- 反模式定位：`run_agent.py` 用 `src = src.replace('sk-你的key', api_key)` 把真实密钥
  **注入 `.san` 源码文本**（主 Agent + 子 Agent 两处），还打印密钥长度。密钥会进入内存
  源码串/日志/缓存，是泄露面。
- 新增 `agent_system/config.py`：不可变 `AgentConfig.from_env()`（api_key/provider/model/
  model_url/timeout，一次加载）+ `api_key_from_env()`。密钥**只从环境**（`SANYAN_API_KEY`
  优先、`LLM_KEY` 兼容）读，占位符（含 "你的"）一律视为未设置。
- 接线：`load_api_key()` 的环境读取改走 `config.api_key_from_env()`（typed 单入口）；
  保留 `.san` 源码兜底但已非首选。删掉两处 `str.replace` 注入 + 密钥长度日志；`.san` 侧
  本就用 `环境变量("SANYAN_API_KEY")` 读取，而 `init_evaluator`/子 Agent 路径均已 setenv，
  故删注入后密钥仍经环境正常传递（行为不变、不再落源码）。
- 守护：`tests/test_config.py`（env 读取、占位符视空、LLM_KEY 兜底、类型字段+默认、
  坏 timeout 回退）。验证：全量 41 失败不变 / 2321 通过（+13 新测试）→ 零回归。
- 未做（更大、单列）：`LLMHandler._get_config` 仍从 `.san` 求值器动态读模型/URL/超时
  （非密钥），如要统一进 `AgentConfig` 需兼顾 `.san` 动态改配置语义，风险更高，留待后续。

## 当前阻塞
本环境沙箱无法启动，`pytest`/`mypy` 未能由我执行。阶段 0 的改动已用静态方式
核对（精确匹配改写、grep 零残留、保留测试依赖属性）。请在本地跑：

```
mypy .
python -X utf8 -m pytest tests/test_contracts.py tests/test_agent_v5.py -q
```

绿了再推进阶段 1。

> 注（2026-07-01）：上述"沙箱无法启动"已不成立——本轮所有阶段均已本地跑通 pytest，
> agent 相关 15 套件 290 passed、零回归；重构主体（阶段 0-5 + loop.py 抽出）已提交于分支
> `agent-refactor-seams`（`95cc000` 及其后续）。以下为下一步战略方向。

---

# 三言：自我更新的 agent（迭代自身 + 三言语言）

**目标**：一个能对**自身代码**与**三言编译器/stdlib**做**有界、测试锚定、人可门控**的自迭代 agent。
**不追求**无界/全自主/递归自我改进（研究前沿，会撞奖励作弊、能力停滞、自举崩溃）。

## 为什么可行（护城河）
自我修改 agent 多数死在"没法稳健判断改动变好还是变坏"。而三言**自举 + 有测试套件 + 已写
`verify_bytecode_compiler`/`verify_vm_consistency`** → 天然有个**强、难作弊的 oracle**：
一个改动"好" ⟺ `全量测试绿(对齐既有基线) + 三言仍能编译自己 + VM 自洽`。

## 现成零件（约 70-80%，但多为"写了未接线"，需先验真再拼）
- `agent_evolution_v2.py`：`propose_candidates` / `generate_patch` / `apply_patch` / `rollback_patch`
  （补丁 提议→应用→回滚 全生命周期）。
- `agent_evolution.py`：`verify_bytecode_compiler` / `verify_vm_consistency` / `verify_change`（验证器）。
- `agent_loop_monitor.py`：`verify_clean` / `verify_no_stash` / `verify_after_rollback`（git 安全护栏）。
- `ExperienceStore`（学习）、`extract_git_tasks`（任务挖掘）、本轮的结构化工具/loop seam。

## 两条不可动摇的红线（先钉死）
1. **oracle 在 agent 写权限之外**（头号风险=奖励作弊）：agent 不得改判它自己的测试/`verify_*`；
   若要改，必须人工复核。否则它迟早删失败测试、弱化断言来"作弊"。
2. **worktree 隔离**：运行中的 agent **绝不改自己的活进程**——改副本、worktree 里验证、下一轮才生效。

## 分阶段路径
- **P0（本轮基本完成）**：结构化地基（ToolResult / 密封测试 / loop seam）。重构不是绕路，是铺跑道。
- **P1 —— 拼一条闭环（当前在做）**：单任务安全自编辑。任务 → 独立 git worktree → 生成补丁
  （evolution_v2）→ **硬 oracle**（全量套件 vs 41 基线 + `verify_bytecode_compiler` +
  `verify_vm_consistency` + 自举）→ 过则留、否则 `rollback` → **人工合并**。先**验真**现成件是否真跑通。
- **P2 —— 自造任务**：从仓库挖 concrete 可验证任务（失败测试 / TODO / 超长函数 / 覆盖缺口）。
- **P3 —— 候选淘汰赛**：一任务生成 N 候选补丁，各在 worktree 过 oracle，选最优或全弃（CandidateTournament）。
- **P4 —— 元循环**：把 P1-3 指向 `agent_system/` 自身。安全关键：改**副本**，用**改后的 agent 跑
  固定 held-out 评测集**看能力升降，才提升。
- **P5 —— 自主度旋钮**：从全人工门控起步，只对"可证明安全"的改动（只加测试 / 只修一个失败测试且
  改动 < X 文件）逐步自动合并。

## P1 最小闭环设计（落地）
新增 `agent_system/self_update.py`（暂名），一个 `SelfUpdateLoop`：
1. `run_task(task, target_files)` → 在 `git worktree` 建隔离副本；
2. 调 agent（`run_agent` / `AgentRuntime`）在副本里改代码；
3. **oracle 门**：副本里跑 `pytest`（比对基线失败数不增、通过数增）+ `verify_bytecode_compiler`
   + `verify_vm_consistency`；任一不过 → `rollback` + 记录失败模式（喂 ExperienceStore）；
4. 全过 → 产出一个**待人工合并的分支/补丁**（不自动合并，遵守红线）。
守护：`tests/test_self_update.py` 用假 oracle/假 agent 驱动"过则留、败则回滚"两条路径。

**进度（2026-07-01）—— P1 最小闭环已落地 + 验真：**
- **验真的关键发现（印证红线①）**：现成的 `DifferentialVerifier`（本想当 oracle）是**假绿**的——
  (a) 它把三言代码当命令行参数传给 `main.py`，而 `main.py` 只吃**文件路径** → 两后端全失败；
  (b) 更危险：一致性逻辑在"所有后端都失败→outputs 为空"时 `consistent` 保持默认 `True`，
  于是 **全崩也算"一致"、success_rate=1.0**。在这种 oracle 上建自更新＝把一切改坏也被接受。
  （另：它的两个"后端"其实都是默认 VM，非"解释器 vs VM"，差分名存实亡。）→ 故 P1 **不用**它，
  改用**最强、最难作弊的 canonical oracle = pytest 基线**（含 self_host/VM/compiler，比对 41 基线、
  无输出归一化难题）。`DifferentialVerifier` 的 fail-closed 修复留作单列（安全地雷）。
- **新增 `agent_system/self_update.py`**：`SelfUpdateLoop(repo_root, oracle)` —— 隔离 git worktree
  （仓库外临时目录）→ 调 `edit_fn(wt)` 改副本 → 捕获 diff（无改动即拒）→ **fail-closed oracle**
  （异常/超时/摘要不可解析/失败数>基线/有 error 一律拒）→ 过则 `worktree remove` **保留分支供人工
  合并**、败则 `worktree remove` + `branch -D` **整体回滚**。主工作树全程不动、**绝不自动合并**（红线①②）。
  附 `parse_pytest_summary` + `make_pytest_oracle(baseline_failed, scope, runner=)` + `combine_oracles`。
- **守护 + 验真**：`tests/test_self_update.py`（7 测：接受留分支/拒绝整体回滚/无改动拒/oracle 异常
  fail-closed/oracle 见 worktree 内容/摘要解析/基线门，用一次性 tmp git 仓库跑真 worktree 机制）；
  另做**真 sanyan 仓库端到端 smoke**：无害改动 + 真 pytest 快子集 oracle → accepted、产出分支
  `self-update/…`、主工作树未动、worktree 自清理。全绿、真仓库零残留。
- 下一步：P2（从仓库挖 concrete 任务）把 `edit_fn` 接上真 agent（`AgentRuntime`/`run_agent`），
  oracle 升级为 `combine_oracles([pytest 全量基线, 修好的差分一致性, 自举验证])`。

**进度（2026-07-02）—— 目录重构（0a4099a）后的断裂修复与文件找回：**
- 重构把根目录 .py 分类进 `core/` 等，但一批**未提交**的 seam 文件被清掉：`paths.py`、`config.py`、
  `tests/conftest.py`、`test_paths/test_store/test_config`。`paths.py`+conftest+两个测试已从会话
  记录**逐字恢复**（此前 `store.py:22` 的 `from agent_system.paths import db_path` 一直是断的）；
  `config.py`/`test_config.py` 经分类**不予恢复**——main 上无消费者、env 读密钥与 `load_api_key`
  前段重复，阶段 5 接线时按其测试合同（env-only、占位符"你的"视为空、typed 字段）重建。
  教训：**产出即提交**。
- **合并进 main 的是 seam 分支的中期快照**：store/contracts/registry/loop_policy/loop/self_update
  都在，但 `ExperienceStore`/`DomainKnowledgeLayer` 等 20+ 处 `paths.db_path` 接线被回退为硬编码
  `dirname(__file__)`（不认 AGENT_DATA_DIR → conftest 隔离对它们暂不生效）。重做阶段 2 合库接线时，
  以 test_store.py 当时的第 4 测（ExperienceStore 默认进 agent.db + adopt_legacy）为验收标准。
- 重构引出的两个路径雷已修：`core/runtime.py` 的 BUILTIN_OPS 迁入 core/ 后按 `core/language/`
  找词表 → **静默空集**（lexer 关键字识别全丢），改锚仓库根后恢复 259 词；`core/skin.py` 皮肤
  路径由 CWD 相对改锚仓库根。`tests/test_deadloop.py`（手动 LLM 探针，import 即真跑死循环任务）
  加 `collect_ignore` 退出 pytest 收集。

**进度（2026-07-02 续）—— P2 落地：自造任务 + 真 agent 接线 + 差分 oracle 修复：**
- **DifferentialVerifier 假绿修复**（agent_evolution.py）：① 代码经临时 .san 文件传入（main.py
  只吃文件路径）；② fail-closed——任一后端失败该用例即判不一致，全崩=0% 而非 100%；③ 真差分——
  `--eval` 求值器 vs 默认字节码 VM（旧版两个"后端"都是默认 VM）；④ 输出归一化（去 `[OK] 编译`
  噪音行、把求值器回显 `=> v（三进制:…）`/`结果: v` 还原成裸值）；⑤ cwd/runner 可注入（cwd 指
  worktree = 验证**副本**里的引擎）。tests/test_differential.py 7 测（含真后端 E2E 4/4 一致）。
- **修好的差分当天就抓到真分歧（多语句 .san 文件）**：VM 路径只编译**第一个**顶层表达式
  （`(设 x 10)␊(输出 (加 x 5))` 编译出 7 字节只含 设、输出全丢）；eval 路径行为不稳
  （`(输出 1)␊(输出 2)` 两条都执行，`(输出 "你好")␊(输出 …)` 只执行第一条）。**→ 当天闭环修复**
  （见下一条），差分用例已解除单顶层表达式约束。
- **多语句分歧当天闭环（core/parser.py + 两个文件级入口）**：根因是 `parse()` 只取**第一个**
  顶层形式（REPL 单表达式语义），文件级入口误用它——VM 路径直接丢后续语句；eval 路径"不稳"
  实为 sugar 解析成败决定是否走 S-表达式回退。修法：新增 `parse_program()` 返回全部顶层形式
  （`parse()` 既有语义不动，`--ast-json` 调试口未动），compile_bytecode.py 与 repl/main.py
  的 S-表达式回退改用它。探针复核三组多语句用例两引擎一致（VM bin 7→16 字节）；差分内置用例
  增至 5/5（含多语句回归守护），tests/test_parse_program.py 5 测；mypy/ruff/全量 pytest 全绿。
- **task_mining.py（P2 自造任务）**：三类来源按可验证性排序——failing_test（解析 pytest 输出）
  > todo（TODO/FIXME/HACK/XXX 扫描）> long_function（AST 超长函数降序）。任务书 `prompt()`
  内嵌红线①文案（**不得删/跳/弱化测试**）。真仓库冒烟：11 todo + 30 超长函数（榜首
  run_agent.init_evaluator 794 行）。tests/test_task_mining.py 5 测。
- **self_update.py 新增两工厂**：`make_agent_edit_fn(prompt)`——agent 以子进程跑在 worktree
  （cwd=副本，红线②；用**副本里的** run_agent，P4 元循环时 agent 改自身也自动落在验证范围内；
  失败/超时抛异常→整体回滚）；`make_differential_oracle()`——零用例/异常/不一致均拒（fail-closed）。
  test_self_update.py 增至 12 测。
- **run_self_update.py（CLI 入口）**：`--list` 看挖到的任务 / 默认取第一任务跑闭环 / `--task`
  自定义任务书 / `--pytest-log` 喂失败测试。oracle = pytest 基线（默认 0）AND 差分一致性。
- **顺手修的重构雷（重要）**：run_agent.py 在 import 时 `os.chdir(dirname(__file__))`——重构前
  它在仓库根所以没事，迁入 agent_system/ 后 CWD 被切到 `agent_system/`，其文内所有仓库根相对
  路径（`agent_system/sanyan/agent.san` 等）失效、agent CLI 完全起不来；这也是 test_deadloop
  「皮肤文件不存在」报错的直接原因（import 它的进程 CWD 被劫持）→ chdir 目标改为仓库根。
- 分类处置：昨日恢复的 `config.py`/`test_config.py` 复删（main 无消费者，见上一条进度注）。
- **阶段 5 欠账核查（安全红线）**：合并中间快照把 config.py 连同「密钥不入源码」的修复一起
  回退——run_agent.py 两处 `src.replace('sk-你的key', …)` 注入复活 → 复删（主/子 Agent 路径
  均已 setenv，agent_policy.san 经 `环境变量("SANYAN_API_KEY")` 优先读取，删注入零行为变化）。
  typed `AgentConfig` 仍待按 test_config 合同重建（欠账单列）。
- **遗留问题清扫（用户指示"都修一下"）**：以 agent-refactor-seams 分支为源，批量复原被合并
  中间快照回退的四项——阶段 2 并库（ExperienceStore/DomainKnowledgeLayer→agent.db）、
  LearningHandler 捕获陷阱（save_experience 读过期空 memory、经验保存**静默失效**；
  learn_from_task 单参签名 vs runtime 双参调用 = 潜伏 TypeError）、record_outcome 双计数、
  typed config 接线（load_api_key / _get_config → AgentConfig.from_env）。测试守护
  test_store(5)/test_learning_store(7)/test_config(8) 一并复原；conftest 密封注记更新。
  外加阶段 2 路径统一复原：10 模块 14 处硬编码 DB_PATH 复归 paths.db_path（照抄分支样式，
  但**不**整文件照搬——分支上混有重构前旧路径如根目录 run_agent.py，main 在那些点更新）。
  另修 httpbin 外网测试守卫（非 503 异常曾打红全量 CI 一次）。仓根陈旧
  agent_evolution_memory.db 已不存在，无需处置。
- **仍未合回的 seam 工作（单列，别当已完成）**：main 与分支在 agent_runtime(±191 行)/
  agent_tools(±227)/contracts(±114)/registry(±64)/agent_llm_handler(parse_tool 结构化参数、
  complete() 协议) 仍深度分叉，分支侧 test_contracts/test_registry/test_fallback/test_tool_args
  四个守护文件因此**未**复原（实现不在，先复测会直接红）。建议专门一轮对账，或喂给 P2 闭环、
  以这四个测试文件为人工钉死的 oracle 逐项收回；动手前先核对 stash@{0}（分支 tip 之上的
  WIP 快照，可能比 a6301c6 更新）。
- **--list 首跑（零成本、无 LLM）**：挖掘/排序工作正常，但 TODO 的 11 条命中经逐条核查
  **全为假阳性**（三引号测试骨架模板、提示词示例、test_task_mining 自身夹具串）——正则扫原始
  文本分不清注释与字符串。修法：`.py` 经 `tokenize` 只认真 COMMENT token（tokenize 失败跳过，
  与 ast 同策略），加回归测试（6 测）。修后本仓真 TODO 注释为零 → P2 任务源实际是
  failing_test（当前套件全绿则空）和 long_function（榜首 run_agent.init_evaluator 787 行）。
- 下一步（P2 收尾 → P3）：真 LLM 首跑 `python -X utf8 agent_system/run_self_update.py`（需
  SANYAN_API_KEY、烧 token、人工触发）；oracle 可再并入自举验证；P3 = 一任务 N 候选淘汰赛
  （CandidateTournament 复用前先照 DifferentialVerifier 的教训验真）。

**进度（2026-07-03）—— P2 真 LLM 首跑闭环成功（12 轮探针、10 个真 bug）：**

- **里程碑**：`run_self_update.py` 正式产出首个 oracle 全过的分支
  `self-update/custom-20260703-183546`（pytest 基线 2469/0 AND 差分 5/5），待人工审。
  安全机制全程零事故：每次失败干净回滚、无残留 worktree/分支、绝无自动合并。
- **首跑连环挖出的真 bug（各带回归测试，逐一提交）**：① run_agent.py 直跑缺 sys.path 锚定
  （重构遗留）；② LLMHandler/ModelRouter 缺 complete()——**主 LLM 通路自 Phase 4 合并起
  就是断的**，单测全假件无人察觉（+协议一致性 3 测）；③ `环境变量()` 对 sugar 带引号字面量
  生取→永取空——**密钥注入反模式当年正是给这个语言 bug 打的补丁**（+system_ops 3 测 +
  配置层占位符过滤）；④ edit_fn 超时只杀子不杀树，孤儿 pytest 锁 worktree、`_git()` 无超时
  吊死回滚 30+ 分钟（+杀树 2 测 + git 120s 超时）；⑤ LLM 生成规则垃圾参数劫持整轮、done
  谎报完成→零改动闸门回退主循环（+2 测）；⑥ read_file「起始行|行数」被当「结束行」切出
  永远的空串——模型反复读 308 行读到的全是虚空（+4 测）；⑦ 三态 classify 全文嗅探内容负载,
  读到含 error 字样的代码即判高置信 NEGATE 断轮——agent 被禁止阅读一切含错误处理的代码
  （读类工具改信封判定，+3 测）；⑧ execute_rule 对 dict 参数直接崩进程（+1 测）；
  ⑨ max_tokens=4096 截断整函数级 replace 的 JSON、parse_tool 缺 cmd 键、内部 300s 预算
  不够慢代理（8192/补键/420s，+2 测）；⑩ 上下文只喂「上一步结果[:800]」——任务与历史每轮
  丢失、弱模型必然打转（重申任务+历史+阶段推进提示+4000 字符结果窗，+2 测）。
- **产物质量的诚实评估**：首个分支的 diff 行为不变、测试全绿，但属**半成品重构**——
  辅助函数嵌套定义且未被调用，目标函数反而 94→~125 行。oracle 只判「不退化」，判不了
  「有改进」。这正是 P3 的入口：任务感知 oracle（long_function 任务附加「目标函数行数
  必须下降」的静态检查）+ 候选淘汰赛。
- 已知未清余留：parse_tool 按 | 摊平 args（旧文本含管道符会错切，结构化参数对账时一并收）；
  execute_rule 首段死循环体（空 results 上查 UR，i=4 必打印必 break 的幽灵行）；Kleene 传播
  被单次工具失败永久污染（置信度只降不升）；run_shell 子进程 GBK 解码线程异常（Windows）。

**进度（2026-07-03 续）—— P3 前两块落地：任务感知 oracle + 重试/可观测：**

- **make_shrink_oracle**（P3 第一块）：long_function 任务的验收补上"有改进"维度——目标函数
  span 必须 < 基线（ast 静态判，毫秒级，置组合首位短路）；文件不可解析/函数消失 fail-closed。
  首个实战即立功：agent 把文件改出语法错，oracle#0 当场拒绝，没烧 70s pytest。
- **--pick 子串挑任务 / --attempts 顺序重试 / agent 日志持久化**（P3 第二块）：弱模型单次
  成功方差靠重试摊薄（首个过 oracle 即停）；agent 全程输出落临时日志（回滚不灭），每次拒绝
  自动打日志尾——P2 排障期为看行为跑了一打盲探针，此盲区永久封堵。
- **三连拒实录（质量杆抬高后的现状）**：①改坏语法→shrink oracle 毫秒拒；②600s 超时→杀树
  净回滚；③读两轮即 done 放弃→无改动拒。基建全部按设计工作；瓶颈已收敛为**模型能力**：
  当前模型在 94 行重构任务上有效产出率 ~1/5，唯一过过旧 oracle 的半成品现在也会被正确拒绝。
- 下一步候选（按杠杆排序）：换更强编码模型（SANYAN_MODEL/SANYAN_PROVIDER 一变即换，harness
  已验证）；failing_test 类任务优先（对弱模型友好）；--attempts 加大硬怼；P3 完全体淘汰赛
  （并行 N 候选取优——基建活，不解决单候选质量）。

**进度（2026-07-04）—— 循环内生存性批 + 尸检可观测链 + 置信度回血；3 连验证首现"真变短候选进 pytest"：**

- **preflight 复活（自 v3.50 目录重构后首次全绿）**：两处 script-mode `sys.path` 断裂
  （`preflight.py` 迁进 `scripts/`、`test_self_host.py` 直跑 → `ModuleNotFoundError: compiler`）
  + 170 个 `.py` 工作树 CRLF 归一（`core.autocrlf input`）→ ALL CHECKS PASSED。CI 长期红
  导致的"改前不敢跑全量"隐患解除。
- **尸检可观测链**：拒绝理由带失败用例名（`FAILED/ERROR` 短摘要，封顶 3）；`reject_hook`
  回滚**前**把被拒 `patch+stat` 落 agent 日志（红线内只读缝，异常吞掉不挡回滚）；agent 子进程
  `-u` 无缓冲（超时树杀不再只剩启动头）。首战即揪出污染：某"未变短"拒绝的 diff 里只有一条
  `learned_styles.md` 学习记录，**根本没改码**——据此有了下面的 A/B。
- **循环内生存性批（A/B/⑥）**：A 副产物排除（学习记录/状态库 `reset` 出暂存区，只剩副产物即判
  无改动，产出分支不再混噪音）；B 改动只认成功（`cog=='AFFIRM'` 才记 `modified`，UNCERT 失败
  替换不再伪装"修改文件"）；⑥ 零改动 `done` 顶回（`SANYAN_REQUIRE_EDIT`，至多两次）+ 任务书
  "别 `run_shell` 数行数"指引。
- **置信度回血（⑦，`core/ternary_engine.py`）**：Kleene 传播旧无条件乘性衰减（纯成功链也
  0.81→…→0.01、失败毒化只降不升，两处恶果——NEGATE 门因低置信失灵、长成功链撞"信息增益不足"）
  → 成功用几何均值回血、"信息增益不足"阻断加 `confidence<0.6` 守卫。
- **3 连验证跑（`--pick ternary_match --attempts 3`，18:00–18:20，全拒但基建全绿）**：
  - **里程碑 —— 尝试 2 首现"真变短候选进 pytest"**：agent 用 `replace_lines` 把 L326-399 循环块
    换成 `result = _ternary_match_branch_loop(...); if result is not None: return result`（-74/+3
    行），**过了 shrink oracle（真变短）**，止步 oracle#1——3 测试挂。失败用例名
    （`test_run_analyze_auto` / `test_run_find_symbol_auto` / `test_generated_rule…`）+ 尸检 diff
    一并落盘。**bug 是弱模型典型：抽取后调用了 `_ternary_match_branch_loop` 却从没定义它**
    （r9 search `def _ternary_match_branch_loop` 空手而归）——静态长度 oracle 抓不到"引用未定义"，
    pytest 抓到了。全链路首次产出真候选并被 oracle 精确、可读地拒绝。
  - **B/A/⑦ 实证**：B——尝试 1 的 UNCERT replace 未记 `modified`（面板无"修改文件"、诚实判无
    改动），尝试 2 的成功 `replace_lines` 记了（面板"修改文件: ops/control_ops.py"）；A——三次尸检
    零 `learned_styles` 噪音（尝试 2 面板仍"[学习]…"写了 worktree 副本，但排除出提交，尸检 diff
    纯代码）；⑦——成功链稳在 0.81-0.90，毒化链也回血（尝试 2 验证段 0.24→0.48→0.61→0.70 上行，
    旧行为此处早塌到 0.01）。
  - **新暴露的模型侧失效（都非基建）**：①抽取后忘定义辅助函数（尝试 2，静态长度 oracle 盲区）；
    ②思维链整段漏成"工具"（尝试 1 r7 把大段推理当 tool 名，解析废一轮）；③用 `sed -n` 走
    `run_shell` 读文件绕过 `read_file`（尝试 3，"数行"指引没覆盖"shell 读"）。
  - **瓶颈判定不变**：oracle/观测/安全/⑦/A/B/⑥ 全按设计工作，唯一真候选栽在模型没自查"调用了
    未定义函数"。质量杆下模型有效产出率仍 ~1/5。
- **下一步候选（按杠杆，据本轮更新）**：① shrink oracle 加"新函数体引用的名字必须在模块内可解析"
  静态检查（直接抓尝试 2 这类抽取残缺，成本毫秒级，置组合首位）；②换更强编码模型；③ `failing_test`
  类任务（改动局部、对弱模型更友好）；④ hesitation 计数应算"连续"而非"累计"（尝试 3 三连 UNCERT
  触顶合理，非连续累计触顶偏严）；⑤ `learned_styles.md` 路径应认 `AGENT_DATA_DIR/paths.py`（当前
  `__file__` 锚定，测试跑会污染真 tracked 文件——架构遗留）。

**进度（2026-07-05）—— 下一步候选①④⑤ + 带记忆重试落地（单测已封，待实跑验证）：**

- **① shrink oracle 加"引用可解析"静态检查（`51c782c`）**：新增 `_unresolved_calls_in_function`——
  查目标函数体内『裸名调用』(`NAME(...)`) 里模块内解析不到的名字，接在 span 变短检查之后、
  组合首位先行短路。直击 07-04 尝试 2 的死法（抽了 `_ternary_match_branch_loop` 却没定义、过了
  span，靠 pytest 花 ~1 分钟才报 3 个 NameError）：现在 ast 级毫秒成本当场毙。解析范围刻意宽松
  （模块内任意 def/class/import 名 + 任意 Store 名 + 形参 + builtins），宁可漏报绝不误杀——pytest
  才是真兜底；`from x import *` 无法静态推断绑定则放行。守护 +5。
- **带记忆重试（`c9089fe`）**：`--attempts` 此前是 N 次冷启动，每次都不知上次为啥挂；但 reject_hook
  已把失败用例名/被拒 diff 落了盘。新增 `build_retry_feedback`：按拒绝原因分类给对症提示（无改动→
  务必真改文件；解析不到的名字→先定义辅助函数再调用；失败用例→保持逻辑严格等价只做结构拆分；
  未变短→抽最大整块），塞回下一轮任务书首，把盲目重试变成迭代修正（零额外成本、只串上下文）。
  只带最近一次防任务书膨胀。守护 +2。
- **④ hesitation 连续计数（`872010e`）**：`step()` 里笃定一步(AFFIRM/NEGATE)复位犹豫计数。
  `agent_execution` 早写着"连续N次不确定，停止执行"，但计数器从不复位使它实为累计——健康长环会被
  非连续 UNCERT 攒够而误停；此改让实现与既有文案对齐，连续 UNCERT 仍照常触顶。
- **⑤ learned_styles 认 AGENT_DATA_DIR（`872010e`）**：两处 `__file__` 锚定换成 `paths.data_dir()`
  （默认仍 `agent_system/`，生产路径不变）；测试隔离目录下学习记录不再污染真 tracked 文件。
- **模型侧：思维链漏成工具名的解析兜底（`d6f0eba`）**：`parse_tool` 最后兜底 `return raw, ''` 从不返
  None，使 loop 里既有的 `if tool is None` 优雅重提示成死代码——模型整段思维链没给 JSON 时被当工具名，
  "未知工具: <上千字推理>" 白烧一轮（07-04 尝试 1 r7）。改成：单 token 原样返回（"未知工具"仍是有效
  反馈），多词散文/大段思维链返 None 命中优雅路径。签名 `-> Tuple[Optional[str], str]`，mypy 验证调用方。
- **仍待做（按杠杆）**：**候选淘汰赛（P3 完全体）**——一任务并行 N 候选、各过（已加固）oracle 栈、取
  首个通过或全弃，是对付弱模型方差的结构性正解；先看①+带记忆重试把成功率抬到多少再定是否上全并行。
  ②换更强编码模型（用户暂搁置）；③ `failing_test` 类任务（改动局部、对弱模型友好）；模型侧行为件残余：
  `sed -n` 走 `run_shell` 绕过 `read_file`（"数行"指引没覆盖"shell 读文件"）。
- **注**：①④⑤+带记忆重试+解析兜底均单测封住（全量 2527 passed/6 skipped），但**尚未实跑验证**——下一步空一次
  `--pick ternary_match --attempts 3` 实跑，看引用检查能否在 oracle#0 秒毙尝试 2 类残缺、带记忆重试能否
  让次轮真修正上一轮的错（预算/代理允许时）。

**进度（2026-07-05 续）—— 两轮实跑（16:52 / 17:27，各 3 次尝试，全拒 EXIT=1）+ 回敲三件：**

- **第一轮（修复前）全被代理掐死**：Clash 抖动 6 次 LLM read-timeout，重试各吃 60-120s，默认 420s 循环
  总预算把三次尝试全掐死在编辑前（合计**零次编辑工具调用**，3/3"无改动"拒）。另两枚实录：关键词启发式
  （`def/函数/结构`→analyze）抢在散文兜底之前把超时后的思维链劫持成写死目标的 analyze（尝试 2/3 各白烧
  一轮）；尝试 1 r4 幻觉出外项目路径 `cd /mnt/d/project/repomind_eval/...`（✗ 接住，无害废轮）。
- **回敲两件（`5754c8d`）**：`SANYAN_LOOP_TIME_BUDGET` 环境可调（默认仍 420s，自更新 CLI 设 900s；
  外层 `--agent-timeout=1800s` 子进程硬杀兜底）；关键词启发式只对**短单行**生效（多行/超 30 字散文落到
  散文→None 兜底走优雅重提示）。守护 +4（Windows `time.time()` 粒度粗，预算测试用 -1 不用 0）。
- **第二轮（修复后）预算立竿见影**：尝试 1 活满 15 轮/19 次 LLM 调用（第一轮只有 3-4 轮）、零超时强杀、
  零 PARSE 劫持——但模型 15 轮全在徘徊（3 次一模一样的 `read_file 308|100`、search、shell 读），不敢下手
  改；尝试 2 杂讯废跑；**尝试 3 一击 `replace_lines 308-401` 产出真候选**（-89/+29，过 shrink oracle 含
  引用检查），pytest 拒（同 07-04 的 3 个用例）。带记忆重试两次触发标记 ✓。
- **尝试 3 尸检暴露①的作用域盲区（当场回敲，`f4b31ed`）**：候选把辅助函数 `_ternary_match_impl` 定义成
  **类方法**、又在 `ternary_match` 里**裸名调用**——类体绑定对方法内裸名不可见（LEGB 无类作用域），必然
  NameError；旧实现把全树 FunctionDef 名一律计入可解析，恰好放行自己瞄准的 bug 类。重写为作用域感知
  （目标函数局部+闭包外层 → 模块层**不下潜类体** → builtins；global/except-as/match-as 收进绑定形态；
  宽松处仍宽松）。守护 +4（类方法裸名拒 / `C._impl` 正确写法放行 / 模块层绑定 / 闭包可见）。
  候选的另两处行为改写（`len(args)%2!=0` 拒奇数参——而合法 匹配3 恰是奇数参；`SanyanSyntaxError`→
  `ValueError`）由 pytest 正确拦下：**重写而非重构**仍是弱模型主死法。
- **两轮后的瓶颈刻度**：基建全绿（隔离/回滚零残留 ×6、尸检链、纠偏喂回、预算、⑦ 稳置信）；真候选率
  2/6 次尝试，死因全在模型（徘徊不敢改、重写不守等价、类方法裸名调用）。下一步杠杆不变：淘汰赛并行摊
  方差，或 `failing_test` 类局部任务降门槛；模型侧残余 `sed -n` 走 `run_shell` 绕 `read_file`。

**进度（2026-07-05 深夜–07-06）—— 守恒检查+徘徊顶推落地；第三轮实跑（风暴作废）再回敲四件：**

- **守恒检查（`363d560`）**：0705 真候选死因（改校验/换异常）转毫秒级——`make_shrink_oracle` 新增
  `baseline_source`，基线函数体每一行（跳 docstring/注释、strip 归一、≥8 字符含字母数字）必须在新文件
  原样存活；消失行按名进拒绝理由与 `missing_lines`，纠偏新增"原样保留"类。runbook 补"只搬不改""别用
  shell 读文件"。守护 +4。
- **徘徊顶推（`3c7bcdb`）**：REQUIRE_EDIT 下过半仍零改动顶推一次"停止阅读动手改"（⑥只管 done 顶回，
  治不了从不 done 的 15 轮纯阅读）。守护 +2。
- **挖掘去截断（`32fc83e`）**：第三轮起跑即 EXIT=2——`mine_long_functions` 旧默认 `limit=30` 只返回
  最长前 30，当天新增的 loop/oracle 代码把 `run_legacy` 等喂过 94 行，`ternary_match` 跌出榜被 `--pick`
  判"未命中"。**任务身份随无关改动漂移**是坏性质：默认去截断（全库实测 53 个超长函数），展示层自切。
- **第三轮实跑（0706 上午，3/3 无改动拒，环境风暴作废）**：代理风暴级 24 次超时+SSL 断（前两轮各 6 次），
  LLM 三连重试一轮吃 ~360s。**顶推在尝试 1 的 r8 正常触发 ✓**（模型顶完仍继续读——文案待强化），尝试 2/3
  死于 r5-6 没活到顶推。守恒检查未获样本（无候选产出）。
- **风暴尸检再回敲三件（`33a8a1c`）**：① LLM 句柄彻底失败的哨兵串 `error|LLM调用失败…` 曾流进解析——
  幻影 error"工具"烧轮、重复错误文案把 UR 退化检测毒成 r5-6 早夭（实录 UR=0.45/0.47）：loop 识别哨兵转
  RuntimeError 走既有失败路径（计连败、三次快中止、不进 llm_outputs/history）。② 停机原因如实上报：
  旧实现所有 break 都报"已达N轮"，实跑三次面板全谎报（900s 预算/UR 退化×2），尸检被误导两回——各 break
  落 stop 原因。③ 顶推触发加"时间过半"或款（固定第 8 轮在风暴下常来不及，预算先烧完）。守护 +2。
- **三轮总刻度**：9 次尝试 2 个真候选，全部死因均已转成毫秒级静态拦截或有对症纠偏；环境风暴现在
  快中止而非慢性放血。**下一步**：等代理平稳窗口重跑一次看守恒+顶推+纠偏闭环的真实效果；然后再定
  淘汰赛/failing_test 路线。

**进度（2026-07-06 午后）—— 第四轮实跑（迄今信息量最大）+ 回敲两件（`33141b4`）：**

- **第四轮（3/3 拒，EXIT=1，16 次超时属中等噪音）**：尝试 1 在 r5 用 `replace_in_file` 锚定
  `@staticmethod` **整块插入 79 行辅助函数（忠实搬运！diff 逐行与原块一致）**——但没做第二步替换原块，
  oracle#0 按"94 行 ≥ 基线 94 行"**毫秒毙**（不烧 pytest ✓）；随后正死于 `read_file` 全程限 5 次的硬
  约束，第二步没机会做。尝试 2/3 徘徊死（顶推均触发 ✓ 但模型仍继续读；分别死于 read 约束/900s 预算）。
  **如实停机原因全面上岗**：面板报"约束违规停止（read_file）""总执行时间超过900秒"，不再谎报已达15轮。
- **回敲两件**：① `SANYAN_TOOL_REPEAT_LIMIT` 环境可调（默认 5，自更新 10）——重构 94 行函数读 2-3 窗+
  改后自检，5 次是新的绑定瓶颈；② "未变短"纠偏点名**两步都要做完**（第一步搬辅助函数/第二步
  `replace_lines` 替换原块），`build_retry_feedback` 增 `hints` 参数把挖掘静态标注的候选块行区间
  随纠偏指名。守护 +1、纠偏断言换两步文案。
- **模型能力边界的新刻度**：模型**能**忠实整块搬运（第一步 ✓），失在"记得做第二步"——这正是纠偏
  与放宽限额瞄准的空隙。四轮 12 次尝试 3 个真候选（1 全程 / 2 半程），全部机械死因已拆除。

**进度（2026-07-06 下午）—— 第五轮实跑（首现"两步齐做"）+ 回敲四件（`846f4f4`）：**

- **第五轮（35 次超时风暴级，3/3 拒，三次全死在 900s 预算）**：尝试 1 **首次两步齐做**——顶推后 r8
  `replace_lines 326-399` 抽取+替换一气呵成，但辅助函数**嵌套定义在原函数体内**（P2 首跑同型），
  94→99 反而变长，oracle#0 毫秒毙。尝试 3 r5 曾发起**完整的两步替换**（308-357 整段换 helper+调用），
  却被**列表参数泄漏**毁掉：模型把 new 给成 JSON 数组，摊平器 str() 出 `['def _process…` 列表字面量
  当代码写入，守卫按语法错误拦回（UNCERT 0.19）——本轮最痛，一个可能的首胜就此报废；随后退化成只插
  helper（+73）不替换。尝试 2 徘徊 900s。**顶推→编辑因果首次可见**（尝试 1/3 顶推后 2-3 轮内均动手）。
- **回敲四件**：① `_flat_arg` 列表参数按行拼接（数组语义就是多行；write_file content 同治）；
  ② shrink oracle 嵌套 def 诊断（未变短且基线无嵌套时点名"须与原函数平级"，基线本有嵌套/无基线不给
  可能失真的提示）；③ 纠偏带两课（`classify_tip` 拆出、`earlier_tip` 参数——尝试 1 的"两步都做完"曾被
  尝试 2 的"无改动"顶掉，尝试 3 重蹈覆辙；不同才带、相同去重）；④ runbook 点名"辅助函数与原函数平级，
  不要嵌套"。守护 +6，全量 2552 passed/4 skipped。
- **五轮总刻度（15 次尝试）**：真候选 4 个（0704 未定义 helper / 0705 重写+类方法裸名 / 0706 半程×2），
  外加 1 个被列表泄漏毁掉的"准候选"。死因谱系完整闭环：每一类死法都已有毫秒级拦截 + 点名病灶 + 对症
  纠偏三件套。模型在干净跑道上的表现逐轮逼近：不改→只做第一步→两步齐做（位置错）。首胜在望。

**进度（2026-07-06 傍晚收官）—— 第六/七轮实跑 + 回敲两件（`3592f2a`/`6ea18ed`）；当日风暴五连，暂停实跑：**

- **第六轮（31 次超时）**：尝试 1 只做第二步——替换了原块、忘定义 helper（0704 死法镜像），**作用域检查
  毫秒点名 `_ternary_match_branches`**（当年烧整轮 pytest 的死法今天零成本）。顶推→编辑因果第三次复现。
  回敲：runbook 与顶推文案点明**先定义、后替换**顺序（被顶推后模型的自然反应是先替换）。
- **第七轮（30 次超时，--attempts 4）**：尝试 1 只做第一步（+19）；尝试 3 **退化性大粘贴**（+390/-0
  整段重复贴入，风暴下输出质量崩坏的新形态）——span 毫秒拦下但"两步都做完"的纠偏不对症。回敲：未变短
  且文件净增 > 目标函数体量时点名"疑似整段重复粘贴"，纠偏新类"整个改动只需两笔"。
- **当日总账（7 轮 22 次尝试，0704 起累计）**：真候选 6 个，全部毫秒级拒绝+点名病灶；死法排列已集齐
  （不改/第一步/第二步/嵌套/重写/大粘贴），唯缺"两步齐做+位置正确"。**风暴五连（29/16/35/31/30 次超时）
  是当日头号税**——每个"调用失败"轮烧 ~360s，900s 预算实际只剩 4-6 个有效轮；风暴下模型输出质量同步
  崩坏（大粘贴即样本）。**暂停实跑，待代理恢复**（重启 Clash / 关开 TUN；也可能是供应商对连跑限流，
  间隔冷却亦有效）。机械面已无已知欠账：下一个平稳窗口的实跑即是模型真实水平的干净读数。

**进度（2026-07-06 晚）—— 第八轮实跑：S0 首个轻噪读数（10 次超时，基本有效）：**

- **4/4 拒，EXIT=1**：尝试 1/3 徘徊死（900s 预算 / UR 退化，停机原因如实 ✓）；尝试 2/4 产出候选。
- **守恒检查首战立功（本轮头条）**：尝试 2 删掉 74 行原块、换成 `return self._ternary_match_loop(...)`
  却**从没定义这个方法**——`self.` 属性调用绕过引用可解析检查（只查裸名，Attribute 调用天然放行），
  **守恒检查毫秒接住**："重写而非搬运：43 行原始语句消失"并点名前三行。这是 oracle 栈**层间互补**的
  首个实战证明：引用检查的结构性盲区恰被守恒覆盖（该死法若无守恒需烧 pytest 才见 AttributeError）。
- 尝试 4 又是"只做第一步"（+67 忠实搬运插入类级、未替换）→ 未变短毫秒拒。顶推触发 ✓（其后 r5 即动手）。
- **S0 记账**：读数 1/2-3——轻噪窗口下模型产出候选率 2/4，两步完整率仍 0。按 S0 完成判据，再攒 1-2 轮
  干净读数若仍 0 接受 → 转 S2 淘汰赛。八轮累计：26 次尝试、真候选 8 个、全部毫秒级拒绝+点名病灶。

**进度（2026-07-07 上午）—— 第九轮实跑：S0 读数 2（11 次超时+1 次彻底失败，与第八轮同级）+ 回敲两件（`97c5b03`）：**

- **4/4 拒，EXIT=1，全部零编辑死**（3 连相同输出退化 / 900s 预算×2 / UR=0.47）。与第八轮同级噪音下
  候选率从 2/4 掉到 0/4——**单轮方差极大**，S2 淘汰赛（并行摊方差）的动机再添实证。
- **机械根因（本轮头条）——工具链自相矛盾**：顶推文案推荐 `replace_lines` 按行号整段替换且"不要再调用
  读类工具"，而 read_file 范围读**不带行号**——模型两次原话抱怨"没显示具体行号"，被迫凭记忆构造 old 串
  （尝试 3 r9 的 replace_in_file 失败，UNCERT 0.19）或在"如何才能精确"的散文里空转烧光预算。回敲：
  范围读每行带绝对行号 `N│`；old/new 混入行号前缀自动剥除（原文直接命中绝不剥，防误伤）；顶推留出口
  "行号滚出上下文可再读一次目标区间"；runbook/loop 顶推同步教 replace_lines 优先；工具输出/上下文注入
  上限 4000→4500 吸收行号开销。
- **回敲第二件——管道解析护栏**：尝试 3 r8 散文里引用旧调用"参数=308|95"，#2 管道兜底对任意含 `|` 文本
  生效且抢在散文护栏之前——整段思维链被劈成幻影工具名白烧一轮（#3/#4 层各有护栏，唯独 #2 裸奔）。
  改为首段须像工具名（短单 token 无换行）才按管道劈。守护 +6，全量 2560 passed / 0 failed。
- **S0 记账**：读数 2/2-3——两轮合计候选率 2/8，两步完整率 0。行号补给是新变量（模型首次拿到可用坐标，
  与 replace_lines 打法闭合），第十轮为 S0 末读；若仍 0 接受 → 按既定判据转 S2 淘汰赛。

**进度（2026-07-07 午后）—— 第十轮实跑：首个全零超时窗口，揭出 UR 误杀（`e7f8b27`）：**

- **4/4 拒，全部零编辑，全部死于 UR≈0.47（r3-r8，顶推都没活到）**——十轮以来第一个零超时窗口，
  却是护杀系统自己杀的：UR 在全历史累积 token 上算独特率，模板化 JSON 工具调用只有参数在变，重复
  token 逐轮堆积，第 4 条输出**必然**跌破 0.5 阈值。参数各异的正常探索（尝试 4：300|110→308|120→
  280|50 三轮即死）被判"退化"——**模型行为越规矩死得越快**：解析越干净（第九轮护栏）+ 窗口越干净 =
  输出越整齐 = 死得越早。第九轮修复本身零回归（全轮无 PARSE 错、无幻影工具、行号读数正常）。
- **回敲**：UR 检查从"每轮 raw 全喂"移进 `tool is None` 分支——只喂解析不出工具调用的散文/胡言，
  回归其 docstring 自述本职（那种不进 history、`results_degenerate` 看不见）；真工具调用的打转由
  results_degenerate（3 连同结果）+ 同工具限额 + 轮数/预算兜底。守护 +2，全量 2562 passed / 0 failed。
- **S0 记账修正**：第十轮读数**作废**（死因全是考官侧误杀，非模型失能）——有效读数仍 2（第八轮 2/4、
  第九轮 0/4）。第十一轮（UR 修复 + 行号坐标 + 若窗口再干净）将是十一轮来条件最好的读数，作 S0 末读。
- **元观察**：连续两轮回敲对象全是"考官/工具链自伤"而非模型失能（行号缺失+散文管道劫持 → UR 误杀）——
  跑道机械欠账见底中，模型真实水平即将首次无遮挡露出。十轮累计 34 次尝试、真候选 8、基建零事故。

**进度（2026-07-07 午后）—— 第十一轮实跑：行号机制首战走通 + 三级递进反制读循环（`43c6835`）：**

- **4/4 拒（2 次超时，干净读数）**：UR 修复完全生效——零误杀，四次尝试全活到 11-13 轮（上轮 3-8）。
  **行号机制首次实战走通**：尝试 2 在 r10 用 `replace_lines 402|402` 把 70 行辅助函数按坐标一次插到
  类级正确位置（第一步 ✓ 忠实 ✓ 平级 ✓），随后回到通读模式找替换目标，**烧光 10 次读额而死**
  （新绑定瓶颈）；未变短毫秒拒。尝试 1/3/4 纯读循环（`308|100` 一轮内重复读 4-5 次），r8 顶推前已耗
  7-8 次读额，顶推后余额 2-3 次全花在继续读——"约束违规停止（read_file）"×3。
- **回敲三件（三级递进反制）**：① 徘徊顶推加行为触发——读满 5 次仍零改动即顶推（r5-6），不再干等
  轮次/时间过半；② 读额告罄警告写进读结果**头部**（带内）——上下文顶推被无视，工具结果才是模型注意力
  最高的位置（used ≥ limit-3 起，置 ternary.step 后不污染判定，头部防 4500 截断）；③ **第二步顶推**
  （一次性）——首笔改动落盘的下一轮立即推"用 replace_lines 把原块替换成一行调用"（38 次尝试"两步齐做+
  位置正确"仍未出现，第一步成功的瞬间是第二步最好的教学时机）。守护 +4，全量 2566 passed / 0 failed。
- **S0 记账**：第十一轮为有效读数 3/3——候选率 1/4（半程）。**S0 判据已满足（3 个有效读数、0 接受）**：
  按既定路线转 **S2 候选淘汰赛**；但第十一轮三件反制（尤其第二步顶推）直接瞄准"两步齐做"缺口，
  S2 动工前再跑 1 轮验证其效果，收益/成本比最高。十一轮累计 38 次尝试、真候选 9、基建零事故。

**进度（2026-07-07 傍晚）—— 第十二轮实跑（反制验证轮）：done 谎报完成现形 + 回敲两件（`6676525`）：**

- **4/4 拒（7 次超时，轻噪有效）**：候选率回到 2/4。尝试 1 行号插入链**稳定复现**（`replace_lines
  402|402` +77，第一步 ✓ 忠实 ✓ 平级 ✓）→ **第二步顶推按设计触发**（r11）→ 模型 r12 以 `done
  已完成重构` 应答——未变短拒。尝试 4 **首次先做第二步**：`replace_lines 308|402` 重写函数体、
  调用 `_match_ternary_branches` 却没定义 → 顶推补笔触发 → 模型 done"重构完成：已拆分为辅助函数
  _match…"——**幻觉 helper 已定义**，作用域检查毫秒点名。尝试 2/3 顽固读循环型（还试了违禁
  run_shell），读额死。**新缺口精确定位：模型凭信念 done、不凭状态**——落一笔即认为完工。
- **回敲两件**：① done 闸门 v2——REQUIRE_EDIT 下**只落一笔改动的 done 顶回一次**点名缺笔（与既有
  零改动 done 顶回同构；再 done 放行交 oracle，其点名会进带记忆重试）；② 第二步顶推文案**不预设
  顺序**（尝试 4 证明模型会先替换后定义）——点名两笔（①定义②替换）缺哪补哪。守护 +2，全量
  2566 passed / 0 failed（skip 4→6 属 gcc 漂移）。
- **记账**：十二轮累计 42 次尝试、真候选 11、基建零事故。死法阶梯持续上移：读额瓶颈 → **done 谎报**
  （两步只差最后一"补"）。第十三轮验证 done 闸门；仍 0 接受则按既定判据**立即转 S2**，不再顺延。

**进度（2026-07-07 晚）—— 第十三轮实跑：候选首进 pytest 层 + 守恒 v2（`9eaf2b0`）+ S2 落地（`e4dbc16`）：**

- **4/4 拒（11 次超时，有效读数），但质变**：尝试 1/2 **两步齐做+净变短**——done 闸门+补笔顶推逼出
  合理新策略『一笔整段 `replace_lines 308|401`』（一次调用同时完成定义+替换），静态四连闸全过，
  **十三轮来首次打进 pytest 层**；oracle#1 点名 4 个失败用例（test_agent_runtime 簇：改写破坏 匹配3
  行为，AgentRuntime 初始化链上的 .san 流程受损）。尝试 3 只插入（+66，未变短拒）；尝试 4 零编辑
  （replace_lines 一次格式失败后徘徊，读额死）。
- **守恒盲区现形 → v2（`9eaf2b0`）**：集合成员判定下重复行有"不在场证明"——ternary_match 内
  `matched = False` ×3、conf 比较阶梯 ×4，压缩改写只要留一份副本就静态全过（本轮实证烧了两轮 pytest
  才拒）；**行为等价的改写更会被直接接受**，违反"只搬不改"契约（真实误放行风险）。改**整文件行计数**：
  纯搬运不改变任何一行出现次数，删任何一份重复立即亏空，毫秒拒且纠偏对症。守护 +2。
- **S2 落地（`e4dbc16`）**：`run_tournament(loop, task_name, edit_fn_factory, n, *, breaker=2,
  tip_fn, on_candidate)` 按规格进 self_update.py 尾部——教训经 classify_tip 跨候选**去重累积**（比带
  记忆重试的"最多两课"更完整）、首个 accepted 即停、全败返回信息量最大的拒绝（失败用例 > 守恒/解析 >
  粘贴/嵌套 > 未变短 > 无改动）、连续 breaker 个零编辑判风暴断路；CLI `--candidates N`（与 --attempts
  互斥，parse 后立即拦）。守护 +6，全量 2574 passed / 0 failed。
- **记账**：13 轮 46 次尝试、真候选 14、基建零事故。死法阶梯：done 谎报 → **行为等价/只搬不改**
  （pytest 层）——守恒 v2 已把后者拉回毫秒级。下一步：首个 S2 淘汰赛实跑（`--candidates 4`）。

**进度（2026-07-07 晚）—— 第十四轮实跑（首个 S2 淘汰赛）+ 回敲三件（`0b13d59`）：**

- **赛制机械面全部按设计工作**（6 次超时，干净窗口）：候选 1 真候选（+77 只插入，毫秒拒）→ 教训经
  classify_tip 合并注入候选 2/3（'[S2] 已合并此前候选教训' ✓）→ 两个零编辑 → **断路器止损**（中止于
  3/4，省下候选 4 预算）→ 全败回传**信息量最大**的拒绝（未变短，而非无改动）。EXIT=1 语义正确。
- **暴露三处**：① 读额警告教会模型**换工具**——read_file 逼近限额就轮换 analyze/search_code 继续读
  （候选 3 还试了违禁的 `run_shell python -c` 读文件），单工具限额被规避，顽固徘徊在干净窗口烧满
  15 轮（31 次 LLM 调用零编辑，'已达15轮'死）；② 断路器"疑似代理风暴"归因错误——干净窗口下顽固徘徊
  也连出零编辑；③ 4 候选赛制里 breaker=2 太急，可能误杀后续候选（第十三轮的晚转化候选 r13 才动手）。
- **回敲三件**：① 零编辑下所有读类调用**共担带内警告**（'已连续探索 N 次仍零编辑——换读类工具不会有
  新信息'），换工具不再是出路；② 断路归因两写（风暴或徘徊），尸检看噪音计数区分；③ CLI 侧 breaker
  2→3（库默认仍 2）。守护 +1，全量 2575 passed / 0 failed。
- **记账**：14 轮 49 次尝试（淘汰赛 3 候选）、真候选 15、基建零事故。徘徊型的画像收敛：警告/顶推/
  教训全部收到仍不动手的候选，其余额价值≈0——断路省预算是对的，下一轮观察共担警告能否转化。

**进度（2026-07-07 深夜）—— 第十五轮实跑（淘汰赛②，读数平淡）+ S4 落地（`57bfbca`）：**

- **第十五轮（4 次超时干净档，3 候选全零编辑，breaker=3 正确断路）**：候选 1 死于一阵瞬时噪音爆发
  （LLM 三连败快中止，设计行为）；候选 2/3 徘徊型烧满 900s/读额——**共担警告未能转化顽固徘徊型**。
  无新机械教训：所有死法均为已知已反制类别。**判定：同模型下已到收益平台期**——15 轮 52 次尝试、
  真候选 16、0 接受；跑道机械面（坐标/警告/顶推/闸门/淘汰赛/断路）全部就位且工作正常，剩余杠杆
  按既定结论只有换模型（`SANYAN_MODEL`，用户拍板）或继续磨方差。实跑暂停，待用户定夺。
- **S4 落地（`57bfbca`，规划"可随时做、P4 前必须做"项）**：红线①机械化——`SelfUpdateLoop.run` 在
  commit 之后、**oracle 之前**检查 `PROTECTED_PATHS` 前缀（tests/、self_update.py、run_self_update.py、
  task_mining.py、preflight.py），命中即拒并点名路径与红线①（pytest oracle 防不住"把测试改成恒过"
  ——循环论证）；P5 密钥闸提前落地（diff **新增行**含 SANYAN_API_KEY/sk- 样式字面量即拒，上下文行
  不误伤）。守护 +4（含"oracle 恒过也拦"的先后序钉）。全量 2578 passed / 0 failed。
- **S0-S6 进度盘点**：S0 ✓（3 读数）、S2 ✓（落地+两轮实跑）、S4 ✓（本条）；S1 待首胜触发、
  S3 待真实红测触发、S5/S6 在 S1 之后。**下一个可动的**：等窗口再跑淘汰赛磨方差，或用户换模型。

**进度（2026-07-07 深夜②）—— 用户拍板：淘汰赛继续（次日起跑）；v3.55.0 发布 + FFI M1 地基落地：**

- **用户决策**：不换模型，继续淘汰赛磨方差（次日动手）；先发版、再立 FFI 地基。
- **v3.55.0 发布（`5544a8e`）**：CHANGELOG 依既有格式记 P3 收官周（单日七轮实跑、S2+S4 落地、
  工具链自伤三连修、守恒 v2、平台期判定）；版本锚点五处同步，doc_sync 全绿。
- **FFI M1 地基（`6e8332e`，RFC docs/ffi_plan.md §3 层 A）**：`ops/py_bridge_ops.py` 六算子
  （py导入/py取/py调/py项/py列/py释）+ `信封判`；三态信封（判定/载荷双通道分离）；封送
  （回程 True/False/None→真/假/可能，入参**数值直通**——"真即 1"语言语义下 RFC 原案会数值失真，
  偏差记开放问题 #8）；句柄注册表（上限 4096、幂等缓存、py释 同步失效缓存）；`SANYAN_FFI`
  默认关（能力面四算子信封报假，#7 记 py列/py释 不设门的偏差）；`解包/或解` 识别信封（裸
  TritValue 回归钉在册）；回调 fail-closed；差分排除 FFI 用例且 `skipped_ffi` 可见；
  **自更新环境不设 SANYAN_FFI 绊线钉**（§3.6-3，S4 配套）。守护 +26；真实解释器双态冒烟通过
  （开门 json 三行示例出 `{"a": 1}`，关门可读安全拒绝）。编译路径显式报错归 M2。
  全量 2603 passed / 0 failed。

**进度（2026-07-08 上午）—— 第十六轮实跑（淘汰赛③）：4/4 全真候选零徘徊 + 诊断消歧回敲（`e890494`）：**

- **里程碑：候选率 4/4、零徘徊、零零编辑（十六轮首次）**——完整反制栈（行号坐标/共担警告/补笔顶推/
  done 闸门）把徘徊型全部转化；7 次超时干净档，全部拒绝均为 oracle#0 毫秒层。
- **守恒 v2 首战立功**：候选 3 整函数改写（+81/-77，改报错文案/换变量名/幻觉 `Self.`）毫秒点名
  "46 行原始语句消失"——该死法第十三轮曾烧两轮 pytest，现零成本且纠偏对症。
- **新对症缺口：类内裸名调用**（0705 死法回归）：候选 1/2 都用了聪明的最小编辑（函数中段插 `def` 把
  后半身劈成新方法，仅 +5 行）但类方法裸名调用必然 NameError；**候选 2 收到候选 1 教训后原样重蹈**——
  旧文案"抽取了辅助函数却没定义它"误导（明明定义了，病在调用形式）。回敲：oracle 诊断消歧（名字绑定
  在类体时点名类名与两条出路：搬模块级 / `类名.名字(...)` 限定调用）+ classify_tip 同步 + runbook
  首选模块级顶格（"模块级或同一类里"是弱模型陷阱）。守护 +2，全量 2605 passed / 0 failed。
- **记账**：16 轮 56 次尝试、真候选 20、基建零事故。候选质量阶梯：徘徊型清零 → 全员动手 → 现役死法
  只剩"调用形式/搬运忠实度"两类，均已毫秒级+对症。第十七轮验证消歧文案能否点破类内裸名。

**进度（2026-07-08 上午②）—— 第十七轮实跑（淘汰赛④）：纯方差轮，0/3 全徘徊，断路止损：**

- **1 次超时（史上最净窗口）却 0/3 全零编辑读额死**，breaker=3 正确断路——与第十六轮（同栈同窗口
  4/4 全候选）构成鞭梢式反差：**单轮方差 0%↔100%**（第八/九轮 2/4→0/4 的放大版）。消歧文案本轮
  没等到"类内裸名"样本（无候选产出）。零新机械教训，不发明无证据的回敲；淘汰赛继续滚方差。
- 记账：17 轮 59 次尝试、真候选 20、基建零事故。

**进度（2026-07-08 上午③）—— 第十八轮实跑（淘汰赛⑤）：再一个全徘徊轮；任务书加长嫌疑排除：**

- **0/3 全零编辑（10 次超时轻噪），breaker=3 再次断路**（今日第二次省下候选 4）。曾疑第十六轮后加长的
  runbook（类名.方法名 条款）压垮弱模型——但第十四/十五轮（旧短版）同样全徘徊，第十六轮才是离群值：
  **结论仍是方差**，不回退。候选 2 又试违禁 run_shell（`?` 标记，被拦）。
- **淘汰赛五轮总账（14-18）**：16 个候选里 5 个动手（~31% 转化率），0 接受；断路两次止损、教训注入
  全程工作、全部拒绝毫秒层。赛制经济学成立：徘徊候选 ~12-15 分钟/个，断路把无效窗口的损失封顶。
- 记账：18 轮 62 次尝试、真候选 20、基建零事故。继续滚。

**进度（2026-07-08 上午④）—— 第十九轮实跑（淘汰赛⑥）：受控对比翻案——"首选模块级"文案是徘徊推手（`1073bbc`）：**

- **0/3 全徘徊（10 次超时），三连全徘徊轮达 0/9**——昨日"任务书加长嫌疑排除"被今日受控对比**推翻**：
  今日四轮噪音同档（7/1/10/10），旧文案轮（16）4/4 全候选、新文案轮（17/18/19）0/9 全徘徊，任务书是
  唯一持续变量（按 31% 基线率，连续 9 零编辑概率 ≈3.5%）。**教训：隔天数据不能当对照组**。
- **因果机制**：①"首选模块级（顶格、类外）"迫使模型在 100 行读窗里**寻找类边界**——定位成本暴涨，
  读循环死；旧文案允许紧挨可见代码插入。②"必然 NameError"威胁语引发谨慎偏置。
- **回敲（`1073bbc`）**：迎着模型自然路径——runbook 改推**类内新增 @staticmethod**（同级缩进、紧挨着
  放）+ `类名.方法名(...)` 调用（第十六轮候选 1/2 本就走这条路，只差 7 字前缀）；模块级降备选；威胁语
  撤出任务书（保留在事后纠偏）；tip/oracle 消歧同向翻转（最小修复=补前缀 在前）。
- 记账：19 轮 65 次尝试、真候选 20。第二十轮为新文案 A/B 的验证读数。

**进度（2026-07-08 午前）—— 第二十轮实跑（淘汰赛⑦，A/B 验证轮）：候选率回升，假说获初步支持：**

- **2/4 候选（6 次超时干净档）**：撤回"首选模块级"后候选率从 0/9 回到 2/4——A/B 初步支持"文案定位
  成本"假说（n 仍小，继续观察）。候选 1 只插入（+67，未变短毫秒拒）；候选 4 只替换（-76/+1，调用
  未定义的 `_ternary_match_branches`，作用域毫秒点名——名字未绑定在任何类体，消歧提示按设计不触发）；
  候选 2/3 预算徘徊。断路未触发（候选 1 即动手）。
- 记账：20 轮 69 次尝试、真候选 22、基建零事故。"两步齐做+调用形式正确"仍未合体——继续滚。

**进度（2026-07-08 午后）—— 第二十一轮实跑（淘汰赛⑧）：1/4，A/B 续持：**

- **1/4 候选（3 次超时干净档）**：候选 1 只替换（-75/+3，调用真未定义的 `_ternary_match_loop`，
  毫秒点名）；候选 2/4 徘徊（预算/读额）；候选 3 死于**三态门阻断（高置信拒绝 0.62）**——少见但
  合法的循环内护杀首次在淘汰赛现身。断路在候选 1 之后三连零编辑处正确触发（4/4 中止）。
- **A/B 续持**：撤回文案后两轮 3/8（≈37%）回到基线转化率（31%）——0/9 异常段确认为文案所致。
- 记账：21 轮 73 次尝试、真候选 23、基建零事故。继续滚。

**进度（2026-07-08 午后②）—— 第二十二轮实跑（淘汰赛⑨）：3/4，撤案后最佳；零件集齐待合体：**

- **3/4 候选（6 次超时干净档）**：候选 2 只插入（+78，且内藏改写——`return body_node` 丢了
  `evaluator.eval`，未变短先拒故守恒未及出手）；候选 3 **忠实只插入**（+73）；候选 4 **干净只替换**
  （-74/+3，调用未定义 `_ternary_match_loop`）。三个候选合起来零件齐全——教训注入可见生效
  （候选 4 按 2/3 的"未变短"教训做了替换，却丢了插入）：**模型把两步当二选一而非顺序**，
  单候选完整度仍是天花板。撤案后三轮 6/12=50% 转化率，A/B 结论稳固。
- 记账：22 轮 77 次尝试、真候选 26、基建零事故。继续滚。

---

## 前瞻规划（2026-07-06 定稿）—— P3 收官 → P4 元循环 → 常态化

**本节按"交接文档"标准落笔：下一位接手者（人或 AI）读完本节 + 上面的进度日志，
不需要问任何人就能继续创作。** 按依赖顺序编号 S0-S6；每步给「做什么 / 为什么 /
触发条件 / 实现位置与接口 / 守护测试落点 / 完成判据」。

### 交接快照（动手前必读）

**北极星与红线（不可动摇）**
- 终局目标：agent 能**安全迭代自己的代码**（P4 元循环），人只做最终合并裁决。
- 红线①：oracle 必须在 agent 写权限之外——`tests/`、`agent_system/self_update.py`、
  `agent_system/run_self_update.py`、`agent_system/task_mining.py`、`scripts/preflight.py`
  是"考官域"，agent 不得改判自己的考官（S4 之前靠任务书文字约束，S4 起机械化）。
- 红线②：一切修改都在**临时 git worktree**（从 HEAD 建、放仓库外 tempdir）里发生；
  过 oracle → 留 `self-update/<名>-<时间戳>` 分支**由人合并**，绝不自动 merge；
  被拒 → 回滚删净（worktree+分支零残留，22 次尝试实测无一例外）。
- `tests/test_deadloop.py` 永不进 pytest 收集（`tests/conftest.py` 的 `collect_ignore`
  守着，别动）。提交规范：中文信息、结尾 Co-Authored-By 尾注、**未经用户要求绝不 push**、
  提交前全量 CI。用户已明示暂不换模型（`SANYAN_MODEL` 通道保留，S6 做对照实验时再议）。

**一键命令**
```bash
# 实跑（仓库根执行；需环境变量 SANYAN_API_KEY，密钥绝不写进源码/仓库）
python -X utf8 agent_system/run_self_update.py --pick ternary_match --attempts 4
#   EXIT 0=有候选被接受(打印分支名)  1=尝试耗尽全拒  2=--pick 未命中(先 --list 看榜)
# 跑前检查：git status 必须干净、无残留 self-update/* 分支、git worktree list 只有主树
# 全量 CI（提交前必跑）——注意 pytest 必须限定 tests/（裸 pytest 会撞 csrc/ 的 torch/numpy）
ruff check . && ruff format --check . && mypy .
python -X utf8 scripts/preflight.py --quick        # ALL CHECKS PASSED 10/12 (2 quick-skip) 为绿
python -X utf8 -m pytest tests/ -q                 # 基线 2554 passed / 4 skipped
#   skip 数随 gcc 是否在 PATH 漂 4-6、passed 数 ±2 属环境浮动，0 failed 才是硬指标
```

**关键文件地图（谁负责什么）**
- `agent_system/self_update.py` —— 核心闭环。`SelfUpdateLoop.run(task_name, edit_fn)`：
  建 worktree → `edit_fn(wt)` → `git add -A` + `commit_excludes` 把副产物（learned_styles.md、
  agent*.db）reset 出暂存 → 无 diff 拒 → commit → oracle → 接受留分支/拒绝走
  `reject_hook(wt, reason)`（尸检窗口，异常被吞不挡回滚）→ 回滚。oracle 工厂：
  `make_shrink_oracle(rel_path, func_name, baseline_span, baseline_source=)`（静态四连闸：
  span 变短 → 嵌套 def/大粘贴诊断 → 引用可解析（作用域感知 `_unresolved_calls_in_function`）
  → 守恒检查（`_function_body_lines`，原函数体每行必须存活）——全毫秒级，置组合首位）；
  `make_pytest_oracle(baseline_failed, timeout=)`（失败数≤基线 + `failing_test_names` 进理由）；
  `make_differential_oracle()`；`combine_oracles([...])` 依序短路。
- `agent_system/run_self_update.py` —— CLI。挖掘 → `pick_task` 子串选靶 → 任务书 =
  `picked.prompt()` + `_RUNBOOK`（实战指引：只搬不改/平级定义/先定义后替换/别 shell 读文件）
  → 设 `SANYAN_SKIP_RULE_GEN=1`、`SANYAN_REQUIRE_EDIT=1`、`SANYAN_LOOP_TIME_BUDGET=900`、
  `SANYAN_TOOL_REPEAT_LIMIT=10`（经子进程继承）→ `--attempts` 循环。
  纠偏：`classify_tip(reason, hints)` 七类对症（对照表见下）；`build_retry_feedback(reason,
  hints, earlier_tip)` 两课链（最近一课+更早一课，同课去重）。`make_reject_diff_dumper`
  回滚前把被拒 patch+stat 追进 agent 日志。
- `agent_system/loop.py` —— agent 主循环 `run_legacy(rt, task, max_rounds, dry_run)`。
  轮顶依序：结果退化检测 → 时间预算护杀（`SANYAN_LOOP_TIME_BUDGET`，损坏值回 420）→
  单步超时 → 徘徊顶推（`SANYAN_REQUIRE_EDIT` 且零改动且轮次>一半或耗时>预算一半，一次性，
  文案点明先定义后替换）→ 上下文压缩 → LLM 调用（`error|` 哨兵串转 RuntimeError 走连败
  计数，三连快中止，不进 llm_outputs）→ 解析 → 工具执行（`cog=='AFFIRM'` 才记 modified）→
  done 分支（REQUIRE_EDIT 下零改动 done 顶回至多 2 次）。所有 break 落 `stop` 真实原因，
  return `stop or '已达N轮'`——面板不说谎。
- `agent_system/agent_llm_handler.py` —— `llm_call`（3 重试，彻底失败返回 `error|LLM调用失败…`
  哨兵串——是给上层识别的契约，别改成 raise，其它调用方按字符串消费）；`parse_tool`
  五级解析：JSON 括号计数（`_TOOL_ARG_ORDER` 按工具拍平 dict 参数，`_flat_arg` 列表按行拼）
  → 管道格式 → done → 关键词启发式（**只对短单行**）→ 单 token 原样 / 多词散文返 None
  （loop 有优雅重提示）。
- `agent_system/agent_runtime.py` —— `_constraint_violation`（同工具限额
  `SANYAN_TOOL_REPEAT_LIMIT` 默认 5）；`_parse_tool`/`_llm_call` 薄委托。
- `agent_system/task_mining.py` —— `mine_all(root, pytest_output=)` 产 MinedTask
  （failing_test > todo > long_function 排序）；`mine_long_functions` 默认**不截断**
  （曾因 limit=30 让靶子随无关代码增长蒸发）；`MinedTask.hints` 是静态标注的候选块行区间
  （如 "L326-399（循环块，74行）"），已接进任务书与纠偏。
- 守护测试地图：`tests/test_self_update.py`（闭环机制/排除/回滚）、`tests/test_shrink_oracle.py`
  （静态四连闸全家）、`tests/test_selfupdate_cli.py`（CLI/纠偏/两课/尸检）、`tests/test_loop.py`
  （主循环：`_LoopRt` 脚本化假件底座——新循环行为测试都长在它上面）、`tests/test_agent_runtime.py`
  （parse_tool 全形态/约束限额）、`tests/test_task_mining.py`。

**环境变量总表**
| 变量 | 谁设 | 语义 |
| --- | --- | --- |
| `SANYAN_API_KEY` | 用户 | LLM 密钥，只走环境，绝不入库 |
| `SANYAN_MODEL` / `SANYAN_PROVIDER` | 用户 | 换模型/供应商通道（S6 对照实验）|
| `SANYAN_SKIP_RULE_GEN` | CLI 自动=1 | 跳过规则生成前奏（省 2-4 次 LLM 调用）|
| `SANYAN_REQUIRE_EDIT` | CLI 自动=1 | 启用零改动 done 顶回 + 徘徊顶推 |
| `SANYAN_LOOP_TIME_BUDGET` | CLI 自动=900 | loop 总预算秒（默认 420；子进程硬杀 1800s 兜底）|
| `SANYAN_TOOL_REPEAT_LIMIT` | CLI 自动=10 | 同工具调用上限（默认 5）|
| `AGENT_DATA_DIR` | 测试 | agent 持久化数据隔离目录（learned_styles/agent.db 认它）|

**环境坑（全部实测，先信这个再排障）**
- Clash 代理 `127.0.0.1:7890`：agent 超时事件 **≤6 次/轮=正常噪音；≥20 次=风暴**——该轮
  读数作废（模型输出质量同步崩坏，大粘贴即风暴产物），暂停实跑等恢复（重启 Clash/关开 TUN，
  或供应商限流冷却）。探针 `curl -x 127.0.0.1:7890 -sI -m 8 https://api.anthropic.com`
  0.3s 返回=当下健康，**但只代表当下**（0706 五轮全是探针健康、跑中风暴）。
- gcc 是否在 PATH 漂移 → pytest skip 4-6 / passed ±2 浮动，非回归；0 failed 才算数。
- `.md` 提交时 CRLF→LF warning 正常（.gitattributes 约定）。
- Windows `time.time()` 粒度粗：时间类测试用 `-1` 当"立即超时"，别用 `0`（首轮 elapsed
  可恰为 0.0）。
- CLI stdout 重定向到文件有块缓冲：后台跑时 `EXIT=$?` 用 `>>` 追加进同一日志再读。
- 后台实跑期间**不要 commit**：每次尝试的 worktree 从当时 HEAD 建，中途提交会让同轮
  尝试跑在不同代码上，实验作废。

**尸检工作流（每轮跑完照此判读）**
1. CLI 日志（scratchpad）看各尝试拒绝原因：`oracle#0` 前缀=静态闸毙（毫秒级，理由已点名
   病灶）；`oracle#1`=pytest 毙（带失败用例名）；`无改动`=徘徊/空转。
2. agent 日志在 `%TEMP%/sanyan-su-agent-<时间戳>.log`（CLI 起跑时打印路径）：
   `grep -c "TimeoutError|SSL"` 定噪音级别 → `grep "工具=replace|工具=write"` 看是否触及
   编辑 → `grep 顶推` 看顶推触发及其后 2-3 轮是否动手 → 拒绝时自动追加的
   `=== 被拒改动尸检 ===` 段（patch 前、stat 后）看改成了什么样。
3. 新死法出现 → 照三件套模式扩展：**毫秒级拦截（shrink oracle 加诊断）+ 点名病灶（拒绝
   理由带修复方向）+ 对症纠偏（`classify_tip` 加分支）**，各配回归钉。

**死法↔反制对照表（22 次尝试实测；`classify_tip` 的分支即此表）**
| 死法（实例轮次） | 毫秒拦截 | 对症纠偏 |
| --- | --- | --- |
| 零改动徘徊/空转（多轮） | 无 diff 拒 | "务必真改文件" + 循环内顶推 |
| 只做第一步：插 helper 不替换（0706 四轮A1/七轮A1） | span 未变短 | "两步都要做完" + 候选块行区间 |
| 只做第二步：替换却没定义（0704A2/0706 六轮A1） | 引用可解析（作用域感知） | "先定义再调用，两步都落文件" |
| 两步齐做但嵌套 def（P2 首跑/0706 五轮A1） | 未变短 + 嵌套诊断 | "搬到与原函数平级" |
| 重写而非搬运：改校验/换异常（0705 二轮A3） | 守恒检查点名消失行 | "这些行原样保留" |
| 大粘贴 +390/-0（0706 七轮A3，风暴产物） | 未变短 + 净增超体量诊断 | "整个改动只需两笔" |
| 挂测试：行为变了（进 pytest 的候选） | pytest + 失败用例名 | "保持逻辑严格等价" |

---

### S0 平稳窗口读数（当前阻塞项，其余步骤的分流阀）

- **做什么**：代理恢复后跑 2-3 轮 `--pick ternary_match --attempts 4`，读干净环境下的真实
  成功率。有效读数口径：超时 ≤6/轮；风暴轮作废重跑。每轮跑完按上面的尸检工作流判读并把
  结果追进本文件进度日志（沿用既有格式：轮次/超时数/各尝试死因/候选与否）。
- **为什么**：0704–0706 的 22 次尝试全部带环境噪音，模型真实水平从未被干净测量；机械欠账
  已清零，继续改代码没有已知目标——先测量再决策。
- **触发**：用户确认代理恢复，或探针健康 + 首轮超时 ≤6。
- **完成判据**：首个被接受分支出现（→ S1）；或 2-3 轮干净读数仍 0 接受（→ S2）。

### S1 首胜处理流程（触发：首个 accepted 分支出现）

- **做什么**：① `git show <branch>` 人工审 diff——守恒/引用/变短已被静态背书，人只审语义
  合理性与命名品位；② 在分支上跑全量 CI（四件套 + `pytest tests/`）；③ 合并（普通 merge，
  保留分支名里的时间戳信息于 merge message）；④ CHANGELOG 记账（沿用 v3.5x 格式，作为
  "首个 agent 自产合并"里程碑条目）；⑤ **同任务再跑 3-5 轮**，把接受率基线写进本文件
  （后续 S2/S5/换模型全部用它做对照）。
- **注意**：接受的分支 diff 里不应有 learned_styles/agent.db（`commit_excludes` 已排除，
  审查时顺手确认）；若分支落后 main 多个提交，先 rebase 到 main 再跑 CI（worktree 建自
  当时 HEAD，与现 HEAD 可能有距离）。
- **完成判据**：合并完成 + 接受率基线数字写进本文件进度日志。

### S2 候选淘汰赛（P3 完全体；触发：S0 干净读数 2-3 轮仍 0 接受，或要直接提吞吐）

- **做什么**：一任务 N 候选取优，失败教训跨候选累积。
- **实现位置与接口**（`agent_system/self_update.py` 尾部新增，不动 `SelfUpdateLoop` 本体）：
  ```python
  def run_tournament(loop, task_name, edit_fn_factory, n, *, breaker=2) -> UpdateResult:
      """n 个候选串行赛（代理/供应商是瓶颈，并行只会加剧限流）。
      edit_fn_factory(k: int, feedback: str) -> edit_fn   # k 从 1 起；feedback 为
      前面所有候选拒绝原因经 classify_tip 去重合并的多课提示（把抽签变爬山）。
      首个 accepted 即返；全败返回"信息量最大"的一次拒绝（优先带病灶诊断的）。
      breaker: 连续 breaker 个候选零编辑调用 → 判风暴断路，中止本批（防对风暴烧预算）。
      """
  ```
  CLI 侧 `--candidates N`（与 `--attempts` 互斥，N≥2 走淘汰赛路径）；`edit_fn_factory` 由
  现有 `make_agent_edit_fn(prompt+feedback, ...)` 包一层即得；"零编辑调用"判据复用
  agent 日志 grep 或让 `SelfUpdateLoop.run` 把"无改动"原因回传（已有）计数。
- **守护测试落点**：`tests/test_self_update.py` 用假 edit_fn 钉三条——首过即停不烧后续、
  全败返回最优拒绝理由、断路器在连续零改动时中止；`tests/test_selfupdate_cli.py` 钉
  `--candidates` 接线与 feedback 逐候选累积。
- **完成判据**：同预算下接受率 > 顺序 `--attempts`（用 S1 基线对照）。

### S3 failing_test 任务类激活（触发：真实失败测试出现；平时休眠）

- **做什么**：CI 红时 `pytest tests/ -q > fail.log; python -X utf8 agent_system/run_self_update.py
  --pytest-log fail.log`（挖掘器把 FAILED/ERROR 排最高优先）。需补两件：
  ① `make_target_green_oracle(test_id, *, timeout)`——先单跑 `pytest <test_id>` 判**由红转绿**，
  再复用 `make_pytest_oracle` 判全量不退化（组合首位放转绿判定，失败最常见、先短路）；
  CLI 在 `picked.kind == 'failing_test'` 分支接线（现在该分支只有通用 oracle）。
  ② 任务书模板：把失败输出关键片段（assert 行/异常类型）截进 prompt 帮模型定位——
  `MinedTask.detail` 已存失败摘要，核对截断长度即可。
- **为什么**：修失败测试是弱模型最友好的任务类（改动局部、oracle 天然二值、无结构性
  要求），也是自更新体系第一个真实生产价值出口。
- **守护测试落点**：`tests/test_shrink_oracle.py` 旁新增 `test_target_green_oracle.py`：
  假 runner 注入（红→绿放行 / 仍红拒 / 全量退化拒）。
- **完成判据**：一次真实红测被 agent 修绿并人工合并。

### S4 oracle 域写保护（P4 前置硬闸；可随时做，P4 前必须做）

- **做什么**：红线①机械化 + P5 密钥闸提前落地。
- **实现位置与接口**（`agent_system/self_update.py`）：
  ```python
  PROTECTED_PATHS = ('tests/', 'agent_system/self_update.py', 'agent_system/run_self_update.py',
                     'agent_system/task_mining.py', 'scripts/preflight.py')
  # SelfUpdateLoop.run 第 2 步 commit 之后、oracle 之前：
  #   touched = git show --name-only --format= HEAD  (在 worktree 里)
  #   任一命中 PROTECTED_PATHS 前缀 → _reject('触碰考官域: <路径>（红线①，fail-closed）')
  #   diff 文本含 SANYAN_API_KEY 字面量或新增 os.environ['SANYAN_API_KEY']= 写入 → 同拒
  ```
  为什么放 commit 后：复用现成 `_git('show', ...)`，且尸检钩子仍能拿到完整 diff。
  注意保护检查**必须在 oracle 之前**——pytest oracle 防不住"把测试改成恒过"（改了 tests/
  再跑 tests/ 是循环论证）。
- **守护测试落点**：`tests/test_self_update.py` mini 仓库里写 `tests/x.py` → 必拒；写密钥
  字面量 → 必拒；正常 ops/ 改动 → 不受影响。
- **完成判据**：单测全绿 + 一次实跑演示"触碰 tests/ 的候选被当场拒、理由点名红线①"。

### S5 P4 元循环首战（触发：S1 完成、long_function 接受率 ≥ ~30%、S4 已上线）

- **做什么**：挖掘目标指向 `agent_system/` 自己。首个目标建议 `agent_system/loop.py` 的
  `run_legacy`（220 行，挖掘榜 #6）——属 agent 代码但**非考官域**（S4 保护清单不含 loop.py，
  这是有意的：loop 是"选手"，self_update/oracle 才是"考官"）。跑法与 S0 完全一致，只是
  `--pick run_legacy`；oracle 栈自动生效（S4 域保护 + shrink 四连闸 + 全量 pytest——
  `tests/test_loop.py` 的 `_LoopRt` 假件用例正是改后 agent 的行为回归——+ 差分）。
  产出分支仍由人合并（红线②在 P4 不放松）。
- **风险与对策**：agent 改 loop.py 改坏顶推/纠偏等自更新依赖 → 该分支上的 test_loop 会红
  （oracle 拦）；改动语义微妙难审 → 人工审查时对照本文件"关键文件地图"里 run_legacy 的
  轮顶顺序清单逐项核。
- **为什么**：北极星本体。它不是新工程——是"S0-S4 的能力指向自身"，所以门槛设在接受率
  而非代码量。
- **完成判据**：agent 产出的 agent 代码分支被人工合并，合并后自更新闭环全量回归绿。

### S6 常态化（触发：S1 后即可与 S2-S5 并行）

- **做什么**：
  ① **夜间自动跑**：定时任务（Windows 计划任务或 Claude Code 的 loop/schedule）——起跑前
  探针，健康才跑、风暴跳过；每晚 1-2 轮攒统计；跑前 `git status` 必须干净（脏树直接跳过
  并记日志，绝不 stash 用户工作）。
  ② **结果聚合** `scripts/su_stats.py`：输入 agent 日志目录，按启动时间戳分轮输出
  `轮次 | 尝试数 | 超时数 | 编辑调用数 | 各尝试死因(拒绝理由首行) | 是否接受`；死因分类
  直接复用拒绝理由里的关键词（与 classify_tip 同一套词表，保持一处定义）。0706 的手工
  grep 原型见进度日志。
  ③ **模型对照通道**：同任务 `SANYAN_MODEL`/`SANYAN_PROVIDER` A/B（换模型与否用户拍板；
  既有数据表明模型是时间表头号变量——换强模型预计整体估期÷2~3）。
- **完成判据**：连续一周无人值守跑出周报级统计（接受率曲线成为 S2/S5 触发仪表盘）。

### 长期（S6 之后，按需）

- **todo 任务类**：挖掘已产出（`mine_todos`），oracle 需按 TODO 语义逐条定制——最难泛化，
  排最后；先挑"TODO: 补测试"这类 oracle 天然可判（新测试文件存在且绿）的子类试点。
- **跨文件重构**：守恒检查扩到多文件（`baseline_source` 变映射：路径→内容；消失行判定
  改为"在任一新文件存活"）；引用可解析需理解 import 图——工程量大，等单文件任务类
  接受率稳定后再议。
- **P5 深化**：密钥闸已在 S4 落地；余项为 agent 工具面权限收敛（run_shell 白名单化——
  实测模型爱用 shell 读文件/数行数，白名单 `python -X utf8 -m pytest` 等少数命令即可）
  与审计日志（每个被接受分支附 oracle 判定全记录——`OracleVerdict.report` 已有结构，
  落盘即可）。待 P4 稳定后按实际风险排。
