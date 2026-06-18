# Sanyan Agent Operations Manual

> [中文版](agent_operations.md)

---

## Quick Start

```bash
# Basic usage
python -X utf8 run_agent.py "your question"

# Interactive mode
python -X utf8 run_agent.py
```

## Core Concepts

### Three-Layer Architecture

```
┌─────────────────────────────────────────────────────┐
│  Layer 5: Knowledge Layer                           │
│  - TaskClassifier / TaskEmbedding / ClusterLearning │
├─────────────────────────────────────────────────────┤
│  Layer 2: Evolution Layer                           │
│  - Ranking / Cost / Budget / UCB                    │
├─────────────────────────────────────────────────────┤
│  Layer 1: Policy Layer                              │
│  - Config / Strategy / Hypothesis                   │
├─────────────────────────────────────────────────────┤
│  Layer 0: Frozen Core                               │
│  - Reviewer / Replay / History / Ternary            │
└─────────────────────────────────────────────────────┘
```

### Ternary Logic

| Layer | Ternary Expression | Description |
|---|---|---|
| Language | TRUE / FALSE / UNKNOWN | Kleene three-valued logic |
| Agent | High confidence / Low confidence / Unknown | Decision gating |
| Knowledge Layer | Trusted knowledge / Weak knowledge / Unknown knowledge | Knowledge reliability |

---

## Tool Reference

### File Operations

| Tool | Parameters | Description |
|------|------------|-------------|
| `read_file` | `path\|start\|end` | Read file content |
| `write_file` | `path\|content` | Write file |
| `replace_in_file` | `path\|old\|new` | Replace in file |
| `replace_all` | `pattern\|old\|new` | Batch replace |
| `list_files` | `pattern` | List files |
| `analyze` | `path` | Analyze file structure |

### Search Tools

| Tool | Parameters | Description |
|------|------------|-------------|
| `search_code` | `keyword` | Search code content |
| `find_symbol` | `name` | Find symbol definition/reference |

### Test Tools

| Tool | Parameters | Description |
|------|------------|-------------|
| `run_test` | `test_file` | Run tests |

### Git Tools

| Tool | Parameters | Description |
|------|------------|-------------|
| `git_diff` | - | View git diff |
| `git_status` | - | View git status |
| `git_stash` | - | Save and revert |
| `git_reset_hard` | - | Hard reset to last commit |
| `git_commit_auto` | `msg` | Auto commit |

### Control Tools

| Tool | Parameters | Description |
|------|------------|-------------|
| `run_shell` | `cmd` | Execute shell command |
| `done` | `answer` | Task complete, output final answer |

### SQLite Operations

| Tool | Parameters | Description |
|------|------------|-------------|
| `sqlite_open` | `path` | Open database connection |
| `sqlite_close` | `path` | Close connection |
| `sqlite_exec` | `path\|sql` | Execute SQL |
| `sqlite_query` | `path\|sql` | Query SQL (returns list) |
| `sqlite_tables` | `path` | List all tables |
| `sqlite_schema` | `path\|table` | Get table structure |
| `sqlite_insert` | `path\|table\|dict` | Insert data |
| `sqlite_update` | `path\|table\|dict\|where` | Update data |
| `sqlite_delete` | `path\|table\|where` | Delete data |
| `sqlite_count` | `path\|table` | Count rows |

---

## CLI Commands

### Basic Commands

```bash
# Interactive mode
python -X utf8 run_agent.py

# Single question
python -X utf8 run_agent.py "your question"

# Execute Sanyan code directly
python -X utf8 run_agent.py "(set x 10)(print(add x 5))"
```

### Rule Management Commands

```bash
# List all rules
python -X utf8 run_agent.py --list-rules

# Approve pending rule
python -X utf8 run_agent.py --approve-rule

# Reject pending rule
python -X utf8 run_agent.py --reject-rule

# Export rules to file
python -X utf8 run_agent.py --export-rules my_rules.tar.gz

# Import rules from file
python -X utf8 run_agent.py --import-rules my_rules.tar.gz
```

### Learning Commands

```bash
# Batch learn project style from git history
python -X utf8 run_agent.py --learn
```

### Model Selection Commands

```bash
# Specify model
python -X utf8 run_agent.py "task" --model deepseek-v4-pro
python -X utf8 run_agent.py "task" --model local/qwen2.5-0.5b
```

### Evolution System Commands

```bash
# Constraint evolution verification
python -X utf8 run_agent.py --evolve

# Self-host verification
python -X utf8 run_agent.py --self-host

# Automated evolution loop
python -X utf8 run_agent.py --auto-evolve --max-cycles 3

# Agent autonomous code modification
python -X utf8 run_agent.py --code-evolve --max-cycles 3

# Reviewed evolution loop
python -X utf8 run_agent.py --review-evolve

# MetaConfig evolution
python -X utf8 run_agent.py --metaconfig

# Evolution validation
python -X utf8 run_agent.py --validate

# Evolution dashboard
python -X utf8 run_agent.py --evo-dashboard
```

### Autonomous Loop Commands

```bash
# File monitoring mode
python -X utf8 agent_loop.py --watch

# Continuous loop mode
python -X utf8 agent_loop.py --continuous

# View stats and health
python -X utf8 agent_loop.py --status
```

---

## Interactive Commands

| Command | Description |
|---------|-------------|
| `/status` | Ternary decision summary |
| `/memory` | Task memory |
| `/dashboard` | Real-time dashboard |
| `/trace` | Decision chain visualization |
| `/perf` | Performance report (Token usage, tool duration) |
| `/experience` | Cross-session experience (tool reliability, failure modes) |
| `/sandbox` | Security sandbox status (audit log) |
| `/shared` | Shared context space |
| `/pipeline` | Tool pipeline list |

---

## LLM Configuration

### Supported Providers

| Provider | Base URL | Default Model |
|----------|----------|---------------|
| DeepSeek | https://api.deepseek.com/v1 | deepseek-v4-pro |
| OpenAI | https://api.openai.com/v1 | gpt-4o |
| Anthropic | https://api.anthropic.com | claude-sonnet-4 |
| Gemini | https://generativelanguage.googleapis.com/v1beta | gemini-2.5-flash |
| Qwen | https://dashscope.aliyuncs.com/compatible-mode/v1 | qwen-max |
| GLM | https://open.bigmodel.cn/api/paas/v4 | glm-4 |
| Moonshot | https://api.moonshot.cn/v1 | moonshot-v1-8k |
| SiliconFlow | https://api.siliconflow.cn/v1 | deepseek-ai/DeepSeek-V3 |
| OpenRouter | https://openrouter.ai/api/v1 | anthropic/claude-sonnet-4 |

### Configuration

```bash
# Environment variables
export SANYAN_API_KEY=sk-xxx
export LLM_PROVIDER=deepseek
export LLM_MODEL=deepseek-v4-pro
```

Or edit `agent_system/sanyan/agent_policy.san`:

```san
set 模型提供商 = "deepseek"
set 模型名 = "deepseek-v4-pro"
```

---

## Architecture

### Five-Layer Architecture

| Layer | Components | Responsibility |
|-------|------------|----------------|
| Layer 5 | Knowledge Validation | Confidence, Cluster, Consistency |
| Layer 4 | Knowledge Layer | MetaLearningDB, TaskEmbedding, ClusterLearning |
| Layer 3 | Evolution Layer | Ranking, Cost, Budget, UCB |
| Layer 2 | Policy Layer | Config, Strategy, Hypothesis |
| Layer 1 | Frozen Core | Reviewer, Replay, History, Ternary |

### Three-Layer Knowledge System

| Layer | Content | Sharing Strategy |
|-------|---------|------------------|
| Global Knowledge | Task Pattern → Strategy Pattern (meta-knowledge) | Share statistical patterns |
| Project Memory | Project-specific experience | Share within project |
| Personal Memory | User preferences/habits | Never share |

### Core Formulas

**Knowledge Confidence:**
```
confidence = sample_factor × 0.4 + sr_factor × 0.3 + consistency_factor × 0.3
```

**Cost-Aware Efficiency:**
```
efficiency = improvement / cost
cost = verification_time + tokens/1000
```

**UCB1 Exploration:**
```
UCB_score = avg_value + c × sqrt(ln(total_plays) / n_plays)
```

---

## Experimental Results

### Causal Chain Closed-Loop

| Agent | Predicted SR | Actual SR | Gap |
|-------|--------------|-----------|-----|
| Baseline | 40.8% | 40.9% | 0.1% |
| Knowledge | 82.9% | 82.5% | 0.4% |
| Knowledge+Conf | 83.0% | 84.5% | 1.5% |

### Knowledge Transfer

| Target Project | Baseline | Config Transfer | Pattern Transfer |
|----------------|----------|-----------------|------------------|
| iot_system | 30.4% | 25.8% (-4.6%) | 58.4% (+24.2%) |
| web_app | 33.8% | 31.0% (-2.8%) | 65.0% (+31.6%) |

### Knowledge Confidence

| Task Type | Samples | Success Rate | Confidence |
|-----------|---------|--------------|------------|
| documentation | 151 | 90.0% | 0.92 |
| analysis | 111 | 84.0% | 0.87 |
| feature | 172 | 80.2% | 0.84 |
| bug_fix | 183 | 74.2% | 0.79 |

---

## Core Insights

> Knowledge → Confidence → Selection → Success

**Ternary Logic Throughout the System:**
- Language: TRUE / FALSE / UNKNOWN
- Agent: High confidence / Low confidence / Unknown
- Knowledge Layer: Trusted knowledge / Weak knowledge / Unknown knowledge

**LLM Knowledge vs Agent Knowledge:**
- LLM = Prior (speculation)
- Agent = Evidence (verified)
