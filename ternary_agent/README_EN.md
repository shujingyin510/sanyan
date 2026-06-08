# Agent Readable Decision DSL

[中文](README.md)

> LLM Agent powered by [ternary-engine](https://pypi.org/project/ternary-engine/) — every tool call carries confidence, safety gates block when uncertain.

---

## Quick Start

```bash
set SANYAN_API_KEY=sk-your-key

# Single question
python -X utf8 run_agent.py "analyze run_agent.py"
# → ⚠ >50行: init_evaluator, run_once, main, _analyze_file

# Autonomous (read → modify → test → fix → loop)
python -X utf8 run_agent.py "fix _test_verify.py so tests pass" --auto
# → [AFFIRM]→真 ●●● [0.81] → fixed

# Dry-run (preview only)
python -X utf8 run_agent.py "replace v0.3 with v0.4" --dry-run
# → [干跑] would replace in AGENTS.md
```

---

## Architecture

```
User Task
  │
  ├─ _force_tool()        Smart first round (analyze/find_symbol, skip LLM)
  ├─ _pre_analyze()       Pre-analysis (file structure + symbols + recall)
  │
  ▼
  LLM chooses tool ──→ TernaryEngine.step()
  │                      ├─ classify()   AFFIRM/NEGATE/UNCERT
  │                      ├─ map_trit()   -1/0/1
  │                      ├─ propagate()  Kleene logic
  │                      ├─ confidence() Bayesian decay
  │                      └─ protect()    safety gate
  │
  ▼
  Execute ──→ MemoryStore (keywords + LLM summary + time decay)
  │
  ▼
  Reflect ──→ continue / fix / done
```

## File Layers

| File | Role | Lines |
|------|------|-------|
| `ternary_engine.py` | Decision engine (Kleene + Bayesian + gating) | 131 |
| `agent_runtime.py` | V3 runtime (SymbolTable / MemoryStore / ProjectGraph) | 492 |
| `agent_tools.py` | Tool layer (12 pure functions, zero dependencies) | 170 |
| `agent_policy.san` | Policy config (model / thresholds / rules, hot-reload) | 194 |
| `decision.san` | Legacy decision core (to be migrated) | 185 |
| `agent.san` | Legacy main loop (interactive mode) | 1242 |

## Tools

| Tool | Purpose | Format |
|------|---------|--------|
| `analyze` | File structure (functions/imports/lines) | `file_path` |
| `find_symbol` | Symbol definition + references | `symbol_name` |
| `read_file` | Read file with line range | `path\|start\|end` |
| `search_code` | Global keyword search | `keyword` |
| `replace_in_file` | Single file replace | `path\|old\|new` |
| `replace_all` | Batch cross-file replace | `pattern\|old\|new` |
| `write_file` | Write file | `path\|content` |
| `list_files` | List files recursively | `pattern` |
| `run_test` | Run pytest | `test_path` |
| `git_diff` | Git diff --stat | (none) |
| `git_status` | Git status --short | (none) |

## CLI

```bash
python -X utf8 run_agent.py "task"              # Single-shot (V3 engine)
python -X utf8 run_agent.py                      # Interactive (legacy)
python -X utf8 run_agent.py "task" --auto        # Autonomous
python -X utf8 run_agent.py "task" --dry-run     # Read-only preview
python -X utf8 run_agent.py "task" --report      # Task report
python -X utf8 run_agent.py "task" --rounds 5    # Max rounds
python -X utf8 run_agent.py --list-tasks          # Task history
```

## Setup

```san
设 模型提供商 = "deepseek"
设 超时秒数 = 60
设 最大轮次 = 10
```

Supports 7 providers: DeepSeek, OpenAI, Qwen, Gemini, MIMO, TokenPlan, Ollama.

## Ternary Display

```
[AFFIRM]→真 ●●● [0.81]     ← cognition → trit-value confidence
[NEGATE]→假 ○○○ [0.34]     ← failure downgrades
[UNCERT]→可能 ◐◐◐ [0.15]  ← triggers hesitation counter
```

## Village Observer

```bash
python -X utf8 run_village_observe.py --days=5
```

NPC life + LLM dialogue + TernaryEngine trust tracking + SVG charts.

## Tests

```bash
python -X utf8 tests/test_agent.py -v          # 31 tests
python -X utf8 tests/test_agent_runtime.py -v  # 27 tests
```

---

**Powered by [ternary-engine](https://pypi.org/project/ternary-engine/)**
