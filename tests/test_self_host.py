"""字节码编译器自举检测：验证 bytecode_compiler.san 能编译自身并输出字节一致的结果"""

import sys
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

REFERENCE_SHA256 = '66c3dc27bfbee618a7d1da85c8a6b53eb2123aaadaa648ec37a5f08a67d4162e'


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


if __name__ == '__main__':
    unittest.main()
