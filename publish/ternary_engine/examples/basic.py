"""三元引擎 5 行示例 — pip install ternary-engine 后直接运行"""

from ternary_engine import TernaryEngine

engine = TernaryEngine()

# 模拟 Agent 三步：成功 → 失败 → 修复
for i, (tool, result) in enumerate([('analyze', '37函数'), ('replace', '未找到'), ('replace', '已替换 1 处')]):
    trit, conf, gate, cog = engine.step(tool, result)
    print(f'[{i + 1}] [{cog}]→ {engine.trit_display(trit, conf)}  {engine.summary()}')
