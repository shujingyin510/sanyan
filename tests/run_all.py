"""回归测试运行器：执行所有 .san 测试文件"""
from __future__ import annotations
import subprocess
import sys
import os

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

TEST_DIR = "tests"
EXAMPLES_DIR = "examples"
EXCLUDE_TESTS = set()


def run_san(filepath: str) -> tuple[bool, str]:
    """运行一个 .san 文件，返回 (成功, 输出)"""
    try:
        result = subprocess.run(
            [sys.executable, "-X", "utf8", "main.py", filepath],
            capture_output=True, text=True, timeout=30,
            encoding="utf-8", errors="replace"
        )
        output = (result.stdout + result.stderr).strip()
        return result.returncode == 0, output
    except subprocess.TimeoutExpired:
        return False, "测试超时 (>30s)"
    except Exception as e:
        return False, str(e)


def main():
    test_files = []

    if os.path.isdir(TEST_DIR):
        for f in os.listdir(TEST_DIR):
            if f.endswith('.san') and f not in EXCLUDE_TESTS:
                test_files.append(os.path.join(TEST_DIR, f))

    if os.path.isdir(EXAMPLES_DIR):
        for f in sorted(os.listdir(EXAMPLES_DIR)):
            if f.endswith('.san'):
                fp = os.path.join(EXAMPLES_DIR, f)
                if os.path.exists(fp):
                    test_files.append(fp)

    total = len(test_files)
    passed = 0
    failed = []

    for filepath in sorted(test_files):
        print(f"运行: {filepath} ... ", end="", flush=True)
        ok, output = run_san(filepath)
        if ok:
            print("✓")
            passed += 1
        else:
            print("✗")
            failed.append((filepath, output))

    print(f"\n{passed}/{total} 通过")
    if failed:
        print("失败的测试:")
        for filepath, output in failed:
            print(f"  [{filepath}]")
            for line in output.split('\n')[:10]:
                print(f"    {line}")
    return len(failed)


if __name__ == "__main__":
    sys.exit(main())
