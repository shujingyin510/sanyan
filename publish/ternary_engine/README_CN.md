# 三元认知引擎

**三态认知计算框架** — Kleene 逻辑 × 贝叶斯置信度 × 保护门控。

处理现实世界的不确定性：传感器会失灵、用户会犹豫、代码会写错。三元引擎用"可能"来表达——而不是强行归为对错。

```python
from ternary_engine import TernaryEngine

engine = TernaryEngine(max_hesitation=3, min_gain=0.05)

# 步骤 1：Agent 分析文件
trit, conf, gate, cog = engine.step("analyze", "37个函数, 40个导入")
print(f"[{cog}]→ {engine.trit_display(trit, conf)}")  # [AFFIRM]→ 真 ●●● [0.81]

# 步骤 2：替换失败
trit, conf, gate, cog = engine.step("replace_in_file", "未找到")
print(engine.summary())  # 假(0.34)

# 步骤 3：修复重试
trit, conf, gate, cog = engine.step("replace_in_file", "已替换 1 处")
print(engine.trit_display(trit, conf))  # 假 ●●● [0.20]
```

## 快速开始

```bash
pip install ternary-engine
```

## 原理

```
事件 → 认知分类(确信/拒绝/不确定)
     → 三态映射(-1/0/1)
     → Kleene 逻辑传播 (上游 × 当前)
     → 贝叶斯置信度衰减 (上游置信度 × 当前置信度)
     → 保护门控 (高风险 + 不确定 = 拦截)
     → 决策
```

## 应用场景

- **AI Agent**：用置信度门控 LLM 工具调用
- **IoT 传感器**：积累不可靠读数后才行动
- **NPC 信任网络**：在社交网络中传播信任
- **风险评估**：不确定时拦截高风险操作

## API

```python
TernaryEngine(max_hesitation=3, min_gain=0.05)

engine.step(tool, result, risk='低') → (trit, conf, gate, cog)
engine.classify(tool, result)         → 认知态
engine.propagate(上游, 当前)          → 传播后三态值
engine.confidence(cog, tool)          → 置信度
engine.protect(风险, trit, conf)      → 门控动作
engine.summary()                      → "真(0.81)"
engine.trit_display(trit, conf)       → "真 ●●● [0.81]"
```

MIT 协议。零依赖。
