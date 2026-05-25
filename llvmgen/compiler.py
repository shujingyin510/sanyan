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
    d = args[0] if isinstance(args[0], dict) else evaluator.eval(args[0])
    k = evaluator.eval(args[1])
    if isinstance(k, TritValue):
        k = k.to_int()
    if isinstance(d, dict) and k in d:
        return d[k]
    return ""


def _list_contains(evaluator, args):
    """检查列表是否包含元素，返回 TritValue(1/0)。"""
    lst = args[0] if isinstance(args[0], list) else evaluator.eval(args[0])
    item = evaluator.eval(args[1])
    if isinstance(lst, (list, tuple)):
        return TritValue(1 if item in lst else 0)
    return TritValue(0)


def _list_len(evaluator, args):
    """返回列表长度。"""
    lst = args[0] if isinstance(args[0], list) else evaluator.eval(args[0])
    if isinstance(lst, (list, tuple)):
        return TritValue(len(lst))
    return TritValue(0)


def _dict_len(evaluator, args):
    """返回字典键数量。"""
    d = args[0] if isinstance(args[0], dict) else evaluator.eval(args[0])
    if isinstance(d, dict):
        return TritValue(len(d))
    return TritValue(0)


def _list_get_safe(evaluator, args):
    """安全列表取值，索引越界返回空串。"""
    lst = args[0] if isinstance(args[0], list) else evaluator.eval(args[0])
    idx = evaluator.eval(args[1])
    if isinstance(idx, TritValue):
        idx = idx.to_int()
    if isinstance(lst, (list, tuple)) and isinstance(idx, int) and 0 <= idx < len(lst):
        val = lst[idx]
        return val
    return ""


def _list_contains(evaluator, args):
    """检查列表是否包含元素，返回 TritValue(1/0)。"""
    lst = evaluator.eval(args[0])
    item = evaluator.eval(args[1])
    if isinstance(lst, (list, tuple)):
        return TritValue(1 if item in lst else 0)
    return TritValue(0)


def _list_len(evaluator, args):
    """返回列表长度。"""
    lst = args[0] if isinstance(args[0], list) else evaluator.eval(args[0])
    if isinstance(lst, (list, tuple)):
        return TritValue(len(lst))
    return TritValue(0)


def _dict_len(evaluator, args):
    """返回字典键数量。"""
    d = evaluator.eval(args[0])
    if isinstance(d, dict):
        return TritValue(len(d))
    return TritValue(0)


def _list_get_safe(evaluator, args):
    """安全列表取值，索引越界返回空串。"""
    lst = evaluator.eval(args[0])
    idx = evaluator.eval(args[1])
    if isinstance(idx, TritValue):
        idx = idx.to_int()
    if isinstance(lst, (list, tuple)) and 0 <= idx < len(lst):
        return lst[idx]
    return ""


def _list_append(evaluator, args):
    """列表追加元素，返回列表本身。"""
    lst = args[0] if isinstance(args[0], list) else evaluator.eval(args[0])
    item = evaluator.eval(args[1])
    if isinstance(lst, list):
        lst.append(item)
    return lst


def _dict_keys(evaluator, args):
    """返回字典所有键的列表。"""
    d = args[0] if isinstance(args[0], dict) else evaluator.eval(args[0])
    if isinstance(d, dict):
        return list(d.keys())
    return []


def _dict_new_empty(evaluator, args):
    return {}


def _list_new_empty(evaluator, args):
    return []


def _str_bytelen(evaluator, args):
    """返回字符串 UTF-8 字节长度。"""
    s = evaluator.eval(args[0])
    if isinstance(s, str):
        return TritValue(len(s.encode('utf-8')))
    return TritValue(0)


def _escape_llvm_str(evaluator, args):
    """转义字符串用于 LLVM IR c\"...\" 格式。"""
    s = evaluator.eval(args[0])
    if isinstance(s, str):
        s = s.replace('\\', '\\\\')
        s = s.replace('"', '\\22')
        s = s.replace('\n', '\\0A')
        s = s.replace('\r', '\\0D')
        s = s.replace('\t', '\\09')
        return s
    return ""


def _str_endswith(evaluator, args):
    """检查字符串是否以指定后缀结尾。"""
    s = evaluator.eval(args[0])
    suffix = evaluator.eval(args[1])
    if isinstance(s, str) and isinstance(suffix, str):
        return TritValue(1 if s.rstrip().endswith(suffix.strip()) else 0)
    return TritValue(0)


def _str_contains(evaluator, args):
    """检查字符串是否包含子串。"""
    s = evaluator.eval(args[0])
    sub = evaluator.eval(args[1])
    if isinstance(s, str) and isinstance(sub, str):
        return TritValue(1 if sub in s else 0)
    return TritValue(0)


def _register_func_name(evaluator, args):
    """注册函数名→ASCII映射，返回映射后的ASCII名。"""
    name = evaluator.eval(args[0])
    if isinstance(name, str) and name not in _func_name_map:
        idx = _func_name_counter[0]
        _func_name_counter[0] += 1
        _func_name_map[name] = f'_m{_module_id}_fn{idx}'
    return _func_name_map.get(name, name)


def _get_func_name(evaluator, args):
    """取函数的ASCII名（用于LLVM IR）。"""
    name = evaluator.eval(args[0])
    if isinstance(name, str):
        return _func_name_map.get(name, name)
    return name


from ops.registry import register as _register

# 非ASCII函数名映射 (Chinese → _mN_fnM)
_func_name_map = {}
_func_name_counter = [0]
_module_id = 0


def _set_module_id(evaluator, args):
    global _module_id, _func_name_map, _func_name_counter
    _module_id = evaluator.eval(args[0]).to_int()
    _func_name_map = {}
    _func_name_counter = [0]
    return TritValue(0)

_register('container_ops_list_contains', _list_contains)

# 合并上下文：用于控制流收敛（供 llvmgen.san handler 使用）
_merge_label = ""


def _set_merge_label(evaluator, args):
    global _merge_label
    _merge_label = evaluator.eval(args[0]) if args else ""
    return TritValue(0)


def _clear_merge_label(evaluator, args):
    global _merge_label
    _merge_label = ""
    return TritValue(0)


def _get_merge_label(*args):
    return _merge_label


_register('container_ops_set_merge_label', _set_merge_label)
_register('container_ops_clear_merge_label', _clear_merge_label)

_label_counter = 0
_reg_counter = 0


def _next_label(evaluator=None, args=None):
    global _label_counter
    _label_counter += 1
    return _label_counter


def _next_reg(evaluator=None, args=None):
    global _reg_counter
    _reg_counter += 1
    return _reg_counter


def _is_terminated(evaluator, args):
    """检查 LLVM IR 文本是否以终止指令 (ret/br) 结尾。返回 TritValue(1)=已终止, TritValue(0)=未终止。"""
    text = evaluator.eval(args[0]) if args else ""
    if not text:
        return TritValue(0)
    last = str(text).rstrip().rsplit('\n', 1)[-1].strip()
    if last.startswith('ret') or last.startswith('br'):
        return TritValue(1)
    return TritValue(0)


_register('container_ops_next_label', _next_label)
_register('container_ops_next_reg', _next_reg)
_register('container_ops_is_terminated', _is_terminated)

_loop_stack_global = []


def _loop_push(evaluator=None, args=None):
    hdr = args[0] if args else ""
    _loop_stack_global.append(hdr)
    return 0


def _loop_pop(evaluator=None, args=None):
    if _loop_stack_global:
        _loop_stack_global.pop()
    return 0


def _loop_top(evaluator=None, args=None):
    if _loop_stack_global:
        return _loop_stack_global[-1]
    return ""


_register('container_ops_loop_push', _loop_push)
_register('container_ops_loop_pop', _loop_pop)
_register('container_ops_loop_top', _loop_top)


def self_hosted_compile(source: str, module_name: str = 'main') -> str:
    """自举编译：sugar.san 解析 + llvmgen.san 生成 IR。零 Python codegen。"""
    from evaluator import SanyanEvaluator
    from skin import SkinManager
    from ops.file_ops import clear_cache
    import os

    clear_cache()
    evaluator = SanyanEvaluator(skin_manager=SkinManager('chinese'))
    # 注册辅助函数
    from ops.container_ops import ContainerOps

    evaluator.commands['新字典'] = ([], [['return', ['container_ops_dict_new_empty']]], {}, None)
    _register('container_ops_dict_new_empty', _dict_new_empty)
    evaluator.commands['存变量'] = (['d', 'k', 'v'], [['container_ops_dict_set', 'd', 'k', 'v']], {}, None)
    evaluator.commands['新列表'] = ([], [['return', ['container_ops_list_new_empty']]], {}, None)
    _register('container_ops_list_new_empty', _list_new_empty)
    # 字符串字节长度 (UTF-8)
    evaluator.commands['取字长'] = (['s'], [['container_ops_str_bytelen', 's']], {}, None)
    _register('container_ops_str_bytelen', _str_bytelen)
    # LLVM IR 字符串转义
    evaluator.commands['转义LLVM字符串'] = (['s'], [['container_ops_str_escape_llvm', 's']], {}, None)
    _register('container_ops_str_escape_llvm', _escape_llvm_str)
    # 字符串后缀检查
    evaluator.commands['后缀'] = (['s', 'suffix'], [['container_ops_str_endswith', 's', 'suffix']], {}, None)
    _register('container_ops_str_endswith', _str_endswith)
    # 模块ID设置
    evaluator.commands['设置模块ID'] = (['mid'], [['container_ops_set_module_id', 'mid']], {}, None)
    _register('container_ops_set_module_id', _set_module_id)
    # 字符串包含检查
    evaluator.commands['字符串包含'] = (['s', 'sub'], [['container_ops_str_contains', 's', 'sub']], {}, None)
    _register('container_ops_str_contains', _str_contains)
    # 非ASCII函数名映射 (Chinese → _fnN, 使用模块级全局变量)
    evaluator.commands['注册函数名'] = (['name'], [['container_ops_register_func_name', 'name']], {}, None)
    _register('container_ops_register_func_name', _register_func_name)
    evaluator.commands['取函数名'] = (['name'], [['container_ops_get_func_name', 'name']], {}, None)
    _register('container_ops_get_func_name', _get_func_name)

    _register('container_ops_dict_set', ContainerOps.dict_set)
    # 查键: 字典键存在返回 value，否则返回空串
    evaluator.commands['查键'] = (['d', 'k'], [['container_ops_dict_get_safe', 'd', 'k']], {}, None)
    _register('container_ops_dict_get_safe', _dict_get_safe)
    # 包含: 列表包含检查
    evaluator.commands['包含'] = (['lst', 'item'], [['container_ops_list_contains', 'lst', 'item']], {}, None)
    # 列表取长: 获取列表长度
    evaluator.commands['列表取长'] = (['lst'], [['container_ops_list_len', 'lst']], {}, None)
    _register('container_ops_list_len', _list_len)
    # 字典取长: 获取字典键数量
    evaluator.commands['字典取长'] = (['d'], [['container_ops_dict_len', 'd']], {}, None)
    _register('container_ops_dict_len', _dict_len)
    # 列表取: 安全列表取值，索引越界返回空串
    evaluator.commands['列表取'] = (['lst', 'idx'], [['container_ops_list_get_safe', 'lst', 'idx']], {}, None)
    # 列表追加: lst.append(item)，返回列表本身
    evaluator.commands['列表追加'] = (['lst', 'item'], [['container_ops_list_append', 'lst', 'item']], {}, None)
    _register('container_ops_list_append', _list_append)
    # 字典取所有键
    evaluator.commands['字典键列表'] = (['d'], [['container_ops_dict_keys', 'd']], {}, None)
    _register('container_ops_dict_keys', _dict_keys)
    # 合并上下文控制
    evaluator.commands['进入合并上下文'] = (['label'], [['container_ops_set_merge_label', 'label']], {}, None)
    evaluator.commands['退出合并上下文'] = ([], [['container_ops_clear_merge_label']], {}, None)
    evaluator.commands['取合并标签'] = ([], [['return', ['container_ops_get_merge_label']]], {}, None)
    _register('container_ops_get_merge_label', _get_merge_label)
    _register('container_ops_list_get_safe', _list_get_safe)

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
    evaluator.commands['列表追加'] = (['lst', 'item'], [['container_ops_list_append', 'lst', 'item']], {}, None)
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
    ir = evaluator.eval(['编译顶层', module_ast])
    return ir if isinstance(ir, str) else ''


def _merge_ir_modules(ir_parts: list[str]) -> str:
    """合并多个LLVM IR模块，去重define/declare。"""
    if not ir_parts:
        return ""
    result = ""
    seen_defines = set()
    seen_declares = set()
    for i, part in enumerate(ir_parts):
        for line in part.split('\n'):
            s = line.strip()
            if i > 0 and ('target triple' in s or 'ModuleID' in s):
                continue
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
