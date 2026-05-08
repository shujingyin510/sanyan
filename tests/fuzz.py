"""三言模糊测试：只测试糖语法解析器，不执行代码"""
import sys
import os
import random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sugar import SugarConverter

WORDS = [
    "设", "若", "循环", "遍历", "定义", "函数", "输出",
    "真", "假", "可能", "开", "关", "守",
    "灯", "风扇", "加热", "人体", "光线", "温度",
    "x", "y", "z", "a", "b", "c"
]

def random_var():
    return random.choice(WORDS)

def random_num():
    return str(random.randint(0, 100))

def random_expr(depth=0):
    if depth > 2 or random.random() < 0.3:
        if random.random() < 0.5:
            return random_var()
        else:
            return random_num()
    left = random_expr(depth + 1)
    right = random_expr(depth + 1)
    op = random.choice(["+", "-", "*", "/", ">", "<", "==", "且", "或"])
    return f"({left} {op} {right})"

def random_statement(depth=0):
    if depth > 4:
        return f"输出({random_num()})"
    kind = random.choice(["set", "print", "if", "loop", "for"])
    if kind == "set":
        return f"设 {random_var()} = {random_expr()}"
    elif kind == "print":
        return f"输出({random_expr()})"
    elif kind == "if":
        cond = random_expr()
        body = random_block(depth + 1)
        return f"若 ({cond}) {{ {body} }}"
    elif kind == "loop":
        cond = random_expr()
        body = random_block(depth + 1)
        return f"循环 ({cond}) {{ {body} }}"
    elif kind == "for":
        var = random_var()
        start = random_num()
        end = random_num()
        body = random_block(depth + 1)
        return f"遍历 {var} 从 {start} 到 {end} {{ {body} }}"
    return ""

def random_block(depth=0):
    stmts = [random_statement(depth) for _ in range(random.randint(1, 2))]
    return " ; ".join(stmts)

def generate_code():
    lines = []
    for _ in range(random.randint(1, 4)):
        lines.append(random_statement(0))
    return "\n".join(lines)

def test_parse(code):
    try:
        ast = SugarConverter.convert(code)
        return True, ast
    except SyntaxError:
        return False, "SyntaxError (expected)"
    except Exception as e:
        return False, f"UNEXPECTED: {type(e).__name__}: {e}"

def main():
    total = 500
    ok = 0
    unexpected = []

    print(f"Fuzzing {total} random parse tests...")
    for i in range(total):
        code = generate_code()
        success, out = test_parse(code)
        if success:
            ok += 1
        elif "UNEXPECTED" in str(out):
            unexpected.append((code, out))

    print(f"Parse success: {ok}/{total} ({100*ok//total}%)")
    print(f"Unexpected errors: {len(unexpected)}")
    if unexpected:
        for code, err in unexpected[:5]:
            print(f"\nUNEXPECTED:")
            print(code)
            print(err)
    return len(unexpected)

if __name__ == "__main__":
    sys.exit(main())