# Agent 可读决策 DSL

[English](README_EN.md)

> 基于 [ternary-engine](https://pypi.org/project/ternary-engine/) 的 LLM Agent ——每步决策带置信度，不确定时自动门控拦截。

---

## 快速开始

```bash
set SANYAN_API_KEY=sk-你的key

# 单次提问
python -X utf8 run_agent.py "run_agent.py有哪些函数超过50行"
# → ⚠ >50行: init_evaluator, run_once, main, _analyze_file

# 自主模式（读→改→测→修→完成）
python -X utf8 run_agent.py "修复 _test_verify.py 让测试通过" --auto
# → [AFFIRM]→真 ●●● [0.81] → 修复成功

# 只读不改
python -X utf8 run_agent.py "把AGENTS.md里v0.3改成v0.4" --dry-run
# → [干跑] 将在 AGENTS.md 替换 v0.3 → v0.4
```

---

## 架构

```
用户任务
  │
  ├─ _force_tool()        智能首轮：检测"函数"→直接 analyze，省一次 LLM
  ├─ _pre_analyze()       预分析：扫码文件结构 + 符号表 + 跨任务回忆
  │
  ▼
  LLM 决定下一步工具 ──→ TernaryEngine.step()
  │                        ├─ classify()   分类：AFFIRM/NEGATE/UNCERT
  │                        ├─ map_trit()   映射：1/0/-1
  │                        ├─ propagate()  Kleene 传播
  │                        ├─ confidence() 贝叶斯置信度衰减
  │                        └─ protect()    门控：高风险+不确定=拦截
  │
  ▼
  执行工具 ──→ MemoryStore.add()
              │  ├─ 关键词提取（英文标识符 + 中文双字片语）
              │  ├─ LLM 5字摘要 → S-Memory 语义检索
              │  └─ 时间衰减（60秒权重减半）
              │
              ▼
              反思 ──→ 继续 / 修正 / 完成
```

### 文件分层

| 文件 | 职责 | 行数 |
|------|------|------|
| `ternary_engine.py` | 三态决策引擎（Kleene + 贝叶斯 + 门控） | 131 |
| `agent_runtime.py` | V3 运行时（SymbolTable / MemoryStore / ProjectGraph / 预分析） | 492 |
| `agent_tools.py` | 工具层（12 个工具，纯函数，0 外部依赖） | 170 |
| `agent_policy.san` | 策略配置（模型 / 阈值 / 场景规则，热重载） | 194 |
| `decision.san` | 旧引擎决策核心（三态传播/保护/投票，待迁移） | 185 |
| `agent.san` | 旧引擎主循环（交互模式，待迁移） | 1242 |
| `run_agent.py` | 启动器（CLI 参数 + 双引擎切换） | 1068 |

---

## 工具

| 工具 | 用途 | 参数格式 |
|------|------|----------|
| `analyze` | 分析文件结构（函数/导入/行数），自动标记 >50 行函数 | `文件路径` |
| `find_symbol` | 查找符号定义和所有引用 | `符号名` |
| `read_file` | 读文件，支持行范围 | `路径\|起始行\|结束行` |
| `search_code` | 全局搜索关键词，返回匹配行 | `关键词` |
| `replace_in_file` | 单文件替换，`\n` 转义为换行 | `路径\|旧\|新` |
| `replace_all` | 批量跨文件替换 | `模式\|旧\|新` |
| `write_file` | 写文件，`\n` 转义为换行 | `路径\|内容` |
| `list_files` | 列文件，递归搜索 | `模式` |
| `run_test` | 运行 pytest，返回通过/失败+错误摘要 | `测试路径` |
| `git_diff` | 查看 git 修改（--stat） | （无参数） |
| `git_status` | 查看 git 状态（--short） | （无参数） |

---

## CLI

```bash
python -X utf8 run_agent.py "任务"              # 单次提问（V3 引擎）
python -X utf8 run_agent.py                      # 交互模式（旧引擎）
python -X utf8 run_agent.py "任务" --auto        # 自主模式：跑完才停
python -X utf8 run_agent.py "任务" --dry-run     # 只读不改：写操作返回预览
python -X utf8 run_agent.py "任务" --report      # 完成后输出任务报告
python -X utf8 run_agent.py "任务" --rounds 5    # 限制最大轮次
python -X utf8 run_agent.py --list-tasks          # 查看 SQLite 任务历史
python -X utf8 run_agent.py --resume             # 续接上次未完成任务
```

---

## 配置

编辑 `agent_policy.san`（修改后热重载，无需重启）：

```san
# 模型
设 模型提供商 = "deepseek"  # deepseek / openai / qwen / gemini / mimo / ollama / tokenplan
设 模型URL = "https://api.deepseek.com/v1/chat/completions"
设 模型名 = "deepseek-chat"
设 超时秒数 = 60

# 决策阈值
设 最大轮次 = 10
设 最大犹豫次数 = 3
设 最小增益阈值 = 0.05

# 场景规则（非程序员可直接编辑）
设 场景规则 = 列表(
    字典("场景", "借钱", "关键词", "借钱,借款...", "风险", "高", "要求好感", 30, "信任阈值", 25),
    字典("场景", "修改Agent配置", "关键词", "最大轮次,API密钥...", "风险", "高", "要求好感", 60),
    ...
)
```

支持 7 家模型提供商，一行切换。高风险场景自动门控 + 信任感知权重。

---

## 三态显示

每步工具调用后显示三态传播链：

```
[AFFIRM]→真 ●●● [0.81]     ← 认知态 → 三态值 置信度
[NEGATE]→假 ○○○ [0.34]     ← 失败降为假
[UNCERT]→可能 ◐◐◐ [0.15]  ← 不确定进入犹豫计数
```

三态符号：`●`=真 / `◐`=可能 / `○`=假。门控触发时自动拦截。

---

## 村庄观察器

```bash
python -X utf8 run_village_observe.py --days=5
```

NPC 自主生活 + LLM 驱动对话 + TernaryEngine 三态信任演变 + SVG 图表 + JSON 日志。

每轮对话后三元引擎追踪村庄全局置信度：

```
凝聚力: 0.237  假:2 可能:1 真:1  三态: 真 ●●● [0.25]
凝聚力: 0.198  假:8 可能:2 真:1  三态: 真 ●●● [0.01]
```

---

## 测试

```bash
python -X utf8 tests/test_agent.py -v          # 31 项：决策流水线（映射/传播/投票/保护/规则）
python -X utf8 tests/test_agent_runtime.py -v  # 27 项：V3 引擎（SymbolTable/MemoryStore/约束/工具）
python -X utf8 tests/run_all.py                # 46 项集成测试
```
