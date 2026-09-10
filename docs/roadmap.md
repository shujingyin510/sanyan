# Roadmap

> 本仓只维护**三言语言 / 编译器 / VM / 约束系统**工程项。  
> 研究叙事（UR / 周期谱）真相源：独立仓库 <https://github.com/shujingyin510/UR> 与知识库 `sanyan-obsidian`。  
> Agent 子系统 **2026-09-10 拆出** → <https://github.com/shujingyin510/sanyan-agent>（自更新线冻结）。见 [`AGENT_MOVED.md`](AGENT_MOVED.md)。

## Completed（本体）

| Milestone | Details |
|-----------|---------|
| **C VM (ISA v2)** | 16-bit LOAD/STORE, 32-bit CALL, CLOSURE, PUSH_STR16 |
| **Level 3 Bootstrap** | C seed VM → TCC/Linux syscall + MinGW/Windows CRT 双路径 |
| **Level 4 Bootstrap** | 617-line x86_64 NASM assembly VM |
| **FFI M1–M5** | Python 桥 → 语法糖 → C 头生成 → ctypes+LLVM 双后端 → 安全收口 |
| **Network envelope** | `SANYAN_NET` + 超时=可能 + SSRF 豁免（v3.57.0） |
| **Constraint MVP first cut** | 能力栈默认拒绝 + `任务{约束}`（v3.58.0） |
| **Constraint MVP closed** | 信封式判假·因=约束 + E7 并发继承 + 字节码拒约束算子 + 糖语法 `任务名{约束{…}}` + S1–S4 测试全绿（54 项） |
| **`允许` 抑制语义** | `允许(x)` 挂 tolerated 元通道；`若(可能)` D8 关卡豁免；帧级 `允许 可能`（2026-09-10） |
| **sugar 解析 AST 契约** | 修 `字列→STR_TO_LIST`；真/假 发 PUSH_I；嵌套循环跳出隔离；`_exec_frame` 隔离 stack；VM 词法多 token 契约锁定 |
| **Windows Level 3 C 种子** | `sanyan_vm_seed.c` 加 `_WIN32` CRT 模拟层（fread/fwrite/固定堆）；`main` 入口；差分电池 28/28 全平台 |
| **Agent split** | `agent_system` + Agent 测试迁至 `sanyan-agent` 独立仓（2026-09-10） |
| **拆仓扫尾** | README/AGENTS/project_structure 去 Agent 正文改指针；`.coveragerc`/mypy 去 `agent_system`；PLAN_v* 与 Agent 加固计划入 `docs/archive/`；CLAIMS 安全/越界冲突归账 |
| **Playground / Pages** | 纯静态在线试玩入口 |
| **Agent Safety / Honesty / Evolution** | 已有基准保留；数字以 `docs/CLAIMS.md` 清账为准（进化实验为合成模拟·机制演示） |

> 三态门控 / 神经推理 / UR 阈值与 R1–R4 周期谱**不在本仓维护** → <https://github.com/shujingyin510/UR>

---

## Next（本体工程）

| Priority | Item | Notes |
|----------|------|-------|
| 🟢 | **NASM L4 差分闭环** | 已知三缺陷待 nasm+Linux 实证 |
| 🟢 | **类型系统编译期检查** | 当前仅运行时部分 |
| 🟢 | **增量 LSP** | 避免大文件全量重扫 |
| ⚪ | ~~文档漂移（opcode/匹配3/PLAN 归档）~~ | **本轮完成**（2026-09-10） |
| ⚪ | ~~Agent 数据外置 / 双轨收敛~~ | **不在本仓** → sanyan-agent；自更新线冻结 |

### 中长期

| Item | Notes |
|------|-------|
| C VM 多线程 | 性能 |
| LLVM JIT 缓存 | 避免重复编译 |
| 正式语言规范 RFC | 约束语义定稿后再写 |

---

## Frozen

| Item | Reason |
|------|--------|
| Agent S0–S6 扩张（S1/S3/S5/S6） | 2026-09-10 冻结；见知识库 Roadmap |
| UR / GGUF / CUDA / 论文 | 属 UR 仓 |
| 新增 `agent_*.py` 双轨实验 | 先写知识库笔记，不进本仓 |
