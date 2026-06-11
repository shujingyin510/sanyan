"""字节码编译器自举检测：验证 bytecode_compiler.san 能编译自身并输出字节一致的结果"""

import os
import hashlib


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

REFERENCE_SHA256 = 'b828d68d0dc90fa70f0a2abeec26d8c069dd1e09fed416e169f689a180ca64bb'


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
