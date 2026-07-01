"""宏操作：定义和使用宏"""

from __future__ import annotations
from core.values import SanyanSyntaxError
from ops.registry import register, register_alias
from core.macro import get_global_macro_env


def macro_define(evaluator, args):
    """定义宏(名称 参数列表 体) — 定义编译期宏

    用法: (定义宏 守护 (条件 体) (若 条件 体 (可能)))
    """
    if len(args) < 3:
        raise SanyanSyntaxError('定义宏 需要: 名称 参数列表 体')

    # 获取宏名
    name_node = args[0]
    if isinstance(name_node, list):
        name = name_node[0] if isinstance(name_node[0], str) else str(name_node[0])
    else:
        name = str(name_node)

    # 获取参数列表（不求值，直接使用）
    params_node = args[1]
    if isinstance(params_node, list):
        params = [str(p) for p in params_node]
    else:
        params = [str(params_node)]

    # 获取宏体（不求值，保留 AST）
    body = args[2]

    # 注册宏
    env = get_global_macro_env()
    env.define(name, params, body)

    return name


def macro_expand(evaluator, args):
    """展开宏(表达式) — 展开宏调用

    用法: (展开宏 (守护 (大于 x 0) (输出 "正数")))
    """
    if not args:
        raise SanyanSyntaxError('展开宏 需要一个表达式参数')

    # 获取表达式
    expr = args[0]

    # 展开宏
    env = get_global_macro_env()
    expanded = env.expand(expr)

    return expanded


def macro_list(evaluator, args):
    """宏列表() — 列出所有已定义的宏

    用法: (宏列表)
    """
    env = get_global_macro_env()
    return env.list_macros()


def macro_undefine(evaluator, args):
    """取消宏(名称) — 取消宏定义

    用法: (取消宏 守护)
    """
    if not args:
        raise SanyanSyntaxError('取消宏 需要宏名称')

    name = str(evaluator.eval(args[0]))
    env = get_global_macro_env()
    return env.undefine(name)


# 注册宏操作
register('定义宏', macro_define)
register('展开宏', macro_expand)
register('宏列表', macro_list)
register('取消宏', macro_undefine)

register_alias('defmacro', '定义宏')
register_alias('macro_expand', '展开宏')
register_alias('macro_list', '宏列表')
register_alias('undefmacro', '取消宏')
