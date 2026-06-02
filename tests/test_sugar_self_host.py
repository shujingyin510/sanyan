"""sugar.bin 自举验证：验证 sugar.san 可通过引导链编译并输出字节一致的结果

引导链：
1. _bootstrap.san（S 表达式）由 Python 解析器加载
2. _bootstrap.san 的 解析 函数解析 sugar.san
3. bytecode_compiler.san 编译解析后的 AST
4. 输出与参考 sugar.bin 比较
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import os
import hashlib


import unittest
from compile_bytecode import compile_source
from ops.file_ops import _load_sugar_parser, _parse_with_sugar_san, clear_cache
from evaluator import SanyanEvaluator
from skin import SkinManager

REFERENCE_BIN = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'stdlib',
    'sugar.bin',
)
SOURCE_SAN = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'stdlib',
    'sugar.san',
)
OUTPUT_BIN = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    'sugar_self_host_output.bin',
)


def _get_evaluator():
    return SanyanEvaluator(skin_manager=SkinManager('chinese'), max_loop_steps=500000)


class TestSugarSelfHost(unittest.TestCase):
    """验证 sugar.san 自举编译稳定性"""

    @classmethod
    def setUpClass(cls):
        """计算参考文件 SHA256"""
        if os.path.exists(REFERENCE_BIN):
            with open(REFERENCE_BIN, 'rb') as f:
                cls.reference_sha256 = hashlib.sha256(f.read()).hexdigest()
        else:
            cls.reference_sha256 = None

    def test_sugar_self_host(self):
        """sugar.san 编译结果应与参考 sugar.bin 字节一致"""
        if not os.path.exists(REFERENCE_BIN):
            self.skipTest('参考文件 sugar.bin 不存在')
        if not os.path.exists(SOURCE_SAN):
            self.skipTest('源文件 sugar.san 不存在')

        with open(SOURCE_SAN, 'r', encoding='utf-8') as f:
            source = f.read()

        # 使用 compile_source 编译（内部使用 sugar parser + bytecode compiler）
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
        self.assertEqual(sha256, self.reference_sha256, 'SHA256 不匹配')

    def test_sugar_parser_loads(self):
        """sugar.san 解析器应能正常加载"""
        clear_cache()
        e = _get_evaluator()
        parser = _load_sugar_parser(e)
        self.assertIsNotNone(parser, 'sugar 解析器加载失败')
        self.assertIn('解析', parser.commands)
        self.assertIn('词法分析', parser.commands)

    def test_sugar_parser_parses_source(self):
        """sugar.san 解析器应能解析简单代码"""
        clear_cache()
        e = _get_evaluator()
        parser = _load_sugar_parser(e)
        self.assertIsNotNone(parser)

        # 解析简单表达式
        result = _parse_with_sugar_san('设 x = 42', e)
        self.assertIsNotNone(result, 'sugar.san 解析失败')

    def tearDown(self):
        if os.path.exists(OUTPUT_BIN):
            os.remove(OUTPUT_BIN)


if __name__ == '__main__':
    unittest.main()
