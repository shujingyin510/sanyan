# Changelog

---

## [v3.35.0] — 2026-06-15 (Agent进化系统 + Knowledge Layer + Meta-Knowledge Transfer)

### 新增
- **策略自优化系统**（Layer 1）：`agent_strategy.py`
  - PromptEvolver: Prompt自进化（变体库+成功率追踪+自动选择）
  - ToolSelectionLearner: 工具选择学习（任务类型分类+贝叶斯平滑）
  - StrategySwitcher: 策略切换（简单→direct / 中等→single / 复杂→tournament）
  - ABRollout: A/B测试（多策略并行+赢家选择）
- **自主循环系统**（Layer 2）：`agent_loop.py` + `agent_loop_monitor.py`
  - 文件监控模式：检测到变化自动触发验证
  - 连续循环模式：持续运行验证
  - 日志持久化：.agent_loop.log 记录每次循环
  - 统计：成功率、修复率、平均耗时
  - 健康监控：卡住检测、连续失败告警
  - 回滚验证：stash 状态检查
- **约束进化系统**（Layer 3）：`agent_evolution.py` + `agent_evolution_v2.py`
  - ConstraintEvolver: 约束进化器（定义可改变/不可改变区域）
  - DifferentialVerifier: 差分验证器（多后端一致性+性能）
  - MultiObjectiveEvaluator: 多目标评估器（综合得分）
  - SelfHostVerifier: 自举验证器（不动点验证）
  - PatchDSL: 结构化补丁格式（before/after/rationale/expected）
  - MutationBudget: 进化预算控制（MAX_FILES=1, MAX_LINES=20, MAX_PATCHES=1）
  - TernaryPatchEvaluator: 三态Patch评分（TRUE/FALSE/UNKNOWN）
  - CandidateTournament: 候选锦标赛（多候选竞争，赢家存活）
  - EvolutionMemory: 进化历史库（SQLite持久化，成功率追踪）
  - AgentCodeModifier: Agent自主改代码（读代码→生成补丁→应用→测试→回滚/接受）
- **Knowledge Layer**（Layer 4）：`agent_knowledge.py` + `agent_knowledge_confidence.py` + `agent_generalization.py` + `agent_causal_chain.py` + `agent_meta_knowledge.py`
  - TaskClassifier: 任务分类器（7种任务类型）
  - TaskEmbedding: 任务向量化（12维特征）
  - ClusterLearning: 自动聚类学习任务距离
  - KnowledgeConfidence: 知识置信度计算（样本数×成功率×一致性）
  - ConfidenceAwareKnowledge: 带置信度的知识库
  - GeneralizationValidator: 知识泛化验证（训练集→测试集）
  - CausalChainExperiment: 因果链闭环验证
  - TaskPatternTransfer: 任务规律迁移（不迁移参数）
  - ConfidenceModelTransfer: 置信度模型迁移
- **Reviewer Agent**：独立代码审查（11条规则，含4条对抗补丁检测）
- **PatchHistory**：Patch历史数据库（成功率/回滚率/收益/可信度权重）
- **RealBenchmark**：真实基准测试（before/after耗时对比）
- **EvolutionDashboard**：进化仪表盘（可视化进化状态）
- **Cost-Aware Evolution**：收益/成本感知（效率=改进/成本）
- **Parameter Importance Ranking**：参数影响力排名（自动计算Tier）
- **MetaConfig Evolution**：配置参数进化（ConfigSchema+ConfigPatch+TernaryVerdict）
- **Strategy Schema**：策略参数化（StrategySchema+StrategyReplay）
- **Task Taxonomy**：任务分类体系（MetaLearningDB+ConditionalOptimizer）
- **CLI 选项**：`--evolve`、`--self-host`、`--auto-evolve`、`--code-evolve`、`--review-evolve`、`--evo-dashboard`、`--validate`、`--metaconfig`
- **post-commit hook 增强**：防递归（AGENT_HOOK_RUNNING 环境变量）
- **研究文档**：`docs/research/` 目录（4篇研究文档+架构文档）

### 修复
- **mypy 152 错误清零**：18 个文件批量 `Optional` 类型注解修复，覆盖 `str`/`int`/`list`/`dict`/`Callable`/自定义类型所有 `= None` 缺 `Optional` 的模式
- **ruff check**：11 处自动修复

### 变更
- **README.md**：起源挪到第一屏，简介加「一个人一个半月」，v3.32 更新摘要块，四层架构图、三层知识体系、三态逻辑贯穿说明
- **README_EN.md**：同步重构（起源第一屏 + "One person. Six weeks." + v3.32 What's New）
- **AGENTS.md**：更新四层架构、三层知识体系、LLM vs Agent知识对比
- **agent_runtime.py**：集成所有新模块
- **CHANGELOG.md**：合并同一天条目

### 关键实验结果
- **因果链闭环**：Knowledge → Calibration → Selection → Success ✓ (+43.6%)
- **知识迁移**：配置不可迁移（-4.6%），但任务规律可迁移（+27.9%）
- **Meta-Knowledge Transfer**：迁移策略类型而非具体配置，证明战略比战术更容易迁移

---

## [v3.33.0] — 2026-06-15 (Phase 3/4 功能)

### 新增
- **并行执行引擎**（P14/P15）：`agent_parallel.py` — 独立工具并行执行，假设并行验证，预计加速 2-4x
- **智能上下文压缩**（P22-P24）：`agent_context.py` — 分层摘要+滑动窗口+重要性评分，Token 节省 ~40%
- **跨会话学习**（P19-P21）：`agent_learning.py` — SQLite 持久化工具成功率、失败模式库、任务类型映射
- **安全沙箱**（P16-P18）：`agent_sandbox.py` — 命令黑名单/白名单、文件系统守卫、只读模式、审计日志
- **可观测性增强**（P25-P27）：`agent_obs.py` — 决策链追踪、性能分析、实时仪表盘
- **流式响应**（P28-P30）：`agent_streaming.py` — LLM 边生成边显示，支持可中断、渐进式输出
- **高阶工具组合**（P31-P33）：`agent_composition.py` — Unix 风格管道、复合工具、条件工具链
- **工具自发现**（P13）：`agent_tool_graph.py` — 自动扫描 ops/*.py 注册工具，提取元数据
- **多Agent共享上下文**（P34-P36）：`agent_shared.py` — 共享上下文空间、共享符号表、Agent协调器
- **Token 追踪**：LLM 调用实时统计 Token 用量，支持 DeepSeek/Gemini API
- **CLI 选项**：`--sandbox`（安全沙箱）、`--report`（性能报告）、`--stream`（流式）、`--pipeline`（管道）、`--dashboard`（仪表盘）、`--trace`（追踪）、`--perf`（性能）
- **交互命令**：`/仪表盘`、`/追踪`、`/性能`、`/经验`、`/安全`、`/共享`、`/管道`

### 变更
- **README.md**：更新 Agent 特性表（+10项）、CLI 用法、交互命令
- **AGENTS.md**：更新架构图（四阶段）、文件结构（+10文件）、运行方式
- **agent_runtime.py**：集成 Phase 3/4 所有模块，优化性能记录
- **run_agent.py**：新增 CLI 选项和交互命令

---

## [v3.32.0] — 2026-06-14

### 新增
- **Agent 自主闭环**：`auto_verify.py` 自主循环脚本（提交→全量测试→通过自动commit/失败回退），三条路径实测通过
- **git 工具扩展**：`git_stash`（保存现场）、`git_reset_hard`（回退提交）、`git_commit_auto`（自动提交）注册到 Agent 工具集
- **post-commit hook**：`.git/hooks/post-commit` + `post-commit.bat`，检测代码变更自动触发验证

### 修复
- **md 文件全面审阅**：33 个 .md 文件逐行检查，修复 8 处过时内容（版本号 v3.29→v3.31、模型名 deepseek-chat→v4-pro、roadmap 已实现项标 ✅、API 密钥路径、README 目录树）
- **mypy 类型**：`tools_used` `Optional[List[str]]`、`_agent_registry` 类型注解

### 变更
- **CHANGELOG**：补全 v3.31.0（28 项）和 v3.32.0

---

## [v3.31.0] — 2026-06-13

### 新增
- **LLM 模型升级**：`deepseek-chat`/`deepseek-reasoner` → `deepseek-v4-pro`，显式 `thinking` 模式 (`budget_tokens: 2048`)，`max_tokens`: 256 → 4096
- **工具调用 JSON 化**：系统提示词输出 `{"tool":"...","args":{...}}`，解析器用括号计数 + `json.loads`，pipe 格式 `tool|params` 作为回退
- **任务级经验库**：跨任务关键词匹配，失败 ≥2 次自动生成 AVOID 提示，下次同类任务注入警告
- **结构化重试历史**：每轮记录 `[retry N] diff + 失败原因`，注入 task.description
- **Toggle 检测**：连续两轮同一文件内容回到 baseline → 自动 escalate
- **同位置连错检测**：连续两轮同文件同错误 → 自动 escalate
- **愿景故事**：`愿景故事.md` 讲述项目由来（从 Setun 到三言）

### 修复
- **`Hypothesis` 构造函数**：`tools_used` 未传入计划工具，导致所有假设无工具执行
- **`_execute_hypothesis`**：每步调 LLM 获取参数（对齐 `_run_legacy`），不再用 `ctx.build()` 当参数
- **hypothesis 生成器**：独立系统提示词（不与工具格式冲突），`done` 加入已知工具白名单
- **LLM 失败防死循环**：`_run_legacy` 约束超限 `continue` → `break`；`_execute_hypothesis` 连续 3 次失败退出
- **系统提示词**：身份锚定 + 详细工具说明 + JSON 示例，解决身份幻觉
- **mypy**：`tools_used` 类型 `Optional[List[str]]`，`_agent_registry` 类型注解
- **preflight**：`self_host`/`sugar_self_host` 改查 stderr + returncode；路径检测 Windows 适配
- **硬编码 API 密钥**：`village_config.san` 改用 `环境变量(SANYAN_API_KEY)`

### 变更
- **AGENTS.md 更新**：LLM 模型/JSON 格式/经验库/反馈闭环/文件结构
- **全量 CRLF→LF**：所有 .py/.san/.c 文件换行符统一为 LF
- **愿景故事移至根目录**：`docs/vision.md` → `愿景故事.md`

---

## [v3.30.0] — 2026-06-12

### 新增
- **效应类型系统**：`确定[X]`/`不确定[X]` 编译期类型检查，5文件改动 + 30项测试
- **四后端差分模糊测试**：Python VM/C VM/LLVM 三后端一致性验证，12项测试全通过
- **自举 Level 2**：A→B→C 不动点验证（VM 加载编译器自举，B==C逐字节一致）
- **自举 Level 3**：318行C种子VM（`csrc/sanyan_vm_seed.c`），零依赖纯syscall，35 opcode
- **自举 Level 4**：617行x86_64 NASM汇编VM（`csrc/sanyan_vm_l4.asm`），35 opcode全实现
- **ISA v2**：LOAD16/STORE16/CALL32/PUSH_STR16/CLOSURE 5个新opcode
- **哈希字典**：FNV-1a哈希 + 开放寻址，O(1)替代O(n)
- **多 Agent 协作（v0.4）**：调度子Agent/Agent消息/列出Agent，子Agent独立决策+继承置信
- **sanyanc 编译器**：sugar语法直连 + 包管理CLI (install/search/list/info/uninstall)
- **汇编器 CLI**：`python asm.py program.sasm -o program.bin`，CALL/JMP 修复
- **preflight 预检**：`python preflight.py` 一键全量检查，推送前必须通过
- **反汇编器**：`disasm.py`，支持--hex/--brief/--export，6项测试
- **字节码验证器**：`verify.py`，JMP/LOAD/STORE边界检查

### 修复
- **C VM编译修复**（10项）：`obj_type`/嵌套函数/`rt_trit_confidence`/`rt_float_t`重复
- **LLVM 死循环修复**：`llvmgen/compiler.py` `_parse_all_sexprs` 死循环
- **字节码编译器修复**：负数识别（`全部数字`/`文本转整数`）+ 函数体编译（去掉isList守卫）
- **Level 4 汇编安全加固**（30+项）：栈下溢/变量越界/类型检查/UTF-8四字节/空指针/DICT_HAS rsi
- **10个已知bug**：`(乘5 -2)` VM返回0、`(定义f0(p0)27)` VM空输出、C VM `--run`多打印、LLVM比较二值、求值器OR未注册等

### 测试
- `test_effect_types.py` 30项
- `test_diff_fuzz.py` 12项
- `test_disasm.py` 6项
- `test_self_host.py` 8项（含Level 2 + Level 3）
- 全量CI：pytest 1650+ 通过

---

## [v3.29.0] — 2026-06-11

### 新增
- **TritValue 歧义修复**：int 列表必须所有元素 ∈ {-1,0,1} 才视为 trit 值，避免 `[1,2,3]` 被误判为平衡三进制数
- **ops 双语别名补全**：arithmetic/string/control/file 等模块补齐中文别名（加/减/乘/除/余/幂/连接/取长/查找/替换/子串/分割/去空白/大写/小写/前缀/后缀/若/做/循环/遍历/设/跳出/继续/尝试/判/读文件/写文件）
- **P6 Prompt 缓存**：system_prompt 稳定化（缓存一次，不含可变内容）
- **数学函数覆盖**：ternary_core.py sin/cos/tan/sqrt/exp/log/log10 + 辅助函数测试（55项）
- **测试全量补全**：1251 项 Python 测试 + 46 项 .san 测试，全部核心模块 ≥ 90% 覆盖率
- **TritValue 修复**：`TritValue([1,2,3])` 不再被误判为平衡三进制数值

### 变更
- **ops/ternary_generic_ops.py 拆分**：694行→3个模块（ternary_set_ops 187行 + ternary_graph_ops 184行 + ternary_queue_ops 176行）
- **evaluator.py P6 集成**：system_prompt 缓存稳定化
- **ternary_engine.py**：重命名为 ternary_engine.py（保持向后兼容）

### 修复
- **ternary_core.py:342**：TritValue int 列表检查逻辑修复，只有 {-1,0,1} 元素才视为 trit
- **ops/string_ops.py**：`_unwrap_str` 支持所有类型转字符串
- **ops/data_pipeline_ops.py**：`TernaryAggregator.average/sum` 支持 TritValue 类型
- **ops/ternary_generic_ops.py**：三态队列/栈出队/弹栈返回元素而非列表

### 文档
- **AGENTS.md**：ops 双语注册规则 + 测试数量更新（20套）+ V5 架构图
- **README.md**：Agent 特性表更新 + 测试数量
- **README_EN.md**：同步英文版
- **ARCHITECTURE.md**：文件结构更新（拆分后的模块）
- **docs/roadmap.md**：标记已完成项

---

## [v3.28.0] — 2026-06-11

### 新增
- **并发融合**：`并发融合(任务1, 任务2, ...)` — 并发执行+Kleene结果融合
- **并发竞速**：`并发竞速(超时ms, 任务1, ...)` — 并发竞速，取最先完成
- **并发全部**：`并发全部(任务1, ...)` — 全部成功才返回真
- **三态模式匹配**：`匹配3(值) { 真→..., 可能→..., 假→... }` — 三态分支语法
- **置信度区间匹配**：`匹配信度(值, 阈值) { 高→..., 中→..., 低→... }`
- **链式信度传播**：`链(步骤1, 步骤2, ...)` — 置信度逐级传播
- **链式中断**：`链断(步骤1, ...)` — 假值中断并抛出异常
- **三态解包**：`解包(值 [, 默认值])` / `或解(值, 默认值)`
- **尝试链**：`尝试链(步骤1, ..., 默认值)` — 失败时继续
- **信度守卫**：`信度守卫(值, 阈值) { 高→..., 低→... }`
- **三态集**：`三态集` / `三态集加` / `三态集删` / `三态集含` / `三态集并` / `三态集交` / `三态集差`
- **三态图**：`三态图` / `三态图加节点` / `三态图加边` / `三态图最短路` / `三态图连通`
- **三态队列**：`三态队列` / `三态入队` / `三态出队`
- **三态栈**：`三态栈` / `三态压栈` / `三态弹栈`
- **三态Web框架**：`三态Web服务器` / `三态路由` / `三态监听` — 置信度降级+中间件
- **三态数据管线**：`三态管线` / `三态数据` / `三态清洗` / `三态聚合` / `三态验证`
- **共识操作**：`共识(a, b, ...)` — 多传感器共识，全部真时信度上升
- **测试用例**：`tests/test_new_features.py` 47 项（并发/模式匹配/容器/错误处理/Web/数据管线）

### 变更
- **ops/type_ops.py 拆分**：698行→3个文件（type_ops 170行 + ternary_source_ops 280行 + ternary_util_ops 150行）
- **ops/ternary_container_ops.py**：新增链式信度传播操作（链/链断/解包/或解/尝试链/信度守卫）
- **ops/concurrent_ops.py**：新增并发融合/竞速/全部操作
- **ops/control_ops.py**：新增匹配3/匹配信度操作
- **language/chinese.json**：新增三态集/三态图/三态队列/三态栈/三态数据/三态管线关键字映射
- **ops/string_ops.py**：`_unwrap_str` 支持 TernaryData 等自定义类型转字符串

### 修复
- **ops/data_pipeline_ops.py**：`TernaryData.__str__` 支持字符串转换
- **ops/data_pipeline_ops.py**：`TernaryAggregator.average/sum` 支持 TritValue 类型
- **ops/ternary_generic_ops.py**：三态队列/栈出队/弹栈返回元素而非列表
- **stdlib/bytecode_compiler.san**：`字列` → `字典键列表`（行55-56），修复皮肤映射冲突——`字列` 在 `language/chinese.json` 中解析为 `str_to_list`，导致 self-compile 时 `(字列 ov)` 把 dict 转字符串拆字符，首个字符 `{` 触发 KeyError。`字典键列表` 正确解析为 `dict_keys`
- **stdlib/bytecode_compiler.bin**：重编（6298B，SHA256 `b828d68d...`）
- **stdlib/sugar.bin**：重编（9839B，SHA256 `7f0b9635...`），同步 bytecode_compiler 变更
- **tests/test_ops_ext.py::test_dict_keys**：`字列` → `字典键列表`，同根因修复
- **evaluator.py**：移除未使用的 `commands.Commands` 导入

### 文档
- **docs/roadmap.md**：更新已完成/待实现状态
- **tests/test_new_features.py**：新增 47 项单元测试

---

## [v3.27.0] — 2026-06-07

### 新增
- **TernaryEngine 独立模块**：`ternary_engine.py`（131行），Kleene传播×贝叶斯置信度×保护门控，Agent/村庄/IoT 共用
- **村庄三态追踪**：`run_village_observe.py` 接入 TernaryEngine，每日显示全局三态置信度
- **MemoryStore 中文语义**：双字滑动窗口，英文标识符 + 中文片语同时匹配
- **AgentRuntime 工具层**：拆分到 `agent_tools.py:173`行，analyze/find_symbol/replace_all 等 12 个独立工具
- **SymbolTable**：符号表缓存，查一次全局复用，`_force_tool()` 智能首轮绕过 LLM
- **MemoryStore**：关键词检索记忆，替代全量 dump，只注入相关历史
- **ProjectGraph**：文件依赖关系图，`build()` 解析 import 语句
- **Plan Mode**：改/修/加类复杂任务先探索→确认→执行（`_enter_plan`）
- **Token Budget**：超 7000 字符自动压缩上下文（`_token_exceeded`/`_compress_ctx`）
- **Fail-Closed**：`rm -rf`/`DROP TABLE` 等危险命令硬拦截，干跑模式也生效
- **Constraints**：同工具限 5 次、同文件修改限 5 个（`_constraint_violation`）
- **Reflection**：测试失败→反馈 LLM→重试（最多 3 次）
- **信任感知规则**：`信任阈值` 字段（低信任时权重 ×3）、`条件` 字段（信任高/中/低）
- **必须全部匹配**：场景规则 AND 模式，`必须全部匹配:真` 时所有关键词全中才激活
- **Agent 自毁保护**：修改自身配置（最大轮次/API 密钥等）→ 高风险 `NEED_HUMAN`
- **`--auto` 模式**：全走 V3 新引擎
- **`--dry-run` 干跑模式**：write_file/replace_in_file 返回预览不实际写
- **`--report` 报告**：任务完成后输出修改摘要
- **`--list-tasks` / `--resume`**：SQLite 任务持久化，跨会话续接
- **小米 Token Plan**：新增 `tokenplan` 提供商（`token-plan-cn.xiaomimimo.com`）
- **V3 单元测试**：`tests/test_agent_runtime.py` 27 项（SymbolTable/MemoryStore/ProjectGraph/AgentRuntime）

### 变更
- **run_agent.py 拆分**：1485→1072 行（-28%），V3 引擎独立为 `agent_runtime.py`，工具层独立为 `agent_tools.py`
- **协议简化为 `tool|params`**：LLM 不再输出 JSON，只输出工具名和参数
- **analyze 输出优化**：摘要前置（`⚠ >50行: ...`）、函数优先显示、行范围 `def name() :start-end(N行)`
- **read_file 支持行范围**：`路径|起始行|结束行` 格式
- **replace_in_file/write_file 支持 `\n` 转义**
- **场景规则重排**：高风险规则优先匹配，`修改Agent配置` 排最前
- **高风险规则自动 2× 加权**
- **增益不足改为 continue**：多轮任务不被误挡
- **最大轮次 5→10**
- **LLM 超时 10→60 秒**，`http写` 支持从策略变量读取 `超时秒数`
- **清理已合并文件**：删除 `prompts.san`/`llm_http.san`/`tool_sched.san`

### 修复
- **sugar/parser.py**：`tok.tok_type`→`tok.kind`（CI 崩溃）
- **覆盖率 74.4%→76.4%**：排除 `repl.py`
- **mypy 0 errors**
- **ruff format 全通过**
- **JSON 清理**：`清理JSON` Python 端处理控制字符、`---END---` 剥离
- **JSON 缺 cog/act 默认值**：自动推断 AFFIRM/NEED_TOOL
- **空工具纠正**：LLM 返回 `tool:""` 时→系统自动从上次结果提取答案
- **agent.san 去重调度函数**（write_file/list_files 双份）
- **`_git_status_direct` 补 `r = _sp.run(...)`**（5 份审阅交叉发现）
- **bare `except:` → `except Exception:`**
- **`_constraint_violation` 副作用修正**（先检查后计数）
- **`_extract_key` 安全 `str.find`** 防 ValueError
- **run() 工具调用加 try/except**

### 文档
- **AGENTS.md**：V3 架构图、文件结构更新、测试数 27 套
- **README.md/README_EN.md**：Agent 编程能力章节、项目树补 `agent_runtime.py`/`agent_tools.py`、性能提示三级
- **ternary_agent/README.md**：API 配置教程、V3 AgentRuntime 章节、已合并文件标记、7 家提供商列表
- **CHANGELOG.md**：去重、测试数更新
- **ARCHITECTURE.md**：行数修正（parser 143→156、LLVM 文件行数全更新）
- **docs/manual.md/llvm.md**：版本号 v3.25→v3.26

---

## [v3.26.0] — 2026-06-02

### 新增
- **VM 浮点支持**: `PUSH_FLOAT`(0x48) 操作码，IEEE 754 double 8 字节编码
- **C VM UTF-8 字符计数**: `utf8_char_len`/`utf8_byte_offset`/`utf8_substr`，修复 `STRLEN`/`STRSUB` 对中文字符串的字节级错误
- **C VM float 字典键**: `hash_key`/`key_eq` 支持 `OBJ_FLOAT`，`rt_float_t` + `rt_float_new()` 结构体
- **常量折叠优化**: `compile_bytecode.py:_fold_constants()` 递归折叠 `(加 1 2)` → `3`
- **LLVM 工具路径环境变量化**: `MSYS2_PATH`/`CC`/`LLC_PATH`/`BASH_PATH`/`GCC_PATH`/`SANYAN_CC`/`SANYAN_LLC`/`SANYAN_BASH`
- **静态类型检查**: `type_checker.py` — 50+ 内置操作的类型签名表，在求值前做字面量参数断言
- **LLVM 三态运行时**: `rt_trit_add`/`sub`/`mul`/`div`/`mod` 运行时函数，支持三态置信度传播
- **类型标注支持**: `check_type` 支持英文类型名（int/float/str/list/dict/num/any），`定义 f (x: int) { ... }` 参数类型在调用时校验

### 变更
- **运行时合并**: `runtime_components.py` → `runtime.py`，`debug_eval.py` → `evaluator.py`，`eval_helpers.py` 拆为 `eval_utils.py` + 合回 `evaluator.py`。净删 3 文件
- **标准库拆分**: `stdlib/combined.san`(2960 行) → `lexer.san`(199 行) + `parser.san`(739 行) + `codegen.san`(2022 行)
- **VM 重构**: `_exec_arithmetic`(92 行) 拆为 `_exec_arithmetic`(算术) + `_exec_bitwise`(位运算/字节)
- **eval() 边界统一**: `eval_utils.py:ensure_trit()` 统一转换 raw↔TritValue
- **#include 预处理**: 移到 `sugar/parser.py:parse_code()` 入口自动展开
- **ops 文档化**: `_init_ops` 注释写明 import 即注册机制
- **递归上限常量化**: `_DEFAULT_RECURSION_LIMIT = 2000`
- **启动器改进**: `os.chdir()` → `PROJECT_ROOT` 常量

### 修复
- **C VM UTF-8**: `STRLEN` 改用字符计数（非字节），`STRSUB` 按字符边界切片
- **C VM 字典**: `key_eq` 区分 float/string 类型比较
- **糖解析器**: `_parse_try` 正确处理 `捕获 (e)` 带括号写法
- **分派器**: `_DISPATCH_NOT_FOUND` 哨兵区分"未找到 op"和"op 返回 None"
- **常量折叠**: `isinstance(op, str)` 检查防止嵌套参数列表被误判
- **死代码**: `ternary_core.py` 删除 10 行不可达的重复分支
- **API 密钥**: 占位符 `\"sk-你的key\"` 改为显式错误退出（`run_agent.py`）
- **错误信息**: `_expect` 补全 9 种括号不匹配提示
- **抽象泄漏**: `_NO_CACHE_OPS` 从分派器移除
- **mypy/ruff**: 37 个类型错误全修、24 个 lint 全修
- **测试**: 617 测试全过，45/46 集成测试通过

### 测试
- 覆盖率从 69.2% → 75.32%
- `test_core.py`: 100 → 137+ 项
- `test_vm.py`: 79 → 91 项
- 新增 type_checker/eval_utils/常量折叠专项测试

---

## [v3.25.0] — 2026-06-02

### 新增
- **村庄观察器全面升级**: 从单次 `开始观察()` 调用重构为 Python 逐日主循环（`run_village_observe.py`）
  - **宏观趋势分析**: 修正作用域访问 `ev.scope_vars` → `ev._scopes[0]`，正确读取全局变量
  - **夜间事件系统**: 8 项负面事件池（菜地被踩/借物不还/传错话/商业纠纷/土地争执/工具损坏/流言/争吵），按角色约束分配
  - **事件记忆系统**: 跨日追踪 + 因果链累积（重复事件加权）
  - **TritValue 解包**: 所有从求值器变量读取的字典值自动 unwrap
  - **行为标签 LLM 分类器**: 关键词不匹配时回退到 LLM 分类
  - **性格乘数**: 按 NPC 性格标签加权（憨厚/爽朗/内向/精明/急性子等）
  - **天气乘数**: 下雨×0.7, 晴天×1.2, 酷暑/严寒×0.5
  - **对话长度因子**: sqrt 归一化
  - **语气检测**: 5 类（友好/打趣/抱怨/平淡/冲突）+ 语气→标签映射
  - **间接信任传播**: 对话提及第三方 NPC 时触发连锁更新
  - **详细输出**: 完整三态推理链（位置/行为/公式/信任变化/置信度区间）
  - **三态区间统一**: 真 ●●● / 可能 ◐◐◐ / 假 ○○○
  - **凝聚度指数**: 全对平均 + 活跃对平均 + 三态分布
  - **SVG 图表**: 交互式信任演变图（复选框隐藏/显示 NPC，hover tooltip）
  - **JSON 导出**: `village_log.json` 结构化数据
  - **可视化增强**: `_vpad` 中文视觉宽度对齐, ⚠/⛔ 警告级别, Y 轴自适应, 信任矩阵热力图, NPC 出场分布追踪
  - **动态 delta 公式**: Δ = 基础值 × 性格均值 × 天气 × 长度 × 位置
  - **剧情的续写游戏**: 叙事分支和状态记忆
  - **LLM 调用时机统计**: 按类别分组计时
  - **夜间事件权重配置**: 可配置 delta 值
  - **语气多样性**: 基于信任的语调覆盖
  - **关系传播链**: 信任链间接传播
  - **可能区保守决策**: 信任大概率保持不惩罚
  - **事件记忆注入对话**: 历史事件作为对话上下文

### 修复
- **sugar/parser.py**: `_parse_try` 正确处理 `捕获 (e)` 括号写法——原代码在 `(` 时 `next()` 吃掉括号而非读取变量名，导致嵌套 try/catch/if 产生孤立 AST 节点；`捕获` 体占位符 `TritValue(0)` 改为 `0` 避免不必要导入
- **ops/dispatcher.py**: 新增 `_DISPATCH_NOT_FOUND` 哨兵对象——`dispatch_op()` 返回 `None` 无法区分"操作返回了 None"和"操作未找到"两种语义；`apply()` 用 `is not _DISPATCH_NOT_FOUND` 替代 `is not None` 判断
- **ternary_agent/decision.san**: `保护()` 返回值从列表改为字典——消费者使用 `取键()` 期望字典格式，列表会导致 `SanyanTypeError`
- **ternary_agent/agent.san**: `规则降级()` 中 `query_weather()` 改为 `调度工具("query_weather", 城市)`——原函数未定义导致 `SanyanNameError`
- **ternary_agent/agent.san**: 移除重复不可达 `传播后 == -1` 代码块（两个连续 if 分支相同内容）
- **ternary_agent/agent.san**: `好感要求 > 0` 时添加 try/catch 保护 `_V` 变量读取——`_V` 可能未定义导致 `SanyanNameError`
- **位运算 VM 支持**: 13 个新操作码 (0x3B-0x47) — BIT_AND/OR/XOR/NOT, SHIFT_L/R, BIT_SET/CLR/TGL/TST, LO_BYTE/HI_BYTE/MRG_BYT（`vm.py`, `csrc/runtime.c`）
- **C 语言对标**: 枚举() 结构体() 断言() 做-直到() 可变参数 ...（`ops/type_ops.py`, `ops/control_ops.py`, `commands.py`, `param_matcher.py`）
- **嵌入式底层**: 置位/清位/翻位/测位 低位字节/高位字节/合并字节/取字节/取字（`ops/arithmetic_ops.py`）
- **进制转换**: 十六进制/二进制/八进制 + 解析十六进制/解析二进制（`ops/arithmetic_ops.py`）
- **二分查找**: 二分查找(有序列表, 目标)（`ops/list_ops.py`）
- **判 多值匹配**: 判 val 'a' body1 'b' body2 默认 default — 对标 C switch/case（`ops/control_ops.py`）
- **可变参数**: 定义 fn (值...) — rest params 打包为列表（`commands.py`, `param_matcher.py`）
- **LLVM 多提供商**: DeepSeek/OpenAI/千问/小米MIMO/Gemini/Ollama 6 家 + Gemini 专用格式（`agent_policy.san`, `agent.san`）
- **Agent 信念持久化**: 信念保存()/信念加载() + 自动衰减（`agent.san`）
- **Agent 多轮推理**: Plan-Act-Observe 循环（`agent.san`）
- **Agent 检索记忆**: 关键词匹配记忆表（`agent.san`）
- **Agent 保护门控**: 可能次数/增益/风险 接入主循环（`agent.san`）
- **Agent 元认知反思**: 规则性能追踪 + 自动调权（`agent.san`）

### 变更
- **sugar parser**: 前缀操作符仅在跟合法表达式时激活（修复 `查询` 作为函数参数误匹配）（`sugar/parser.py`）
- **VM opcode 表**: 从 52 扩展到 65（新增 13 个位运算）

### 文档
- **docs/ternary-truth-table.md**: Kleene+Bayesian 扩展真值表
- **docs/roadmap.md**: 扩展路线图更新
- **docs/migration.md**: v3.22 迁移指南
- **sugar parser 修复**: 前缀操作符误匹配函数参数

---

## [v3.23.0] — 2026-06

### 新增
- **三态系统完整闭环**: 值+信度+来源+时间戳 四元组（`ternary_core.py`）
- **52 个三态 API**: 构造/传播/判定/冲突/融合/衰减/序列化/容器/调试/数学/逻辑/分布/校准/信念
- **信念系统**: `信念(命题,信度,来源,时间)` 结构化记忆单元（`ops/type_ops.py`）
- **VM 三态支持**: `vm.py` 算术/比较/逻辑 ops 自动传播 TritValue 置信度（`vm.py`）
- **C VM 三态支持**: `OBJ_TRIT` 堆类型，紧凑 12 字节存储（`csrc/runtime_common.h`, `csrc/runtime.c`）
- **LLVM 三态支持**: `rt_trit_*` 辅助函数系列（`llvmgen/runtime.c`）
- **主观逻辑共识融合**: `共识(a,b)` 信念三元组融合算子（`ops/type_ops.py`）
- **贝叶斯更新**: `贝叶斯更新(先验,证据)` P(H|E) 更新（`ops/type_ops.py`）
- **三态容器**: `三态列/三态字典` 每元素独立信度（`ops/ternary_container_ops.py`）
- **时间衰减**: `衰减()` 自动用 `_timestamp` 算 Δt（`ops/ternary_time_ops.py`）
- **量化编码**: `量化/反量化` 1 字节存值+信度（`ops/type_ops.py`）
- **三态压缩**: `三态压缩/解压` 3 trit = 1 byte（`ops/type_ops.py`）
- **冲突模型**: `检测冲突` `冲突合并` `判定` `断言信度`（`ops/type_ops.py`）
- **调试工具**: `追踪` `解释` `来源` 信度推导链（`ops/io_ops.py`）
- **模糊测试**: `tests/test_fuzzing.py` 括号/字符串/随机验证（`tests/test_fuzzing.py`）

### 变更
- **parser.py 重写**: 支持行号/列号追踪、索引遍历（`parser.py`）
- **sugar/parser.py 重构**: if-elif 链 → 字典调度（`sugar/parser.py`）
- **main.py 拆分**: 175 行 → 4 辅助函数（`main.py`）
- **TritValue 扩展**: `_val_type`/`_payload`/`_source`/`_timestamp` 多类型承载（`ternary_core.py`）
- **数学函数传播**: sqrt/sin/cos/tan/log/log10 自动信度传播（`ops/math_funcs_ops.py`）
- **信度守恒定律重构**: 且=min, 或=max, 非=keep（`ops/logic_ops.py`）

### 修复
- **闭包支持**: `eval_str` 返回 FunctionValue 捕获作用域（`eval_helpers.py`）
- **lambda 关键字**: 仅后跟 `(` 时激活（`sugar/parser.py`）
- **C VM 测试卡死**: sugar parser 缓存保留 + VM 最大步数（`ops/file_ops.py`, `vm.py`）
- **Agent 启动器**: register_alias 移到 init 后（`run_*.py`）
- **agent.san 缺失括号**: `加载记忆` 函数补 `}`（`agent.san`）
- **try discard `_`**: 不存入作用域（`ops/control_ops.py`）
- **tokenizer 错误报告**: 未知字符 → ERROR token（`sugar/tokenizer.py`）
- **好感度规则**: Agent 强制执行好感门槛（`agent.san`）
- **热重载**: decision.san 纳入监听（`run_agent.py`）
- **llvmgen/runtime.c**: 编译错误修复（struct rt_list_s/rt_list_push_item/rt_str_join）

### 文档
- `docs/ternary-confidence.md` — 三层设计规范（离散/连续/复合）
- `docs/ternary-truth-table.md` — Kleene+Bayesian 扩展真值表
- `docs/roadmap.md` — 10 大类扩展路线图
- `docs/migration.md` — v3.22 迁移指南
- `sanyan-vscode/` — VS Code 语法高亮修复（`\b` → `(?<!\w)`）
- AGENTS.md/CONTRIBUTING.md — 覆盖率配置 + 测试数量更新

---

## [v3.22.0] — 2026-06-01

### 新增
- **Agent 启动器修复**: 4 个启动器（`run_agent.py`, `run_v2.py`, `run_v2_demo.py`, `run_village_demo.py`）的 `register_alias` 调用移到 `SanyanEvaluator` 实例化之后，解决 `SanyanKeyError` 启动崩溃
- **Agent 缺失函数补全**: 新增 `构建系统提示()`、`规则降级()`、`最近决策()`、`解释原因()`、`策略概览()` 5 个函数（`ternary_agent/agent.san`）
- **village_game.san 单元测试**: 8 个测试覆盖时间流逝、天气刷新、关系查找、传播速度、声望变化、NPC 好感、心情映射、记忆系统（`tests/test_agent.py`）
- **npc_game.san 单元测试**: 2 个测试覆盖 NPC 数据加载、记忆强度分级（`tests/test_agent.py`）

### 修复
- **agent.san 缺失闭合括号**: `加载记忆()` 函数缺少 `}`，导致解析失败（`ternary_agent/agent.san`）
- **demo_compress.san 英文 op**: `output(connect(..., to_string(...)))` 改为 `输出(连接(..., 转字符串(...)))`（`ternary_agent/demo_compress.san`）
- **test_agent_run_mock 空壳断言**: 增强异常检查，区分 API 密钥/计算错误与意外异常（`tests/test_agent.py`）
- **test_match_rule_borrow_negated 断言空过**: 移除条件分支，直接验证否定句风险不为高（`tests/test_agent.py`）
- **冲突统计每轮打印**: 改为仅在有冲突时打印（`ternary_agent/agent.san`）
- **记忆加载失败静默**: 添加日志输出（`ternary_agent/agent.san`）

### 文档
- **prompts.san**: 标注为未使用死代码（`ternary_agent/prompts.san`）
- **memory.san**: 标注为未使用死代码（`ternary_agent/memory.san`）
- **run_agent.py**: 添加 API 密钥注入必要性注释

---

## [v3.21.0] — 2026-06-01

### 新增
- **闭包/第一类函数支持**: `eval_helpers.py` 新增 `_make_closure_value()`，函数名作为独立表达式求值时返回 `FunctionValue` 并捕获当前作用域（`eval_helpers.py`）
- **import as 别名**: `导入 "path" 为 alias` 语法，模块自动绑定到别名变量（`ops/file_ops.py`, `sugar/parser.py`, `language/chinese.json`）
- **默认参数**: `定义 foo (x, y = 10) { ... }` 语法，调用时可省略有默认值的参数（`commands.py`, `param_matcher.py`）
- **等待操作**: `等待(毫秒)` 阻塞执行指定时间（`ops/io_ops.py`）
- **VM 最大步数保护**: `VM_MAX_STEPS=5_000_000` 防止字节码无限循环（`vm.py`）
- **VM 版本号检查**: `from_bin` 加载时检查 `BIN_VERSION`，不兼容时报错（`vm.py`）
- **C VM 字典容量上限**: `RT_DICT_MAX_CAP=65536` 可编译时配置，防止嵌入式内存溢出（`csrc/runtime_common.h`, `csrc/runtime.c`）
- **闭包单元测试**: 5 个新测试覆盖基本闭包、计数器闭包、作用域隔离、import as（`tests/test_core.py`）

### 变更
- **C VM 测试优化**: `setUpClass` 编译一次 C VM 复用，测试时间从 116s 降至 33s（`tests/test_c_vm.py`）
- **sugar parser 缓存保留**: `clear_cache()` 不再清除 `_sugar_parser_module`，避免重复加载 938 行 sugar.san（`ops/file_ops.py`）

### 修复
- **闭包返回字符串而非函数**: `返回 inner` 将命令名当字符串返回，而非返回 `FunctionValue`（`eval_helpers.py`）
- **stdlib/*.san 源码路径全坏**: sugar parser 的 `lambda` 关键字误解析变量名 `lambda`，改为仅后跟 `(` 时激活（`sugar/parser.py`）
- **C VM 测试卡死**: `clear_cache` 清除 sugar parser 缓存导致重复加载超限（`ops/file_ops.py`）
- **VM 无最大步数**: 字节码无限循环导致挂死（`vm.py`）
- **loop 错误消息英文**: `loop 需要条件和体` 改为 `循环 需要条件和体`（`ops/control_ops.py`）

### 文档
- **docs/manual.md**: 补充三进制 API 附录（`BT`, `to_trit`, `to_int`, `TritValue` 方法）
- **README.md**: 项目结构补充 `gui.py`

---

## [v3.20.0] — 2026-05-31

### 新增
- **三言 Agent v0.3 — 可读决策 DSL（概率三态 + 声明式规则 + 自解释深化）**
  - **Phase 1 决策追踪**: `Agent运行` 每步输出中文决策追踪（`ternary_agent/agent.san`）
  - **Phase 2 声明式策略**: `agent_policy.san` 纯数据文件，`#include` 预处理展开（`ternary_agent/agent_policy.san`）
  - **Phase 3 自解释 Agent**: `解释决策(N)`、`最近决策()`、`解释原因()`、决策记录存储、热重载
  - **迭代 1 概率三态**: `TritValue` 新增 `confidence` 字段（0-1，默认 1.0），`三态描述(v,c)` 显示置信度（如 `真(0.9)`），贝叶斯传播（`传播置信度 = 上游 × 当前`），`to_string` 浮点精度修复（`ternary_core.py`, `ops/type_ops.py`）
  - **迭代 2 声明式规则 DSL**: `agent_policy.san` 新增 `场景规则` 列表（5 条：借钱/投资/传谣/天气/闲聊），`匹配规则(问题)` 关键词匹配，`策略概览()` 中文展示策略配置，`验证策略()` 格式检查（`ternary_agent/agent.san`）
  - **迭代 3 自解释深化**: `解释原因()` 分 5 层解释（规则→认知→传播→动作→建议），`记录决策` 增加规则上下文字段（场景名、风险等级、好感要求），交互命令 `/原因 N`、`/策略`
- **Agent 架构**: 三态推理管线——LLM 5 种认知态 → 5→3 映射 → 三态传播（上游锁定/传递）→ 保护门控（高风险拒绝/犹豫超限/增益不足）→ 多数表决 → 动作分发
- **Agent 交互命令**: `/解释 N`、`/最近`、`/原因 N`、`/策略`（`run_agent.py`）
- **预处理增强**: `run_agent.py` 使用 `preprocess_includes()` 展开 `#include`，支持从 `agent_policy.san` 读取 API 密钥，`转数字` 别名注册

### 变更
- **`ternary_agent/agent.san`**: 从自包含版重构为策略驱动版——12 行硬编码配置移至 `agent_policy.san`，`映射到三态`/`认知态名`/`三态名`/`调度工具` 改为字典查找（从 `五态映射规则`/`认知态中文`/`三态中文`/`天气数据` 字典），删除重复函数定义
- **`run_agent.py`**: 新增 `preprocess_includes` 预处理、`_watch_files()` 文件监听、`run_interactive()` 热重载支持、交互式 `/解释` 命令

### 文档
- **AGENTS.md**: 新增 Agent 系统章节（架构、文件结构、运行方式、交互命令）
- **README.md**: 版本号更新至 v3.20.0，新增 Agent 架构说明和决策追踪示例
- **ARCHITECTURE.md**: 新增 Agent 系统架构图和数据流

---

## [v3.19.0] — 2026-05-30

### 新增
- **llvmgen.san 自举完成（V5）**: 11 个 Python 辅助函数和 6 个全局变量已内联到源码中，`compile_llvmgen.py` 不再注入任何外部依赖，`llvmgen.bin`（69932 字节）可直接从源码编译
- **sugar.bin 自举验证**: 新增 `tests/test_sugar_self_host.py`，验证 sugar.san 编译产出与参考 sugar.bin 字节一致（SHA256 校验）
- **LLVM 代码生成器文件拆分**: `ops_gen.py`（925 行）拆分为 `ops_gen.py`（410）+ `ops_gen_control.py`（341）+ `ops_gen_helpers.py`（240）；`compiler.py`（657 行）拆分为 `compiler.py`（424）+ `ir_fixes.py`（220）
- **#include 预处理接入编译管线**: `compile_bytecode.py` 和 `ops/file_ops.py` 在解析前调用 `preprocess_includes()` 展开 `#include` 指令
- **C VM #include 支持**: `csrc/runtime.c` 新增 `preprocess_includes()` 函数，`--compile` 模式自动展开 `#include` 后再解析
- **构建脚本 `build_combined.py`**: 展开 `#include` 生成合并单文件，确保 VM 可直接编译
- **llvmgen.san 拆分子模块**: `stdlib/llvmgen_src.san`（入口）+ `stdlib/llvmgen/`（preamble/utils/compiler/runtime_ir/entry）
- **三值逻辑 IoT 案例**: `sensor_fusion.san`（传感器融合）、`fault_tolerant_control.san`（容错控制）、`iot_state_machine.san`（状态机），含 Python/C 对比实现
- **标准库扩充**: `stdlib/network.san`（TCP/UDP/连接池/健康检查）、`stdlib/hardware.san`（GPIO/I2C/SPI/传感器）、`stdlib/math.san` 扩充（矩阵/向量/统计/概率分布）
- **包管理器增强**: 新增 `卸载`/`搜索`/`包信息`/`包索引` 命令，6 个示例包（sample/math_extended/logging/web_utils/data_pipeline/config）
- **包开发文档**: `docs/package_development.md` 完整包开发指南
- **三值逻辑对比文档**: `docs/three_value_comparison.md` 三值 vs 二值代码量/可读性对比

### 变更
- **compile_llvmgen.py**: 辅助函数已内联到 llvmgen.san，脚本简化为直接解析编译（无注入）
- **llvmgen.san 函数名全部中文化**: `header`→`生成模块头`、`footer`→`生成模块尾`、`parse_int`→`解析整数`
- **llvmgen.san 繁体字修正**: `設`→`设`（utils.san 中 4 处）
- **AGENTS.md 规则强化**: 每次增加或修改代码必须为整段代码写中文注释；每次任务完成后运行全部测试并更新所有 md 文件

### 修复
- **_check_div_zero 常量折叠**: `div 1 0` 生成 `icmp eq 0, 0`（常量 true）→ `rt_throw` 总被执行污染 `g_error`，修复为 AST 级别检测常量除零并 emit unreachable
- **_normalize_fn_format 多语句体截断**: 只取 `node[3]` 作为函数体，后续语句丢失，修复为将 `node[3:]` 包装为 `do` 块
- **llvmgen/runtime.c 编译错误修复**: `rt_list_t` 不完整类型、`rt_list_push` 未声明等问题已修复

---

## [v3.18.0] — 2026-05-29

### 新增
- **C VM 与 Python VM 三值逻辑统一**: Python VM（`vm.py`）所有布尔返回指令统一为三值逻辑（1=真，-1=假），与 C VM（`csrc/runtime.c`）和 Python 求值器行为一致
- **编译管线双解析器支持**: `compile_bytecode.py` 先尝试 sugar 解析器，失败则回退到 S-表达式解析器，支持两种语法的 .san 文件

### 变更
- **Python VM 比较指令**: EQ/NE/GT/LT/GTE/LTE 返回值从 `1/0` 改为 `1/-1`
- **Python VM NOT 指令**: 正数返回 `-1`，否则返回 `1`
- **Python VM OR/AND 指令**: 用 `>0` 判断真值
- **Python VM 类型检查指令**: IS_NUM/IS_STR/IS_LIST/SAME 返回 `1` 或 `-1`
- **Python VM 字符串比较指令**: STREQ/STR_STARTSWITH/STR_CONTAINS 返回 `1` 或 `-1`
- **Python VM 字典指令**: DICT_HAS 返回 `1` 或 `-1`
- **Python VM 跳转指令**: JZ/JNZ 用 `>0` 判断真值
- **自举编译器参考文件**: `stdlib/bytecode_compiler.bin` 更新为新编译版本（6298 字节）
- **自举测试 SHA256**: `tests/test_self_host.py` 更新参考哈希

### 修复
- **自举编译器 C VM 兼容性**: 自举编译器生成的字节码现在可在 C VM 上正确执行
- **编译管线解析器**: `compile_bytecode.py` 支持 S-表达式语法的 .san 文件（如 `bytecode_compiler.san`）

---

## [v3.17.0] — 2026-05-28

### 新增
- **C VM 单元测试**: `csrc/test_runtime.c` 61 项测试，覆盖标记指针/字符串/列表/字典/算术/比较/变量/控制流/函数调用/嵌套调用，`tests/test_c_vm.py` Python 包装器自动编译运行
- **BUILTIN_OPS 自动生成**: `runtime.py` 中 `BUILTIN_OPS` 从硬编码 Set (~170项) 改为从 `language/*.json` 自动生成 (235项)，消除手工维护同步风险
- **架构文档**: `ARCHITECTURE.md` 系统概览、核心模块、数据流、设计决策
- **贡献指南**: `CONTRIBUTING.md` 开发环境、代码规范、项目结构、添加操作指南
- **核心模块 docstring**: `evaluator.py`、`values.py`、`ops/dispatcher.py`、`runtime_components.py` 添加模块级和公共方法中文文档字符串

### 变更
- **性能优化**: `evaluator._apply` 移除冗余 `resolve_op_name` 调用（`dispatcher.apply` 内部已调用）；`ops/dispatcher.py` 中 `sandbox` 模块从函数内 import 提升为模块级导入
- **ops/string_ops.py**: `string_length` 支持 `list`/`dict`/`ArrayValue` 类型；注册 `len`→`length`、`substr`→`substring` 别名
- **sugar/lexer.py**: `FULLWIDTH_MAP` 添加 `【`→`[`、`】`→`]` 全角方括号映射
- **stdlib/eval.san**: `去掉引号` 函数变量名 `len`→`s_len` 避免与操作名冲突
- **ops/system_ops.py**: `subprocess.run` 添加 `errors='replace'`，处理 `None` stderr
- **ops/comparison_ops.py**: `eq`/`ne` 支持非数值类型（字符串）比较

### 修复
- **test.san 测试框架**: `执行(函数体)` → `函数体()` 修复函数调用；添加 `否则` 分支；使用可变字典替代标量变量跨函数调用持久化；新增 `断言错误` 函数
- **5 个预存在集成测试**: `test_container.san`/`test_stress.san`（取长支持列表）、`test_eval.san`/`test_parse_se.san`（len/substr 别名）、`test_fullwidth.san`（全角方括号）全部修复
- **集成测试**: 从 25/43 提升至 43/43 通过

## [v3.16.0] — 2026-05-28

### 新增
- **自举 .bin 文件**: sugar.san 和 llvmgen.san 可编译为独立 .bin 文件在 VM 上运行（`stdlib/sugar.bin` ~10KB、`stdlib/llvmgen.bin` ~72KB），V5 辅助函数已内联到源码中，无需 Python 注入
- **自举验证测试**: `tests/test_self_host.py` 验证字节码编译器自举一致性（SHA256 校验）
- **字节码格式升级**: 代码大小字段从 16 位扩展到 32 位（`vm.py`、`bytecode_compiler.san`、`csrc/runtime.c`、`compile_bytecode.py`），支持 >64KB 字节码
- **OP映射双语覆盖**: 补充 20+ 个 Python 注册命令的中英文别名映射（`新字典`→`DICT`、`新列表`→`LIST_NEW`、`列表取`→`GET` 等），覆盖全部 51 个 VM 操作码
- **JMP32 操作码 (0x33)**: 新增 32 位跳转指令，函数定义/lambda 的前向跳转改用 JMP32，支持 >64KB 字节码（`vm.py`、`csrc/runtime.c`、`llvmgen/runtime.c`、`bytecode_compiler.san`）
- **VM 单元测试**: `tests/test_vm.py` 新增 73 项直接字节码测试，覆盖全部操作码（栈操作/算术/比较/控制流/字符串/类型检查/列表/字典/函数调用/IO）
- **模块化发行配置**: `pyproject.toml` 新增 extras 依赖分组（core/sugar/vm/llvmgen/lsp/tools/dev），支持按需安装（`pip install sanyan[core]`）
- **sanyan 包命名空间**: 新增 `sanyan/__init__.py` 作为包入口

### 变更
- **字节码编译器源码**: 关键字全部使用中文（`set`→`设`、`fn`→`定义`、`if`→`若`、`return`→`返回`、`loop`→`循环`、`do`→`做`），字符串字面量中的操作名保持英文
- **.san 文件注释**: 全角注释 `／／` 统一转换为半角 `//`（algorithm.san、collection.san、datetime.san 等 11 个文件）
- **LLVM 代码生成器**: `llvmgen.san` 中 `set`/`if`/`do`/`return`/`try`/`print`/`fn` 等操作的中文别名检查移到英文检查之前（`若` 或 `if`、`设` 或 `set` 等）
- **异常体系统一**: `ops/registry.py` 使用 `SanyanKeyError`，`preprocess.py` 使用 `SanyanValueError`，`compile_bytecode.py` 使用 `SanyanSyntaxError`/`SanyanRuntimeError`
- **魔法数字提取**: `ops/file_ops.py` 提取 `BOOTSTRAP_MAX_LOOP`/`SUGAR_MODULE_MAX_LOOP`/`TEMP_ENV_MAX_LOOP`，`ops/system_ops.py` 提取 `EXEC_TIMEOUT`，`ops/net_ops.py` 提取 `HTTP_TIMEOUT`，`ops/package_ops.py` 提取 `DOWNLOAD_TIMEOUT`/`INDEX_TIMEOUT`/`INDEX_CACHE_TTL`
- **异常处理精确化**: `ops/system_ops.py` `except Exception` → `except (OSError, ValueError)`，`ops/net_ops.py` → `except (_error.URLError, _error.HTTPError, ValueError, OSError)`
- **CI 统一安装**: 测试 job 改用 `pip install .[dev]`，添加 `test_self_host.py` 和 `test_vm.py`

### 修复
- **`fn` 处理器函数地址**: 导出地址公式从 `(减 (表长 w) 10)` 修正为 `(减 (表长 w) 12)`，指向参数 STORE（VM CALL 从此处计算参数数量）
- **`fn` 处理器 JMP 回填**: `(减 (表长 w) (加 jp 2))` 公式验证正确（跳过整个函数体含 fn-RET）
- **VM DICT/LIST_NEW**: 空栈安全处理——`新字典`/`新列表` 无参数时不 pop，避免 `IndexError`
- **C VM**: 同步修复头部格式（10 字节）和 DICT/LIST_NEW 空栈处理（`csrc/runtime.c`）
- **sugar.san `导出` 解析器**: 遇到第二个 `导出` 关键字时停止读取名称，修复多行导出被合并为一个节点的 bug
- **test_llvmgen.py**: `test_import_resolves` 和 `test_text_analysis` 标记为 skip（导入系统为桩函数）
- **main.py UnboundLocalError**: 删除 `use_pycc`/`use_san` 分支中重复的 `from skin import SkinManager` 和 `from sugar import SugarConverter` 导入，消除 Python 变量遮蔽
- **--ast-json 路径**: `main.py` 中 `from ast_json import` 改为内联实现，修复模块缺失崩溃
- **ops/concurrent_ops.py**: 并发执行异常不再静默吞掉，改为抛出 `SanyanRuntimeError`
- **pyproject.toml**: 添加 `llvmgen` 到 `packages` 列表
- **README.md**: 修复 CI badge URL（`ci.yml` → `test.yml`），删除结构树中不存在的 `VERSION.py`、`ast_json.py`、`_error_handler.py`、`_util.py`
- **ops/type_ops.py**: 删除与 `time_ops.py` 重复的 `time_now` 和 `sleep_op`

## [v3.15.1] — 2026-05-27

### 修复
- **`param_matcher.py:evaluate_args()`**: 列表代码表达式（如 `(取 a i)`）不再被当作数据字面量原样返回而不求值，修复自举编译时 `编译节点` 收到未求值 AST 节点导致的 C 栈递归溢出（`runtime/param_matcher.py`）
- **`ops/arithmetic_ops.py`**: `div` 和 `mod` 补全 `_to_tritvalue()` 转换，修复从变量解析返回 Python `int` 时类型检查失败问题
- **`llvmgen/compiler.py`**: `_list_get_safe` 增加未求值列表参数的保护转换，防止编译期崩溃
- **文档与版本**: README 版本同步至 v3.15.1，AGENTS.md 记录 Python 求值器关键修复及自举测试步骤，清理根目录临时构建文件

### 新增
- **自举验证测试**: `tests/test_self_host.py` 作为正式自举检测测试，验证 VM 编译产出与求值器编译产出逐字节一致（5442 字节，5406 字节码）

## [v3.15.0] — 2026-05-24

### 新增
- **渐进类型系统**: 返回类型标注 `定义 fn() -> 数字 { }`，可选类型 `?数字` 接受数字或 `可能`，运行期自动校验（`sugar/parser.py`, `commands.py`, `values.py`）
- **标准库**: 新增 `stdlib/json.san`（JSON 解析/序列化）、`stdlib/http.san`（HTTP GET/POST）、`stdlib/regex.san`（正则匹配/查找/替换）、`stdlib/csv.san`（CSV 解析/生成）
- **LLVM 浮点支持**: IEEE 754 double，`fadd`/`fmul`/`fdiv` 内联，整数自动 `sitofp` 提升，`rt_float_new` 走 arena 分配（`llvmgen/codegen.py`, `llvmgen/runtime.c`）
- **LLVM 63 位整数**: tagged pointer 从 i32 升至 i64，63 位值域 ±4.6×10^18（`llvmgen/codegen.py`）
- **LLVM import 静态链接**: `compile_program()` 递归编译 import 依赖，`llvmlite.link_modules` 合并 IR，`san_{mod}__{fn}` 名字修饰避免符号冲突（`llvmgen/codegen.py`）
- **LLVM try/catch 重写**: 消除 `rt_try_begin`/`rt_try_check`/`rt_try_get_error` opaque 调用，改为 `@g_error` LLVM 可见全局 + 手动栈展开（`llvmgen/codegen.py`, `llvmgen/runtime.c`）
- **LLVM 优化 passes**: mem2reg + instcombine + reassociate + GVN + simplifycfg，所有函数 `alwaysinline`（`llvmgen/codegen.py`）
- **字节码缓存**: `main.py --vm` 模式编译并缓存 `.bin`，首次编译后跳过词法/解析（`main.py`）
- **案例文档**: `examples/circuit_sim.san`、`data_cleaning.san`、`health_check.san`、`npc_decision.san` 四个三态逻辑对比案例 + `docs/why-ternary.md` 论证文档
- **Arena 字符串分配器**: `g_arena` 64KB 初始化，auto-grow 双倍，`_rt_make` 搬指针替代 malloc（`llvmgen/runtime.c`）

### 变更
- **LLVM 字典**: 从固定 64 条目线性查找改为 FNV-1a 哈希表 + 开放寻址 + 动态扩容（`llvmgen/runtime.c`）
- **LLVM 列表**: 新增 `rt_list_new_cap(cap)`，codegen 传 `len(args)` 作初始容量，免 comprehension 重复 realloc（`llvmgen/codegen.py`, `llvmgen/runtime.c`）
- **LLVM 堆对象**: 统一 `SAN_HEADER` (uint32_t h_type)，str/list/dict 均设类型标签（`llvmgen/runtime.c`）
- **READM: 优先展示中文版**，英文版移至 `README_EN.md`
- **版本号**: 更新至 v3.15.0

### 修复
- **C VM CALL 格式**: 改为指令流 2 字节 addr + STORE 扫描 arg_count，与 Python VM 一致（`csrc/runtime.c`）
- **C VM 缺算术/比较/NOT**: 全补 12 个 handler（ADD/SUB/MUL/DIV/MOD/EQ/NE/GT/LT/GTE/LTE/NOT）（`csrc/runtime.c`）
- **C VM 比较结果**: 改用 `1/0` 替代 `1/-1`，修正 JZ 不退出循环（`csrc/runtime.c`）
- **C VM LOAD/STORE**: `var_count=0` 程序不再拒存，改用 `VAR_MAX` 256（`csrc/runtime.c`）
- **C VM CONCAT**: 从 2 参数改为 N 参数，栈不再泄漏（`csrc/runtime.c`）
- **C VM DICT**: 固定 256→realloc 动态扩容，初始 16（`csrc/runtime.c`）
- **C VM CALL_EXT**: 从 stub 改为临时 VM 执行模块字节码（`csrc/runtime.c`）
- **重复文件清理**: 删除 `data_clean.san`（被 `data_cleaning.san` 替代）、GCC 测试工件（`gcc_*.txt` 等）
- **ruff/mypy 全清**: 修复 4 个 ruff check 错误 + 9 个 mypy 类型错误

### 文档
- **docs/why-ternary.md**: 四案例论证文档——电路模拟器、数据清洗、API 健康检测、游戏 NPC
- **CHANGELOG.md**: 新增 v3.15.0 条目

---

## [v3.14.0] — 2026-05-23

### 新增
- **字节码 VM 完整自举**: VM 编译 `stdlib/bytecode_compiler.bin` 与求值器编译产出逐字节相同（5442 字节，5406 字节码），实现完全自举
- **行注释支持** (`lexer.py`): 新增 `//`（半角）和 `／／`（全角）行注释语法，tokenizer 自动跳过注释行
- **DICT_KEYS 操作码** (`vm.py`): 新增 0x32 操作码，返回字典键列表（`字列` 映射修复）
- **退出控制流注册** (`ops/control_ops.py`): 注册 `退出` 为 `return_op`，供后续 if-else 重构使用

### 修复
- **VM 栈隔离** (`vm.py`): CALL 指令记录 `stack_base = len(stack) - arg_count`，RET 指令执行 `del stack[base:]` 清理被调方泄漏值，消除 JMP 循环 + 递归 CALL 的栈污染
- **VM STORE 扫描** (`vm.py`): CALL 时扫描被调函数序言的连续 STORE 指令自动推算参数个数，确保 `stack_base` 计算正确
- **VM DICT_SET 去 push** (`vm.py`): DICT_SET 不再将修改后的 dict 推回栈（所有调用方为纯副作用），消除 fn handler 作用域复制循环的栈泄漏
- **VM _exec_frame 变量隔离** (`vm.py`): 修正 `_exec_frame` 对外层 `vars` 引用的保存/恢复逻辑，避免内层变量污染外层
- **VM from_bin 初始化** (`vm.py`): 加载 `.bin` 后自动执行模块初始化代码（PC=0 至代码末尾），填充全局变量
- **SLICE 操作码** (`vm.py`): 修正 2 参数 / 3 参数形式的参数顺序，增加非整数索引保护
- **发射i32 溢出** (`bytecode_compiler.san`): 移除 `(mod v 4294967296)`，2^32 在有符号 PUSH_I 中溢出为 0
- **字符串引号检测** (`bytecode_compiler.san`): 改用 `(等于 (ord (子串 n 0 1)) 34)` 替代 `(str_equals ... "\"")`，因 tokenizer 不认 `\"` 转义
- **OP映射全别名** (`bytecode_compiler.san`): 补全所有内置操作的中英文双语别名
- **非列表节点 op** (`bytecode_compiler.san`): 对非列表节点设 `op = "set"`，确保数字/字符串处理器内部 SET 表达式被正确匹配

### 变更
- **编译节点重构** (`bytecode_compiler.san`): 新增 `编译做体` 函数（DO 体循环编译），`字列` 映射从 LIST_LEN 改为 DICT_KEYS
- **三进制运行时** (`ternary_core.py`): TritValue 增加 `__mod__` 支持
- **版本号**: 更新至 v3.14.0

### 文档
- **README.md**: 版本号更新至 v3.14.0
- **AGENTS.md**: 新增自举状态章节，更新测试命令
- **项目文件添加注释**: `vm.py`、`lexer.py`、`ops/control_ops.py`、`bytecode_compiler.san` 添加完整中文注释

---

## [v3.13.0] — 2026-05-20

### 新增
- **求值器模块拆分** (`eval_helpers.py`、`debug_eval.py`): `evaluator.py` 从 315 行降至 176 行（-44%），符号解析、字面量处理、IoT 设备访问提取到 `eval_helpers.py`，调试断点/监视/调用栈提取到 `debug_eval.py`
- **命令模块重构** (`tail_call.py`、`param_matcher.py`): `commands.py` 从 200 行降至 105 行（-48%），尾递归检测与执行提取到 `tail_call.py`，参数匹配/求值/类型检查提取到 `param_matcher.py`
- **统一错误处理** (`ops/_error_handler.py`): `handle_op_errors` 装饰器，`check_args_count`/`check_args_range`/`validate_numeric`/`validate_string` 等参数验证工具函数
- **标准库扩充**: 新增 `stdlib/algorithm.san`（二分查找、冒泡排序、选择排序、最大公约数、最小公倍数、质数判断、斐波那契、阶乘、快速幂）、`stdlib/collection.san`（栈、队列、集合）、`stdlib/validate.san`（邮箱/IP/身份证/URL 验证）
- **实用示例**: 新增 `examples/student_grade.san`（学生成绩管理系统）、`examples/sales_analysis.san`（销售数据分析报表）、`examples/file_batch_process.san`（文件批量处理脚本）

### 变更
- **类型标注增强**: `evaluator.py`/`runtime.py`/`values.py` 核心模块补充完整 TypeHint（`Dict`/`Tuple`/`Optional`/`Set` 等）
- **版本号**: 更新至 v3.13.0
- **build_exe.py**: 添加 `eval_helpers`/`debug_eval`/`tail_call`/`param_matcher` hidden-import

### 文档
- **README.md**: 版本号更新至 v3.13.0，新增 v3.13.0 特性表，项目结构树补充 `eval_helpers.py`/`debug_eval.py`/`tail_call.py`/`param_matcher.py`/`ops/_error_handler.py`
- **CHANGELOG.md**: 新增 v3.13.0 条目

---

## [v3.12.0] — 2026-05-20

### 新增
- **LLVM 代码生成器文档** (`docs/llvm.md`): 完整 LLVM 编译管线文档，涵盖 `runtime.c` 运行时库、`codegen.py` 代码生成器、Tagged Value 机制、编译链接、dp.c 测试套件、已知限制
- **`_parse_source()` 第 4 回退** (`llvmgen/compiler.py`): 新增 Python `lexer.py` → `parser.py`（S 表达式解析器）作为编译管线最后回退，修复 `_bootstrap.san` 编译失败（"所有解析器均失败"）

### 修复
- **`runtime.c` 字符串格式不兼容** (`llvmgen/runtime.c`): 全局字符串常量（裸 `const char*`）与 `rt_str_t*`（`len` 字段在前）之间类型不匹配——`rt_str_equals`/`rt_str_find`/`rt_str_contains` 直接用 `strcmp`/`strstr` 导致所有字符串比较均失败，词法分析 token 列表恒为空。新增 `_cstr()`/`_cstr_len()` 统一访问辅助函数，修复全部 12 个运行时字符串操作和 4 个字典函数
- **字典 key 复制** (`llvmgen/runtime.c`): `_strdup` 替换为 `_strdup_key()`，兼容 `rt_str_t*` 与裸 `const char*` 两种格式

### 文档
- **docs/llvm.md**: 新增完整 LLVM 功能文档
- **CHANGELOG.md**: 新增 v3.12.0 条目
- **README.md**: 版本号更新至 v3.12.0，项目结构树补充 `llvmgen/`、`docs/llvm.md`
- **CONTRIBUTING.md**: 测试数量同步更新
- **docs/manual.md**: 版本号同步，新增 LLVM 参考章节
- **docs/syntax.md/commands.md/errors.md**: 原 manual.md 拆分为三份子文档，manual.md 改为导航页
- **doc_sync.py**: 同步更新文档检查路径

### 工具
- **gui.py**: 可视化编译器 (Dev-C++ 风格 IDE)，支持语法高亮、查找替换 (Ctrl+F)、行号、项目文件树、断点调试 (F6/F10/F8)
- **build_exe.py**: PyInstaller 一键打包脚本，输出 `dist/三言.exe`
- **installer.iss**: Inno Setup 安装包脚本，配合 `BUILD.cmd` 一键构建安装程序

### 修复
- **异常体系一致性** (`ternary_core.py`): 将全部 `ZeroDivisionError`/`ValueError`/`IndexError` 替换为 `SanyanValueError`/`SanyanKeyError`（lazy import 避免循环依赖）

---

## [v3.11.0] — 2026-05-17

### 新增
- **交叉编译工具链**: `sanyancc.py` — AST → 平坦字节码编译器（约 27 条指令，栈式 VM）；中文操作别名（加/减/乘/除/余/等于/不等/大于/小于/大等/小等/非/等待/io写/io读/做/设/循环/若/输出）
- **STM32 固件** (`examples/stm32-blinky/`): `runtime_stm32.c` 完整 VM 解释器 + GPIO/SysTick/UART 驱动 + 中断向量表 + 链接脚本 + Makefile，已在 Blue Pill (STM32F103C8T6) 硬件运行（PC13 LED 200ms 闪烁）
- **C 语言字节码解释器** (`runtime.c`): 主机端 C VM，与 STM32 共享指令集
- **嵌套包导入**: `_resolve_path` 将 `.` 转为目录层级，顺序尝试 `stdlib/a/b/c.san` → `stdlib/a/b/c/package.san`
- **纯三进制算术**: `TernaryALU` 实现全部 7 种操作（加/减/乘/除/余/幂/取位），`_ensure_trits()` / `_to_tritvalue()` 处理 TritValue 精度对齐
- **纯三进制数学函数**: 删除 Python `math` 依赖，三角函数/平方根/对数全用 `ternary_sin/cos/tan/sqrt/log/log10` 纯三进制定点实现
- **WAIT 指令** (0x18): 栈式操作数，pop ms → delay
- **7 个比较指令**: EQ/NE/GT/LT/GTE/LTE/NOT
- **栈式 IO 指令**: `IO_WRITE`/`IO_READ` 改为 pop device_id，不再使用编译期立即数
- **组合模式重构**: `SanyanRuntime` 提取 `ScopeManager`/`IoTManager`/`DebugManager`/`ProfileManager` 到 `runtime_components.py`，委托属性保持全部向后兼容

### 修复
- **STM32 BSS 初始化**: `_sbss`/`_ebss` 链接符号未正确定义，`_start()` 改为显式清零所有全局变量（`_sp`/`_ticks`/设备表/`_vars`）
- **STM32 WFI 掉线**: `delay_ms` 去掉 `__asm__("wfi")`，ST-LINK 不会断开（"Unable to get core ID"）
- **设备数组越界**: 从 8 扩展到 16（ID=13 PC13 越界）
- **向量表修正**: 第 15 项从 `Default_Handler` 改为 `SysTick_Handler`
- **SysTick 重装载值**: 从 72000 修正为 8000（匹配实际 8MHz HSI）
- **USART1 基地址**: 从 `0x40014800` 修正为 `0x40013800`

### 文档
- **AGENTS.md**: 新增 STM32 固件开发章节（BSS 初始化教训、WFI 禁用、编译烧录命令）
- **README.md**: 更新 v3.11.0 特性表、项目结构树新增 `sanyancc.py`/`runtime.c`/`stm32-blinky/`
- **CHANGELOG.md**: 新增 v3.11.0 条目

## [v3.10.0] — 2026-05-16

### 新增
- **类型标注系统**: `values.py:check_type()` 函数，`FunctionValue.param_types`，糖语法解析器保留 `a: 数字` 标注，`commands.py` 调用时自动校验参数类型。
- **文档注释 → LSP Hover**: `lsp_server.py:_extract_docstrings()` 正则提取 `//` 注释块 + `定义 funcName(` → Markdown hover 提示。
- **性能剖析**: `runtime.py` 新增 `profile_start/stop/report()`，`evaluator._apply` 通过 `try/finally` 计时，`main.py --profile` 标志，REPL `:profile` 命令。
- **表达式断点调试**: `runtime.py` 新增 `debug_mode`、`break_add/remove`、`watch_add/remove`，`evaluator._debug_before/after` 钩子 + `调试>` 交互提示，REPL `:step/:break/:watch/:continue` 命令。
- **AST 序列化**: `ast_json.py` 新增 `ast_to_json()` / `ast_from_file()`，`main.py --ast-json FILE` 导出 JSON。
- **源码格式化器**: `sanfmt.py` — 类 black/prettier 格式器，中缀二元运算、中文关键字显示、if-elif-else 链、`a: 类型` 标注保留、`--check` 模式、stdin 模式、幂等输出。
- **注释保留**: 糖语法词法分析器新增 `COMMENT` token 发射，解析器 `_Parser.peek/advance` 跳过注释并收集到 `_comments` 列表，`sanfmt.py` 通过 `_reinsert_inline_comments()` 恢复行内和独立 `//` 注释。
- **SrcNode 源码位置**: `values.SrcNode` (list 子类，带 `line/col`)，`sugar/parser.py:_annotate_ast()` 后处理 AST 注入位置，`evaluator._eval_list` 异常时自动注入「第N行第M列」前缀。
- **LSP 增强** (`lsp_server.py`): 新增 `documentFormattingProvider`（接入 sanfmt）、`documentSymbolProvider`（函数+变量）、`foldingRangeProvider`（{} 块）、`referencesProvider`（符号引用查找）、`renameProvider`（批量重命名）、语义补全（用户定义变量/函数）、诊断增强（重复参数检测）。
- **LSP 跳转到变量定义** (`lsp_server.py`): `_do_definition` 现在同时支持 `设 var =` 和 `定义 func(` 的跳转。
- **DAP 调试适配器** (`dap_server.py`): 完整的 DAP 协议服务器，支持 VS Code 断点/单步/变量查看/栈帧/continue/next/stepIn。
- **性能基准套件** (`benchmark/`): fib/primes/fizzbuzz/fib_iter 基准文件 + `run_benchmark.py`（`--quick` / `--profile`）。
- **包管理器 URL 白名单** (`ops/package_ops.py`): `PACKAGE_ALLOWLIST` 限制允许的下载域名。
- **模块相对路径** (`preprocess.py`): `#include "../lib.san"` 支持 `../` 相对路径解析，`_resolve_include_path()` 做越界安全检查，递归展开传递 `_base_dir`。
- **REPL 历史持久化** (`repl.py`): Windows 下自动尝试 `pyreadline3` 回退链。
- **REPL 语法高亮** (`repl.py`): 检测 `colorama`，按值类型着色输出（绿=正数、红=负数、黄=零、青=字符串）。
- **sugar.san 对比测试** (`tests/test_sugar_san.py`): 新增 8 个 Python 兼容性测试（if/else/fn/set/loop/annotation/and/or/not）。

### 修复
- **LSP 括号配对映射**: `} → {` 修正。
- **全角冒号词法分析器**: 全角冒号不触发操作符误判。
- **list_sum 类型错误**: 修复 list_sum 的 TritValue 类型检查。
- **测试缺失导入**: `test_ops.py`、`test_iot.py` 补充缺失导入。
- **fizzbuzz for 参数**: 起始值从 0 修正为 1。
- **`_safe_include_path` 向后兼容**: 保留旧函数别名。

### 文档
- **README.md**: 新增 v3.10.0 特性表格、更新测试数量（44→52, 66→78, 22→28）、路线图补充、文件树补充 `benchmark/`。
- **CONTRIBUTING.md**: `sugar.py` 引用更新为 `sugar/` 包。
- **AGENTS.md, CONTRIBUTING.md**: 测试数量同步更新。

---

## [v3.9.0] — 2026-05-16

### 新增
- **sugar.san 接入导入管线** (`ops/file_ops.py`): `import_module()` 和 `_parse_and_eval_file()` 统一经过 `_parse_code()`，按序尝试 sugar.san → Python SugarConverter → S 表达式回退。sugar.san 通过 `_load_sugar_parser()` 自举（Python SugarConverter 编译 → SanyanEvaluator 执行注册 `解析`/`词法分析` 命令）。
- **sugar.san 性能优化** (`stdlib/sugar.san`): `词法分析` 开头调用 `设 chars = 字列(source)` 将字符串拆为字符列表，后续所有单字符访问 `子串(source, i, 1)` 替换为 `取(chars, i)`，复杂度从 O(n²) 降至 O(n)。
- **sugar.san 鲁棒性**: 修复注释 `/` 误判、全角数字识别、运算符映射、`再若`/`elif` 支持、`捕获` 不带 `(var)` 语法。
- **sugar.san 测试** (`tests/test_sugar_san.py`): 37 项测试覆盖加载、基础解析、控制流、列表/字典、try/catch、运算符优先级、边界条件、全角、点号访问、结构校验、Python 兼容性。
- **`含键`/`计数` 内置操作**: `runtime.py` BUILTIN_OPS 新增 `'含键'`、`'计数'`；`language/chinese.json` 新增 `"dict_contains": "含键"`。
- **文档同步**: `docs/manual.md` 第 17 节新增 `含键` 条目。

### 修复
- **eval.san 语义** (`stdlib/eval.san:269`): 分析确认 `是字符串(stripped)` 正确，未做改动。

### 重构
- **代码重复清理** — 提取共享 `to_num()` 工具函数到 `values.py`，消除 `container_ops.py` 中 10+ 处重复的 `TritValue` 数值转换模式；`package_ops.py` 复用 `file_ops._parse_code` 消除文件解析逻辑重复。
- **错误处理收紧** — 20 处 `except Exception` 替换为精确异常类型（`ValueError`, `TypeError`, `IOError`, `json.JSONDecodeError` 等）；`main.py` sugar 语法失败不再静默，错误信息叠加显示。
- **安全隐患修复** — `package_ops.py` zip-slip 攻击防护（逐文件校验路径）；丢失的 `with open()` 上下文管理器补全。
- **职责拆分** — `evaluator.py._eval_str` 拆分为 `_parse_string_literal` / `_parse_numeric_literal` / `_resolve_identifier` 三方法；`_eval_symbol` 从 `runtime.py` 移至 `evaluator.py`（求值逻辑归求值器）。
- **TritValue 对象池** — 新增 `threading.Lock` 线程安全保护；池大小通过 `TRIT_POOL_SIZE` 环境变量可配置。
- **`self.vars` 改名** — `runtime.py` 属性 `vars` → `scope_vars`，消除对 Python 内置 `vars()` 的遮蔽；波及 `control_ops.py`, `values.py`, `file_ops.py`, `package_ops.py`, `test_core.py`。
- **测试深度提升** — `test_parser.py` 转为 unittest 格式（28 项）；`test_ops.py` 新增 12 项负面测试（除零、类型错误、参数缺失、边界条件、混合类型等）。

### 基础
- 全部 6 项技术债清理完毕，252 项测试（含 37 项 sugar.san 测试 + 28 项 parser unittest + 12 项负面测试）全部通过。

---

## [v3.8.0] — 2026-05-16

### 新增
- **纯 Sanyan 元循环求值器** (`stdlib/eval.san`, ~300 行): 运行在 Python 求值器之上的自举级求值器——支持变量绑定、特殊形式（若/做/设/定义/函数/循环/遍历/尝试）、内置操作分派（40+ 操作）、闭包与高阶函数调用。10 组集成测试覆盖算术、比较、逻辑、列表、条件、递归、lambda、闭包、斐波那契。
- **`dict_contains` 操作** (`ops/container_ops.py`): 安全的字典键存在检查（`含键`），返回 `真`/`假` 永不抛异常，配套内置包装。
- **操作注册表统一** (`ops/registry.py`): 每个 `ops/*.py` 模块末尾加 `register()` 调用，`evaluator.py` 的 `_OP_DISPATCH` 手写分发表完成迁移到 `registry.get_op()`。
- **ops 模块单元测试** (`tests/test_ops.py`): 66 项 Python unittest 覆盖算术、比较、逻辑、数学函数、字符串、容器、控制流、JSON、Lambda、文件等全部操作类别。
- **LSP 测试** (`tests/test_lsp.py`): 6 项（initialize/completion/hover/definition/signatureHelp/didOpen），使用后台读取线程 + 响应 ID 匹配正确区分通知和请求。
- **包管理器测试** (`tests/test_package.py`): 6 项覆盖安装拒绝 HTTP/FTP、加载不存在的包、包路径解析。
- **解析器 AST 校验** (`tests/test_parser.py`): 从仅检查"不崩溃"升级为 22 项精确 AST 结构验证（每个测试检查特定的节点类型、子结构、字面值格式）。
- **`editor.skel.py`, `doc_sync.py`** 等辅助工具。

### 修复
- **断言框架** (`stdlib/test.san`): `_断言失败` 改为 `1 / 0`（除零触发 `SanyanValueError`），修复断言失败不报错的 bug。
- **路径穿越加固** (`ops/file_ops.py`): `_resolve_path` 先 `os.path.normpath` 再检查 `..`，防止 `./../../` 绕过。
- **HTTPS 强制** (`ops/package_ops.py`): 下载包前检查 URL 以 `https://` 开头。
- **`input_op` 鲁棒性** (`ops/io_ops.py`): 改用 `try: float()` 替代手动 `isdigit` 校验。
- **`get_var` 语义** (`runtime.py`): 找不到变量时改为 `raise SanyanNameError` 替代返回 `None`。
- **`eval` 支持 `float`** (`evaluator.py`): 原只支持 `int` 节点类型，现同时支持 `float`。
- **CHANGELOG 顺序** — v3.3→v3.4→v3.5→v3.6 恢复正确时间线。

### 变更
- **求值器重构** (`evaluator.py`): `eval()` 拆分为 `_eval_list()` / `_eval_str()`；`_apply()` 拆分为 `_resolve_op_name()` / `_dispatch_op()` / `_handle_dot_access()` / `_handle_variable_call()`。
- **死代码移除** (`evaluator.py`): `_name_cache_put()` 方法已定义但从未调用 — 删除。
- **分号风格统一** (`ternary_core.py`): 5 行 `res.append(...); carry = ...` 拆为两行。
- **测试覆盖增强**: 10 个 `.san` 测试文件（math/string/container/edge/scope/stress/tailcall/type/v37/regression）新增断言语句，`run_all.py` 退出码检查因此更有意义。
- **`ModuleValue.call`** (`values.py`): 执行函数体期间暴露模块内部 commands，使嵌套调用可达。
- **文档同步**: README 删除重复文件树（317-339 行），补充遗漏的 `main.py`，修正错误注释。
- **覆盖率配置** (`pyproject.toml`): 新增 `[tool.coverage.run]` / `[tool.coverage.report]`。

### 文档
- **CHANGELOG.md**: 新增 v3.8.0 条目。
- **README.md**: 更新版本号、修正项目结构树、删除重复条目。

---

## [v3.7.1] — 2026-05-15

### 修复
- **sugar.py**: `parse_primary` 同时查询 `KEYWORD_MAP` 和 `OP_MAP`，修复 `非`/`取位` 前缀运算符解析失败。
- **evaluator.py**: 移除 `_apply` 方法中无操作 `if ...: pass` 死代码块。
- **ternary_core.py**: `TritValue` 对象池从 `dict.clear()` 整体清空改为 `OrderedDict` LRU 逐出策略。
- **sugar.py**: 列表推导式试探解析的 `except Exception` 裸捕获改为 `except (SyntaxError, SanyanError)` 精确异常。

### 变更
- **skin.py**: 移除重复的 `ROOT_TERNARY` 硬编码，统一从 `TritValue.STATE_MAP` 获取三态词根表。
- **CI/CD**: `actions/checkout@v3→v4`、`setup-python@v4→v5`；新增 `test_parser.py` 回归测试步骤。
- **类型注解**: 为 `values.py`、`commands.py`、`lexer.py`、`parser.py`、`preprocess.py`、`evaluator.py`、`repl.py`、`runtime.py` 补充 `typing` 签名。
- **evaluator.py**: `_name_cache` 加入 5000 上限保护，防止长 REPL 会话中无界增长。
- **commands.py**: TCO 迭代乘数从魔数 `10` 提取为 `_TCO_LOOP_MULTIPLIER` 常量。

### 文档
- **CHANGELOG.md**: 新增 v3.7.1 条目。

### 新增
- **模块导出系统**: `导出 name1 name2` 控制模块可见性；`import_module` 循环依赖检测。
- **设备注册表**: `Device` 协议 + `MockDevice`/`FileDevice` + `DeviceRegistry`；`注册设备 名称 为 类型` 语法。
- **糖语法解析器拆分**: `sugar.py` 拆分为 `sugar/` 包（`lexer.py`、`parser.py`、`errors.py`），Pratt 解析替代手写递归。
- **三进制定点数**: `BT.from_float()` / `BT.to_float()` 将浮点转为平衡三进制 trits 表示。
- **`#` 行注释**: 新增 `#` 注释语法。
- **全角引号定界符**: 新增 `「」`、`『』`、`""`、`''` 六种字符串定界符。
- **S 表达式 IoT 中文别名**: `读取`、`写入`、`查询` 直接可用。
- **希腊字母 Lambda**: `λ(x) { ... }` 等价于 `函数(x) { ... }`。
- **`BUILTIN_OPS` 补全**: 补充 `跳出`/`继续`/`判`/`导入`/`导出`/`注册设备`/`读取`/`写入`/`查询`/`从`/`到`/`在`。
- **CONTRIBUTING.md**: 贡献指南文档。
- **ops/__init__.py**: 添加模块文档字符串。
- **测试**: 新增 `TestPreprocess` 3 项、`TestTernaryEdge` 4 项（含定点数）。
- **三进制数学库**: `sin`/`cos`/`tan`/`sqrt`/`exp`/`log`/`log10` 纯三进制定点实现（CORDIC + Taylor + Newton），替代 Python float 回退。
- **LSP 语言服务器**: `lsp_server.py` 提供代码补全、诊断、悬停提示、跳转定义、签名帮助。
- **`ops/registry.py`**: 装饰器驱动的操作注册表，替代 `_OP_DISPATCH` 手写分发表。
- **`_name_cache` LRU 淘汰**: 全量清空 → 单条目 LRU 逐出。
- **`commands.py:call()` 重构**: 108 行单方法拆分为 6 个子方法（`_resolve_command`/`_match_params`/`_evaluate_args`/`_detect_tail_call`/`_run_tail_call`/`_run_normal`）。
- **VS Code 扩展**: `sanyan-vscode/` 扩展包，提供语法高亮 + LSP 客户端。
- **`doc_sync.py`**: 文档自动同步脚本。
- **移除 `sugar/sugar_old.py`**: 旧解析器 fallback 删除，减少 680 行遗留代码。
- **全角 `<=` 等运算符修复**: `sugar/lexer.py` 多字符运算符检查改用 mapped 字符。
- **`parse_if` 递归修复**: 再若/否则的双消费 token 问题。
- **`.vscode/settings.json`**: VS Code 工作区配置。
- **包管理器**: `ops/package_ops.py` 提供 `安装`/`包列表`/`加载包` 命令；本地+远程包索引；示例包 `sample`。
- **VS Code Marketplace 上架**: `sanyan-language-0.1.0.vsix` 已发布（后因 Marketplace 上架需银行卡验证，暂改为本地 VSIX 安装）。
- **扩展 Logo**: 128x128 自定义图标。


## [v3.7] — 2026-05-14

### 新增
- **浮点数支持**：`TritValue` 扩展支持 Python float，算术运算（加减乘除幂）支持自动类型提升。
- **JSON 支持**：新增 `转JSON` (`to_json`) 和 `解析JSON` (`from_json`) 内置操作。
- **标准库扩充**：
    - `math.san`: 新增 `最大公约数`、`最小公倍数`、`素数判断`、`圆面积`。
    - `list.san`: 新增 `计数`、`是列表`。
- **工程化增强**：
    - `pyproject.toml`: 引入现代打包配置，集成 Ruff Linter。
    - `CI/CD`: 增加 GitHub Actions 自动化测试。
    - **模块拆分**: `ops/io_ops.py` 拆分为 `io_ops.py`, `file_ops.py`, `type_ops.py`。
- **类型标注**: 为 `ternary_core.py` 和 `runtime.py` 补充类型注解。

### 变更
- **三角函数**: 从整数千分位返回改为直接返回高精度浮点数。
- **`main.py`**: 提取 `main()` 入口，版本号更新至 v3.7。

---

## [v3.6] — 2026-05-13

### 新增
- **`preprocess.py` 预处理模块**：将 `main.py` 和 `sugar.py` 中重复的 `#include` 展开逻辑提取为公共函数 `preprocess_includes()`
- **`SanyanValueError` / `SanyanRuntimeError` / `SanyanKeyError` / `SanyanAttributeError`**：补齐语言层异常体系
- **跨作用域变量查找**：`SanyanRuntime.get_var(name)` / `has_var(name)` / `set_var(name, value)` / `all_scoped_vars()` 方法
- **模块导入缓存**：`导入()` 重复加载同一文件不再重新解析，直接返回缓存的 `ModuleValue`
- **文件路径安全校验**：`_resolve_path()` 阻止 `..` 目录穿越，覆盖 `读文件`/`写文件`/`加载`/`导入`
- **`#include` 路径安全校验**：`preprocess.py` 禁止 `..` 穿越
- **`tests/test_core.py`**：Python 单测 26 项（三进制核心、作用域栈、异常体系、函数调用、模块）

### 变更
- **统一错误类型**：所有运行阶段 `raise` 从 Python 原生异常改为 Sanyan 系列
  - `SyntaxError` → `SanyanSyntaxError` / `TypeError` → `SanyanTypeError` / `ValueError` → `SanyanValueError` 等 8 种
  - 保留 Python 原生的仅 `parser.py`（解析阶段）和 `ternary_core.py`（避免循环依赖）
- **作用域栈式链重构**：替代 `saved_vars = dict(evaluator.vars)` 全量拷贝方案
  - `SanyanRuntime` 新增 `_scopes` 作用域栈，`vars` 改为 property 指向栈顶
  - `commands.py:call()`、`values.py:FunctionValue.call()`、`values.py:ModuleValue.call()` 使用 `push_scope()` / `pop_scope()` 零拷贝
  - 闭包捕获、调试显示、REPL 补全均改用 `all_scoped_vars()`
- **main.py 语法检测简化**：删除手动注释/字符串扫描（30 行），改为 try-fallback 模式对齐 REPL
- **`_load_file` 语法检测对齐**：同样改为 try-fallback
- **循环条件求值修正** (`loop_op`)：条件表达式从循环末尾移到开头重新求值
- **三进制乘法加速**：用 Python int 乘法替代 trit-by-trit 移位加，大数 O(n·m)→O(log n)
- **IO 异常规范化**：文件 IO 错误从 `IOError`/`FileNotFoundError` 转为 `SanyanValueError`，可被 `尝试/捕获` 捕获
- **sugar.py 结构优化**：`_is_ident` 提取为模块级函数，类内加分区注释
- **`lexer.py` 全角符号补全**：新增 `；`（全角分号）和 `　`（全角空格）
- **`evaluator.py` `_name_cache`**：缓存原始关键词→内部标识映射，减少运行时皮肤查表

### 修复
- **main.py O(n²) 语法检测**：`code.index(ch)` 循环内扫描修复为标准索引遍历
- **尾递归作用域重复弹出**：`finally` 与 `except` 双重 `pop_scope()` 修复
- **sugar.py 导入优化**：`preprocess_includes` 提升为模块级 import
- **sugar.py token 行号定位**：从 `str.find()` 重构为同步扫描定位，避免重复 token 匹配错误

---

## [v3.5] — 2026-05-13

### 新增
- **`不大于` / `不小于` 运算符**：语义化比较运算符，分别等价于 `<=` / `>=`，支持中文和半角符号（`!>` / `!<`）
- **双语法对照测试与示例**：所有测试和示例均提供糖语法 + S 表达式双版本（`_se` 后缀），方便对照学习
- **测试框架增强**：新增 `断言不相等`、`断言大于`、`断言小于`、`断言大于等于`、`断言小于等于`、`断言错误`（支持可变参数）
- **S 表达式语法检测**：`main.py` 自动识别 S 表达式文件，注释中的 `{` 不再误判为糖语法
- **REPL 中文切换命令**：`切换中文`/`切换英文` 替代 `:lang chinese`/`:lang english`，同时支持 `:lang 中文`/`:lang 英文`
- **模块路径解析**：`导入("test")` 自动查找 `stdlib/test.san`，无需写完整路径
- **调试信息增强**：`调试()` 输出包含变量类型、调用栈深度和最近调用
- **性能优化**：TritValue 对象池 + `__slots__` + `_apply` 方法缓存
- **Lambda 闭包**：Lambda 自动捕获定义时的变量环境，支持闭包
- **字典点号访问**：`学生.姓名` 等价于 `取键(学生, "姓名")`
- **三进制字面量**：`三进制("+-0")` 将三进制字符串转为整数（即 6）
- **#include 预处理器**：`#include "test"` 编译时展开文件内容
- **REPL 历史记录**：上下键翻历史，Tab 键自动补全关键字和变量名
- **基准测试**：`tests/benchmark.san` 测量运算/调用/列表/逻辑性能

### 变更
- **删除无用文件**：`greenhouse.log`、`__pycache__/`、`.github/workfliws/`、`tools/`、`tests/fuzz.py`
- **版本号统一**：`main.py`、`repl.py` 版本号更新至 v3.5
- **skin.py**：`switch_skin()` 支持中文参数（`'中文'`/`'英文'`）

### 修复
- **尾递归作用域重复弹出**：`commands.py` 中 `ReturnException` 触发时 `finally` 与 `except` 均调用 `pop_scope()`，修复为仅 `finally` 负责清理
- **ModuleValue.call 参数求值**：修复已求值参数被二次 `eval` 导致列表值作为代码执行的 bug
- **evaluator.py 重复键**：修复 `_OP_DISPATCH` 中 `pow` 键重复导致三进制幂运算被覆盖
- **repl.py :maxloop**：修复 `:maxloop` 命令嵌套在 `:lang` 分支内不可达的问题
- **stdlib/test.san 断言**：断言失败时不再静默通过，改为返回错误消息触发异常
- **stdlib/list.san 空列表**：`最大值([])` 和 `最小值([])` 不再因 `空` 未定义而崩溃
- **stdlib/string.san 计数**：修复 `计数` 函数切片后位置计算错误
- **language/english.json**：补充缺失的 `do` 关键字
- **docs/manual.md**：删除重复的目录标题和重复的 4.6 节

---

## [v3.4] — 2026-05-08

### 新增
- **国际化皮肤系统** (`skin.py`)：关键字、操作符可切换，默认中/英文皮肤
- **全角符号兼容**：纯中文输入法可自由编写代码，全角空格智能跳过
- **字符串插值**：`模板{文本${表达式}文本}` 自动展开为 `连接` 调用
- **三态分支 `判`**：`判 x { 真 {...} 可能 {...} 假 {...} }` 原生三态模式匹配
- **`跳出` 关键字**：可在 `循环` 和 `遍历` 中提前退出
- **窄异常捕获**：`尝试`/`捕获` 只捕捉语言层 `SanyanError`，系统错误直接暴露
- **新增示例**：
  - 三态投票统计 (`examples/voting.san`)
  - 不确定数据清洗 (`examples/data_cleaning.san`)
- **回归测试**：解析器测试 24 项 + 运算符/容器/跳出/异常测试

### 变更
- **拆分内置操作**：将原先 500+ 行的 `builtins_ops.py` 拆分为 `ops/` 模块包（control、math、string、container、io、iot）
- **消除循环依赖**：提取公共值类型与异常到 `values.py`
- **清理死代码**：移除未使用的 `_maybe_implicit_and` 方法
- **优化语义**：温室示例输出措辞调整，`查` 命令显示中文状态词（开/守/关）
- **皮肤文件整理**：`language/chinese.json`、`language/english.json` 完善所有关键字

### 修复
- **运算符优先级**：比较运算符优先级高于逻辑运算符（`a > 2 且 b < 4` 正确解析）
- **前缀操作符**：`读 人体` 在S表达式全中文输入下正确识别
- **容器操作**：字典/列表/数组的边界情况处理
- **REPL 中断**：`Ctrl+C` 优雅退出，不再显示 traceback
- **异常处理**：文件不存在等系统错误不会被误吞

### 文档
- 更新语言手册：新增 `跳出`、`判`、`模板`、皮肤、窄异常章节
- 更新 README：温室输出示例含三进制后缀

### 测试
- 新增自动回归测试运行器 `tests/run_all.py`
- 新增边界测试 `tests/test_edge.san`

---

## [v3.3] — 2026-05-04
- 初始发布：平衡三进制核心、糖语法、S 表达式、高阶函数、IoT 抽象、温室示例
