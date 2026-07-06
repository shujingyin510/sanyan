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
