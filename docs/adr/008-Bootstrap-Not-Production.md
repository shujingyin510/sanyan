# ADR-008 自举链不升为生产路径（3.59 冻结决策）

- 状态：accepted
- 日期：2026-09-10
- 决策者：项目负责人
- 影响：编译管线、CI、文档叙事

## 背景

自举链为 Level 0–4：Python 求值器 → bytecode_compiler.san → 不动点 → C 种子 → NASM。  
生产编译/解析长期优先 **Python**（`sugar.parser` / `compile_bytecode`），理由是跨平台一致。  
sugar.bin / C 种子用于审计与差分，不是日常主路径。

## 决策

**3.59 冻结：不把自举链升为生产默认。**

- 生产路径继续：Python SugarConverter + Python 字节码编译包装
- C 种子 / sugar.bin：差分与审计资产
- NASM L4：后置，不在 3.59 范围
- 若未来要升自举为生产，**单独 ADR**，不得混入 3.59

## 后果

- 正：跨平台行为一致，文档与测试可预期
- 正：避免「自举不完整」阻塞语言语义规格化
- 负：「全自举」叙事与生产路径不一致，须在 README/本文件诚实声明
- 负：sugar.san 对 else/多语句循环的浅 AST **允许存在**（有 Python 兜底）

## 否决项

- 立刻把生产路径切到 sugar.bin/C 种子（解析仍不完整，风险大）
- 3.59 内并行修 NASM L4（环境依赖 nasm+Linux，拖节奏）

## 引用

- [[ADR-003]] Bootstrap-Strategy（知识库）
- `docs/release-3.59.md`
