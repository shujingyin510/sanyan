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
  ├─ SemanticCache        P5: semantic cache, zero-cost for repeated tasks
  │
  ▼
  DecompositionEngine    Phase 0: task decomposition → recursive split → per-layer summary
  │  ├─ ComplexityClassifier  complexity grading (simple/medium/complex)
  │  ├─ BoundedContext        bounded context (hard limit 4000 tokens)
  │  └─ ToolDependencyGraph   P1: tool chain legality validation
  │
  ▼
  HypothesisGenerator    Phase 1: multi-hypothesis generation
  │  ├─ LLM generates 5 candidate plans
  │  ├─ P1 dependency graph filter    tool order legality
  │  ├─ P9 capability match filter    task needs vs tool capabilities
  │  └─ P8 diversity dedup            keyword clustering, avoid 5≈1
  │
  ▼
  Tournament             Phase 1: tournament
  │  ├─ P2 parallel early stop    execute 2 steps per hypothesis, kill low-confidence
  │  ├─ classic elimination       confidence gap / step gap / LLM fallback
  │  ├─ P3 failure classification 6 FailureModes + retry strategy
  │  └─ P4 adaptive threshold     auto-tune from history after 50 rounds
  │
  ▼
  Execute best ──→ TernaryEngine.step()
  │                 ├─ classify()   AFFIRM/NEGATE/UNCERT
  │                 ├─ map_trit()   -1/0/1
  │                 ├─ propagate()  Kleene logic
  │                 ├─ confidence() Bayesian decay
  │                 └─ protect()    safety gate
  │
  ▼
  ResourceManager        Phase 2: unified resource management
  │  ├─ tool_reliability()    tool reliability (time decay)
  │  ├─ P7 MetricsCollector   full-chain observability metrics
  │  ├─ P10 CostPredictor     cost prediction (historical data)
  │  └─ P11 ReplayEngine      execution replay + diff comparison
  │
  ▼
  Reflect ──→ continue / fix / done
```

## File Layers

| File | Role | Patches |
|------|------|---------|
| `ternary_engine.py` | Decision engine (Kleene + Bayesian + gating) | — |
| `agent_tool_graph.py` | Tool dependency graph + capability registry + task capability extraction | P1+P9 |
| `agent_decompose.py` | Task decomposition engine + bounded context + complexity classifier | Phase 0 |
| `agent_hypothesis.py` | Multi-hypothesis + diversity control + tournament + failure classification + adaptive threshold | P2+P3+P4+P8 |
| `agent_resource.py` | Unified resource management + semantic cache + observability + cost prediction + replay | P5+P7+P10+P11 |
| `agent_runtime.py` | V5 runtime (full Phase 0/1/2 integration) | — |
| `agent_tools.py` | Tool layer (12 pure functions, zero dependencies) | — |
| `agent_policy.san` | Policy config (model / thresholds / rules, hot-reload) | — |

## Test Coverage

| Module | Test File | Count |
|--------|-----------|-------|
| Agent decisions | `test_agent.py` | 31 |
| AgentRuntime V5 | `test_agent_runtime.py` | 39 |
| Agent V5 new modules | `test_agent_v5.py` | 158 |
| **Total** | | **228** |

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
python -X utf8 tests/test_agent_runtime.py -v  # 39 tests (V5: decomposition + tournament)
python -X utf8 tests/run_all.py                # 46 integration tests
```

---

**Powered by [ternary-engine](https://pypi.org/project/ternary-engine/)**
