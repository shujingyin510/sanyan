"""三言 → LLVM 编译器入口"""

from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING, Any, cast

from llvmgen.codegen import compile_top_level
from ternary_core import TritValue

if TYPE_CHECKING:
    from llvmgen.codegen import CodegenContext


def _parse_source(source: str) -> list:
    from ops.file_ops import _parse_with_sugar_san, clear_cache
    from evaluator import SanyanEvaluator

    clear_cache()
    evaluator = SanyanEvaluator()

    # 1. Python SugarConverter（产出 codegen 兼容的内部 AST）
    try:
        from sugar import SugarConverter

        parsed = SugarConverter.convert(source, evaluator.skin_manager)
        if parsed is not None and isinstance(parsed, list):
            return cast(list[Any], parsed)
    except Exception:
        pass

    # 2. 自举糖解析器（产出中文关键字 AST——仅用于求值器路径）
    try:
        parsed = _parse_with_sugar_san(source, evaluator)
        if parsed is not None and isinstance(parsed, list):
            return cast(list[Any], parsed)
    except Exception:
        pass

    # 3. C S 表达式解析器
    parsed = _parse_c_s_expr(source)
    if parsed is not None:
        return parsed

    # 4. Python S 表达式解析器（fallback）
    try:
        from lexer import tokenize
        from parser import parse

        tokens = tokenize(source)
        parsed = parse(tokens)
        if parsed is not None and isinstance(parsed, list):
            return cast(list[Any], parsed)
    except Exception:
        pass

    raise SyntaxError('所有解析器均失败')


def _parse_c_s_expr(source: str) -> list | None:
    """使用 C 共享库解析 S 表达式。"""
    import ctypes
    import json
    import os

    dll_path = os.path.join(os.path.dirname(__file__), '..', 'csrc', 'sanyan_parse.dll')
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
            return cast(list[Any] | None, ast)
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


def _dict_get_safe(evaluator, args):
    """安全取字典键：存在返回值，不存在返回空串。"""
    d = evaluator.eval(args[0])
    k = evaluator.eval(args[1])
    if isinstance(k, TritValue):
        k = k.to_int()
    if isinstance(d, dict) and k in d:
        return d[k]
    return ""


def _list_contains(evaluator, args):
    """检查列表是否包含元素，返回 TritValue(1/0)。"""
    lst = evaluator.eval(args[0])
    item = evaluator.eval(args[1])
    if isinstance(lst, (list, tuple)):
        return TritValue(1 if item in lst else 0)
    return TritValue(0)


from ops.registry import register as _register

_register('container_ops_list_contains', _list_contains)


def self_hosted_compile(source: str, module_name: str = 'main') -> str:
    """自举编译：sugar.san 解析 + llvmgen.san 生成 IR。零 Python codegen。"""
    from evaluator import SanyanEvaluator
    from skin import SkinManager
    from ops.file_ops import clear_cache
    import os

    clear_cache()
    evaluator = SanyanEvaluator(skin_manager=SkinManager('chinese'))
    evaluator.commands['新字典'] = ([], [['return', {}]], {}, None)
    evaluator.commands['存变量'] = (['d', 'k', 'v'], [['container_ops_dict_set', 'd', 'k', 'v']], {}, None)
    evaluator.commands['新列表'] = ([], [['return', []]], {}, None)
    # 注册辅助函数
    from ops.container_ops import ContainerOps
    from ops.registry import register

    register('container_ops_dict_set', ContainerOps.dict_set)
    # 查键: 字典键存在返回 value，否则返回空串
    evaluator.commands['查键'] = (['d', 'k'], [['container_ops_dict_get_safe', 'd', 'k']], {}, None)
    register('container_ops_dict_get_safe', _dict_get_safe)
    # 包含: 列表包含检查
    evaluator.commands['包含'] = (['lst', 'item'], [['container_ops_list_contains', 'lst', 'item']], {}, None)

    stdlib_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'stdlib')

    # 1. 加载 sugar.san
    with open(os.path.join(stdlib_dir, 'sugar.san'), encoding='utf-8') as f:
        sugar_code = f.read()
    sugar_ast = _parse_source(sugar_code)
    if isinstance(sugar_ast, list) and len(sugar_ast) > 0 and sugar_ast[0] == 'do':
        sugar_ast = sugar_ast[1:]
    for stmt in sugar_ast:
        if isinstance(stmt, list) and stmt[0] == 'export':
            continue
        evaluator.eval(stmt)

    # 2. 加载 llvmgen.san
    with open(os.path.join(stdlib_dir, 'llvmgen.san'), encoding='utf-8') as f:
        llvmgen_code = f.read()
    llvmgen_ast = _parse_source(llvmgen_code)
    if isinstance(llvmgen_ast, list) and len(llvmgen_ast) > 0 and llvmgen_ast[0] == 'do':
        llvmgen_ast = llvmgen_ast[1:]
    for stmt in llvmgen_ast:
        if isinstance(stmt, list) and stmt[0] == 'export':
            continue
        evaluator.eval(stmt)

    # 3. sugar.san 解析用户源码
    ast = evaluator.eval(['解析', source])
    if not isinstance(ast, list):
        raise SyntaxError(f'sugar.san 解析失败: {ast}')

    # 4. llvmgen.san 生成 IR
    ir_text = evaluator.eval(['编译顶层', ast])
    if not isinstance(ir_text, str):
        raise RuntimeError(f'llvmgen.san 生成失败: {type(ir_text).__name__}')

    return ir_text


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
