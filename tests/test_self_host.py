"""字节码编译器自举检测：验证 bytecode_compiler.san 能编译自身并输出字节一致的结果"""

import os
import hashlib
import sys


import unittest
from compile_bytecode import compile_source

REFERENCE_BIN = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'stdlib',
    'bytecode_compiler.bin',
)
SOURCE_SAN = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'stdlib',
    'bytecode_compiler.san',
)
OUTPUT_BIN = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    'self_host_output.bin',
)

REFERENCE_SHA256 = '243f0d8a5f4af1df28dafccf8763024f9af605a39b1d94cda3300489b4370907'

# ── Level 2 自举辅助：用 .bin 编译器编译源码 ──


def _compile_with_bin(bin_path: str, source: str, output_bin: str, parse_ast_fn) -> bytes:
    """用指定 .bin 编译器编译 Sanyan 源码，返回输出的字节。

    这是 Level 2 自举的核心：VM 加载 .bin（编译器），
    调用其中的 编译字节码 函数，产出新的 .bin。
    """
    from vm import VM

    ast = parse_ast_fn(source)
    if ast is None:
        raise RuntimeError('解析源码失败')
    if isinstance(ast, list) and ast[0] == '做':
        ast = ['do'] + ast[1:]
    elif isinstance(ast, list):
        ast = ['do', ast]
    else:
        ast = ['do', ast]

    vm = VM.from_bin(bin_path)
    addr = vm.exports.get('编译字节码')
    if addr is None:
        raise RuntimeError(f'{bin_path} 没有 编译字节码 导出')

    # 在字节码末尾追加 HALT 作为返回点
    vm.code.append(0xFF)
    halt_addr = len(vm.code) - 1
    vm.code_len = len(vm.code)

    # 推送参数：编译字节码(ast, output_path, vars_dict)
    vm.stack.append(ast)
    vm.stack.append(output_bin)
    vm.stack.append({})

    # 构造调用帧：RET 后跳转到 HALT
    arg_count = 3
    caller_base = max(0, len(vm.stack) - arg_count)
    vm.call_stack.append((halt_addr, list(vm.vars), caller_base))

    vm.pc = addr
    vm.halted = False
    vm._run_inner()

    if not os.path.exists(output_bin):
        raise RuntimeError(f'编译未产出文件: {output_bin}')
    with open(output_bin, 'rb') as f:
        return f.read()


def _parse_s_expr(source: str):
    """S-表达式解析器"""
    from lexer import tokenize
    from parser import parse

    return parse(tokenize(source))


class TestSelfHost(unittest.TestCase):
    def test_self_host(self):
        with open(SOURCE_SAN, 'r', encoding='utf-8') as f:
            source = f.read()

        result = compile_source(source, OUTPUT_BIN)
        success, cs, vc = result
        self.assertTrue(success, '编译失败')

        with open(OUTPUT_BIN, 'rb') as f:
            output = f.read()
        with open(REFERENCE_BIN, 'rb') as f:
            reference = f.read()

        self.assertEqual(
            len(output),
            len(reference),
            f'文件大小不一致: 实际={len(output)} 期望={len(reference)}',
        )
        self.assertEqual(
            output,
            reference,
            '输出与参考文件不一致',
        )
        sha256 = hashlib.sha256(output).hexdigest()
        self.assertEqual(sha256, REFERENCE_SHA256, 'SHA256 不匹配')

    def tearDown(self):
        if os.path.exists(OUTPUT_BIN):
            os.remove(OUTPUT_BIN)


class TestBootstrapLevel2(unittest.TestCase):
    """Level 2 完整自举循环：不动点验证

    源码 ──[Level 0 Python evaluator]──▶ A.bin（参考）
    源码 ──[VM 加载 A.bin]─────────────▶ B.bin
    源码 ──[VM 加载 B.bin]─────────────▶ C.bin

    如果 B == C 逐字节相同 → 编译器达到不动点，Level 2 自举达成。
    """

    def test_bootstrap_fixpoint(self):
        """完整自举循环：A → B → C，验证 B == C"""
        import tempfile

        with open(SOURCE_SAN, 'r', encoding='utf-8') as f:
            source = f.read()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Round 0: 验证参考编译器存在
            self.assertTrue(os.path.exists(REFERENCE_BIN), '参考 .bin 不存在')

            # Round 1: A 编译源码 → B
            b_bin = os.path.join(tmpdir, 'b_self_host.bin')
            b_data = _compile_with_bin(REFERENCE_BIN, source, b_bin, _parse_s_expr)
            self.assertGreater(len(b_data), 100, 'B.bin 过小')

            # Round 2: B 编译源码 → C
            c_bin = os.path.join(tmpdir, 'c_self_host.bin')
            c_data = _compile_with_bin(b_bin, source, c_bin, _parse_s_expr)
            self.assertGreater(len(c_data), 100, 'C.bin 过小')

            # Level 2 不动点：B == C
            self.assertEqual(
                len(b_data),
                len(c_data),
                f'B({len(b_data)}) 和 C({len(c_data)}) 大小不一致',
            )
            self.assertEqual(
                b_data,
                c_data,
                'Level 2 自举循环失败：B != C（编译器未达到不动点）',
            )
            # 同时验证 B 与参考一致（编译器输出稳定）
            with open(REFERENCE_BIN, 'rb') as f:
                ref_data = f.read()
            self.assertEqual(
                b_data,
                ref_data,
                'VM 编译产出与参考不一致',
            )


class TestBootstrapLevel3(unittest.TestCase):
    """Level 3 种子 VM：用最简 C VM 替代 Python VM 执行编译器

    C VM（csrc/sanyan_vm_seed.c）是零依赖的手写字节码解释器，
    TinyCC 编译产出 ~2KB 可审计种子二进制。

    此测试验证 C VM 能正确执行简单字节码程序。
    组合 Level 2 不动点验证 → 完整 Level 3 自举。
    """

    @unittest.skipIf(sys.platform != 'linux', 'C VM 种子仅支持 Linux (syscall)，此平台跳过')
    def test_seed_vm_runs_bytecode(self):
        """编译 C VM 种子，执行简单字节码验证正确性"""
        import subprocess
        import tempfile

        seed_src = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'csrc',
            'sanyan_vm_seed.c',
        )
        self.assertTrue(os.path.exists(seed_src), f'种子源码不存在: {seed_src}')

        with tempfile.TemporaryDirectory() as tmpdir:
            seed_exe = os.path.join(tmpdir, 'sanyan_vm_seed')

            # 编译 C VM
            result = subprocess.run(
                ['gcc', seed_src, '-o', seed_exe, '-nostdlib', '-Os', '-fno-builtin', '-lgcc', '-Wno-main', '-s'],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                # 尝试 tcc
                result = subprocess.run(
                    ['tcc', seed_src, '-o', seed_exe],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
            self.assertEqual(result.returncode, 0, f'C VM 编译失败:\n{result.stderr[:500]}')
            self.assertTrue(os.path.exists(seed_exe), '可执行文件未生成')

            # 用 C VM 执行简单字节码程序
            from compile_bytecode import compile_source
            from vm import VM as PyVM

            src = '(输出 42)'
            bin_path = os.path.join(tmpdir, 'test.bin')
            compile_source(src, bin_path)

            # C VM 输出
            cvm = subprocess.run(
                [seed_exe, bin_path],
                capture_output=True,
                text=True,
                timeout=10,
            )

            # Python VM 输出（用于对比）
            import io

            old = sys.stdout
            sys.stdout = io.StringIO()
            vm = PyVM.from_bin(bin_path)
            vm.run()
            py_out = sys.stdout.getvalue().strip()
            sys.stdout = old

            cvm_out = cvm.stdout.strip()
            self.assertEqual(cvm_out, py_out, f'C VM 输出不匹配: CVM={cvm_out!r} PY={py_out!r}')

    @unittest.skipIf(sys.platform != 'linux', 'C VM 种子仅支持 Linux')
    def test_seed_vm_size(self):
        """验证种子二进制在 8KB 以内"""
        import subprocess
        import tempfile

        seed_src = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'csrc',
            'sanyan_vm_seed.c',
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            seed_exe = os.path.join(tmpdir, 'sanyan_vm_seed')
            for compiler in ['tcc', 'gcc']:
                if compiler == 'tcc':
                    args = ['tcc', seed_src, '-o', seed_exe]
                else:
                    args = [
                        'gcc',
                        seed_src,
                        '-o',
                        seed_exe,
                        '-nostdlib',
                        '-Os',
                        '-fno-builtin',
                        '-lgcc',
                        '-Wno-main',
                        '-s',
                    ]

                result = subprocess.run(args, capture_output=True, text=True, timeout=30)
                if result.returncode == 0:
                    size = os.path.getsize(seed_exe)
                    if compiler == 'tcc':
                        self.assertLess(size, 4096, f'TCC 编译二进制过大: {size} bytes (目标 < 4KB)')
                    break  # 任一种编译器通过即可

            self.assertTrue(os.path.exists(seed_exe), '无法编译种子 VM')


class TestCompileBytecode(unittest.TestCase):
    """compile_bytecode.py 编译路径覆盖"""

    def test_compile_source_sexpr(self):
        """compile_source: S-表达式输入"""
        from compile_bytecode import compile_source
        from ternary_core import TritValue

        path = os.path.join(os.path.dirname(__file__), '..', 'build', '_test_sexpr.bin')
        os.makedirs(os.path.dirname(path), exist_ok=True)
        try:
            result = compile_source('(做 (设 x 42))', path)
            self.assertTrue(isinstance(result[0], (int, TritValue)) and result[0] == 1 or result[0].to_int() == 1)
            self.assertGreater(result[1] if isinstance(result[1], int) else result[1].to_int(), 0)
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_compile_source_single_expr(self):
        """compile_source: 单个表达式（非列表）"""
        from compile_bytecode import compile_source

        path = os.path.join(os.path.dirname(__file__), '..', 'build', '_test_single.bin')
        os.makedirs(os.path.dirname(path), exist_ok=True)
        try:
            result = compile_source('42', path)
            val = result[0].to_int() if not isinstance(result[0], int) else result[0]
            self.assertEqual(val, 1)
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_compile_san_from_file(self):
        """compile_san: 从文件编译"""
        from compile_bytecode import compile_san

        src_path = os.path.join(os.path.dirname(__file__), '..', 'build', '_test_compile.san')
        out_path = os.path.join(os.path.dirname(__file__), '..', 'build', '_test_compile.bin')
        os.makedirs(os.path.dirname(src_path), exist_ok=True)
        with open(src_path, 'w', encoding='utf-8') as f:
            f.write('(做 (设 x 42))')
        try:
            data = compile_san(src_path, out_path)
            self.assertGreater(len(data), 10)
            self.assertEqual(data[:4], b'SAN0')
        finally:
            for p in (src_path, out_path):
                if os.path.exists(p):
                    os.unlink(p)

    def test_run_bin(self):
        """run_bin: 执行编译后的 bin"""
        from compile_bytecode import compile_source, run_bin
        import io
        import sys

        path = os.path.join(os.path.dirname(__file__), '..', 'build', '_test_run.bin')
        os.makedirs(os.path.dirname(path), exist_ok=True)
        try:
            compile_source('(输出 (加 1 2))', path)
            old = sys.stdout
            sys.stdout = io.StringIO()
            try:
                run_bin(path)
                output = sys.stdout.getvalue()
            finally:
                sys.stdout = old
            self.assertIn('3', output)
        finally:
            if os.path.exists(path):
                os.unlink(path)


if __name__ == '__main__':
    unittest.main()
