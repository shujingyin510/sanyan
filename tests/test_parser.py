"""糖语法解析器回归测试"""
import sys
sys.path.insert(0, '.')
from sugar import SugarConverter

tests = [
    # (描述, 代码)
    ("变量赋值", "设 x = 10"),
    ("连续赋值", "x = 5"),
    ("输出", "输出(x)"),
    ("条件分支", "若 (x > 5) { 输出(x) }"),
    ("否则若", "若 (x > 5) { 输出(1) } 再若 (x < 0) { 输出(-1) } 否则 { 输出(0) }"),
    ("循环", "循环 (x < 10) { x = x + 1 }"),
    ("遍历", "遍历 i 从 1 到 10 { 输出(i) }"),
    ("函数定义", "定义 平方 (x) { x * x }"),
    ("匿名函数", "设 加倍 = 函数(x) { x * 2 }"),
    ("字符串插值", "输出(模板{温度: ${x}°C})"),
    ("三态分支判", "判 x { 真 { 输出(1) } 可能 { 输出(0) } 假 { 输出(-1) } }"),
    ("异常处理", "尝试 { 设 a = 读文件(\"no.txt\") } 捕获 (e) { 输出(e) }"),
    ("前缀读传感器（无括号）", "设 y = 读 人体"),
    ("前缀读传感器（有括号）", "设 y = 读(人体)"),
    ("前缀非", "输出(非 真)"),
    ("前缀取位", "输出(取位 123)"),
    ("列表字面量", "设 lst = 列表(1, 2, 3)"),
    ("字典", "设 d = 字典(\"a\", 1, \"b\", 2)"),
    ("数组", "设 arr = 数组(5, 0)"),
    ("容器索引", "输出(lst(0))"),
    ("高阶函数映射", "映射(函数(x) { x * 2 }, 列表(1,2))"),
    ("连接", "输出(连接(\"a\", \"b\"))"),
    ("全角符号", "设 a＝5；输出（a＋2）"),
    ("全角字符串内含句号", "输出(\"测试。\")"),
]

total = 0
passed = 0
failed = []

for desc, code in tests:
    total += 1
    try:
        ast = SugarConverter.convert(code)
        # 简单结构检查：AST 应为列表，且第一个元素是内部标识符或列表
        if isinstance(ast, list) and len(ast) > 0:
            passed += 1
            print(f"✓ {desc}")
        else:
            failed.append((desc, code, "空 AST 或格式错误"))
            print(f"✗ {desc} - AST: {ast}")
    except Exception as e:
        failed.append((desc, code, str(e)))
        print(f"✗ {desc} - 错误: {e}")

print(f"\n{passed}/{total} 通过")
if failed:
    print("\n失败的测试:")
    for desc, code, err in failed:
        print(f"  [{desc}] {code}\n    -> {err}")