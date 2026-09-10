# Roadmap

> 本仓只维护**三言语言 / 编译器 / VM / 约束系统**工程项。  
> 研究叙事（UR / 周期谱）真相源：独立仓库 <https://github.com/shujingyin510/UR> 与知识库 `sanyan-obsidian`。  
> Agent 自更新线（2026-09-10）**冻结**：同模型平台期已判定，死因考古见知识库；解冻条件=换强模型或约束系统收尾后重评。

## Completed（本体）

| Milestone | Details |
|-----------|---------|
| **C VM (ISA v2)** | 16-bit LOAD/STORE, 32-bit CALL, CLOSURE, PUSH_STR16 |
| **Level 3 Bootstrap** | 318-line C seed VM → TCC-compiled binary |
| **Level 4 Bootstrap** | 617-line x86_64 NASM assembly VM |
| **FFI M1–M5** | Python 桥 → 语法糖 → C 头生成 → ctypes+LLVM 双后端 → 安全收口 |
| **Network envelope** | `SANYAN_NET` + 超时=可能 + SSRF 豁免（v3.57.0） |
| **Constraint MVP first cut** | 能力栈默认拒绝 + `任务{约束}`（v3.58.0） |
| **Constraint MVP closed** | 信封式判假·因=约束 + E7 并发继承 + 字节码拒约束算子 + 糖语法 `任务名{约束{…}}` + S1–S4 测试全绿（54 项） |
| **Playground / Pages** | 纯静态在线试玩入口 |
| **Agent Safety / Honesty / Evolution** | 已有基准保留；数字以 `docs/CLAIMS.md` 清账为准（进化实验为合成模拟·机制演示） |

> 三态门控 / 神经推理 / UR 阈值与 R1–R4 周期谱**不在本仓维护** → <https://github.com/shujingyin510/UR>

---

## Next（本体工程）

| Priority | Item | Notes |
|----------|------|-------|
| 🔴 | **文档漂移修复（本轮已修 opcode/匹配3）** | PLAN_v* 归档仍待做 |
| 🟡 | **Agent 数据外置** | 19 个 `.db` 迁出源码树；双轨 evolution 收敛；安全/校准模块进覆盖率（**不扩新功能**） |
| 🟡 | **sugar.bin 解析器** | 返回 AST 替代字符串（预存在 bug） |
| 🟡 | **Windows Level 3 C 种子** | 当前仅 Linux/TCC |
| 🟢 | **NASM L4 差分闭环** | 已知三缺陷待 nasm+Linux 实证 |
| 🟢 | **类型系统编译期检查** | 当前仅运行时部分 |
| 🟢 | **增量 LSP** | 避免大文件全量重扫 |

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
