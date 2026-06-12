"""反汇编器测试"""
import tempfile
import os

from compile_bytecode import compile_source
from disasm import disasm


def test_basic():
    """简单程序: (输出 42)"""
    src = "(输出 42)"
    with tempfile.TemporaryDirectory() as td:
        bp = os.path.join(td, "t.bin")
        compile_source(src, bp)
        with open(bp, "rb") as f:
            data = f.read()
        result = disasm(data)
        assert "PUSH_I" in result, f"PUSH_I missing:\n{result}"
        assert "PRINT" in result, f"PRINT missing:\n{result}"
    print("basic: OK")


def test_function():
    """函数调用: (做 (定义 f (x) (乘 x 2)) (输出 (f 21)))"""
    src = "(做 (定义 f (x) (乘 x 2)) (输出 (f 21)))"
    with tempfile.TemporaryDirectory() as td:
        bp = os.path.join(td, "t2.bin")
        compile_source(src, bp)
        with open(bp, "rb") as f:
            data = f.read()
        result = disasm(data)
        assert "CALL" in result, f"CALL missing:\n{result}"
        assert "RET" in result, f"RET missing:\n{result}"
    print("function: OK")


def test_string():
    """字符串: (输出 (连接 \"hello\" \" world\"))"""
    src = '(输出 (连接 "hello" " world"))'
    with tempfile.TemporaryDirectory() as td:
        bp = os.path.join(td, "t3.bin")
        compile_source(src, bp)
        with open(bp, "rb") as f:
            data = f.read()
        result = disasm(data)
        assert "PUSH_STR" in result, f"PUSH_STR missing:\n{result}"
        assert "CONCAT" in result, f"CONCAT missing:\n{result}"
    print("string: OK")


def test_hex():
    """十六进制模式"""
    src = "(输出 (加 1 2))"
    with tempfile.TemporaryDirectory() as td:
        bp = os.path.join(td, "t4.bin")
        compile_source(src, bp)
        with open(bp, "rb") as f:
            data = f.read()
        result = disasm(data, show_hex=True)
        assert "01" in result, f"hex bytes missing:\n{result[:200]}"
    print("hex: OK")


def test_errors():
    """错误输入"""
    assert disasm(b"notvalid") == "文件过小"
    assert "无效 magic" in disasm(b"BAD0.......")
    print("errors: OK")


def test_control_flow():
    """控制流: 若/循环"""
    src = "(做 (设 i 0) (循环 (小于 i 3) (设 i (加 i 1))) (若 (大于 i 2) (输出 1) (输出 -1)))"
    with tempfile.TemporaryDirectory() as td:
        bp = os.path.join(td, "t5.bin")
        compile_source(src, bp)
        with open(bp, "rb") as f:
            data = f.read()
        result = disasm(data)
        assert "JMP" in result or "JZ" in result, f"jump missing:\n{result[:300]}"
    print("control_flow: OK")


def test_all():
    test_basic()
    test_function()
    test_string()
    test_hex()
    test_errors()
    test_control_flow()
    print("\n全部通过!")


if __name__ == "__main__":
    test_all()
