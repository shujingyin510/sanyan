from evaluator import SanyanEvaluator

env = SanyanEvaluator()

# 测试输出命令
result = env.eval(['print', 'Hello'])
print("结果1:", result)

# 测试赋值
result = env.eval(['set', 'a', 1])
print("结果2:", result, type(result))