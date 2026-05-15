"""文件读取、写出、模块加载与导入"""
import os
from ternary_core import TritValue
from values import SanyanSyntaxError, SanyanValueError, ModuleValue

_SAFE_PATH_SEPARATORS = frozenset({'/', '\\'})
_module_cache = {}

def _resolve_path(raw_path, auto_stdlib=True):
    """路径解析与安全校验，防止目录穿越。"""
    path = str(raw_path)
    for sep in _SAFE_PATH_SEPARATORS:
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
        module_env.eval(ast)
        module = ModuleValue(module_env.vars, module_env.commands)
        _module_cache[abs_path] = module
        return module
