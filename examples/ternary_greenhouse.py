"""
三态温室决策 — TernaryEngine IoT 应用示例
python -X utf8 examples/ternary_greenhouse.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import random

from ternary_engine import TernaryEngine

print('=== 三态温室决策 ===\n')
print('TernaryEngine: Kleene 传播 × 贝叶斯置信度 × 保护门控\n')

# 模拟传感器读数：返回 (值, 是否可靠)
sensors = {
    '温度': lambda: (random.randint(15, 35), random.random() > 0.7),
    '湿度': lambda: (random.randint(30, 95), random.random() > 0.9),
    '光照': lambda: (random.randint(100, 1000), True),
    '人体': lambda: (random.choice([0, 1]), random.random() > 0.5),
}

engine = TernaryEngine(max_hesitation=3, min_gain=0.01)
engine.TOOL_CONFIDENCE['传感器读数'] = 0.95  # 传感器高可靠

for hour in range(6, 22, 2):
    results = {}
    for name, read_fn in sensors.items():
        val, reliable = read_fn()
        results[name] = (val, reliable)

    # 三态决策：每轮评估所有传感器
    print(f'\n{hour:02d}:00 —', ', '.join(f'{k}:{v[0]}{"?" if not v[1] else ""}' for k, v in results.items()))
    trit, conf, gate, cog = engine.step(
        '传感器读数',
        str(results),
        risk='中' if any(not v[1] for v in results.values()) else '低',
    )

    # 决策
    t = results['温度'][0]
    h = results['湿度'][0]
    if gate['action'] == 'block':
        print(f'  [门控] {gate["reason"]}')
    elif trit == 1 and conf > 0.4:
        if t > 30:
            print(f'  决策: 开启通风 ({t}°C)')
        elif t < 18:
            print(f'  决策: 开启暖气 ({t}°C)')
        else:
            print('  决策: 维持正常')
    else:
        print(f'  决策: 人工确认 (置信度 {conf:.2f})')

print(f'\n=== 最终三态: {engine.trit_display(*engine.history[-1]) if engine.history else "无"} ===')
