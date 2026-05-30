"""
sensor_fusion.py — 二值逻辑传感器融合（对比实现）
功能与 sensor_fusion.san 相同，但用 Python 的 None/枚举处理不确定性
展示二值逻辑需要多少额外代码来处理三值逻辑天然支持的场景
"""
import random
from enum import Enum
from typing import Optional, Tuple

class SensorState(Enum):
    NORMAL = "normal"
    FAULT = "fault"
    OFFLINE = "offline"

def simulate_sensor(name: str, fault_rate: int) -> SensorState:
    r = random.randint(1, 100)
    if r <= fault_rate:
        return SensorState.FAULT
    if r <= fault_rate + 10:
        return SensorState.OFFLINE
    return SensorState.NORMAL

def read_temperature() -> Tuple[SensorState, Optional[int]]:
    state = simulate_sensor("温度", 15)
    if state == SensorState.NORMAL:
        return (state, random.randint(18, 35))
    elif state == SensorState.OFFLINE:
        return (state, None)  # 离线返回 None
    else:
        return (state, None)  # 故障返回 None

def read_humidity() -> Tuple[SensorState, Optional[int]]:
    state = simulate_sensor("湿度", 10)
    if state == SensorState.NORMAL:
        return (state, random.randint(30, 80))
    return (state, None)

def read_gas() -> Tuple[SensorState, Optional[int]]:
    state = simulate_sensor("气体", 20)
    if state == SensorState.NORMAL:
        return (state, random.randint(0, 500))
    return (state, None)

def fuse_sensor_states(states: list[SensorState]) -> SensorState:
    """融合多个传感器状态 — 需要显式枚举处理"""
    has_fault = any(s == SensorState.FAULT for s in states)
    has_offline = any(s == SensorState.OFFLINE for s in states)
    all_normal = all(s == SensorState.NORMAL for s in states)

    if has_fault:
        return SensorState.FAULT
    if all_normal:
        return SensorState.NORMAL
    return SensorState.OFFLINE  # 至少一个离线

def temperature_safe(temp: Optional[int]) -> SensorState:
    if temp is None:
        return SensorState.OFFLINE
    if temp > 40 or temp < 10:
        return SensorState.FAULT
    return SensorState.NORMAL

def humidity_safe(humid: Optional[int]) -> SensorState:
    if humid is None:
        return SensorState.OFFLINE
    if humid > 90 or humid < 20:
        return SensorState.FAULT
    return SensorState.NORMAL

def gas_safe(gas: Optional[int]) -> SensorState:
    if gas is None:
        return SensorState.OFFLINE
    if gas > 400:
        return SensorState.FAULT
    if gas > 200:
        return SensorState.OFFLINE  # 警告
    return SensorState.NORMAL

def environment_decision(overall: SensorState, temp, humid, gas) -> str:
    if overall == SensorState.FAULT:
        print(f"🚨 警报：传感器故障或环境危险！")
        print(f"  温度: {temp}  湿度: {humid}  气体: {gas}")
        return "紧急停机"
    elif overall == SensorState.OFFLINE:
        print("⚠️ 警告：部分传感器离线，降级运行")
        if temp is not None and temp > 35:
            return "降级-开启风扇"
        return "降级-维持现状"
    else:
        print("✅ 环境正常，全速运行")
        if temp is not None and temp > 30:
            return "开启空调"
        if humid is not None and humid < 40:
            return "开启加湿器"
        return "维持现状"

def main():
    print("═" * 43)
    print("  二值逻辑传感器融合系统 v1.0 (Python)")
    print("═" * 43)
    print()

    count_normal = 0
    count_uncertain = 0
    count_abnormal = 0

    for round_num in range(1, 11):
        print(f"--- 第 {round_num} 轮检测 ---")

        temp_state, temp_val = read_temperature()
        humid_state, humid_val = read_humidity()
        gas_state, gas_val = read_gas()

        temp_safe = temperature_safe(temp_val)
        humid_safe = humidity_safe(humid_val)
        gas_safe_val = gas_safe(gas_val)

        sensor_fusion = fuse_sensor_states([temp_state, humid_state, gas_state])
        safety_fusion = fuse_sensor_states([temp_safe, humid_safe, gas_safe_val])

        # 最终状态：需要显式处理两个枚举的组合
        if sensor_fusion == SensorState.FAULT or safety_fusion == SensorState.FAULT:
            final = SensorState.FAULT
        elif sensor_fusion == SensorState.NORMAL and safety_fusion == SensorState.NORMAL:
            final = SensorState.NORMAL
        else:
            final = SensorState.OFFLINE

        print(f"  传感器: 温度={temp_state.value} 湿度={humid_state.value} "
              f"气体={gas_state.value} → 融合={sensor_fusion.value}")
        print(f"  安全性: 温度={temp_safe.value} 湿度={humid_safe.value} "
              f"气体={gas_safe_val.value} → 融合={safety_fusion.value}")

        decision = environment_decision(final, temp_val, humid_val, gas_val)
        print(f"  决策: {decision}")
        print()

        if final == SensorState.NORMAL:
            count_normal += 1
        elif final == SensorState.OFFLINE:
            count_uncertain += 1
        else:
            count_abnormal += 1

    print("═" * 43)
    print("  统计汇总")
    print("═" * 43)
    print(f"  正常: {count_normal} 轮")
    print(f"  不确定: {count_uncertain} 轮")
    print(f"  异常: {count_abnormal} 轮")
    print()
    print("二值逻辑需要：Enum 类定义、None 检查、显式状态组合")
    print("三值逻辑只需：真/假/可能 + 且/或/非 运算符")

if __name__ == "__main__":
    main()
