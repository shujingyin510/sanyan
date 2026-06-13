"""三言 → LLVM 编译器入口"""

from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING, Any, cast

from llvmgen.codegen import compile_top_level
from llvmgen.ir_fixes import (
    _fix_missing_constants,
    _fix_rt_list_get_null_safe,
    _fix_terminators,
)

if TYPE_CHECKING:
    from llvmgen.codegen import CodegenContext


def _is_paren_sexpr(source: str) -> bool:
    """判断源码是否为 S 表达式语法（以 '(' 开头）。"""
    stripped = source.strip()
    return stripped.startswith('(')


def _has_chinese_keywords(ast: list) -> bool:
    """检测 AST 是否含 LLVM 编译器无法处理的中文关键字。"""
    # 只检测 LLVM 代码生成器不支持的（try/捕获/尝试 已支持）
    chinese_kw = {'再若', '遍历', '跳出', '继续', '导出', '判'}
    for node in ast:
        if isinstance(node, str) and node in chinese_kw:
            return True
        if isinstance(node, list):
            if _has_chinese_keywords(node):
                return True
    return False


def _parse_all_sexprs(source: str) -> list | None:
    """解析源码中所有顶层 S 表达式，返回列表的列表。

    单表达式时直接返回（兼容旧版 _parse_source 行为）；
    多表达式时返回 [expr1, expr2, ...]。
    """
    from lexer import tokenize

    tokens = tokenize(source)
    if not tokens:
        return None

    # 用可变位置追踪器替代 parse 的局部 pos
    pos = [0]

    def _next():
        if pos[0] >= len(tokens):
            return None
        tok = tokens[pos[0]]
        pos[0] += 1
        return tok

    def _peek():
        if pos[0] >= len(tokens):
            return None
        return tokens[pos[0]]

    def _parse_one():
        tok = _next()
        if tok is None:
            return None
        if tok == '(':
            L = []
            while _peek() is not None and _peek() != ')':
                child = _parse_one()
                if child is not None:
                    L.append(child)
            if _peek() == ')':
                _next()  # 跳过 ')'
            return L
        elif tok == ')':
            return None
        return tok

    results = []
    while pos[0] < len(tokens):
        parsed = _parse_one()
        if parsed is None:
            break
        results.append(parsed)

    if not results:
        return None
    if len(results) == 1:
        return results[0]
    return results


def _parse_source(source: str) -> list:
    from ops.file_ops import _parse_with_sugar_san, clear_cache
    from evaluator import SanyanEvaluator

    clear_cache()
    evaluator = SanyanEvaluator()

    if _is_paren_sexpr(source):
        # S 表达式语法：先用 S 表达式解析器
        # 1. Python S 表达式解析器（批量解析）
        try:
            parsed = _parse_all_sexprs(source)
            if parsed is not None:
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
                # 检查是否含中文关键字（说明 SugarConverter 失败回退到 sugar.san）
                if not _has_chinese_keywords(parsed):
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

        # 4. Python S 表达式解析器（fallback，批量解析）
        try:
            parsed = _parse_all_sexprs(source)
            if parsed is not None:
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
    """自举编译：sugar.san 解析 + llvmgen.san 生成 IR。

    V5: 辅助函数已内联到 llvmgen.san，无需 Python 注入。
    直接加载 .san 文件，用 Python evaluator 运行即可。
    """
    from evaluator import SanyanEvaluator
    from skin import SkinManager
    from ops.file_ops import clear_cache

    clear_cache()
    evaluator = SanyanEvaluator(skin_manager=SkinManager('chinese'))

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
    evaluator._op_cache.clear()
    ir_text = evaluator.eval(['编译顶层', ast])
    if not isinstance(ir_text, str):
        raise RuntimeError(f'llvmgen.san 生成失败: {type(ir_text).__name__}')

    return ir_text


def compile_module_test(module_name: str) -> str:
    """编译单个 .san 模块到 LLVM IR（测试用）。

    V5: 辅助函数已内联到 llvmgen.san，无需 Python 注入。
    """
    from evaluator import SanyanEvaluator
    from skin import SkinManager
    from ops.file_ops import clear_cache

    clear_cache()
    evaluator = SanyanEvaluator(skin_manager=SkinManager('chinese'))

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

    return ir_text if isinstance(ir_text, str) else ''


def compile_to_object(source: str, module_name: str = 'main') -> bytes:
    """编译三言源码到目标文件 (.o)，不依赖外部 llc。

    使用 llvmlite 内置 TargetMachine.emit_object()，
    Windows 上若 targets 未注册则回退为 None。
    """
    from llvmlite import binding

    ir_text, cg = compile_source(source, module_name)
    if not ir_text:
        raise RuntimeError('IR 生成失败')

    try:
        tm = binding.Target.from_default_triple().create_target_machine()
        obj = tm.emit_object(cg.module)
        return bytes(obj)
    except RuntimeError:
        return None  # Windows 上无 target，回退 llc


def compile_to_executable(
    source: str,
    output_path: str,
    module_name: str = 'main',
) -> bool:
    """一步编译三言源码到可执行文件。

    优先使用 llvmlite 内置 codegen，回退到 llc + gcc。
    """
    import tempfile

    obj_data = compile_to_object(source, module_name)
    rt_src = os.path.join(os.path.dirname(__file__), 'runtime.c')
    if not os.path.exists(rt_src):
        return False

    with tempfile.TemporaryDirectory() as tmpdir:
        obj_path = os.path.join(tmpdir, f'{module_name}.o')
        rt_obj = os.path.join(tmpdir, 'runtime.o')

        if obj_data:
            # 直接写入 llvmlite 编译的目标文件
            with open(obj_path, 'wb') as f:
                f.write(obj_data)
        else:
            # 回退到 llc
            from utils.compiler_tools import find_llc, run_in_shell, win_to_posix

            llc = find_llc()
            if llc is None:
                return False
            ir_text, _ = compile_source(source, module_name)
            ir_path = os.path.join(tmpdir, f'{module_name}.ll')
            with open(ir_path, 'w', encoding='utf-8') as f:
                f.write(ir_text)
            r = run_in_shell(
                f'{win_to_posix(llc)} {win_to_posix(ir_path)} -filetype=obj -o {win_to_posix(obj_path)}',
                check=False,
                timeout=30,
            )
            if r.returncode != 0:
                return False

        # 编译 runtime + 链接
        from utils.compiler_tools import find_cc, run_in_shell, win_to_posix

        cc = find_cc()
        if cc is None:
            return False

        rt = win_to_posix(rt_src)
        rt_obj_posix = win_to_posix(rt_obj)
        r = run_in_shell(f'gcc -c {rt} -o {rt_obj_posix} -std=c99 -O2', check=False, timeout=30)
        if r.returncode != 0:
            return False

        obj_p = win_to_posix(obj_path)
        out_p = win_to_posix(output_path)
        libs = '-lm'
        if sys.platform == 'win32':
            libs += ' -lwinhttp'
        r = run_in_shell(f'gcc {obj_p} {rt_obj_posix} -o {out_p} {libs}', check=False, timeout=30)
        return r.returncode == 0


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
