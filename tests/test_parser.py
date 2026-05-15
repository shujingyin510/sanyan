"""糖语法解析器回归测试 — 验证 AST 结构正确性"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

from sugar import SugarConverter

tests = [
    # (描述, 代码, AST校验函数)
    # 注意：糖语法解析器输出中文关键字和字符串字面量，不转换内部名
    ("变量赋值", "设 x = 10",
     lambda ast: ast[0] == 'set' and ast[1] == 'x' and ast[2] == '10'),
    ("连续赋值", "x = 5",
     lambda ast: ast[0] == 'set' and ast[1] == 'x' and ast[2] == '5'),
    ("输出", "输出(x)",
     lambda ast: ast[0] == 'print' and ast[1] == 'x'),
    ("条件分支", "若 (x > 5) { 输出(x) }",
     lambda ast: ast[0] == 'if' and ast[1][0] == 'gt' and ast[2][0] == 'print'),
    ("否则若", "若 (x > 5) { 输出(1) } 再若 (x < 0) { 输出(-1) } 否则 { 输出(0) }",
     lambda ast: ast[0] == 'if' and len(ast) == 4 and ast[3][0] == 'if'),
    ("循环", "循环 (x < 10) { x = x + 1 }",
     lambda ast: ast[0] == 'loop' and ast[1][0] == 'lt' and ast[2][0] == 'set'),
    ("遍历", "遍历 i 从 1 到 10 { 输出(i) }",
     lambda ast: ast[0] == 'for' and ast[1] == 'i' and ast[2] == '1' and ast[3] == '10' and ast[4][0] == 'print'),
    ("函数定义", "定义 平方 (x) { x * x }",
     lambda ast: ast[0] == 'fn' and ast[1] == '平方' and ast[2] == ['x']),
    ("匿名函数", "设 加倍 = 函数(x) { x * 2 }",
     lambda ast: ast[0] == 'set' and ast[2][0] == 'lambda' and ast[2][1] == ['x']),
    ("字符串插值", "输出(模板{温度: ${x}°C})",
     lambda ast: ast[0] == 'print' and ast[1][0] == 'concat'),
    ("三态分支判", "判 x { 真 { 输出(1) } 可能 { 输出(0) } 假 { 输出(-1) } }",
     lambda ast: ast[0] == 'judge' and ast[1] == 'x'),
    ("异常处理", "尝试 { 设 a = 读文件(\"no.txt\") } 捕获 (e) { 输出(e) }",
     lambda ast: ast[0] == 'try' and ast[2][0] == '捕获'),
    ("前缀读传感器", "设 y = 读(人体)",
     lambda ast: ast[0] == 'set' and ast[2][0] == 'read'),
    ("前缀非", "输出(非 真)",
     lambda ast: ast[0] == 'print' and ast[1][0] == 'not'),
    ("列表字面量", "设 lst = 列表(1, 2, 3)",
     lambda ast: ast[0] == 'set' and ast[2][0] == '列表'),
    ("字典", "设 d = 字典(\"a\", 1, \"b\", 2)",
     lambda ast: ast[0] == 'set' and ast[2][0] == '字典'),
    ("数组", "设 arr = 数组(5, 0)",
     lambda ast: ast[0] == 'set' and ast[2][0] == '数组'),
    ("容器索引", "输出(lst(0))",
     lambda ast: ast[0] == 'print' and ast[1][0] == 'lst'),
    ("高阶函数映射", "映射(函数(x) { x * 2 }, 列表(1,2))",
     lambda ast: ast[0] == '映射' and ast[1][0] == 'lambda'),
    ("连接", "输出(连接(\"a\", \"b\"))",
     lambda ast: ast[0] == 'print' and ast[1][0] == '连接'),
    ("全角符号", "设 a＝5；输出（a＋2）",
     lambda ast: ast[0] == 'do' and ast[1][0] == 'set'),
    ("全角字符串内含句号", "输出(\"测试。\")",
     lambda ast: ast[0] == 'print' and isinstance(ast[1], str) and '。' in ast[1]),
]

total = 0
passed = 0
failed = []

for desc, code, validator in tests:
    total += 1
    try:
        ast = SugarConverter.convert(code)
        if isinstance(ast, list) and len(ast) > 0 and validator(ast):
            passed += 1
            print(f"✓ {desc}")
        else:
            failed.append((desc, code, f"AST 结构校验失败: {ast}"))
            print(f"✗ {desc} - AST: {ast}")
    except Exception as e:
        failed.append((desc, code, str(e)))
        print(f"✗ {desc} - 错误: {e}")

print(f"\n{passed}/{total} 通过")
if failed:
    print("\n失败的测试:")
    for desc, code, err in failed:
        print(f"  [{desc}] {code}\n    -> {err}")
