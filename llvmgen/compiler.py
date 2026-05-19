"""三言 → LLVM 编译器入口"""

import os
import sys
from llvmgen.codegen import compile_top_level


def _parse_source(source: str) -> list:
    """解析三言源码为 AST 列表。"""
    from ops.file_ops import _parse_with_sugar_san, _load_sugar_parser, clear_cache
    from evaluator import SanyanEvaluator
    from sugar import SugarConverter
    from skin import SkinManager

    clear_cache()
    evaluator = SanyanEvaluator()
    skin = evaluator.skin_manager

    # 优先用糖解析器
    ast = _parse_with_sugar_san(source, evaluator)
    if ast is not None:
        return ast

    # 回退到 SugarConverter
    ast = SugarConverter.convert(source, skin)
    if ast is not None:
        return ast

    # 最后回退到 S 表达式解析
    from lexer import tokenize
    from parser import parse
    tokens = tokenize(source)
    ast = parse(tokens)
    if ast is not None:
        return ast

    raise SyntaxError('所有解析器均失败')


def compile_source(source: str, module_name: str = 'main'):
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
