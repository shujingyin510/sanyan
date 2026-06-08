# 三元认知引擎 Ternary Engine

[![PyPI](https://img.shields.io/pypi/v/ternary-engine)](https://pypi.org/project/ternary-engine/)
[![Python](https://img.shields.io/pypi/pyversions/ternary-engine)](https://pypi.org/project/ternary-engine/)
[![License](https://img.shields.io/pypi/l/ternary-engine)](https://pypi.org/project/ternary-engine/)

[English](#english) | [中文](#三元认知引擎-ternary-engine)

**三态认知计算框架** — 131 行，0 依赖，MIT 协议。

现实世界不是 0 和 1。三元引擎用 `真 ●●● [0.81]` / `可能 ◐◐◐ [0.45]` / `假 ○○○ [0.12]` 来表达不确定性——延迟决策直到证据充分。

## 一行接入

```python
from ternary_engine import TernaryEngine
engine = TernaryEngine()
trit, conf, gate, cog = engine.step("事件名", "结果")
print(engine.trit_display(trit, conf))  # 真 ●●● [0.81]
```

## 三步必看

```python
from ternary_engine import TernaryEngine

engine = TernaryEngine(max_hesitation=3, min_gain=0.05)

# 步骤 1：Agent 分析文件成功
trit, conf, gate, cog = engine.step("analyze", "37个函数, 40个导入")
print(f"[{cog}]→ {engine.trit_display(trit, conf)}")  # [AFFIRM]→ 真 ●●● [0.81]

# 步骤 2：替换失败，置信度下降
trit, conf, gate, cog = engine.step("replace_in_file", "未找到")
print(engine.summary())  # 假(0.34)

# 步骤 3：修复重试成功
trit, conf, gate, cog = engine.step("replace_in_file", "已替换 1 处")
print(engine.summary())  # 假(0.20)
```

更多示例：`python publish/ternary_engine/examples/basic.py`

## 三个真实用例

| 场景 | 怎么用 | 代码 |
|------|--------|------|
| **AI Agent 门控** | 每步工具调用后 `engine.step()`，门控拦截高风险操作 | [`agent_runtime.py`](https://github.com/shujingyin510/sanyan/blob/main/agent_runtime.py) |
| **村庄 NPC 信任** | 每次对话后追踪信任演化，每人独立三态历史 | [`run_village_observe.py`](https://github.com/shujingyin510/sanyan/blob/main/run_village_observe.py) |
| **IoT 传感器** | 积累不可靠读数，置信度够了才行动 | [`ternary_greenhouse.py`](https://github.com/shujingyin510/sanyan/blob/main/examples/ternary_greenhouse.py) |

## 原理

```
事件 → classify(确信/拒绝/不确定)
     → map_trit(-1/0/1)
     → propagate() Kleene 逻辑 (上游=-1→永远-1)
     → confidence() 贝叶斯衰减 (上游 × 当前)
     → protect() 门控 (高风险+不确定=拦截)
     → 决策
```

## API

```python
engine.step(tool, result, risk='低') → (trit, conf, gate, cog)
engine.classify(tool, result)         → 认知态
engine.propagate(上游, 当前)          → 传播值
engine.confidence(cog, tool)          → 置信度
engine.protect(风险, trit, conf)      → 门控动作
engine.summary()                      → "真(0.81)"
engine.trit_display(trit, conf)       → "真 ●●● [0.81]"
```

---

## English

**Tri-State Cognitive Computing Framework** — 131 lines, zero dependencies, MIT.

```bash
pip install ternary-engine
```

```python
from ternary_engine import TernaryEngine
engine = TernaryEngine()
trit, conf, gate, cog = engine.step("analyze", "37 functions, 40 imports")
print(engine.trit_display(trit, conf))  # 真 ●●● [0.81]
```

### Use Cases

| Scenario | How |
|----------|-----|
| AI Agent | Gate LLM tool calls with confidence |
| NPC Trust | Track character trust with personal ternary history |
| IoT Sensors | Accumulate unreliable readings, act when confident |

[GitHub](https://github.com/shujingyin510/sanyan)
