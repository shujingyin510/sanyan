# Agent 可读决策 DSL

[English](README_EN.md)

> **一句话**：基于三元引擎的 LLM Agent——每步决策带置信度，不确定时自动门控拦截。

---

## 目录

1. [快速开始](#快速开始)
2. [架构](#架构)
3. [工具](#工具)
4. [CLI](#cli)
5. [配置](#配置)
6. [村庄观察器](#村庄观察器)

---

## 快速开始

```bash
# 配置密钥
set SANYAN_API_KEY=sk-你的key

# 单次提问
python -X utf8 run_agent.py "run_agent.py有哪些函数超过50行"

# 自主模式
python -X utf8 run_agent.py "修复 _test_verify.py 让测试通过" --auto
```

---

## 架构

```
用户任务
  │
  ├─ _force_tool()      智能首轮（analyze/find_symbol 跳过 LLM）
  ├─ _pre_analyze()     预分析层（符号表 + 文件结构 + 跨任务回忆）
  │
  ▼
  LLM 决定工具 ──→  TernaryEngine.step()
  │                    ├─ classify()   认知分类
  │                    ├─ propagate()  Kleene 传播
  │                    ├─ confidence() 贝叶斯衰减
  │                    └─ protect()    门控拦截
  │
  ▼
  执行工具 ──→ MemoryStore.add()
              │   ├─ 关键词提取
              │   ├─ LLM 语义摘要
              │   └─ 时间衰减
              │
              ▼
              反思 ──→ 继续 / 完成
```

### 文件分层

| 文件 | 职责 | 行数 |
|------|------|------|
| `ternary_engine.py` | 三态决策引擎（Kleene + 贝叶斯 + 门控） | 131 |
| `agent_runtime.py` | V3 运行时（SymbolTable / MemoryStore / ProjectGraph） | 492 |
| `agent_tools.py` | 工具层（12 个纯函数） | 170 |
| `agent_policy.san` | 策略配置（模型 / 阈值 / 场景规则，热重载） | 194 |
| `decision.san` | 旧引擎决策核心（待迁移） | 185 |
| `agent.san` | 旧引擎主循环（交互模式） | 1242 |

---

## 工具

| 工具 | 用途 | 示例 |
|------|------|------|
| `analyze` | 分析文件结构 | `analyze\|run_agent.py` |
| `find_symbol` | 查找符号引用 | `find_symbol\|main` |
| `read_file` | 读文件 | `read_file\|run_agent.py\|1\|20` |
| `search_code` | 搜索代码 | `search_code\|def main` |
| `replace_in_file` | 单文件替换 | `replace_in_file\|f.py\|old\|new` |
| `replace_all` | 批量替换 | `replace_all\|*.py\|old\|new` |
| `write_file` | 写文件 | `write_file\|path\|content` |
| `list_files` | 列文件 | `list_files\|*.py` |
| `run_test` | 跑测试 | `run_test\|tests/test_agent.py` |
| `git_diff` | 查看修改 | `git_diff\|` |
| `git_status` | 文件状态 | `git_status\|` |

---

## CLI

```bash
python -X utf8 run_agent.py "任务"              # 单次（V3）
python -X utf8 run_agent.py "任务" --auto        # 自主
python -X utf8 run_agent.py "任务" --dry-run     # 只读
python -X utf8 run_agent.py "任务" --report      # 报告
python -X utf8 run_agent.py --list-tasks          # 历史
```

---

## 配置

编辑 `agent_policy.san`：

```san
设 模型提供商 = "deepseek"  # deepseek/openai/qwen/gemini/mimo/ollama/tokenplan
设 超时秒数 = 60
设 最大轮次 = 10
```

---

## 村庄观察器

```bash
python -X utf8 run_village_observe.py --days=5
```

NPC 自主生活 + LLM 对话 + 三态信任演变。SVG 图表 + JSON 导出。
