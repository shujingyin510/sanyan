"""三言 → LLVM 编译器入口"""

from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING, Any, cast

from llvmgen.codegen import compile_top_level
from llvmgen.helpers import (
    OPCODE_MAP,
    box_py,
    dict_get_safe,
    dict_keys,
    dict_len,
    dict_new_empty,
    env_pop,
    env_push,
    escape_llvm_str,
    get_func_name,
    get_merge_label,
    is_terminated,
    list_append,
    list_contains,
    list_get_safe,
    list_len,
    list_new_empty,
    loop_pop,
    loop_push,
    loop_top,
    next_label,
    next_reg,
    register_all_helpers,
    register_func_name,
    set_module_id,
    str_bytelen,
    str_contains,
    str_endswith,
    tag_op,
    unbox_py,
)
from ops.registry import get_op as _get_op
from ops.registry import register as _register
from llvmgen.ir_fixes import (
    _fix_missing_constants,
    _fix_rt_list_get_null_safe,
    _fix_terminators,
)

if TYPE_CHECKING:
    from llvmgen.codegen import CodegenContext


# 向后兼容：保留模块级引用
_OPMAP = OPCODE_MAP


def _is_paren_sexpr(source: str) -> bool:
    """判断源码是否为 S 表达式语法（以 '(' 开头）。"""
    stripped = source.strip()
    return stripped.startswith('(')


def _parse_source(source: str) -> list:
    from ops.file_ops import _parse_with_sugar_san, clear_cache
    from evaluator import SanyanEvaluator

    clear_cache()
    evaluator = SanyanEvaluator()

    if _is_paren_sexpr(source):
        # S 表达式语法：先用 S 表达式解析器
        # 1. Python S 表达式解析器
        try:
            from lexer import tokenize
            from parser import parse

            tokens = tokenize(source)
            parsed = parse(tokens)
            if parsed is not None and isinstance(parsed, list):
                return cast(list[Any], parsed)
        except Exception:
            pass

        # 2. C S 表达式解析器（fallback）
        parsed = _parse_c_s_expr(source)
        if parsed is not None:
            return parsed
    else:
        # 糖语法：先用糖解析器
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

        # 3. C S 表达式解析器（fallback）
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


def self_hosted_compile(source: str, module_name: str = 'main') -> str:
    """自举编译：sugar.san 解析 + llvmgen.san 生成 IR。零 Python codegen。"""
    from evaluator import SanyanEvaluator
    from skin import SkinManager
    from ops.file_ops import clear_cache
    from ops.registry import _OP_DISPATCH
    from ops.container_ops import ContainerOps

    clear_cache()
    evaluator = SanyanEvaluator(skin_manager=SkinManager('chinese'))

    # 强制覆盖 box/unbox 派发 + 清所有缓存
    _OP_DISPATCH['box'] = (box_py, None)
    _OP_DISPATCH['unbox'] = (unbox_py, None)
    evaluator._op_cache.clear()

    # 注册辅助函数
    register_all_helpers()

    evaluator.commands['新字典'] = ([], [['return', ['container_ops_dict_new_empty']]], {}, None)
    _register('container_ops_dict_new_empty', dict_new_empty)
    evaluator.commands['存变量'] = (['d', 'k', 'v'], [['container_ops_dict_set', 'd', 'k', 'v']], {}, None)
    evaluator.commands['新列表'] = ([], [['return', ['container_ops_list_new_empty']]], {}, None)
    _register('container_ops_list_new_empty', list_new_empty)
    evaluator.commands['取字长'] = (['s'], [['container_ops_str_bytelen', 's']], {}, None)
    _register('container_ops_str_bytelen', str_bytelen)
    evaluator.commands['转义LLVM字符串'] = (['s'], [['container_ops_str_escape_llvm', 's']], {}, None)
    _register('container_ops_str_escape_llvm', escape_llvm_str)
    evaluator.commands['后缀'] = (['s', 'suffix'], [['container_ops_str_endswith', 's', 'suffix']], {}, None)
    _register('container_ops_str_endswith', str_endswith)
    evaluator.commands['设置模块ID'] = (['mid'], [['container_ops_set_module_id', 'mid']], {}, None)
    _register('container_ops_set_module_id', set_module_id)
    evaluator.commands['字符串包含'] = (['s', 'sub'], [['container_ops_str_contains', 's', 'sub']], {}, None)
    _register('container_ops_str_contains', str_contains)
    evaluator.commands['注册函数名'] = (['name'], [['container_ops_register_func_name', 'name']], {}, None)
    _register('container_ops_register_func_name', register_func_name)
    evaluator.commands['取函数名'] = (['name'], [['container_ops_get_func_name', 'name']], {}, None)
    _register('container_ops_get_func_name', get_func_name)

    _register('container_ops_dict_set', ContainerOps.dict_set)
    evaluator.commands['查键'] = (['d', 'k'], [['container_ops_dict_get_safe', 'd', 'k']], {}, None)
    _register('container_ops_dict_get_safe', dict_get_safe)
    evaluator.commands['包含'] = (['lst', 'item'], [['container_ops_list_contains', 'lst', 'item']], {}, None)
    evaluator.commands['列表取长'] = (['lst'], [['container_ops_list_len', 'lst']], {}, None)
    _register('container_ops_list_len', list_len)
    evaluator.commands['字典取长'] = (['d'], [['container_ops_dict_len', 'd']], {}, None)
    _register('container_ops_dict_len', dict_len)
    evaluator.commands['列表取'] = (['lst', 'idx'], [['container_ops_list_get_safe', 'lst', 'idx']], {}, None)
    evaluator.commands['列表追加'] = (['lst', 'item'], [['container_ops_list_append', 'lst', 'item']], {}, None)
    _register('container_ops_list_append', list_append)
    evaluator.commands['进栈'] = (['stack'], [['container_ops_env_push', 'stack']], {}, None)
    evaluator.commands['出栈'] = (['stack'], [['container_ops_env_pop', 'stack']], {}, None)
    _register('container_ops_env_push', env_push)
    _register('container_ops_env_pop', env_pop)
    evaluator.commands['字典键列表'] = (['d'], [['container_ops_dict_keys', 'd']], {}, None)
    _register('container_ops_dict_keys', dict_keys)
    evaluator.commands['进入合并上下文'] = (['label'], [['container_ops_set_merge_label', 'label']], {}, None)
    evaluator.commands['退出合并上下文'] = ([], [['container_ops_clear_merge_label']], {}, None)
    evaluator.commands['取合并标签'] = ([], [['return', ['container_ops_get_merge_label']]], {}, None)
    _register('container_ops_get_merge_label', get_merge_label)
    _register('container_ops_list_get_safe', list_get_safe)

    evaluator.commands['新标签ID'] = ([], [['return', ['container_ops_next_label']]], {}, None)
    _register('container_ops_next_label', next_label)
    evaluator.commands['新寄存器ID'] = ([], [['return', ['container_ops_next_reg']]], {}, None)
    _register('container_ops_next_reg', next_reg)

    evaluator.commands['循环进栈'] = (['label'], [['container_ops_loop_push', 'label']], {}, None)
    evaluator.commands['循环出栈'] = ([], [['container_ops_loop_pop']], {}, None)
    evaluator.commands['循环栈顶'] = ([], [['return', ['container_ops_loop_top']]], {}, None)
    _register('container_ops_loop_push', loop_push)
    _register('container_ops_loop_pop', loop_pop)
    _register('container_ops_loop_top', loop_top)

    evaluator.commands['是终止指令'] = (['s'], [['container_ops_is_terminated', 's']], {}, None)
    _register('container_ops_is_terminated', is_terminated)

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

    # 2. 加载 llvmgen.san（求值 + 编译到 LLVM IR）
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

    # 4. llvmgen.san 生成 IR（只编译用户代码）
    evaluator._op_cache.clear()  # 编译前清空
    ir_text = evaluator.eval(['编译顶层', ast])
    if not isinstance(ir_text, str):
        raise RuntimeError(f'llvmgen.san 生成失败: {type(ir_text).__name__}')

    return ir_text


def compile_module_test(module_name: str) -> str:
    """编译单个 .san 模块到 LLVM IR（测试用）。"""
    from evaluator import SanyanEvaluator
    from skin import SkinManager
    from ops.file_ops import clear_cache
    from ops.container_ops import ContainerOps
    import os

    clear_cache()
    evaluator = SanyanEvaluator(skin_manager=SkinManager('chinese'))
    # 强制覆盖 box/unbox 派发 + 清所有缓存
    from ops.registry import _OP_DISPATCH

    _OP_DISPATCH['box'] = (box_py, None)
    _OP_DISPATCH['unbox'] = (unbox_py, None)
    evaluator._op_cache.clear()
    evaluator.commands['新字典'] = ([], [['return', ['container_ops_dict_new_empty']]], {}, None)
    evaluator.commands['存变量'] = (['d', 'k', 'v'], [['container_ops_dict_set', 'd', 'k', 'v']], {}, None)
    evaluator.commands['新列表'] = ([], [['return', ['container_ops_list_new_empty']]], {}, None)
    _register('container_ops_dict_new_empty', dict_new_empty)
    _register('container_ops_list_new_empty', list_new_empty)
    _register('container_ops_dict_set', ContainerOps.dict_set)
    _register('container_ops_dict_get_safe', dict_get_safe)
    _register('container_ops_list_len', list_len)
    _register('container_ops_dict_len', dict_len)
    _register('container_ops_list_get_safe', list_get_safe)
    _register('container_ops_list_append', list_append)
    _register('container_ops_env_push', env_push)
    _register('container_ops_env_pop', env_pop)
    _register('container_ops_dict_keys', dict_keys)
    _register('container_ops_list_contains', list_contains)
    _register('container_ops_str_bytelen', str_bytelen)
    _register('container_ops_str_escape_llvm', escape_llvm_str)
    _register('container_ops_register_func_name', register_func_name)
    _register('container_ops_get_func_name', get_func_name)
    _register('container_ops_set_module_id', set_module_id)
    _register('container_ops_str_endswith', str_endswith)
    _register('container_ops_str_contains', str_contains)
    evaluator.commands['查键'] = (['d', 'k'], [['container_ops_dict_get_safe', 'd', 'k']], {}, None)
    evaluator.commands['包含'] = (['lst', 'item'], [['container_ops_list_contains', 'lst', 'item']], {}, None)
    evaluator.commands['列表取长'] = (['lst'], [['container_ops_list_len', 'lst']], {}, None)
    evaluator.commands['字典取长'] = (['d'], [['container_ops_dict_len', 'd']], {}, None)
    evaluator.commands['列表取'] = (['lst', 'idx'], [['container_ops_list_get_safe', 'lst', 'idx']], {}, None)
    # tag_op: Python 命令，AST 节点头部查字典得 opcode（避免自举 IR 中的字符串比较）
    evaluator.commands['tag_op'] = (['ast'], [['container_ops_tag_op', 'ast']], {}, None)
    _register('container_ops_tag_op', tag_op)
    assert _get_op('container_ops_tag_op') is not None, 'tag_op registration failed!'
    evaluator.commands['列表追加'] = (['lst', 'item'], [['container_ops_list_append', 'lst', 'item']], {}, None)
    evaluator.commands['进栈'] = (['stack'], [['container_ops_env_push', 'stack']], {}, None)
    evaluator.commands['出栈'] = (['stack'], [['container_ops_env_pop', 'stack']], {}, None)
    evaluator.commands['字典键列表'] = (['d'], [['container_ops_dict_keys', 'd']], {}, None)
    evaluator.commands['取字长'] = (['s'], [['container_ops_str_bytelen', 's']], {}, None)
    evaluator.commands['转义LLVM字符串'] = (['s'], [['container_ops_str_escape_llvm', 's']], {}, None)
    evaluator.commands['注册函数名'] = (['name'], [['container_ops_register_func_name', 'name']], {}, None)
    evaluator.commands['取函数名'] = (['name'], [['container_ops_get_func_name', 'name']], {}, None)
    evaluator.commands['设置模块ID'] = (['mid'], [['container_ops_set_module_id', 'mid']], {}, None)
    evaluator.commands['后缀'] = (['s', 'suffix'], [['container_ops_str_endswith', 's', 'suffix']], {}, None)
    evaluator.commands['字符串包含'] = (['s', 'sub'], [['container_ops_str_contains', 's', 'sub']], {}, None)
    evaluator.commands['进入合并上下文'] = (['label'], [['container_ops_set_merge_label', 'label']], {}, None)
    evaluator.commands['退出合并上下文'] = ([], [['container_ops_clear_merge_label']], {}, None)
    evaluator.commands['取合并标签'] = ([], [['return', ['container_ops_get_merge_label']]], {}, None)
    _register('container_ops_get_merge_label', get_merge_label)

    evaluator.commands['新标签ID'] = ([], [['return', ['container_ops_next_label']]], {}, None)
    _register('container_ops_next_label', next_label)

    evaluator.commands['新寄存器ID'] = ([], [['return', ['container_ops_next_reg']]], {}, None)
    _register('container_ops_next_reg', next_reg)

    evaluator.commands['循环进栈'] = (['label'], [['container_ops_loop_push', 'label']], {}, None)
    evaluator.commands['循环出栈'] = ([], [['container_ops_loop_pop']], {}, None)
    evaluator.commands['循环栈顶'] = ([], [['return', ['container_ops_loop_top']]], {}, None)
    _register('container_ops_loop_push', loop_push)
    _register('container_ops_loop_pop', loop_pop)
    _register('container_ops_loop_top', loop_top)

    evaluator.commands['是终止指令'] = (['s'], [['container_ops_is_terminated', 's']], {}, None)
    _register('container_ops_is_terminated', is_terminated)

    stdlib_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'stdlib')
    # Load llvmgen.san
    with open(os.path.join(stdlib_dir, 'llvmgen.san'), encoding='utf-8') as f:
        llvmgen_code = f.read()
    llvmgen_ast = _parse_source(llvmgen_code)
    if isinstance(llvmgen_ast, list) and len(llvmgen_ast) > 0 and llvmgen_ast[0] == 'do':
        llvmgen_ast = llvmgen_ast[1:]
    for stmt in llvmgen_ast:
        if isinstance(stmt, list) and stmt[0] == 'export':
            continue
        evaluator.eval(stmt)

    # Compile the target module
    with open(os.path.join(stdlib_dir, module_name), encoding='utf-8') as f:
        code = f.read()
    ast = _parse_source(code)
    if isinstance(ast, list) and len(ast) > 0 and ast[0] == 'do':
        ast = ast[1:]
    module_ast = ['do'] + [s for s in ast if not (isinstance(s, list) and s[0] == 'export')]

    evaluator.eval(['设置模块ID', 0])
    evaluator._op_cache.clear()
    ir = evaluator.eval(['编译顶层', module_ast])
    ir = _fix_terminators(ir) if isinstance(ir, str) else ''
    ir = _fix_missing_constants(ir) if isinstance(ir, str) else ''
    # _fix_param_unbox 会导致 comp_env 中的 alloca 寄存器与 IR 不一致——暂时跳过
    # ir = _fix_param_unbox(ir) if isinstance(ir, str) else ''
    ir = _fix_rt_list_get_null_safe(ir) if isinstance(ir, str) else ''
    return ir if isinstance(ir, str) else ''


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
