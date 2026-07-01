"""文件读取、写出、模块加载与导入"""

import os
import sys
from core.ternary_core import TritValue
from core.values import (
    SanyanError,
    SanyanSyntaxError,
    SanyanValueError,
    SanyanNameError,
    SanyanTypeError,
    SanyanRuntimeError,
    SanyanIOError,
    ModuleValue,
)
from core.skin import SkinManager
from ops.registry import register, register_alias


# 项目根目录：文件操作不允许超越此目录
def _find_project_root() -> str:
    """查找项目根目录（含 stdlib/ 的目录）。

    开发环境：模块在 ops/file_ops.py → 上级目录
    pip 安装：模块在 site-packages/ops/file_ops.py → 需搜索 CWD
    """
    # 从模块目录向上查找含 stdlib/ 的目录
    d = os.path.dirname(os.path.abspath(__file__))
    for _ in range(6):
        if os.path.isdir(os.path.join(d, 'stdlib')):
            return d
        d = os.path.dirname(d)
    # 回退：从 CWD 向上查找
    d = os.getcwd()
    for _ in range(6):
        if os.path.isdir(os.path.join(d, 'stdlib')):
            return d
        d = os.path.dirname(d)
    # 最后回退
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


_PROJECT_ROOT = _find_project_root()
_SAFE_PATH_SEPARATORS = frozenset({'/', '\\'})
_module_cache: dict = {}
_import_stack: set = set()
_sugar_parser_module = None

# 最大循环步数
BOOTSTRAP_MAX_LOOP = 50000
SUGAR_MODULE_MAX_LOOP = 100000
TEMP_ENV_MAX_LOOP = 50000


def clear_cache():
    """清理模块缓存，用于测试隔离。

    保留 _sugar_parser_module 缓存：sugar.san 解析器加载开销大（938 行），
    且无状态副作用，跨调用复用安全。
    """
    _module_cache.clear()
    _import_stack.clear()


def _get_cache(evaluator) -> tuple[dict, set]:
    """获取模块缓存和导入栈（优先使用 evaluator 实例属性）。"""
    if hasattr(evaluator, '_module_cache'):
        return evaluator._module_cache, evaluator._import_stack
    return _module_cache, _import_stack


def _resolve_path(raw_path, auto_stdlib=True):
    path = str(raw_path)
    norm = os.path.normpath(path)
    parts = norm.replace('\\', '/').split('/')
    if '..' in parts:
        raise SanyanValueError(f"路径不允许包含 '..': {raw_path}")
    abs_path = os.path.abspath(norm)
    # 允许系统临时目录（测试用）
    import tempfile

    tmp_root = os.path.abspath(tempfile.gettempdir())
    if not abs_path.startswith(os.path.abspath(_PROJECT_ROOT)) and not abs_path.startswith(tmp_root):
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


def _load_sugar_from_bin(sugar_bin):
    """从预编译 sugar.bin 创建 ModuleValue，执行初始化后通过 VM 导出函数代理调用。"""
    from vm import VM
    from core.values import ModuleValue

    try:
        vm = VM.from_bin(sugar_bin)
    except Exception:
        return None

    exports = set(vm.exports.keys())
    if '解析' not in exports:
        return None

    commands = {}
    for name in exports:
        commands[name] = ([], [])
    mod = ModuleValue({}, commands, exports)

    # 存储 VM 引用，通过 call 代理到 VM._exec_frame
    mod.vars['__sugar_vm__'] = vm
    mod.vars['__sugar_exports__'] = exports
    return mod


# 增强 ModuleValue.call 以支持 sugar VM 回退
_orig_module_call = ModuleValue.call


def _enhanced_module_call(self, evaluator, args):
    vm = self.vars.get('__sugar_vm__')
    if vm is None or not args:
        return _orig_module_call(self, evaluator, args)
    func_name = args[0]
    func_args = args[1:]
    exports = self.vars.get('__sugar_exports__', set())
    if func_name in exports:
        addr = vm.exports.get(func_name)
        if addr is not None:
            import io

            old_stdout = sys.stdout
            sys.stdout = io.StringIO()
            try:
                vm._exec_frame(vm.code, addr, func_args)
                result = vm.stack[-1] if vm.stack else None
            except Exception:
                result = None
            finally:
                sys.stdout = old_stdout
            if isinstance(result, TritValue) and result.to_int() in (-1, 0):
                return None
            return result
    return _orig_module_call(self, evaluator, args)


ModuleValue.call = _enhanced_module_call  # type: ignore[method-assign]


def _load_sugar_parser(evaluator):
    """预加载 stdlib/sugar.san 作为 Sanyan 模块（自举引导），缓存备用。"""
    global _sugar_parser_module
    if _sugar_parser_module is not None:
        return _sugar_parser_module

    sugar_bin = os.path.join('stdlib', 'sugar.bin')

    # 优先从预编译 sugar.bin 加载（执行模块初始化后使用 VM 导出函数）
    if os.path.exists(sugar_bin):
        mod = _load_sugar_from_bin(sugar_bin)
        if mod is not None:
            _sugar_parser_module = mod
            return mod

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

    from core.values import ReturnException
    from core.lexer import tokenize
    from core.parser import parse
    from core.evaluator import SanyanEvaluator

    skin_mgr = evaluator.skin_manager if evaluator and evaluator.skin_manager else SkinManager('chinese')

    # Phase 1: 引导 — 用 Python 简单解析器加载 _bootstrap.san（S-表达式）
    if not os.path.exists(bootstrap_path):
        return None
    with open(bootstrap_path, 'r', encoding='utf-8') as f:
        bootstrap_code = f.read()
    if not bootstrap_code.strip():
        return None

    try:
        bootstrap_tokens = tokenize(bootstrap_code)
        bootstrap_ast = parse(bootstrap_tokens)
    except SyntaxError:
        return None

    bootstrap_env = SanyanEvaluator(skin_manager=skin_mgr, max_loop_steps=BOOTSTRAP_MAX_LOOP)
    try:
        bootstrap_env.eval(bootstrap_ast)
    except (SanyanError, SyntaxError, RecursionError):
        return None

    # Phase 2: 用 bootstap 的 解析 解析 sugar.san
    cmd_def = bootstrap_env.commands.get('解析')
    if cmd_def is None:
        return None

    body = cmd_def[1]
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
    except (SanyanError, SyntaxError, RecursionError):
        return None

    if sugar_ast is None:
        return None

    # Phase 3: 评估 sugar.san AST
    module_env = SanyanEvaluator(skin_manager=skin_mgr, max_loop_steps=SUGAR_MODULE_MAX_LOOP)
    try:
        module_env.eval(sugar_ast)
    except (SanyanError, SyntaxError, RecursionError):
        return None

    exports = _collect_exports(sugar_ast) or {'词法分析', '解析'}
    _sugar_parser_module = ModuleValue(module_env.scope_vars, module_env.commands, exports)
    return _sugar_parser_module


def _parse_with_python_converter(code, evaluator):
    """使用 Python SugarConverter 解析糖语法代码（VM 解析器的可靠回退）。"""
    from sugar import SugarConverter

    try:
        ast = SugarConverter.convert(code, evaluator.skin_manager)
        if isinstance(ast, list):
            return ast
    except SyntaxError:
        pass
    return None


def _parse_with_sugar_san(code, evaluator):
    """使用 stdlib/sugar.san 的 解析 函数解析糖语法代码。"""
    parser = _load_sugar_parser(evaluator)
    if parser is None:
        return None
    try:
        from core.evaluator import SanyanEvaluator

        temp_env = SanyanEvaluator(skin_manager=evaluator.skin_manager, max_loop_steps=TEMP_ENV_MAX_LOOP)
        result = parser.call(temp_env, ['解析', code])
        if isinstance(result, TritValue):
            iv = result.to_int()
            if iv == -1 or iv == 0:
                return None
        # VM 解析器返回非列表结果时，回退到 Python SugarConverter
        if not isinstance(result, list):
            result = _parse_with_python_converter(code, evaluator)
        return result
    except (
        SanyanNameError,
        SanyanSyntaxError,
        SanyanTypeError,
        SanyanValueError,
        SanyanRuntimeError,
        SyntaxError,
        ZeroDivisionError,  # sugar.san 解析引擎在CI环境的除零
    ):
        return None


def _parse_code(code, evaluator):
    """解析代码：#include 预处理 → SugarConverter → sugar.san 自举解析 → S-表达式降级。"""
    from core.preprocess import preprocess_includes

    code = preprocess_includes(code)
    # 优先 Python 原生 SugarConverter（跨平台一致性最优）
    try:
        from sugar import SugarConverter

        ast = SugarConverter.convert(code, evaluator.skin_manager)
        if isinstance(ast, list):
            return ast
    except SyntaxError:
        pass
    # S-表达式检测：以 ( 或 （ 开头的代码直接用 S-表达式解析器，不走 sugar.san 自举路径
    stripped = code.strip()
    if (stripped.startswith('(') and stripped.count('(') == stripped.count(')')) or (
        stripped.startswith('\uff08') and stripped.count('\uff08') == stripped.count('\uff09')
    ):
        from core.lexer import tokenize
        from core.parser import parse

        wrapped = '(do\n' + code + '\n)'
        tokens = tokenize(wrapped)
        return parse(tokens)
    # 备选：sugar.san 自举解析器（如果可用）
    ast = _parse_with_sugar_san(code, evaluator)
    if isinstance(ast, list):
        return ast
    # 最后：S-表达式降级
    from core.lexer import tokenize
    from core.parser import parse

    wrapped = '(do\n' + code + '\n)'
    tokens = tokenize(wrapped)
    return parse(tokens)


def _parse_and_eval_file(code, evaluator):
    """解析并执行文件代码（sugar.san 自举解析 → S-表达式降级）。"""
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
        """导入模块，支持可选别名：导入 "path" 或 导入 "path" 为 alias"""
        if len(args) < 1:
            raise SanyanSyntaxError('导入 需要一个文件路径')
        path = evaluator.eval(args[0])
        if hasattr(path, 'to_int'):
            path = str(path.to_int())
        path = _resolve_path(path)

        # 解析别名：导入 "path" 为 alias
        alias = None
        if len(args) >= 3:
            # args[1] 可能是 '为' 或 'as'（关键字），args[2] 是别名
            alias_arg = args[2] if isinstance(args[1], str) and args[1] in ('为', 'as') else args[-1]
            alias = evaluator.eval(alias_arg) if not isinstance(alias_arg, str) else alias_arg
            if isinstance(alias, str) and alias in ('为', 'as'):
                alias = None  # 关键字不是别名

        abs_path = os.path.abspath(path)

        # 使用 evaluator 实例缓存（多实例隔离）
        cache, stack = _get_cache(evaluator)

        # 循环依赖检测
        if abs_path in stack:
            raise SanyanValueError(f'循环依赖检测: {path} 已在导入链中')

        if abs_path in cache:
            module = cache[abs_path]
            if alias:
                evaluator.scope_vars[alias] = module
            return module

        try:
            with open(path, 'r', encoding='utf-8') as f:
                code = f.read()
        except (IOError, OSError) as e:
            raise SanyanIOError(f'导入文件失败: {e}')
        if not code.strip():
            module = ModuleValue({}, {})
            if alias:
                evaluator.scope_vars[alias] = module
            return module

        from core.evaluator import SanyanEvaluator

        module_env = SanyanEvaluator(skin_manager=evaluator.skin_manager)
        ast = _parse_code(code, module_env)

        # 收集导出声明
        exports = _collect_exports(ast)

        # 执行模块
        stack.add(abs_path)
        try:
            module_env.eval(ast)
        finally:
            stack.discard(abs_path)

        module = ModuleValue(module_env.scope_vars, module_env.commands, exports)
        cache[abs_path] = module
        if alias:
            evaluator.scope_vars[alias] = module
        return module

    # 注册文件操作
    @staticmethod
    def write_binary_op(evaluator, args):
        """写二进制文件：路径和整数列表 → 原始字节写入。"""
        if len(args) != 2:
            raise SanyanSyntaxError('写二进制 需要路径和字节列表')
        path = evaluator.eval(args[0])
        data = evaluator.eval(args[1])
        if hasattr(path, 'to_int'):
            path = str(path.to_int())
        path = _resolve_path(path, auto_stdlib=False)
        if not isinstance(data, list):
            raise SanyanTypeError('第二个参数必须是整数列表')
        raw_bytes = bytearray()
        for b in data:
            if isinstance(b, TritValue):
                b = b.to_int()
            if isinstance(b, str):
                b = int(b) if b.isdigit() or (b.startswith('-') and b[1:].isdigit()) else ord(b[0])
            raw_bytes.append(b & 0xFF)
        try:
            with open(str(path), 'wb') as f:
                f.write(bytes(raw_bytes))
        except (IOError, OSError) as e:
            raise SanyanIOError(f'写二进制失败: {e}')
        return TritValue(0)


register('read_file', FileOps.read_file_op)
register('write_file', FileOps.write_file_op)
register('write_binary', FileOps.write_binary_op)
register('load', FileOps._load_file)
register('import', FileOps.import_module)

# 中文别名
_ra = register_alias
_ra('读文件', 'read_file')
_ra('写文件', 'write_file')
