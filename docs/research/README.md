# Research Documents

## Reading Order

### 1. Ternary Gating Report (Main)
**[ternary_gating_report.md](ternary_gating_report.md)**

Full research report on UR ≈ 0.30 degeneration detection:
- Cross-architecture validation (GPT-Neo, GPT-2, Qwen2)
- 1000-prompt benchmarks for each model
- Human blind evaluation
- Ablation study (UR-only vs full trajectory)
- Statistical significance (p < 0.05)
- Induced degeneration experiments
- English abstract at top

### 2. Agent Evolution Report
**[agent_evolution_report.md](agent_evolution_report.md)**

Agent evolution runtime experiments（⚠️ 合成模拟 / synthetic simulation，机制演示，非真实任务实测）:
- 5-layer architecture (Validation → Knowledge → Evolution → Policy → Frozen Core)
- Meta-learning database
- Task taxonomy and conditional optimization
- Knowledge validation and confidence

### 3. Agent Benchmark Report
**[agent_benchmark_report.md](agent_benchmark_report.md)**

Agent safety and honesty evaluation:
- 49 bug injection patterns, 100% detection rate (49/49)
- 100 questions × 5 categories, 3-dimensional scoring
- Truth Calibration Engine
- Logic Audit Engine
- Myth Shield (50 misconception patterns)

---

## Key Result Summary

| File | Core Finding |
|------|-------------|
| ternary_gating_report.md | UR ≈ 0.30 across 4 models, 3 architectures |
| agent_evolution_report.md | Knowledge → Calibration → Selection → Success chain |
| agent_benchmark_report.md | 100% bug detection (49/49), -16.7% cognitive overreach (50.0%→33.3%) |
