# 三言项目结构（详细快照）

> 这是逐文件级的结构快照，可能随开发滞后；权威入口以 [README「项目结构」](../README.md#项目结构) 的顶层树为准。

```text
sanyan/
├── ARCHITECTURE.md            # 架构文档
├── AGENTS.md                  # AI 协作约定（自举状态、测试、代码规范）
├── CHANGELOG.md               # 变更日志
├── CONTRIBUTING.md            # 贡献指南
├── 愿景故事.md                 # 项目愿景故事（从Setun到三言）
├── README.md                  # 项目说明（中文）
├── README_EN.md               # 项目说明（英文）
├── build_combined.py          # 构建脚本：展开 #include 生成合并 .san
├── build_exe.py               # PyInstaller 打包脚本
├── sanyan/                    # 包命名空间（模块化入口）
│   └── __init__.py
├── core/commands.py                # 自定义命令调用
├── compiler/compile_bytecode.py        # .san → .bin 编译器（支持 #include）
├── compiler/compile_llvmgen.py         # llvmgen.san → llvmgen.bin 编译（V5 自举，无注入）
├── lsp/dap_server.py              # DAP 调试适配器
├── doc_sync.py                # 文档同步检查（→ scripts/doc_sync.py）
├── core/eval_utils.py              # 求值工具函数（类型转换/边界检查）
├── core/evaluator.py               # 求值器
├── repl/gui.py                     # 可视化编译器 GUI
├── core/lexer.py                   # S 表达式词法
├── lsp/lsp_server.py              # LSP 服务器
├── repl/main.py                    # 入口（支持 --vm 字节码缓存）
├── core/parser.py                  # S 表达式语法
├── core/param_matcher.py           # 参数匹配与类型检查
├── core/preprocess.py              # #include 预处理器
├── pyproject.toml             # 项目配置
├── repl/repl.py                    # REPL 交互环境
├── core/ternary_engine.py           # 三态认知引擎（Kleene×贝叶斯×门控）
├── compiler/discompiler/asm.py                   # 字节码反汇编器
├── verify.py                   # 字节码验证器
├── scripts/preflight.py        # 发版前预检（lint+test+自举）
├── agent_system/run_agent.py               # Agent 启动器
├── examples/run_v2.py                  # v2 演示启动器
├── examples/run_v2_demo.py             # v2 演示脚本
├── examples/run_village_demo.py        # 村庄演示脚本
├── examples/run_village_observe.py     # 村庄观察器（NPC 自主生活模拟）
├── core/runtime.py                 # 运行环境（作用域/IoT/调试/性能）
├── core/sandbox.py                 # 沙箱安全机制
├── sanfmt.py                  # 源码格式化器
├── compiler/sanyanc.py                # 编译器（S表达式 + sugar） + 包管理器
├── pyproject.toml             # 项目配置（含 setup 元数据）
├── core/skin.py                    # 皮肤管理器
├── core/tail_call.py               # 尾递归优化
├── core/ternary_core.py            # 平衡三进制算术（模拟）
├── core/values.py                  # 值类型 + 异常体系
├── vm/__init__.py                      # 字节码 VM（自举能力）
├── agent_system/              # Agent 系统（运行时 + 自更新闭环 + Sanyan DSL）
│   ├── run_agent.py           # Agent CLI 入口（交互/单次/自主/沙箱/进化）
│   ├── run_self_update.py     # 自更新闭环 CLI（挖掘→隔离编辑→oracle→分支由人合并）
│   ├── agent_loop.py          # 自主循环（文件监控+连续循环+健康监控）
│   ├── agent_runtime.py       # 主运行时（工具注册/约束限额/子系统协调）
│   ├── loop.py                # LLM 多轮主循环（时间预算/徘徊顶推/哨兵/停机如实）
│   ├── loop_policy.py         # 循环策略（UR 退化/上下文判定）
│   ├── agent_llm_handler.py   # LLM 调用（9 家提供商）+ 工具解析（五级兜底）
│   ├── agent_tools.py         # 工具层（read/replace/replace_lines/run_test 等纯函数）
│   ├── agent_core.py          # 基础类（SymbolTable/MemoryStore/ProjectGraph）
│   ├── self_update.py         # SelfUpdateLoop：worktree 隔离→fail-closed oracle→分支/回滚
│   ├── task_mining.py         # 任务挖掘（failing_test/todo/long_function）
│   ├── contracts.py           # ToolResult / LLMProvider 类型契约
│   ├── registry.py            # LazyRegistry 能力懒加载
│   ├── paths.py / store.py    # 数据目录统一（AGENT_DATA_DIR）/ 单一 agent.db
│   ├── config.py              # AgentConfig（agent_policy.san 热重载）
│   ├── agent_domain.py        # 领域知识层（LLM 动态生成 + SQLite 缓存）
│   ├── agent_rules.py         # 规则引擎（200+ 规则）
│   ├── template_manager.py    # 模板管理器（11 个模板库） + templates/
│   ├── ast_parser.py          # AST 解析器（精准上下文）
│   ├── ur_monitor.py          # UR 退化检测
│   ├── …                      # 30+ 能力插件（假设/进化/学习/协作/观测/知识层，懒加载）
│   ├── sanyan/                # Sanyan 语言实现（Agent DSL）
│   │   ├── agent.san          # Agent 核心逻辑（决策函数、记忆、追踪）
│   │   ├── agent_policy.san   # 纯数据策略（配置、阈值、映射规则）
│   │   ├── decision.san       # 决策核心（信任感知规则匹配）
│   │   └── runtime_v2/        # V2 运行时（village_game.san / npc_game.san / …）
│   ├── README.md / README_EN.md            # Agent 文档（中/英）
│   ├── agent_operations.md / _en.md        # 操作手册（中/英）
│   └── REFACTOR_PLAN.md       # 北极星路线（P0-P5 进度日志 + S0-S6 前瞻规划）
├── sugar/                     # 糖语法转换器
│   ├── __init__.py
│   ├── errors.py
│   ├── core/lexer.py
│   └── core/parser.py
├── llvmgen/                   # LLVM 代码生成器（已拆分）
│   ├── __init__.py
│   ├── build.py               # 完整编译管线
│   ├── codegen.py             # AST → LLVM IR（419 行）
│   ├── compiler.py            # 编译入口 + 解析器（424 行）
│   ├── helpers.py             # Python 辅助函数（377 行）
│   ├── ir_builder.py          # CodegenContext 构建器
│   ├── ir_fixes.py            # IR 后处理工具（220 行，从 compiler.py 拆出）
│   ├── ops_gen.py             # 主编译入口（410 行）
│   ├── ops_gen_control.py     # 控制流编译（341 行，从 ops_gen.py 拆出）
│   ├── ops_gen_helpers.py     # 算术/容器辅助（240 行，从 ops_gen.py 拆出）
│   ├── runtime.c              # C 运行时库（arena 分配器 + 52 操作码）
│   └── type_mapping.py        # 类型映射与运行时函数规范
├── ops/                       # 内置操作实现（30 模块）
│   ├── __init__.py
│   ├── arithmetic_ops.py      # 算术运算
│   ├── comparison_ops.py      # 比较运算
│   ├── concurrent_ops.py      # 并发与锁
│   ├── list_ops.py            # 列表/数组/通用容器操作
│   ├── dict_ops.py            # 字典操作
│   ├── control_ops.py         # 控制流
│   ├── crypto_ops.py          # 哈希与编解码
│   ├── device_registry.py     # IoT 设备注册表
│   ├── dispatcher.py          # 操作分派器
│   ├── file_ops.py            # 文件读写（支持 #include）
│   ├── io_ops.py              # 输入输出/调试
│   ├── iot_ops.py             # 传感器/执行器
│   ├── json_ops.py            # JSON 序列化
│   ├── logic_ops.py           # 三态逻辑
│   ├── math_extra_ops.py      # 统计函数
│   ├── math_funcs_ops.py      # 数学函数
│   ├── net_ops.py             # HTTP 请求
│   ├── package_ops.py         # 包管理器（安装/卸载/搜索/信息）
│   ├── random_ops.py          # 随机操作
│   ├── regex_ops.py           # 正则表达式
│   ├── registry.py            # 操作注册表
│   ├── sandbox_ops.py         # 沙箱操作
│   ├── string_ops.py          # 字符串操作
│   ├── system_ops.py          # 系统命令
│   ├── time_ops.py            # 时间戳/计时
│   ├── type_ops.py            # 类型判断
│   └── unicode_ops.py         # URL/Unicode 编码
├── sanyan-vscode/             # VS Code 扩展
│   ├── package.json
│   ├── extension.js
│   ├── language-configuration.json
│   └── syntaxes/
│       └── sanyan.tmLanguage.json
├── language/                  # 皮肤文件
│   ├── chinese.json
│   └── english.json
├── lsp/                       # LSP 语言服务器组件
│   ├── __init__.py
│   ├── analysis.py
│   ├── handler.py
│   ├── keywords.py
│   └── protocol.py
├── csrc/                      # C 语言 VM（52 指令完整版）
│   ├── runtime.c              # VM 实现（支持 #include 预处理）
│   ├── test_runtime.c         # VM 单元测试（61 项）
│   └── dp.c                   # parse_sanyan 原生编译测试
├── stdlib/                    # 标准库
│   ├── _bootstrap.san         # S 表达式引导解析器（自举起点）
│   ├── bytecode_compiler.san  # 自举字节码编译器（76 行）
│   ├── bytecode_compiler.bin  # 编译器 .bin（VM 可直接加载）
│   ├── sugar.san              # 糖语法解析器（合并版，由 build_combined.py 生成）
│   ├── sugar.bin              # 解析器 .bin（VM 独立运行）
│   ├── sugar_src.san          # （可选）糖语法拆分源码入口
│   ├── llvmgen.san            # LLVM 代码生成器（合并版，由 build_combined.py 生成）
│   ├── llvmgen.bin            # LLVM 编译器 .bin（V5 自举，无注入）
│   ├── llvmgen_src.san        # llvmgen 拆分源码入口（#include 子模块）
│   ├── llvmgen/               # llvmgen 拆分子模块
│   │   ├── preamble.san       # 全局变量 + 辅助函数
│   │   ├── utils.san          # 工具函数（生成模块头/尾、字符串常量）
│   │   ├── compiler.san       # 主编译函数
│   │   ├── runtime_ir.san     # 运行时 IR 生成
│   │   └── entry.san          # 编译顶层入口 + 导出
│   ├── combined.san           # sugar + llvmgen 合并版
│   ├── network.san            # 网络库（TCP/UDP/连接池/健康检查）
│   ├── hardware.san           # 硬件抽象层（GPIO/I2C/SPI/传感器）
│   ├── math.san               # 数学库（矩阵/向量/统计/概率分布）
│   ├── json.san               # JSON 解析/序列化
│   ├── http.san               # HTTP 客户端
│   ├── regex.san              # 正则表达式
│   ├── csv.san                # CSV 解析/生成
│   ├── string.san             # 字符串工具
│   ├── list.san               # 列表操作
│   ├── algorithm.san          # 算法库（排序/搜索/素数/斐波那契）
│   ├── collection.san         # 数据结构（栈/队列/集合）
│   ├── validate.san           # 数据验证
│   ├── iot.san                # IoT 便捷函数
│   ├── logic.san              # 三态逻辑
│   ├── stat.san               # 三态统计
│   ├── datetime.san           # 日期时间
│   ├── file.san               # 文件工具
│   ├── io.san                 # IO 工具
│   ├── test.san               # 测试框架
│   ├── eval.san               # 元循环求值器
│   ├── parse.san              # S 表达式解析器
│   ├── tokenize.san           # 词法分析器
│   ├── repl.san               # REPL
│   └── pipeline.san           # 编译管线
├── packages/                  # 包管理器
│   ├── index.json             # 包索引（11 个包）
│   ├── sample/                # 示例包（问候工具）
│   ├── math_extended/         # 扩展数学库（复数/向量）
│   ├── logging/               # 结构化日志库
│   ├── web_utils/             # Web 工具（URL/HTML/Cookie）
│   ├── data_pipeline/         # 数据管道（映射/过滤/聚合）
│   └── config/                # 配置管理库
├── examples/                  # 示例
│   ├── sensor_fusion.san      # 三值逻辑传感器融合（三言版）
│   ├── sensor_fusion.py       # 传感器融合（Python 对比版）
│   ├── sensor_fusion.c        # 传感器融合（C 对比版）
│   ├── fault_tolerant_control.san # 容错控制系统
│   ├── iot_state_machine.san  # IoT 设备状态机（三言版）
│   ├── iot_state_machine.py   # IoT 状态机（Python 对比版）
│   ├── circuit_sim.san        # Kleene 三值电路模拟
│   ├── data_cleaning.san      # 三态数据清洗管道
│   ├── health_check.san       # API 健康检测
│   ├── npc_decision.san       # NPC 犹豫决策
│   ├── greenhouse.san         # 温室监控
│   ├── voting.san             # 三态投票
│   └── stm32-blinky/          # STM32 嵌入式示例
│       ├── blinky.san         # LED 闪烁程序
│       ├── runtime_stm32.c    # STM32 VM + 外设驱动
│       ├── Makefile           # 构建系统
│       └── stm32_flash.ld     # 链接脚本
├── tests/                     # 自动测试（2450+ 项）
│   ├── test_core.py           # 核心单测（138 项）
│   ├── test_ops.py            # ops 模块单测（92 项）
│   ├── test_ops_ext.py        # 扩展 ops 单测（64 项）
│   ├── test_core/parser.py         # 解析器 AST 校验（28 项）
│   ├── test_core/commands.py       # 命令模块单测（18 项）
│   ├── test_sugar_san.py      # sugar.san 测试（45 项）
│   ├── test_llvmgen.py        # LLVM 代码生成测试（53 项）
│   ├── test_self_host.py      # 字节码编译器自举验证（8 项，含 Level 2 + Level 3）
│   ├── test_sugar_self_host.py # sugar.bin 自举验证（3 项）
│   ├── test_effect_types.py    # 效应类型测试（30 项，确定/不确定）
│   ├── test_diff_fuzz.py       # 差分模糊测试（12 项，四后端一致）
│   ├── test_compiler/discompiler/asm.py          # 反汇编器测试（6 项）
│   ├── test_vm/__init__.py             # VM 字节码测试（91 项）
│   ├── test_c_vm/__init__.py           # C VM 测试（14 项，需 gcc）
│   ├── test_agent.py          # Agent 测试（31 项）
│   ├── test_llvm_native.py    # LLVM 原生编译测试
│   └── run_all.py             # 集成测试（46 项）
├── docs/                      # 文档
│   ├── manual.md              # 用户手册
│   ├── llvm.md                # LLVM 文档
│   ├── ternary-logic.md        # 三值逻辑深度解析
│   └── package_development.md # 包开发指南
├── benchmark/                 # 性能基准测试
├── ternary_agent/             # 三言 Agent（可读决策 DSL）
│   ├── agent.san              # Agent 核心逻辑（决策函数、记忆、追踪）
│   ├── agent_policy.san       # 纯数据策略（配置、阈值、映射规则）
│   └── memory.json            # Agent 记忆持久化
├── agent_system/run_agent.py               # Agent 启动器（单次/交互/热重载）
└── csrc/dp.c                  # parse_sanyan 原生编译验证
```
