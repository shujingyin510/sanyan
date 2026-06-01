# 三值逻辑深度解析


Every real-world system encounters uncertainty. Binary logic (true/false) cannot express it; you either force a choice or build workarounds. Sanyan's three-valued logic (true / maybe / false) follows Kleene strong logic — `maybe` propagates correctly through any expression.

## Case 1: Circuit Simulator — Correctness by Construction

**File:** `examples/circuit_sim.san`

A verification circuit `(A AND B) OR (NOT A)` — 9 possible input combinations. With binary logic, the truth table is:

| A | B | Output |
|---|---|---|
| 0 | 0 | 1 |
| 0 | 1 | 1 |
| 1 | 0 | 0 |
| 1 | 1 | 1 |

In Sanyan, every Kleene triple (`true`, `maybe`, `false` mapped as 1, 0, -1):

| A | B | Output |
|---|---|---|
| true | true | 1 |
| true | false | -1 |
| true | maybe | 0 |
| false | true | 1 |
| false | false | 1 |
| false | maybe | 1 |
| maybe | true | 0 |
| maybe | false | 0 |
| maybe | maybe | 0 |

When A=maybe and B=true, the output is **maybe** — the circuit correctly says "I don't know." A binary language would need custom trit enums and 9-branch pattern matching for the same result. Sanyan's `AND`/`OR`/`NOT` are built-in Kleene operators; the verification circuit is a one-liner `(A AND B) OR (NOT A)` with zero bugs.

10-input circuit: 3^10 = 59049 combinations, all semantically correct by construction.

## Case 2: Data Cleaning Pipeline — NULL Is Not Zero

**File:** `examples/data_cleaning.san`

A user-scoring function checks 4 fields (phone, email, ID, address) marked as `verified=True`, `verified=False`, or `verified=Maybe`. The ternary scorer skips `Maybe` fields and reports the score based only on verified data. When all 4 fields are unverified, it returns **maybe** — "I don't have enough data."

The Python `None` equivalent cannot distinguish "data insufficient" from "score is zero." It returns 0 in the all-unverified case. A downstream system might deny credit, flag for manual review, or silently pass a misleading score — all because `None` is indistinguishable from `0`.

| All 4 fields unverified | Ternary output | Python None output |
|---|---|---|
| Meaning | "data insufficient" | 0 (looks like "poor score") |
| Downstream action | request more data | proceed with misleading value |

Kleene propagation guarantees: `maybe AND maybe = maybe`. Uncertainty composes correctly without special-case `if` checks.

## Case 3: API Health Check — Timeout ≠ Down

**File:** `examples/health_check.san`

Four microservices each report health: `healthy`, `down`, or `timeout`. The ternary aggregator:
- If any service is `down` → system is `down`
- If all services are `healthy` → system is `healthy`
- If some are `timeout` (none `down`) → system is **maybe** — "partially uncertain"

A binary system (up/down) must classify timeout as down, triggering unnecessary alerts. The ternary system preserves the distinction: timeout is not failure — it's uncertainty.

| Scenario | Ternary | Binary |
|---|---|---|
| All healthy | healthy | up |
| One timeout, rest healthy | maybe | down (false alert) |
| One down | down | down |

The aggregation logic emerges naturally from Kleene operators without custom state machines.

## Case 4: Game NPC Decision — Hesitation Is a Legitimate Behavior

**File:** `examples/npc_decision.san`

An NPC decides between `attack` and `flee` based on distance, threat level, and HP. When no condition is decisive, the ternary NPC returns **maybe** — the player sees hesitation (patrol, look around, random movement). This is a *stable, persistent behavior*, not a transition state.

A binary NPC (same 3 inputs, no extra state variables) has nowhere to put "uncertain." It must guess randomly. The NPC jitters between attack and flee frame-to-frame, which players perceive as buggy behavior.

| Condition met | Ternary | Binary (no extra vars) |
|---|---|---|
| Distance<3 & threat>0.8 | flee | flee |
| HP<0.3 | flee | flee |
| Distance>10 & threat<0.3 | attack | attack |
| None of the above | **maybe** (hesitate) | random (jitter) |

To achieve consistent hesitation in binary, you need at least 1 external state variable (hesitation timer, suspicion counter, etc.). The ternary approach needs zero — `maybe` is a first-class value.

## Summary

| Criterion | Binary | Ternary (Sanyan) |
|---|---|---|
| Values | true, false | true, maybe, false |
| Uncertainty handling | suppress or hack | native propagation |
| Extra state variables | ≥1 for hesitation-like behavior | 0 |
| Data pipeline safety | None/NaN poisoning | maybe stops the chain |
| API health aggregation | up/down forces false alerts | timeout/down distinction |
| Truth tables | 2^n entries | 3^n entries (all correct) |

Three states are the minimum viable model for expressing uncertainty. Sanyan makes `maybe` a first-class citizen — not a library, not a convention, but a language primitive that propagates correctly through every operator.


---


## 概述

本文档通过 3 个完整 IoT 案例，对比三言（三值逻辑）与 Python/C（二值逻辑）的代码量、可读性和实际优势。

---

## 案例 1：传感器融合

**场景**：工业环境监测系统，融合温度/湿度/气体传感器。传感器可能正常、故障或离线。

### 代码量对比

| 语言 | 文件 | 行数 | 额外定义 |
|------|------|------|----------|
| 三言 | `sensor_fusion.san` | ~160 | 0（内置三值类型和运算符） |
| Python | `sensor_fusion.py` | ~150 | `SensorState` 枚举、`fuse_states()` 函数 |
| C | `sensor_fusion.c` | ~170 | `tristate_t` 枚举、`tri_and()`/`tri_or()`/`fuse_states()` 函数 |

### 核心差异

**三言** — 内置三值运算符：
```
设 整体正常 = (温度状态 且 湿度状态) 且 气体状态
```

**Python** — 需要手写融合逻辑：
```python
def fuse_sensor_states(states):
    has_fault = any(s == SensorState.FAULT for s in states)
    all_normal = all(s == SensorState.NORMAL for s in states)
    if has_fault: return SensorState.FAULT
    if all_normal: return SensorState.NORMAL
    return SensorState.OFFLINE
```

**C** — 更多样板代码：
```c
tristate_t tri_and(tristate_t a, tristate_t b) {
    if (a == STATE_FALSE || b == STATE_FALSE) return STATE_FALSE;
    if (a == STATE_TRUE && b == STATE_TRUE) return STATE_TRUE;
    return STATE_MAYBE;
}
```

### 可读性评分

| 维度 | 三言 | Python | C |
|------|------|--------|---|
| 类型定义 | ⭐⭐⭐ 无需 | ⭐⭐ 需要 Enum | ⭐ 需要 enum + typedef |
| 逻辑表达 | ⭐⭐⭐ `且`/`或`/`非` | ⭐⭐ 需要函数包装 | ⭐ 需要函数 + switch |
| 不确定性传播 | ⭐⭐⭐ 天然传播 | ⭐⭐ 需要显式检查 | ⭐ 需要显式检查 |
| 代码简洁度 | ⭐⭐⭐ | ⭐⭐ | ⭐ |

---

## 案例 2：容错控制

**场景**：工业水泵控制系统，含压力/流量/温度传感器。传感器失效时需安全降级。

### 代码量对比

| 语言 | 文件 | 行数 | 额外定义 |
|------|------|------|----------|
| 三言 | `fault_tolerant_control.san` | ~140 | 0 |
| Python | （参考 sensor_fusion.py 模式） | ~130 | 枚举 + 融合函数 |

### 核心优势

**三值逻辑的关键洞察**：传感器离线 ≠ 传感器故障

```
// 传感器故障→不确定（可能读数正常，可能异常）
若 (等于(压力, 假)) { 返回(可能) }
// 传感器离线→不确定
若 (等于(压力, 可能)) { 返回(可能) }
```

在二值逻辑中，离线和故障通常被合并为同一个 `None`/`null`，丢失了语义信息。

### 降级策略

三值逻辑自然推导降级策略：
```
// 不确定状态：至少一个传感器离线
// 策略：降级运行，降低泵速，增加检查频率
返回(字典("动作", "降级运行", "原因", "部分传感器离线，保守运行"))
```

---

## 案例 3：IoT 设备状态机

**场景**：智能门锁设备生命周期管理。设备状态可能不确定（网络抖动、电池低但未关机）。

### 代码量对比

| 语言 | 文件 | 行数 | 额外定义 |
|------|------|------|----------|
| 三言 | `iot_state_machine.san` | ~170 | 0 |
| Python | `iot_state_machine.py` | ~140 | `TriState` 枚举、`tri_and()`/`tri_or()` |

### 核心差异

**状态转换条件** — 三值逻辑天然支持：
```
定义 应该重启(当前状态, 电池, 网络) {
    // 只有在确认故障且电池充足时才重启
    若 (等于(当前状态, 假) 且 等于(电池, 真)) { 返回(真) }
    // 状态不确定且网络可能恢复时，等待
    若 (等于(当前状态, 可能) 且 等于(网络, 可能)) { 返回(可能) }
    返回(假)
}
```

Python 需要手写 `tri_and` 函数：
```python
def tri_and(a, b):
    if a == TriState.FALSE or b == TriState.FALSE: return TriState.FALSE
    if a == TriState.TRUE and b == TriState.TRUE: return TriState.TRUE
    return TriState.MAYBE
```

---

## 总体对比

### 代码量统计

| 案例 | 三言 | Python | C |
|------|------|--------|---|
| 传感器融合 | 160 行 | 150 行 | 170 行 |
| 容错控制 | 140 行 | ~130 行 | ~150 行 |
| 状态机 | 170 行 | 140 行 | ~160 行 |
| **总计** | **470 行** | **~420 行** | **~480 行** |

三言代码量与 Python/C 相当，但**无需额外类型定义和工具函数**。

### 三值逻辑的实际优势

1. **零样板代码**：`真`/`假`/`可能` 是语言内置类型，`且`/`或`/`非` 是内置运算符
2. **语义丰富**：`可能`（不确定）≠ `假`（确认故障），保留了更多信息
3. **天然传播**：`a 且 b` 中任一为 `可能`，结果自动为 `可能`，无需显式检查
4. **安全降级**：`可能` 状态自然推导降级策略，而非错误地假设安全或危险
5. **代码可读性**：`若 (状态 且 安全)` 比 `if state == OK and safe == True` 更接近自然语言

### 适用场景

| 场景 | 三值逻辑优势 | 二值逻辑劣势 |
|------|-------------|-------------|
| 传感器离线 | `可能` 状态 | `None` 丢失语义 |
| 网络抖动 | `可能` 状态 | 需要额外枚举 |
| 电池低电量 | `可能` 状态 | 需要阈值判断 |
| 设备初始化中 | `可能` 状态 | 需要状态标志 |
| 多源数据融合 | `且`/`或` 自动传播 | 需要循环 + 显式逻辑 |

---

## 文件清单

| 文件 | 说明 |
|------|------|
| `examples/sensor_fusion.san` | 三言：传感器融合 |
| `examples/sensor_fusion.py` | Python：传感器融合 |
| `examples/sensor_fusion.c` | C：传感器融合 |
| `examples/fault_tolerant_control.san` | 三言：容错控制 |
| `examples/iot_state_machine.san` | 三言：IoT 状态机 |
| `examples/iot_state_machine.py` | Python：IoT 状态机 |

