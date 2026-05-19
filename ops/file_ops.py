"""文件读取、写出、模块加载与导入"""

import os
from ternary_core import TritValue
from values import SanyanSyntaxError, SanyanValueError, SanyanNameError, SanyanTypeError, SanyanIOError, ModuleValue
from skin import SkinManager
from ops.registry import register

# 项目根目录：文件操作不允许超越此目录
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
_SAFE_PATH_SEPARATORS = frozenset({'/', '\\'})
_module_cache: dict = {}
_import_stack: set = set()
_sugar_parser_module = None


def clear_cache():
    """清理模块缓存，用于测试隔离。"""
    _module_cache.clear()
    _import_stack.clear()
    global _sugar_parser_module
    _sugar_parser_module = None


def _resolve_path(raw_path, auto_stdlib=True):
    path = str(raw_path)
    norm = os.path.normpath(path)
    parts = norm.replace('\\', '/').split('/')
    if '..' in parts:
        raise SanyanValueError(f"路径不允许包含 '..': {raw_path}")
    abs_path = os.path.abspath(norm)
    if not abs_path.startswith(os.path.abspath(_PROJECT_ROOT)):
        raise SanyanValueError(f'路径不在项目根目录内: {raw_path}')
    if auto_stdlib and not any(s in path for s in _SAFE_PATH_SEPARATORS) and not path.endswith('.san'):
        # 支持嵌套导入 a.b.c → stdlib/a/b/c.san 或 stdlib/a/b/c/package.san
        if '.' in path:
            dotted = path.replace('.', '/')
            candidate = os.path.join('stdlib', dotted + '.san')
            if os.path.exists(candidate):
                return candidate
            candidate_pkg = os.path.join('stdlib', dotted, 'package.san')
            if os.path.exists(candidate_pkg):
                return candidate_pkg
        candidate = os.path.join('stdlib', path + '.san')
        if os.path.exists(candidate):
            return candidate
    return norm


def _load_sugar_parser(evaluator):
    """预加载 stdlib/sugar.san 作为 Sanyan 模块（自举引导），缓存备用。"""
    global _sugar_parser_module
    if _sugar_parser_module is not None:
        return _sugar_parser_module

    sugar_path = os.path.join('stdlib', 'sugar.san')
    bootstrap_path = os.path.join('stdlib', '_bootstrap.san')
    if not os.path.exists(sugar_path):
        return None

    try:
        with open(sugar_path, 'r', encoding='utf-8') as f:
            sugar_code = f.read()
    except (IOError, OSError):
        return None
    if not sugar_code.strip():
        return None

    from values import ReturnException
    from lexer import tokenize
    from parser import parse
    from evaluator import SanyanEvaluator

    skin_mgr = evaluator.skin_manager if evaluator and evaluator.skin_manager else SkinManager('chinese')

    # Phase 1: 引导 — 用 Python 简单解析器加载 _bootstrap.san（S-表达式）
    if not os.path.exists(bootstrap_path):
        return _fallback_convert(sugar_code, skin_mgr)
    with open(bootstrap_path, 'r', encoding='utf-8') as f:
        bootstrap_code = f.read()
    if not bootstrap_code.strip():
        return _fallback_convert(sugar_code, skin_mgr)

    try:
        bootstrap_tokens = tokenize(bootstrap_code)
        bootstrap_ast = parse(bootstrap_tokens)
    except SyntaxError:
        return _fallback_convert(sugar_code, skin_mgr)

    bootstrap_env = SanyanEvaluator(skin_manager=skin_mgr, max_loop_steps=50000)
    try:
        bootstrap_env.eval(bootstrap_ast)
    except Exception:
        return _fallback_convert(sugar_code, skin_mgr)

    # Phase 2: 用 bootstap 的 解析 解析 sugar.san
    cmd_def = bootstrap_env.commands.get('解析')
    if cmd_def is None:
        return _fallback_convert(sugar_code, skin_mgr)

    params, body = cmd_def[0], cmd_def[1]
    sugar_ast = None
    try:
        bootstrap_env.push_scope()
        bootstrap_env.set_var('source', sugar_code)
        for expr in body:
            try:
                bootstrap_env.eval(expr)
            except ReturnException as ret:
                sugar_ast = ret.value
                break
        bootstrap_env.pop_scope()
    except Exception:
        return _fallback_convert(sugar_code, skin_mgr)

    if sugar_ast is None:
        return _fallback_convert(sugar_code, skin_mgr)

    # Phase 3: 评估 sugar.san AST
    module_env = SanyanEvaluator(skin_manager=skin_mgr, max_loop_steps=100000)
    try:
        module_env.eval(sugar_ast)
    except Exception:
        return _fallback_convert(sugar_code, skin_mgr)

    exports = _collect_exports(sugar_ast) or {'词法分析', '解析'}
    _sugar_parser_module = ModuleValue(module_env.scope_vars, module_env.commands, exports)
    return _sugar_parser_module


def _fallback_convert(sugar_code, skin_mgr):
    """回退：使用 Python SugarConverter 转换 sugar.san（当 bootstrap 不可用/失败时）。"""
    from sugar import SugarConverter
    ast = SugarConverter.convert(sugar_code, skin_mgr)
    if ast is None:
        return None
    from evaluator import SanyanEvaluator
    module_env = SanyanEvaluator(skin_manager=skin_mgr)
    module_env.eval(ast)
    exports = _collect_exports(ast) or {'词法分析', '解析'}
    return ModuleValue(module_env.scope_vars, module_env.commands, exports)


def _parse_with_sugar_san(code, evaluator):
    """使用 stdlib/sugar.san 的 解析 函数解析糖语法代码。"""
    parser = _load_sugar_parser(evaluator)
    if parser is None:
        return None
    try:
        from evaluator import SanyanEvaluator

        temp_env = SanyanEvaluator(skin_manager=evaluator.skin_manager, max_loop_steps=50000)
        result = parser.call(temp_env, ['解析', code])
        if isinstance(result, TritValue):
            iv = result.to_int()
            if iv == -1 or iv == 0:
                return None
        return result
    except (SanyanNameError, SanyanSyntaxError, SanyanTypeError, SanyanValueError, SyntaxError):
        return None


def _parse_code(code, evaluator):
    """解析代码：sugar.san 自举 → Python SugarConverter → S-表达式降级。"""
    ast = _parse_with_sugar_san(code, evaluator)
    if ast is not None:
        return ast
    from sugar import SugarConverter

    try:
        return SugarConverter.convert(code, evaluator.skin_manager)
    except SyntaxError:
        pass
    from lexer import tokenize
    from parser import parse

    tokens = tokenize(code)
    return parse(tokens)


def _parse_and_eval_file(code, evaluator):
    """解析并执行文件代码（sugar.san 自举优先 → Python SugarConverter → S 表达式）。"""
    ast = _parse_code(code, evaluator)
    return evaluator.eval(ast) if ast is not None else TritValue(0)


def _collect_exports(ast):
    """从 AST 中收集导出声明。"""
    exports = set()
    if not isinstance(ast, list):
        return None  # None 表示未显式声明导出
    if ast[0] == 'do':
        statements = ast[1:]
    else:
        statements = [ast]
    for stmt in statements:
        if isinstance(stmt, list) and len(stmt) > 0 and stmt[0] == 'export':
            for name in stmt[1:]:
                exports.add(name)
    return exports if exports else None


class FileOps:
    """文件操作：读取、写出、模块加载与导入"""

    @staticmethod
    def read_file_op(evaluator, args):
        if len(args) != 1:
            raise SanyanSyntaxError('读文件 需要文件路径')
        path = evaluator.eval(args[0])
        if hasattr(path, 'to_int'):
            path = str(path.to_int())
        path = _resolve_path(path, auto_stdlib=False)
        try:
            with open(str(path), 'r', encoding='utf-8') as f:
                content = f.read()
        except (IOError, OSError) as e:
            raise SanyanIOError(f'读文件失败: {e}')
        return content

    @staticmethod
    def write_file_op(evaluator, args):
        if len(args) != 2:
            raise SanyanSyntaxError('写文件 需要路径和内容')
        path = evaluator.eval(args[0])
        content = evaluator.eval(args[1])
        if hasattr(path, 'to_int'):
            path = str(path.to_int())
        path = _resolve_path(path, auto_stdlib=False)
        if not isinstance(content, str):
            content = str(content)
        try:
            with open(str(path), 'w', encoding='utf-8') as f:
                f.write(content)
        except (IOError, OSError) as e:
            raise SanyanIOError(f'写文件失败: {e}')
        return TritValue(0)

    @staticmethod
    def _load_file(evaluator, args):
        if len(args) != 1:
            raise SanyanSyntaxError('加载 需要文件路径')
        path = evaluator.eval(args[0])
        if isinstance(path, str):
            path = _resolve_path(path)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                code = f.read()
        except (IOError, OSError) as e:
            raise SanyanIOError(f'加载文件失败: {e}')
        if not code.strip():
            return TritValue(0)
        return _parse_and_eval_file(code, evaluator)

    @staticmethod
    def import_module(evaluator, args):
        if len(args) != 1:
            raise SanyanSyntaxError('导入 需要一个文件路径')
        path = evaluator.eval(args[0])
        if hasattr(path, 'to_int'):
            path = str(path.to_int())
        path = _resolve_path(path)

        abs_path = os.path.abspath(path)

        # 循环依赖检测
        if abs_path in _import_stack:
            raise SanyanValueError(f'循环依赖检测: {path} 已在导入链中')

        if abs_path in _module_cache:
            return _module_cache[abs_path]

        try:
            with open(path, 'r', encoding='utf-8') as f:
                code = f.read()
        except (IOError, OSError) as e:
            raise SanyanIOError(f'导入文件失败: {e}')
        if not code.strip():
            return ModuleValue({}, {})

        from evaluator import SanyanEvaluator

        module_env = SanyanEvaluator(skin_manager=evaluator.skin_manager)
        ast = _parse_code(code, module_env)

        # 收集导出声明
        exports = _collect_exports(ast)

        # 执行模块
        _import_stack.add(abs_path)
        try:
            module_env.eval(ast)
        finally:
            _import_stack.discard(abs_path)

        module = ModuleValue(module_env.scope_vars, module_env.commands, exports)
        _module_cache[abs_path] = module
        return module


# 注册文件操作
register('read_file', FileOps.read_file_op)
register('write_file', FileOps.write_file_op)
register('load', FileOps._load_file)
register('import', FileOps.import_module)
