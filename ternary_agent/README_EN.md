# Agent Readable Decision DSL

[中文](README.md)

> **TL;DR**: LLM Agent powered by TernaryEngine — every step carries confidence, gates block when uncertain.

---

## Quick Start

```bash
# Set API key
set SANYAN_API_KEY=sk-your-key

# Single question
python -X utf8 run_agent.py "analyze run_agent.py"

# Autonomous mode
python -X utf8 run_agent.py "fix _test_verify.py so tests pass" --auto
```

## Architecture

```
User Task
  │
  ├─ _force_tool()      Smart first round (analyze/find_symbol, no LLM)
  ├─ _pre_analyze()     Pre-analysis (symbol table + file structure + recall)
  │
  ▼
  LLM chooses tool ──→  TernaryEngine.step()
  │                       ├─ classify()   cognition
  │                       ├─ propagate()  Kleene logic
  │                       ├─ confidence() Bayesian decay
  │                       └─ protect()    safety gate
  │
  ▼
  Execute tool ──→  MemoryStore.add()
                    ├─ keyword extraction
                    ├─ LLM semantic summary
                    └─ time decay
                    │
                    ▼
                    Reflect ──→ continue / done
```

## File Layers

| File | Role | Lines |
|------|------|-------|
| `ternary_engine.py` | Decision engine (Kleene + Bayesian + gating) | 131 |
| `agent_runtime.py` | V3 runtime (SymbolTable / MemoryStore / ProjectGraph) | 492 |
| `agent_tools.py` | Tool layer (12 pure functions) | 170 |
| `agent_policy.san` | Policy config (model / thresholds / rules) | hot-reload |
| `decision.san` | Legacy decision core (to be migrated) | — |
| `agent.san` | Legacy main loop (interactive mode) | — |

## Tools

| Tool | Purpose | Example |
|------|---------|---------|
| `analyze` | File structure | `analyze\|run_agent.py` |
| `find_symbol` | Symbol references | `find_symbol\|main` |
| `read_file` | Read file | `read_file\|run_agent.py\|1\|20` |
| `search_code` | Search code | `search_code\|def main` |
| `replace_in_file` | Single replace | `replace_in_file\|f.py\|old\|new` |
| `replace_all` | Batch replace | `replace_all\|*.py\|old\|new` |
| `write_file` | Write file | `write_file\|path\|content` |
| `list_files` | List files | `list_files\|*.py` |
| `run_test` | Run tests | `run_test\|tests/test_agent.py` |
| `git_diff` | View changes | `git_diff\|` |
| `git_status` | File status | `git_status\|` |

## CLI

```bash
python -X utf8 run_agent.py "task"              # Single-shot (V3)
python -X utf8 run_agent.py "task" --auto        # Autonomous
python -X utf8 run_agent.py "task" --dry-run     # Read-only
python -X utf8 run_agent.py "task" --report      # With report
python -X utf8 run_agent.py --list-tasks          # Task history
```

## Setup

Edit `agent_policy.san`:

```san
设 模型提供商 = "deepseek"
设 模型URL = "https://api.deepseek.com/v1/chat/completions"
设 模型名 = "deepseek-chat"
```

Supports 7 providers: DeepSeek, OpenAI, Qwen, Gemini, Xiaomi MIMO, TokenPlan, Ollama.

## Village Observer

```bash
python -X utf8 run_village_observe.py --days=5
```

NPC autonomous life + LLM-driven dialogue + ternary trust evolution.

## Tests

```bash
python -X utf8 tests/test_agent.py -v          # 31 tests
python -X utf8 tests/test_agent_runtime.py -v  # 27 tests
```

---

**Powered by [ternary-engine](https://pypi.org/project/ternary-engine/)**
