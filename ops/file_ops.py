"""文件读取、写出、模块加载与导入"""
import os
from ternary_core import TritValue
from values import SanyanSyntaxError, SanyanValueError, ModuleValue

_SAFE_PATH_SEPARATORS = frozenset({'/', '\\'})
_module_cache = {}
_import_stack = set()


def _resolve_path(raw_path, auto_stdlib=True):
    path = str(raw_path)
    parts = path.replace('\\', '/').split('/')
    if '..' in parts:
            raise SanyanValueError(f"路径不允许包含 '..': {raw_path}")
    if auto_stdlib and not any(s in path for s in _SAFE_PATH_SEPARATORS) and not path.endswith('.san'):
        candidate = os.path.join('stdlib', path + '.san')
        if os.path.exists(candidate):
            return candidate
    return path


def _parse_and_eval_file(code, evaluator):
    """解析并执行文件代码（sugar 优先，fallback S 表达式）。"""
    from sugar import SugarConverter
    from lexer import tokenize
    from parser import parse

    try:
        ast = SugarConverter.convert(code, evaluator.skin_manager)
    except SyntaxError:
        tokens = tokenize(code)
        ast = parse(tokens)

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
    @staticmethod
    def read_file_op(evaluator, args):
        if len(args) != 1:
            raise SanyanSyntaxError("读文件 需要文件路径")
        path = evaluator.eval(args[0])
        if hasattr(path, 'to_int'):
            path = str(path.to_int())
        path = _resolve_path(path, auto_stdlib=False)
        try:
            with open(str(path), 'r', encoding='utf-8') as f:
                content = f.read()
        except (IOError, OSError) as e:
            raise SanyanValueError(f"读文件失败: {e}")
        return content

    @staticmethod
    def write_file_op(evaluator, args):
        if len(args) != 2:
            raise SanyanSyntaxError("写文件 需要路径和内容")
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
            raise SanyanValueError(f"写文件失败: {e}")
        return TritValue(0)

    @staticmethod
    def _load_file(evaluator, args):
        if len(args) != 1:
            raise SanyanSyntaxError("加载 需要文件路径")
        path = evaluator.eval(args[0])
        if isinstance(path, str):
            path = _resolve_path(path)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                code = f.read()
        except (IOError, OSError) as e:
            raise SanyanValueError(f"加载文件失败: {e}")
        if not code.strip():
            return TritValue(0)
        return _parse_and_eval_file(code, evaluator)

    @staticmethod
    def import_module(evaluator, args):
        if len(args) != 1:
            raise SanyanSyntaxError("导入 需要一个文件路径")
        path = evaluator.eval(args[0])
        if hasattr(path, 'to_int'):
            path = str(path.to_int())
        path = _resolve_path(path)

        abs_path = os.path.abspath(path)

        # 循环依赖检测
        if abs_path in _import_stack:
            raise SanyanValueError(f"循环依赖检测: {path} 已在导入链中")

        if abs_path in _module_cache:
            return _module_cache[abs_path]

        try:
            with open(path, 'r', encoding='utf-8') as f:
                code = f.read()
        except (IOError, OSError) as e:
            raise SanyanValueError(f"导入文件失败: {e}")
        if not code.strip():
            return ModuleValue({}, {})

        from evaluator import SanyanEvaluator
        module_env = SanyanEvaluator(skin_manager=evaluator.skin_manager)
        try:
            from sugar import SugarConverter
            ast = SugarConverter.convert(code, module_env.skin_manager)
        except SyntaxError:
            from lexer import tokenize
            from parser import parse
            tokens = tokenize(code)
            ast = parse(tokens)

        # 收集导出声明
        exports = _collect_exports(ast)

        # 执行模块
        _import_stack.add(abs_path)
        try:
            module_env.eval(ast)
        finally:
            _import_stack.discard(abs_path)

        module = ModuleValue(module_env.vars, module_env.commands, exports)
        _module_cache[abs_path] = module
        return module
