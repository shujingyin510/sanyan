"""能力约束层：默认拒绝的实例级能力栈 + 五能力类 + 分派检查。

分层律（约束-方向研究 §D1，用户裁定）：本模块只被 `约束{}` 上下文
（ops/constraint_ops.py）驱动；表达式层的 许/禁/只许/允许 值算子（ops/planned_ops.py）
绝不触碰这里的能力栈——**共享词汇，不共享运行时状态**。

默认拒绝：约束块内只有纯计算恒通；五效果类（网/盘读/盘写/进程/外链）不 `许`
即 判=假·因=约束。块外无 frame → 零检查、行为与今日完全一致（向后兼容，不碰既有测试）。

能力栈挂 evaluator 实例（惰性属性 `_cap_stack`），修 E6 全局态污染；单调收紧
（子块只能求交、禁累加），修 E5 放松。E7 并发子求值器继承是后续一刀。
"""

from __future__ import annotations

import time
from typing import Optional

from core.values import SanyanConstraintDenied
from ops.registry import entry_names, has_op

CAP_CLASSES = frozenset({'网', '盘读', '盘写', '进程', '外链'})

# 算子内部注册名 → 能力类（中心表；别名经 entry_names 自动继承同族）。
# 只标效果类；其余约 230 个纯计算算子不在表内 = 免检恒通。
# 进程类含元能力（执行/设环境变量/沙箱/沙箱开）——默认拒绝下块内自动锁死，
# 不 `许 进程` 就无法从块内自拆门控或解沙箱（E1/E2/E5 的块级收口顺带落地）。
_CAP_TABLE = {
    # 网
    'http读': '网',
    'http写': '网',
    'http请求': '网',
    '三态Web服务器': '网',
    '三态路由': '网',
    '三态监听': '网',
    '安装': '网',
    '卸载': '网',
    '更新': '网',
    '检查更新': '网',
    '加载包': '网',
    '发布准备': '网',
    # 盘读
    'read_file': '盘读',
    'load': '盘读',
    'import': '盘读',
    '列出目录': '盘读',
    '存在': '盘读',
    '是文件': '盘读',
    '是目录': '盘读',
    '当前路径': '盘读',
    # 盘写
    'write_file': '盘写',
    'write_binary': '盘写',
    'sqlite_open': '盘写',
    'sqlite_exec': '盘写',
    'sqlite_insert': '盘写',
    'sqlite_update': '盘写',
    'sqlite_delete': '盘写',
    'sqlite_close': '盘写',
    # 进程（含元能力）
    '执行': '进程',
    '设环境变量': '进程',
    '沙箱': '进程',
    '沙箱开': '进程',
    # 外链（c释/py释 是清理算子，不标类——清理恒允许，与惰性运维一致）
    'c载入': '外链',
    'c调': '外链',
    'py导入': '外链',
    'py取': '外链',
    'py调': '外链',
    'py项': '外链',
}

_OP_CAP: dict[str, str] = {}
_applied = False

# 自守卫算子（信封式）：被禁时分派处**不抛**，由算子自身返回信封（判假·因=约束）。
# 直取式算子不在此列——分派处直接抛（与其"对 404 也抛"的既有契约一致）。
_SELF_GUARDED: set[str] = set()


def register_self_guarded(name: str) -> None:
    """标记信封式算子：被禁由算子自理（返回信封），分派处不抛。展开到同族别名。"""
    for sib in entry_names(name):
        _SELF_GUARDED.add(sib)


def _ensure_applied() -> None:
    """把中心表展开到所有别名（entry_names 聚合同族），幂等。惰性：首个约束帧激活时才跑。"""
    global _applied
    if _applied:
        return
    _applied = True
    for name, cls in _CAP_TABLE.items():
        if not has_op(name):
            continue
        for sib in entry_names(name):
            _OP_CAP[sib] = cls


def cap_of(internal: str) -> Optional[str]:
    """算子的能力类；纯计算返回 None（免检）。"""
    _ensure_applied()
    return _OP_CAP.get(internal)


class CapFrame:
    """一个 `约束{}` 块的有效能力策略（已与父块求交，单调收紧）。

    allowed=许可能力类集；denied=不可逆禁的能力类（禁 > 许）。
    默认拒绝：不在 allowed 或在 denied → 假。
    """

    __slots__ = ('allowed', 'denied', 'deadline')

    def __init__(self, allowed: frozenset, denied: frozenset, deadline: Optional[float] = None) -> None:
        self.allowed = allowed
        self.denied = denied
        self.deadline = deadline  # 绝对墙钟死线（time.monotonic 基），None=无限时

    def permits(self, cap: str) -> bool:
        if cap in self.denied:
            return False
        return cap in self.allowed


def current_frame(evaluator) -> Optional[CapFrame]:
    st = getattr(evaluator, '_cap_stack', None)
    return st[-1] if st else None


def push_frame(evaluator, allowed: frozenset, denied: frozenset, timeout: Optional[float] = None) -> None:
    """压入约束帧，与父帧求交（单调：子块 allowed⊆父块、denied 累加，只紧不松）。

    timeout（秒，来自 限时）→ 绝对死线 time.monotonic()+timeout；死线亦单调收紧，
    子帧取更早者（不能比父块争取更多时间）。"""
    st = getattr(evaluator, '_cap_stack', None)
    if st is None:
        st = []
        evaluator._cap_stack = st
    deadline = None if timeout is None else time.monotonic() + timeout
    if st:
        parent = st[-1]
        allowed = frozenset(allowed) & parent.allowed
        denied = frozenset(denied) | parent.denied
        if parent.deadline is not None:
            deadline = parent.deadline if deadline is None else min(deadline, parent.deadline)
    else:
        allowed = frozenset(allowed)
        denied = frozenset(denied)
    st.append(CapFrame(allowed, denied, deadline))


def pop_frame(evaluator) -> None:
    st = getattr(evaluator, '_cap_stack', None)
    if st:
        st.pop()


def capture_stack(evaluator) -> list:
    """取能力栈快照——修 E7：并发/异步在 spawn 时捕获约束，子求值器据此继承。

    必须在 spawn 时（父线程）捕获：异步任务延迟执行时父可能已退出约束块，栈已弹空。
    CapFrame 不可变（frozenset），共享帧对象安全。父无栈（常态）→ 空列表，零开销。
    """
    st = getattr(evaluator, '_cap_stack', None)
    return list(st) if st else []


def install_stack(evaluator, snapshot: list) -> None:
    """把快照装进（子）求值器，继承 spawn 时的约束。空快照→空操作。

    新建 list：子的 push/pop 不扰父，跨线程只读共享不可变帧——线程安全。
    """
    if snapshot:
        evaluator._cap_stack = list(snapshot)


def check_dispatch(evaluator, internal: str) -> None:
    """分派处强制：块内被禁能力 → 抛 SanyanConstraintDenied（直取式契约）。

    块外（无 frame）零成本早退——不触发中心表构建，与今日行为完全一致。
    """
    frame = current_frame(evaluator)
    if frame is None:
        return
    cap = cap_of(internal)
    if cap is None:
        return  # 纯计算恒通
    if not frame.permits(cap):
        if internal in _SELF_GUARDED:
            return  # 信封式：算子自理（返回判假·因=约束），分派处不抛
        raise SanyanConstraintDenied(f'约束禁止: {cap}({internal})')


def can(evaluator, cap: str) -> bool:
    """能否(cap)：权限探询，恒真/假（认知/权限分层律，D4）。无 frame → 真（无约束）。"""
    frame = current_frame(evaluator)
    if frame is None:
        return True
    return frame.permits(cap)


def check_deadline(evaluator) -> None:
    """限时看门狗：当前帧超预算 → 抛 SanyanConstraintDenied·因=超时（判假，约束失败）。

    无帧/无死线 → 立即返回（零成本，不影响无约束的热路径）；挂在循环/尾递归迭代点，
    协作式捕获跑飞的不可信代码。墙钟用 time.monotonic（不受系统时钟回拨影响）。
    直线代码不被拦（AST 有限、不会无限跑）——看门狗守的是循环/递归这类跑飞向量。"""
    st = getattr(evaluator, '_cap_stack', None)
    if not st:
        return
    dl = st[-1].deadline
    if dl is not None and time.monotonic() >= dl:
        raise SanyanConstraintDenied('约束超时: 任务超过限时预算', reason='超时')
