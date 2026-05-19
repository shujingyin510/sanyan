"""三言 → LLVM 编译器入口"""

from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING

from llvmgen.codegen import compile_top_level

if TYPE_CHECKING:
    from llvmgen.codegen import CodegenContext


def _parse_source(source: str) -> list:
    """解析三言源码为 AST 列表。

    顺序: 糖解析器 → C S表达式 → Python SugarConverter
    """
    from ops.file_ops import _parse_with_sugar_san, clear_cache
    from evaluator import SanyanEvaluator

    clear_cache()
    evaluator = SanyanEvaluator()

    # 1. 糖解析器
    try:
        parsed = _parse_with_sugar_san(source, evaluator)
        if parsed is not None and isinstance(parsed, list):
            return parsed  # type: ignore[no-any-return]
    except Exception:
        pass

    # 2. C S 表达式解析器
    parsed = _parse_c_s_expr(source)
    if parsed is not None:
        return parsed

    # 3. Python SugarConverter
    try:
        from sugar import SugarConverter

        parsed = SugarConverter.convert(source, evaluator.skin_manager)
        if parsed is not None and isinstance(parsed, list):
            return parsed
    except Exception:
        pass

    raise SyntaxError('所有解析器均失败')


def _parse_c_s_expr(source: str) -> list | None:
    """使用 C 共享库解析 S 表达式。"""
    import ctypes
    import json
    import os

    dll_path = os.path.join(os.path.dirname(__file__), '..', 'sanyan_parse.dll')
    if not os.path.exists(dll_path):
        return None
    try:
        lib = ctypes.CDLL(dll_path)
        lib.sanyan_parse.argtypes = [ctypes.c_char_p]
        lib.sanyan_parse.restype = ctypes.c_char_p
        result = lib.sanyan_parse(source.encode('utf-8'))
        if result:
            ast = json.loads(result.decode('utf-8'))
            if isinstance(ast, list) and len(ast) == 1:
                ast = ast[0]  # 展开外层列表包装
            return ast  # type: ignore[no-any-return]
    except Exception:
        pass
    return None


def compile_source(source: str, module_name: str = 'main') -> tuple[str, 'CodegenContext']:
    """编译三言源码，返回 (ir_text, codegen_context)。"""
    ast = _parse_source(source)
    if not isinstance(ast, list):
        raise SyntaxError(f'解析结果不是列表: {type(ast)}')
    cg = compile_top_level(ast, module_name)
    return cg.verify(), cg


def compile_file(input_path: str, output_path: str | None = None) -> str:
    """编译 .san 文件，返回 IR 文本。若指定 output_path 则写入文件。"""
    with open(input_path, 'r', encoding='utf-8') as f:
        source = f.read()
    name = os.path.splitext(os.path.basename(input_path))[0]
    ir_text, cg = compile_source(source, name)

    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(ir_text)
        print(f'✓ LLVM IR → {output_path}')

    return ir_text


def main():
    if len(sys.argv) < 2:
        print('用法: python -m llvmgen.compiler input.san [-o output.ll]')
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = None
    if len(sys.argv) > 3 and sys.argv[2] == '-o':
        output_path = sys.argv[3]

    ir_text = compile_file(input_path, output_path)

    if '--dump' in sys.argv:
        print(ir_text)


if __name__ == '__main__':
    main()
