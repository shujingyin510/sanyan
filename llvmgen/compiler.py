"""三言 → LLVM 编译器入口"""

from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING, Any, cast

from llvmgen.codegen import compile_top_level
from llvmgen.helpers import (
    OPCODE_MAP,
    box_py,
    clear_merge_label,
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
    set_merge_label,
    set_module_id,
    str_bytelen,
    str_contains,
    str_endswith,
    tag_op,
    unbox_py,
)
from ops.registry import get_op as _get_op
from ops.registry import register as _register
from ternary_core import TritValue

if TYPE_CHECKING:
    from llvmgen.codegen import CodegenContext


# 向后兼容：保留模块级引用
_OPMAP = OPCODE_MAP


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


def _fix_terminators(ir: str) -> str:
    """确保 IR 中每个基本块都有终止指令 (ret/br/unreachable)。"""
    lines = ir.split('\n')
    result = []
    in_block = False
    has_term = True  # 初始为True,等第一个标签后开始检测
    terminators = ('ret ', 'br ', 'unreachable', 'resume ', 'switch ', 'indirectbr ', 'callbr ')

    for line in lines:
        stripped = line.strip()
        # 检测标签 = 新基本块 (无缩进，以:结尾，非注释非字符串)
        is_label = (
            stripped
            and stripped.endswith(':')
            and not stripped.startswith(';')
            and not stripped.startswith('"')
            and line[0] not in (' ', '\t')
            and not line.startswith('  ')
        )

        if is_label:
            if in_block and not has_term:
                result.append('  unreachable')
            in_block = True
            has_term = False

        # } 结束函数
        if stripped == '}':
            if in_block and not has_term:
                result.append('  unreachable')
            in_block = False
            has_term = True

        # 检测终止指令
        for t in terminators:
            if t in stripped and not stripped.startswith(';') and not stripped.startswith('"'):
                has_term = True
                break

        result.append(line)

    return '\n'.join(result)


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

    _OP_DISPATCH['box'] = (_box_py, None)
    _OP_DISPATCH['unbox'] = (_unbox_py, None)
    evaluator._op_cache.clear()
    evaluator.commands['新字典'] = ([], [['return', ['container_ops_dict_new_empty']]], {}, None)
    evaluator.commands['存变量'] = (['d', 'k', 'v'], [['container_ops_dict_set', 'd', 'k', 'v']], {}, None)
    evaluator.commands['新列表'] = ([], [['return', ['container_ops_list_new_empty']]], {}, None)
    _register('container_ops_dict_new_empty', _dict_new_empty)
    _register('container_ops_list_new_empty', _list_new_empty)
    _register('container_ops_dict_set', ContainerOps.dict_set)
    _register('container_ops_dict_get_safe', _dict_get_safe)
    _register('container_ops_list_len', _list_len)
    _register('container_ops_dict_len', _dict_len)
    _register('container_ops_list_get_safe', _list_get_safe)
    _register('container_ops_list_append', _list_append)
    _register('container_ops_env_push', _env_push)
    _register('container_ops_env_pop', _env_pop)
    _register('container_ops_dict_keys', _dict_keys)
    _register('container_ops_list_contains', _list_contains)
    _register('container_ops_str_bytelen', _str_bytelen)
    _register('container_ops_str_escape_llvm', _escape_llvm_str)
    _register('container_ops_register_func_name', _register_func_name)
    _register('container_ops_get_func_name', _get_func_name)
    _register('container_ops_set_module_id', _set_module_id)
    _register('container_ops_str_endswith', _str_endswith)
    _register('container_ops_str_contains', _str_contains)
    evaluator.commands['查键'] = (['d', 'k'], [['container_ops_dict_get_safe', 'd', 'k']], {}, None)
    evaluator.commands['包含'] = (['lst', 'item'], [['container_ops_list_contains', 'lst', 'item']], {}, None)
    evaluator.commands['列表取长'] = (['lst'], [['container_ops_list_len', 'lst']], {}, None)
    evaluator.commands['字典取长'] = (['d'], [['container_ops_dict_len', 'd']], {}, None)
    evaluator.commands['列表取'] = (['lst', 'idx'], [['container_ops_list_get_safe', 'lst', 'idx']], {}, None)
    # tag_op: Python 命令，AST 节点头部查字典得 opcode（避免自举 IR 中的字符串比较）
    evaluator.commands['tag_op'] = (['ast'], [['container_ops_tag_op', 'ast']], {}, None)
    _register('container_ops_tag_op', _tag_op)
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
    _register('container_ops_get_merge_label', _get_merge_label)

    evaluator.commands['新标签ID'] = ([], [['return', ['container_ops_next_label']]], {}, None)
    _register('container_ops_next_label', _next_label)

    evaluator.commands['新寄存器ID'] = ([], [['return', ['container_ops_next_reg']]], {}, None)
    _register('container_ops_next_reg', _next_reg)

    evaluator.commands['循环进栈'] = (['label'], [['container_ops_loop_push', 'label']], {}, None)
    evaluator.commands['循环出栈'] = ([], [['container_ops_loop_pop']], {}, None)
    evaluator.commands['循环栈顶'] = ([], [['return', ['container_ops_loop_top']]], {}, None)
    _register('container_ops_loop_push', _loop_push)
    _register('container_ops_loop_pop', _loop_pop)
    _register('container_ops_loop_top', _loop_top)

    evaluator.commands['是终止指令'] = (['s'], [['container_ops_is_terminated', 's']], {}, None)
    _register('container_ops_is_terminated', _is_terminated)

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


def _fix_rt_list_get_null_safe(ir_text: str) -> str:
    """把常用运行时函数替换为 null-safe 版本。"""
    import re

    # rt_list_get(i8* %lst, i32 %idx)
    ir_text = re.sub(
        r'(define i8\* @rt_list_get\(i8\* %lst, i32 %idx\) \{\n)(?:entry:\n)?',
        r'\1  %_ns_gln = icmp eq i8* %lst, null\n  br i1 %_ns_gln, label %_ns_gl_null, label %_ns_gl_ok\n_ns_gl_null:\n  ret i8* null\n_ns_gl_ok:\n',
        ir_text,
    )

    # rt_list_len(i8* %lst)
    ir_text = re.sub(
        r'(define i32 @rt_list_len\(i8\* %lst\) \{\n)(?:entry:\n)?',
        r'\1  %_ns_lln = icmp eq i8* %lst, null\n  br i1 %_ns_lln, label %_ns_ll_null, label %_ns_ll_ok\n_ns_ll_null:\n  ret i32 0\n_ns_ll_ok:\n',
        ir_text,
    )

    # rt_str_len(i8* %s)
    ir_text = re.sub(
        r'(define i32 @rt_str_len\(i8\* %s\) \{\n)(?:entry:\n)?',
        r'\1  %_ns_sln = icmp eq i8* %s, null\n  br i1 %_ns_sln, label %_ns_sl_null, label %_ns_sl_ok\n_ns_sl_null:\n  ret i32 0\n_ns_sl_ok:\n',
        ir_text,
    )

    # rt_list_push_item(i8* %lst, i8* %item) - consumes entry: label
    ir_text = re.sub(
        r'(define i8\* @rt_list_push_item\(i8\* %lst, i8\* %item\) \{\n)(?:entry:\n)?',
        r'\1  %_ns_pin = icmp eq i8* %lst, null\n  br i1 %_ns_pin, label %_ns_pi_null, label %_ns_pi_ok\n_ns_pi_null:\n  ret i8* null\n_ns_pi_ok:\n',
        ir_text,
    )

    # rt_str_find: null-safe
    ir_text = re.sub(
        r'(define i32 @rt_str_find\(i8\* %s, i8\* %sub\) \{\n)(?:entry:\n)?',
        r'\1  %_ns_sf0 = icmp eq i8* %s, null\n  br i1 %_ns_sf0, label %_ns_sf_null, label %_ns_sf_c1\n_ns_sf_null:\n  ret i32 -1\n_ns_sf_c1:\n  %_ns_sf1 = icmp eq i8* %sub, null\n  br i1 %_ns_sf1, label %_ns_sf_null, label %_ns_sf_ok\n_ns_sf_ok:\n',
        ir_text,
    )

    # _rt_str_eq: 已由 llvmgen.san 生成_字典操作() 生成正确的 null-safe + 长度感知版本
    # 无需后处理替换。详见 stdlib/llvmgen.san:1629

    # rt_str_to_list: return empty list instead of null
    ir_text = ir_text.replace(
        'define i8* @rt_str_to_list(i8* %a) {\n  ret i8* null\n}',
        'define i8* @rt_str_to_list(i8* %a) {\n  %_stl = call i8* @rt_list_new()\n  ret i8* %_stl\n}',
    )

    # rt_int_to_str: return empty string
    ir_text = ir_text.replace(
        'define i8* @rt_int_to_str(i8* %v) {\n  ret i8* null\n}',
        'define i8* @rt_int_to_str(i8* %v) {\n  %_its = call i8* @rt_str_new(i8* null, i32 0)\n  ret i8* %_its\n}',
    )

    # rt_dict_keys: return empty list
    ir_text = ir_text.replace(
        'define i8* @rt_dict_keys(i8* %d) {\n  ret i8* null\n}',
        'define i8* @rt_dict_keys(i8* %d) {\n  %_dk = call i8* @rt_list_new()\n  ret i8* %_dk\n}',
    )

    # rt_list_concat: return non-null arg
    ir_text = ir_text.replace(
        'define i8* @rt_list_concat(i8* %a, i8* %b) {\n  ret i8* %a\n}',
        'define i8* @rt_list_concat(i8* %a, i8* %b) {\n  %_lcn = icmp eq i8* %a, null\n  br i1 %_lcn, label %_lc_retb, label %_lc_reta\n_lc_retb:\n  ret i8* %b\n_lc_reta:\n  ret i8* %a\n}',
    )

    # rt_str_substr: null-safe
    ir_text = ir_text.replace(
        'define i8* @rt_str_substr(i8* %a, i8* %b, i8* %c) {\n  ret i8* %a\n}',
        'define i8* @rt_str_substr(i8* %a, i8* %b, i8* %c) {\n  %_ssn = icmp eq i8* %a, null\n  br i1 %_ssn, label %_ss_ret_ok, label %_ss_ret_a\n_ss_ret_ok:\n  %_ssr = call i8* @rt_str_new(i8* null, i32 0)\n  ret i8* %_ssr\n_ss_ret_a:\n  ret i8* %a\n}',
    )

    # Clean up orphaned entry: labels from patches
    ir_text = re.sub(r'(?<=_ok:\n)entry:\n', r'', ir_text)

    return ir_text


def _fix_param_unbox(ir_text: str) -> str:
    """修复 fn handler 的参数 unbox/rebox 模式：直接 store 参数而非 ptrtoint+ashr+shl+or+inttoptr。
    旧模式把 LSB=0 的堆对象指针变成 LSB=1 的 tagged int，导致后续 rt_list_get 拿到 null。"""
    import re

    lines = ir_text.split('\n')
    # 第 1 遍：找到 ptrtoint param → ashr → alloca → shl → or → inttoptr → store 的 7 行模式
    # 替换为：alloca → store param
    result = []
    i = 0
    fixed = 0
    while i < len(lines):
        # 匹配 ptrtoint i8* %XXX_arg to i64
        m1 = re.match(r'\s*(%\d+)\s*=\s*ptrtoint\s+i8\*\s+(%_\w+_arg)\s+to\s+i64\s*$', lines[i])
        if m1 and i + 6 < len(lines):
            raw = m1.group(1)  # %X
            param = m1.group(2)  # %_arg
            # 第 2 行：ashr i64 %raw, 1
            m2 = re.match(r'\s*(%\d+)\s*=\s*ashr\s+i64\s+' + re.escape(raw) + r'\s*,\s*1\s*$', lines[i + 1])
            # 第 3 行：alloca i8*
            m3 = re.match(r'\s*(%\d+)\s*=\s*alloca\s+i8\*\s*$', lines[i + 2])
            # 第 4 行：shl i64 %val, 1
            # 第 5 行：or i64 %shl, 1
            # 第 6 行：inttoptr i64 %or to i8*
            # 第 7 行：store i8* %ptr, i8** %alloca
            if m2 and m3:
                val = m2.group(1)
                alloca_reg = m3.group(1)
                m4 = re.match(r'\s*(%\d+)\s*=\s*shl\s+i64\s+' + re.escape(val) + r'\s*,\s*1\s*$', lines[i + 3])
                if m4:
                    shl = m4.group(1)
                    m5 = re.match(r'\s*(%\d+)\s*=\s*or\s+i64\s+' + re.escape(shl) + r'\s*,\s*1\s*$', lines[i + 4])
                    if m5:
                        orr = m5.group(1)
                        m6 = re.match(
                            r'\s*(%\d+)\s*=\s*inttoptr\s+i64\s+' + re.escape(orr) + r'\s+to\s+i8\*\s*$', lines[i + 5]
                        )
                        if m6:
                            ptr = m6.group(1)
                            indent = ' ' * (len(lines[i]) - len(lines[i].lstrip()))
                            store_old = f'{indent}store i8* {ptr}, i8** {alloca_reg}'
                            if lines[i + 6].strip() == store_old.strip():
                                # Replace 7 lines with 2
                                result.append(f'{indent}{alloca_reg} = alloca i8*')
                                result.append(f'{indent}store i8* {param}, i8** {alloca_reg}')
                                i += 7
                                fixed += 1
                                continue
        result.append(lines[i])
        i += 1
    return '\n'.join(result)


def _fix_missing_constants(ir_text: str) -> str:
    """补发缺失的 @.str.N 字符串常量定义。"""
    import re

    lines = ir_text.split('\n')
    defs = set()
    refs = set()
    for line in lines:
        if 'private constant' in line:
            for m in re.findall(r'@\.str\.(\d+)', line):
                defs.add(int(m))
        else:
            for m in re.findall(r'@\.str\.(\d+)', line):
                refs.add(int(m))
    missing = refs - defs
    if not missing:
        return ir_text
    extra = []
    for idx in sorted(missing):
        extra.append(f'@.str.{idx} = private constant [22 x i8] c"__sanyan_fixup_{idx:04d}__\\00"')
    result = []
    for line in lines:
        result.append(line)
        if line.startswith('declare ') and extra:
            result.extend(extra)
            extra = []
    if extra:
        result.extend(extra)
    return '\n'.join(result)


def _merge_ir_modules(ir_parts: list[str]) -> str:
    """合并多个LLVM IR模块，去重define/declare。"""
    if not ir_parts:
        return ''
    result = ''
    seen_defines = set()
    seen_declares = set()
    seen_globals = set()
    for i, part in enumerate(ir_parts):
        for line in part.split('\n'):
            s = line.strip()
            if i > 0 and ('target triple' in s or 'ModuleID' in s):
                continue
            if s.startswith('@') and ('global' in s or '= private constant' in s or '= external' in s):
                name = s.split('=')[0].strip().lstrip('@').split()[0]
                if name in seen_globals:
                    continue
                seen_globals.add(name)
            if s.startswith('declare '):
                fn = s.split('@')[1].split('(')[0] if '@' in s else ''
                if fn in seen_declares:
                    continue
                seen_declares.add(fn)
            if s.startswith('define '):
                fn = s.split('@')[1].split('(')[0] if '@' in s else ''
                if fn in ('main', '__init') and i > 0:
                    continue
                if fn in seen_defines and fn not in ('main', '__init'):
                    continue
                seen_defines.add(fn)
            result += line + '\n'
    return result


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
