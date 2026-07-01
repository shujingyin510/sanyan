"""类型推断系统：自动推断变量类型，支持泛型容器。

功能：
- 从赋值推断变量类型
- 泛型容器类型（列表<整数>、字典<字符串, 数字>）
- 类型传播（函数参数→返回值）
- 类型环境管理（作用域级别）

用法：
    from core.type_inference import TypeEnv
    env = TypeEnv()
    env.infer('x', 10)         # x: int
    env.infer('s', 'hello')    # s: str
    env.get_type('x')          # -> 'int'
"""

from __future__ import annotations
from typing import Any, Optional
from core.ternary_core import TritValue


class TypeEnv:
    """类型环境：跟踪变量的推断类型。

    支持：
    - 基本类型推断（int/float/str/list/dict/trit）
    - 泛型容器（列表<元素类型>、字典<键类型, 值类型>）
    - 作用域隔离（push/pop_scope）
    """

    def __init__(self) -> None:
        self._scopes: list[dict[str, str]] = [{}]
        self._generic_cache: dict[str, str] = {}

    def infer(self, name: str, value: Any) -> str:
        """从值推断类型并记录。返回推断的类型名。"""
        type_name = self._infer_value(value)
        self._scopes[-1][name] = type_name
        return type_name

    def set_type(self, name: str, type_name: str) -> None:
        """显式设置变量类型（用于类型标注）。"""
        self._scopes[-1][name] = type_name

    def get_type(self, name: str) -> Optional[str]:
        """获取变量的推断类型，从内向外查找。"""
        for scope in reversed(self._scopes):
            if name in scope:
                return scope[name]
        return None

    def push_scope(self) -> None:
        """创建新的类型作用域。"""
        self._scopes.append({})

    def pop_scope(self) -> None:
        """移除当前类型作用域。"""
        if len(self._scopes) > 1:
            self._scopes.pop()

    def _infer_value(self, value: Any) -> str:
        """推断值的类型。"""
        if isinstance(value, TritValue):
            if value.is_float():
                return 'float'
            return 'trit'
        if isinstance(value, bool):
            return 'int'
        if isinstance(value, int):
            return 'int'
        if isinstance(value, float):
            return 'float'
        if isinstance(value, str):
            return 'str'
        if isinstance(value, list):
            if not value:
                return '列表<any>'
            elem_type = self._infer_value(value[0])
            return f'列表<{elem_type}>'
        if isinstance(value, dict):
            if not value:
                return '字典<any, any>'
            key_type = self._infer_value(next(iter(value.keys())))
            val_type = self._infer_value(next(iter(value.values())))
            return f'字典<{key_type}, {val_type}>'
        return 'any'

    def infer_operation(self, op: str, args: list[Any], result: Any) -> str:
        """推断操作结果的类型。返回结果类型名。"""
        # 对于算术操作，结果类型取决于操作数
        if op in ('add', '加', 'sub', '减', 'mul', '乘', 'div', '除', 'mod', '余'):
            if any(isinstance(a, float) for a in args):
                return 'float'
            if any(isinstance(a, TritValue) and a.is_float() for a in args):
                return 'float'
            return 'int'

        # 对于比较操作，结果是 trit
        if op in ('eq', '等于', 'ne', '不等于', 'gt', '大于', 'lt', '小于', 'gte', '大于等于', 'lte', '小于等于'):
            return 'trit'

        # 对于逻辑操作，结果是 trit
        if op in ('and', '与', 'or', '或', 'not', '非'):
            return 'trit'

        # 对于字符串操作
        if op in ('concat', '连接'):
            return 'str'
        if op in ('strlen', '取长', 'length'):
            return 'int'

        # 对于列表操作
        if op in ('list_len', '表长'):
            return 'int'
        if op in ('list_concat', '列表合'):
            return 'list'
        if op in ('slice', '切片'):
            return 'list'

        # 对于字典操作
        if op in ('dict_keys', '字典键列表'):
            return 'list'

        # 对于类型检查
        if op in ('is_dict', '是字典', 'is_list', '是列表', 'is_string', '是字符串', 'is_number', '是数字'):
            return 'trit'

        # 对于转换
        if op in ('to_string', '转字符串'):
            return 'str'
        if op in ('to_number', '转数字'):
            return 'num'

        # 对于时间
        if op in ('timestamp', '时间戳'):
            return 'int'

        # 对于随机
        if op in ('random', '随机数'):
            return 'int'

        # 对于输出/IO
        if op in ('output', '输出', 'print'):
            return 'none'
        if op in ('read_file', '读文件'):
            return 'str'
        if op in ('write_file', '写文件'):
            return 'int'

        # 默认：从结果推断
        return self._infer_value(result)

    def check_assignment(self, name: str, value: Any) -> Optional[str]:
        """检查赋值是否与已有类型冲突。返回 None 表示通过，返回错误消息表示冲突。"""
        existing = self.get_type(name)
        if existing is None:
            return None  # 新变量，无需检查

        new_type = self._infer_value(value)

        # any 类型可以被任何类型覆盖
        if existing == 'any':
            return None

        # 类型必须兼容
        if not self._types_compatible(existing, new_type):
            return f"类型冲突: '{name}' 已声明为 {existing}，不能赋值为 {new_type}"

        return None

    def _types_compatible(self, t1: str, t2: str) -> bool:
        """检查两个类型是否兼容。"""
        # any 兼容所有类型
        if t1 == 'any' or t2 == 'any':
            return True

        # 相同类型兼容
        if t1 == t2:
            return True

        # num 兼容 int 和 float
        if t1 == 'num' and t2 in ('int', 'float', 'trit'):
            return True
        if t2 == 'num' and t1 in ('int', 'float', 'trit'):
            return True

        # int 和 float 可以互相转换
        if t1 in ('int', 'float') and t2 in ('int', 'float'):
            return True

        # 泛型容器兼容性
        if t1.startswith('列表<') and t2.startswith('列表<'):
            inner1 = t1[3:-1]
            inner2 = t2[3:-1]
            return self._types_compatible(inner1, inner2)

        if t1.startswith('字典<') and t2.startswith('字典<'):
            parts1 = t1[3:-1].split(', ', 1)
            parts2 = t2[3:-1].split(', ', 1)
            if len(parts1) == 2 and len(parts2) == 2:
                return self._types_compatible(parts1[0], parts2[0]) and self._types_compatible(parts1[1], parts2[1])

        return False

    def format_type(self, type_name: str) -> str:
        """格式化类型名为中文显示。"""
        type_map = {
            'int': '整数',
            'float': '浮点数',
            'str': '字符串',
            'list': '列表',
            'dict': '字典',
            'trit': '三态',
            'num': '数字',
            'any': '任意',
            'none': '无',
        }
        return type_map.get(type_name, type_name)


# ── 全局类型环境（用于类型检查）──
_global_type_env: Optional[TypeEnv] = None


def get_global_type_env() -> TypeEnv:
    """获取全局类型环境。"""
    global _global_type_env
    if _global_type_env is None:
        _global_type_env = TypeEnv()
    return _global_type_env


def reset_global_type_env() -> None:
    """重置全局类型环境。"""
    global _global_type_env
    _global_type_env = None
