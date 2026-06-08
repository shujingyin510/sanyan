# Ternary Engine

**Tri-State Cognitive Computing Framework** — Kleene logic × Bayesian confidence × safety gating.

```python
from ternary_engine import TernaryEngine

engine = TernaryEngine(max_hesitation=3, min_gain=0.05)

# Step 1: Agent analyzes file
trit, conf, gate, cog = engine.step("analyze", "37 functions, 40 imports")
print(f"[{cog}]→ {engine.trit_display(trit, conf)}")  # [AFFIRM]→ 真 ●●● [0.81]

# Step 2: Replace fails
trit, conf, gate, cog = engine.step("replace_in_file", "未找到")
print(engine.summary())  # 假(0.34)

# Step 3: Fix and retry
trit, conf, gate, cog = engine.step("replace_in_file", "已替换 1 处")
print(engine.trit_display(trit, conf))  # 假 ●●● [0.20]
```

## Quick Start

```bash
pip install ternary-engine
```

## How It Works

```
Event → classify(AFFIRM/NEGATE/UNCERT)
      → map to trit (-1/0/1)
      → Kleene logic propagation (upstream × current)
      → Bayesian confidence decay (upstream_conf × current_conf)
      → protection gating (high risk + uncertain = block)
      → decision
```

## Use Cases

- **AI Agents**: gate LLM tool calls with confidence
- **IoT Sensors**: accumulate unreliable readings before acting
- **Village NPCs**: propagate trust through social networks
- **Risk Assessment**: block high-risk operations when uncertain

## API

```python
TernaryEngine(max_hesitation=3, min_gain=0.05)

engine.step(tool, result, risk='低') → (trit, conf, gate, cog)
engine.classify(tool, result)         → cog_state
engine.propagate(upstream, current)   → propagated_trit
engine.confidence(cog, tool)          → confidence_score
engine.protect(risk, trit, conf)      → gate_action
engine.summary()                      → "真(0.81)"
engine.trit_display(trit, conf)       → "真 ●●● [0.81]"
```

MIT License. Zero dependencies.
