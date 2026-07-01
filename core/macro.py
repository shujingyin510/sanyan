"""宏系统：编译期代码生成

功能：
- 定义宏（编译期展开）
- 宏模板（带参数替换）
- 宏嵌套（宏调用宏）

用法：
    从三言代码中使用：
    (定义宏 守护 (条件 体) (若 条件 体 (可能)))
    (守护 (大于 x 0) (输出 "正数"))

    从 Python 中使用：
    from core.macro import MacroEnv
    env = MacroEnv()
    env.define('守护', ['条件', '体'], ['若', '条件', '体', ['可能']])
    expanded = env.expand(['守护', ['大于', 'x', 0], ['输出', '"正数"']])
"""

from __future__ import annotations
from typing import Any, Optional


class Macro:
    """宏定义：带参数的代码模板。"""

    def __init__(self, name: str, params: list[str], body: Any):
        self.name = name
        self.params = params  # 形参名列表
        self.body = body  # 模板体（AST）

    def expand(self, args: list[Any]) -> Any:
        """展开宏：用实参替换模板中的形参。"""
        if len(args) != len(self.params):
            raise ValueError(f'宏 {self.name} 需要 {len(self.params)} 个参数，得到 {len(args)} 个')

        # 构建替换映射
        bindings = dict(zip(self.params, args))

        # 递归替换
        return self._substitute(self.body, bindings)

    def _substitute(self, node: Any, bindings: dict[str, Any]) -> Any:
        """递归替换 AST 节点中的形参。"""
        if isinstance(node, str):
            # 如果是形参名，替换为实参
            if node in bindings:
                return bindings[node]
            return node

        if isinstance(node, list):
            # 递归处理列表
            return [self._substitute(item, bindings) for item in node]

        # 其他类型（数字等）直接返回
        return node


class MacroEnv:
    """宏环境：管理宏定义和展开。"""

    def __init__(self):
        self._macros: dict[str, Macro] = {}

    def define(self, name: str, params: list[str], body: Any) -> None:
        """定义宏。"""
        self._macros[name] = Macro(name, params, body)

    def get(self, name: str) -> Optional[Macro]:
        """获取宏定义。"""
        return self._macros.get(name)

    def has(self, name: str) -> bool:
        """检查宏是否存在。"""
        return name in self._macros

    def expand(self, node: Any) -> Any:
        """展开 AST 中的所有宏。"""
        if not isinstance(node, list) or len(node) == 0:
            return node

        head = node[0]
        if isinstance(head, str):
            macro = self.get(head)
            if macro is not None:
                args = node[1:]
                expanded_args = [self.expand(arg) for arg in args]
                expanded = macro.expand(expanded_args)
                return self.expand(expanded)

        # 非宏调用，递归处理子节点
        return [self.expand(item) for item in node]

    def expand_all(self, ast: Any) -> Any:
        """展开 AST 中的所有宏（从内到外）。"""
        if isinstance(ast, list):
            # 先展开子节点
            expanded = [self.expand_all(item) for item in ast]
            # 再展开当前节点
            return self.expand(expanded)
        return ast

    def list_macros(self) -> list[str]:
        """列出所有已定义的宏名。"""
        return list(self._macros.keys())

    def undefine(self, name: str) -> bool:
        """取消定义宏。"""
        if name in self._macros:
            del self._macros[name]
            return True
        return False


# ── 全局宏环境 ──
_global_macro_env: Optional[MacroEnv] = None


def get_global_macro_env() -> MacroEnv:
    """获取全局宏环境。"""
    global _global_macro_env
    if _global_macro_env is None:
        _global_macro_env = MacroEnv()
    return _global_macro_env


def reset_global_macro_env() -> None:
    """重置全局宏环境。"""
    global _global_macro_env
    _global_macro_env = None


# ── 内置宏 ──
def _register_builtin_macros(env: MacroEnv) -> None:
    """注册内置宏。"""
    # 守卫宏：条件执行
    env.define('守护', ['条件', '体'], ['若', '条件', '体', ['可能']])

    # 除非宏：条件不满足时执行
    env.define('除非', ['条件', '体'], ['若', ['非', '条件'], '体', ['可能']])

    # 当宏：循环直到条件不满足
    env.define('当', ['条件', '体'], ['循环', '条件', '体'])

    # 重复宏：执行N次
    env.define(
        '重复',
        ['次数', '体'],
        ['设', '__i__', 0, ['循环', ['小于', '__i__', '次数'], ['体', ['设', '__i__', ['加', '__i__', 1]]]]],
    )

    # 管道宏：链式调用
    env.define('管道', ['值', '函数列表'], ['归并', '函数列表', '值', ['lambda', ['acc', 'f'], ['f', 'acc']]])


# 初始化内置宏
_builtin_env = MacroEnv()
_register_builtin_macros(_builtin_env)
