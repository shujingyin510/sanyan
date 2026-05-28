"""C VM (csrc/runtime.c) 单元测试

通过 Python 编译并运行 C VM 测试可执行文件，验证字节码解释器的正确性。
需要 C 编译器 (gcc/clang) 才能运行，否则自动跳过。
"""

from __future__ import annotations
import subprocess
import sys
import os
import shutil
import tempfile
import unittest


SRC = os.path.join(os.path.dirname(__file__), '..', 'csrc', 'test_runtime.c')
EXE_NAME = 'test_runtime.exe' if sys.platform == 'win32' else 'test_runtime'


def _find_compiler() -> str | None:
    """查找可用的 C 编译器"""
    for compiler in ['gcc', 'clang', 'cc']:
        if shutil.which(compiler):
            return compiler
    # 尝试 MSYS2 路径
    if sys.platform == 'win32':
        msys_gcc = r'D:\msys64\mingw64\bin\gcc.exe'
        if os.path.exists(msys_gcc):
            return msys_gcc
    return None


def _compile_and_run() -> tuple[bool, str]:
    """编译并运行 C VM 测试，返回 (成功, 输出)"""
    compiler = _find_compiler()
    if compiler is None:
        return False, '需要 C 编译器 (gcc/clang)'

    if not os.path.exists(SRC):
        return False, f'测试源文件不存在: {SRC}'

    # 确保 MSYS2 在 PATH 中 (Windows)
    env = os.environ.copy()
    if sys.platform == 'win32':
        msys_bin = r'D:\msys64\mingw64\bin'
        if os.path.isdir(msys_bin):
            env['PATH'] = msys_bin + ';' + env.get('PATH', '')

    with tempfile.TemporaryDirectory() as tmpdir:
        exe_path = os.path.join(tmpdir, EXE_NAME)
        result = subprocess.run(
            [compiler, '-o', exe_path, SRC, '-std=c99', '-Wall', '-Wno-misleading-indentation'],
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )
        if result.returncode != 0:
            return False, f'编译失败:\n{result.stderr}'

        result = subprocess.run(
            [exe_path],
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )
        return result.returncode == 0, result.stdout + result.stderr


class TestCVM(unittest.TestCase):
    """C VM 字节码解释器测试"""

    def test_c_vm(self):
        ok, output = _compile_and_run()
        # 解析输出获取测试统计
        for line in output.splitlines():
            if 'tests,' in line and 'passed' in line:
                parts = line.split(',')
                total = int(parts[0].strip().split()[0])
                passed = int(parts[1].strip().split()[0])
                failed = int(parts[2].strip().split()[0])
                self.assertEqual(failed, 0, f'C VM 测试失败: {failed}/{total}\n{output}')
                self.assertEqual(passed, total, f'C VM 测试不完整: {passed}/{total}\n{output}')
                return
        self.fail(f'无法解析 C VM 测试输出:\n{output}')


if __name__ == '__main__':
    unittest.main()
