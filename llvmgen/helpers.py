"""LLVM 编译器辅助函数 — 注入到自举求值器的 Python 回调

这些函数在 self_hosted_compile() 中注册到求值器，供 llvmgen.san 调用。
"""

from __future__ import annotations

from typing import Any

from ops.registry import register as _register
from ternary_core import TritValue


# ── opcode 分派表（用于 tag_op 命令，避免自举 IR 中的字符串比较） ──
OPCODE_MAP: dict[str, int] = {
    '取': 1,
    'get': 1,
    '列表取': 1,
    'list_get': 1,
    '列表取长': 2,
    'list_len': 2,
    'set': 3,
    '设': 3,
    '設': 3,
    'if': 4,
    '若': 4,
    '循环': 5,
    'loop': 5,
    'forin': 6,
    'fn': 8,
    '定义': 8,
    'define': 8,
    '返回': 9,
    'return': 9,
    '跳出': 10,
    'break': 10,
    '继续': 11,
    'continue': 11,
    'do': 12,
    '做': 12,
    '尝试': 13,
    'try': 13,
    '判断': 15,
    'judge': 15,
    '加': 16,
    'add': 16,
    '减': 17,
    'sub': 17,
    '乘': 18,
    'mul': 18,
    '除': 19,
    'div': 19,
    '小于': 20,
    'lt': 20,
    '大于': 21,
    'gt': 21,
    '等于': 22,
    'eq': 22,
    '且': 23,
    'and': 23,
    '或': 24,
    'or': 24,
    '非': 25,
    'not': 25,
    '大于等于': 26,
    'gte': 26,
    '字符串相等': 27,
    'str_equals': 27,
    '是列表': 28,
    'is_list': 28,
    '是字符串': 29,
    'is_string': 29,
    'print': 30,
    '输出': 30,
    '新寄存器ID': 31,
    '新标签ID': 32,
    '列表': 33,
    'list': 33,
    '取键': 34,
    'get_key': 34,
    '置键': 35,
    '字典': 36,
    'dict': 36,
    '切片': 37,
    'slice': 37,
    '列表合': 38,
    'list_concat': 38,
    '子串': 39,
    'substring': 39,
    '字列': 40,
    'str_to_list': 40,
    '连接': 41,
    'concat': 41,
    '查键': 42,
    '存变量': 43,
    '新列表': 44,
    '新字典': 45,
    '取字长': 46,
    '列表追加': 47,
    '进栈': 48,
    '出栈': 49,
    '字典取长': 50,
    '字典键列表': 51,
    '字符串包含': 52,
    '查找': 53,
    '找': 53,
    'find': 53,
    '是数字': 54,
    'is_number': 54,
    '转数字': 55,
    'to_number': 55,
    '前缀': 56,
    'startswith': 56,
    '注册函数名': 57,
    '取函数名': 58,
    '转义LLVM字符串': 59,
    '是终止指令': 60,
    '循环进栈': 61,
    '循环出栈': 61,
    '循环加锁': 61,
    '进入合并上下文': 62,
    '退出合并上下文': 63,
    '取合并标签': 64,
    'san_read_file': 65,
    'san_write_file': 66,
    'san_argv': 67,
    'san_argc': 68,
    '_rt_malloc': 69,
    '_rt_free': 70,
    '取长': 72,
    'len': 72,
    'length': 72,
    '函数': 73,
    '模块调用': 74,
    '置': 75,
    '读': 76,
    '查': 77,
    '对': 78,
    'export': 79,
    '导出': 79,
    '映射': 80,
    'map': 80,
    '过滤': 81,
    'filter': 81,
    '归并': 82,
    'reduce': 82,
    '是字典': 83,
}

# ── 非 ASCII 函数名映射 ──
_func_name_map: dict[str, str] = {}
_func_name_counter = [0]
_module_id = 0

# ── 合并上下文标签 ──
_merge_label = ''

# ── 标签/寄存器计数器 ──
_label_counter = 0
_reg_counter = 0

# ── 循环栈 ──
_loop_stack: list = []


def tag_op(evaluator: Any, args: list) -> Any:
    """AST 节点头部查字典得 opcode，避免字符串比较。"""
    ast = evaluator.eval(args[0])
    if not isinstance(ast, (list, tuple)) or len(ast) == 0:
        return ast
    head = ast[0]
    if not isinstance(head, str):
        return ast
    opcode = OPCODE_MAP.get(head, 0)
    return [head, TritValue(opcode)] + list(ast[1:])


def dict_get_safe(evaluator: Any, args: list) -> Any:
    """安全取字典键。支持 list-of-dicts 栈：从栈顶向下搜索。"""
    d = evaluator.eval(args[0])
    k = evaluator.eval(args[1])
    if isinstance(k, TritValue):
        k = k.to_int()
    if isinstance(d, list):
        for layer in reversed(d):
            if isinstance(layer, dict) and k in layer:
                return layer[k]
        return ''
    if isinstance(d, dict) and k in d:
        return d[k]
    return ''


def list_contains(evaluator: Any, args: list) -> TritValue:
    """检查列表是否包含元素。"""
    lst = evaluator.eval(args[0])
    item = evaluator.eval(args[1])
    if isinstance(lst, (list, tuple)):
        return TritValue(1 if item in lst else -1)
    return TritValue(-1)


def list_len(evaluator: Any, args: list) -> TritValue:
    """返回列表长度。"""
    lst = args[0] if isinstance(args[0], list) else evaluator.eval(args[0])
    if isinstance(lst, (list, tuple)):
        return TritValue(len(lst))
    return TritValue(0)


def dict_len(evaluator: Any, args: list) -> TritValue:
    """返回字典键数量。"""
    d = evaluator.eval(args[0])
    if isinstance(d, dict):
        return TritValue(len(d))
    return TritValue(0)


def list_get_safe(evaluator: Any, args: list) -> Any:
    """安全列表取值，索引越界返回空串。"""
    lst = evaluator.eval(args[0])
    idx = evaluator.eval(args[1])
    if isinstance(idx, (list, tuple)):
        idx = evaluator.eval(idx)
    if isinstance(idx, TritValue):
        idx = idx.to_int()
    if isinstance(lst, (list, tuple)) and isinstance(idx, int) and 0 <= idx < len(lst):
        return lst[idx]
    return ''


def list_append(evaluator: Any, args: list) -> Any:
    """列表追加元素，返回列表本身。"""
    lst = args[0] if isinstance(args[0], list) else evaluator.eval(args[0])
    item = evaluator.eval(args[1])
    if isinstance(lst, list):
        lst.append(item)
    return lst


def env_push(evaluator: Any, args: list) -> Any:
    """进栈: comp_env 栈顶 push 新层。"""
    d = args[0] if isinstance(args[0], list) else evaluator.eval(args[0])
    if isinstance(d, list):
        d.append({})
    return d


def env_pop(evaluator: Any, args: list) -> Any:
    """出栈: comp_env 栈顶 pop。"""
    d = args[0] if isinstance(args[0], list) else evaluator.eval(args[0])
    if isinstance(d, list) and len(d) > 0:
        d.pop()
    return d


def dict_keys(evaluator: Any, args: list) -> list:
    """返回字典所有键的列表。"""
    d = evaluator.eval(args[0])
    if isinstance(d, dict):
        return list(d.keys())
    return []


def dict_new_empty(evaluator: Any, args: list) -> dict:
    """返回空字典。"""
    return {}


def list_new_empty(evaluator: Any, args: list) -> list:
    """返回空列表。"""
    return []


def str_bytelen(evaluator: Any, args: list) -> TritValue:
    """返回字符串 UTF-8 字节长度。"""
    s = evaluator.eval(args[0])
    if isinstance(s, str):
        return TritValue(len(s.encode('utf-8')))
    return TritValue(0)


def escape_llvm_str(evaluator: Any, args: list) -> str:
    """转义字符串用于 LLVM IR c\"...\" 格式。"""
    s = evaluator.eval(args[0])
    if isinstance(s, str):
        s = s.replace('\\', '\\\\')
        s = s.replace('"', '\\22')
        s = s.replace('\n', '\\0A')
        s = s.replace('\r', '\\0D')
        s = s.replace('\t', '\\09')
        return s
    return ''


def str_endswith(evaluator: Any, args: list) -> TritValue:
    """检查字符串是否以指定后缀结尾。"""
    s = evaluator.eval(args[0])
    suffix = evaluator.eval(args[1])
    if isinstance(s, str) and isinstance(suffix, str):
        return TritValue(1 if s.rstrip().endswith(suffix.strip()) else -1)
    return TritValue(-1)


def str_contains(evaluator: Any, args: list) -> TritValue:
    """检查字符串是否包含子串。"""
    s = evaluator.eval(args[0])
    sub = evaluator.eval(args[1])
    if isinstance(s, str) and isinstance(sub, str):
        return TritValue(1 if sub in s else -1)
    return TritValue(-1)


def register_func_name(evaluator: Any, args: list) -> str:
    """注册函数名→ASCII映射，返回映射后的ASCII名。"""
    name = evaluator.eval(args[0])
    if isinstance(name, str) and name not in _func_name_map:
        idx = _func_name_counter[0]
        _func_name_counter[0] += 1
        _func_name_map[name] = f'_m{_module_id}_fn{idx}'
    return _func_name_map.get(name, name)


def get_func_name(evaluator: Any, args: list) -> Any:
    """取函数的ASCII名（用于LLVM IR）。"""
    name = evaluator.eval(args[0])
    if isinstance(name, str):
        return _func_name_map.get(name, name)
    return name


def set_module_id(evaluator: Any, args: list) -> TritValue:
    """设置模块ID并重置函数名映射。"""
    global _module_id, _func_name_map, _func_name_counter
    _module_id = evaluator.eval(args[0]).to_int()
    _func_name_map = {}
    _func_name_counter = [0]
    return TritValue(0)


def set_merge_label(evaluator: Any, args: list) -> TritValue:
    """设置合并上下文标签。"""
    global _merge_label
    _merge_label = evaluator.eval(args[0]) if args else ''
    return TritValue(0)


def clear_merge_label(evaluator: Any, args: list) -> TritValue:
    """清除合并上下文标签。"""
    global _merge_label
    _merge_label = ''
    return TritValue(0)


def get_merge_label(*args: Any) -> str:
    """获取当前合并上下文标签。"""
    return _merge_label


def next_label(evaluator: Any = None, args: list | None = None) -> int:
    """生成下一个标签ID。"""
    global _label_counter
    _label_counter += 1
    return _label_counter


def next_reg(evaluator: Any = None, args: list | None = None) -> int:
    """生成下一个寄存器ID。"""
    global _reg_counter
    _reg_counter += 1
    return _reg_counter


def is_terminated(evaluator: Any, args: list) -> TritValue:
    """检查 LLVM IR 文本是否以终止指令 (ret/br) 结尾。"""
    sym = args[0] if args else ''
    text = evaluator.get_var(sym) if isinstance(sym, str) else str(sym)
    if not text:
        return TritValue(-1)
    last = str(text).rstrip().rsplit('\n', 1)[-1].strip()
    if last.startswith('ret') or last.startswith('br'):
        return TritValue(1)
    return TritValue(-1)


def box_py(evaluator: Any, args: list) -> list:
    """Python版box: 绕过evaluator的纯函数缓存问题。"""
    v_val = evaluator.eval(args[0]) if len(args) > 0 else '%0'
    reg_val = evaluator.eval(args[1]) if len(args) > 1 else 0
    v = str(v_val)
    r1 = next_reg()
    r2 = next_reg()
    r3 = next_reg()
    s = f'  %{r1} = shl i64 {v}, 1\n'
    s += f'  %{r2} = or i64 %{r1}, 1\n'
    s += f'  %{r3} = inttoptr i64 %{r2} to i8*\n'
    return [s, f'%{r3}', reg_val]


def unbox_py(evaluator: Any, args: list) -> list:
    """Python版unbox。"""
    p = evaluator.eval(args[0]) if len(args) > 0 else 'null'
    reg_val = evaluator.eval(args[1]) if len(args) > 1 else 0
    r1 = next_reg()
    r2 = next_reg()
    s = f'  %{r1} = ptrtoint i8* {p} to i64\n'
    s += f'  %{r2} = ashr i64 %{r1}, 1\n'
    return [s, f'%{r2}', reg_val]


def loop_push(evaluator: Any = None, args: list | None = None) -> int:
    """循环栈 push。"""
    hdr = args[0] if args else ''
    _loop_stack.append(hdr)
    return 0


def loop_pop(evaluator: Any = None, args: list | None = None) -> int:
    """循环栈 pop。"""
    if _loop_stack:
        _loop_stack.pop()
    return 0


def loop_top(evaluator: Any = None, args: list | None = None) -> Any:
    """循环栈顶。"""
    if _loop_stack:
        return _loop_stack[-1]
    return ''


def register_all_helpers() -> None:
    """注册所有辅助函数到 ops registry。"""
    _register('container_ops_list_contains', list_contains)
    _register('container_ops_set_merge_label', set_merge_label)
    _register('container_ops_clear_merge_label', clear_merge_label)
    _register('container_ops_next_label', next_label)
    _register('container_ops_next_reg', next_reg)
    _register('container_ops_is_terminated', is_terminated)
    _register('container_ops_box', box_py)
    _register('container_ops_unbox', unbox_py)
    _register('box', box_py)
    _register('unbox', unbox_py)
    _register('container_ops_loop_push', loop_push)
    _register('container_ops_loop_pop', loop_pop)
    _register('container_ops_loop_top', loop_top)
