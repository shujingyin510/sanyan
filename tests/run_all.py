"""回归测试运行器：执行所有 .san 测试文件"""
import subprocess
import sys
import os

# 强制使用 UTF-8 编码输出，避免中文乱码
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

TEST_DIR = "tests"
EXAMPLES_DIR = "examples"

# 预期崩溃的测试文件（手动验证用，不在自动化中运行）
EXCLUDE_TESTS = set()

def run_san(filepath):
    """运行一个 .san 文件，返回 (成功, 输出)"""
    try:
        result = subprocess.run(
            [sys.executable, "main.py", filepath],
            capture_output=True, text=True, timeout=30,
            encoding="utf-8", errors="replace"
        )
        success = result.returncode == 0
        return success, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return False, "测试超时 (>30s)"
    except Exception as e:
        return False, str(e)

def main():
    test_files = []

    # 收集 tests/ 目录下的 .san 文件
    if os.path.isdir(TEST_DIR):
        for f in os.listdir(TEST_DIR):
            if f.endswith('.san') and f not in EXCLUDE_TESTS:
                test_files.append(os.path.join(TEST_DIR, f))

    # 收集示例文件作为功能测试
    example_files = [
        "greenhouse.san", "greenhouse_se.san",
        "voting.san", "voting_se.san",
        "data_clean.san", "data_clean_se.san",
        "sensor_pipeline_simple.san", "sensor_pipeline_simple_se.san",
    ]
    for f in example_files:
        fp = os.path.join(EXAMPLES_DIR, f)
        if os.path.exists(fp):
            test_files.append(fp)

    total = len(test_files)
    passed = 0
    failed = []

    for filepath in test_files:
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
            # 仅显示前 300 字符，避免刷屏
            print(output[:300])
    return len(failed)

if __name__ == "__main__":
    sys.exit(main())
