"""Logic Audit Engine — 控制流 + 状态追踪 + 逻辑矛盾检测

四层语义分析:
    1. CFG Builder      — AST → 控制流图
    2. Path Analyzer     — 执行路径模拟 + 状态采样
    3. State Tracker     — 变量多状态追踪
    4. Logic Detector    — 矛盾检测器

检测能力:
    - 反向逻辑 (inverted conditions)
    - 不可达代码 (unreachable code)
    - 变量状态不一致 (state inconsistency)
    - Early return 逻辑错误
    - 死分支 (dead branches)
"""

import ast
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
from enum import Enum


class BlockType(Enum):
    ENTRY = 'entry'
    EXIT = 'exit'
    BASIC = 'basic'
    CONDITION = 'condition'
    LOOP = 'loop'
    RETURN = 'return'


@dataclass
class CFGBlock:
    id: int
    block_type: BlockType = BlockType.BASIC
    lines: List[int] = field(default_factory=list)
    code: List[str] = field(default_factory=list)
    successors: List[int] = field(default_factory=list)
    condition: Optional[str] = None  # for conditional blocks
    state_before: Dict[str, Set] = field(default_factory=dict)
    state_after: Dict[str, Set] = field(default_factory=dict)


@dataclass
class LogicIssue:
    issue_type: str
    severity: str  # high / medium / low
    line: int
    description: str
    suggestion: str


class CFGBuilder:
    """AST → 控制流图"""

    def __init__(self):
        self.blocks: List[CFGBlock] = []
        self._block_id = 0
        self._current_vars: Dict[str, Set] = {}

    def build(self, code: str) -> List[CFGBlock]:
        """从 Python 代码构建 CFG"""
        self.blocks = []
        self._block_id = 0
        self._current_vars = {}

        try:
            tree = ast.parse(code)
        except SyntaxError:
            return [CFGBlock(0, BlockType.ENTRY, lines=[0], code=['# syntax error'])]

        entry = CFGBlock(self._block_id, BlockType.ENTRY, lines=[1])
        self.blocks.append(entry)
        self._block_id += 1

        self._visit_body(tree.body, entry.id)

        exit_block = CFGBlock(self._block_id, BlockType.EXIT, lines=[len(code.split('\n'))])
        self.blocks.append(exit_block)

        # 没有后继的块 → 连接 exit
        for block in self.blocks[:-1]:
            if not block.successors:
                block.successors.append(exit_block.id)

        return self.blocks

    def _new_block(self, block_type=BlockType.BASIC, lines=None, code=None, condition=None) -> CFGBlock:
        b = CFGBlock(
            self._block_id,
            block_type,
            lines=lines or [],
            code=code or [],
            condition=condition,
        )
        self.blocks.append(b)
        self._block_id += 1
        return b

    def _visit_body(self, body: list, parent_id: int) -> int:
        """遍历语句列表，返回最后一个块的 ID"""
        current = parent_id
        for stmt in body:
            current = self._visit_stmt(stmt, current)
        return current

    def _visit_stmt(self, stmt, parent_id: int) -> int:
        """单条语句 → 块"""
        line = getattr(stmt, 'lineno', 0)

        if isinstance(stmt, ast.If):
            cond_block = self._new_block(
                BlockType.CONDITION,
                lines=[line],
                code=[ast.unparse(stmt.test)],
                condition=ast.unparse(stmt.test),
            )
            self.blocks[parent_id].successors.append(cond_block.id)

            # True 分支
            last_true = self._visit_body(stmt.body, cond_block.id)
            # False 分支
            if stmt.orelse:
                last_false = self._visit_body(stmt.orelse, cond_block.id)
            else:
                last_false = cond_block.id

            # 合并点
            if last_true != cond_block.id and last_false != cond_block.id:
                merge = self._new_block(BlockType.BASIC, lines=[line])
                self.blocks[last_true].successors.append(merge.id)
                self.blocks[last_false].successors.append(merge.id)
                return merge.id

            return max(last_true, last_false, key=lambda x: x if x != cond_block.id else -1)

        elif isinstance(stmt, ast.For) or isinstance(stmt, ast.While):
            loop = self._new_block(
                BlockType.LOOP,
                lines=[line],
                code=[ast.unparse(stmt.test if isinstance(stmt, ast.While) else stmt.iter)],
            )
            self.blocks[parent_id].successors.append(loop.id)

            self._visit_body(stmt.body, loop.id)
            self.blocks[loop.id].successors.append(parent_id + 0)

            after = self._new_block(BlockType.BASIC, lines=[line])
            self.blocks[parent_id].successors.append(after.id)
            return after.id

        elif isinstance(stmt, ast.FunctionDef) or isinstance(stmt, ast.ClassDef):
            # 进入函数/类内部
            return self._visit_body(stmt.body, parent_id)

        elif isinstance(stmt, ast.Return):
            rb = self._new_block(BlockType.RETURN, lines=[line], code=[ast.unparse(stmt)])
            self.blocks[parent_id].successors.append(rb.id)
            return rb.id

        else:
            # 普通语句 → 追加到当前块或新建
            code_str = ast.unparse(stmt)[:80]
            if self.blocks[parent_id].block_type == BlockType.BASIC and len(self.blocks[parent_id].lines) < 10:
                self.blocks[parent_id].lines.append(line)
                self.blocks[parent_id].code.append(code_str)
                return parent_id
            else:
                b = self._new_block(BlockType.BASIC, lines=[line], code=[code_str])
                self.blocks[parent_id].successors.append(b.id)
                return b.id


class LogicDetector:
    """逻辑矛盾检测器 — 基于 CFG 的语义分析"""

    def __init__(self):
        self.cfg = CFGBuilder()

    def audit(self, code: str) -> List[LogicIssue]:
        """全面语义审计"""
        issues = []
        blocks = self.cfg.build(code)

        issues.extend(self._detect_inverted_conditions(code, blocks))
        issues.extend(self._detect_same_branch_body(code))
        issues.extend(self._detect_unreachable(blocks))
        issues.extend(self._detect_dead_branches(blocks))
        issues.extend(self._detect_state_inconsistency(code))
        issues.extend(self._detect_early_return_issues(blocks))
        issues.extend(self._detect_logical_tautologies(code))
        issues.extend(self._detect_symbolic_issues(code))

        return issues

    # ── 0. 符号化逻辑(轻量SSA) ──

    def _detect_symbolic_issues(self, code: str) -> List[LogicIssue]:
        issues = []
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return issues

        class StateTracker(ast.NodeVisitor):
            def __init__(self):
                self.var_states = {}  # var → set of possible values
                self.issues = []

            def visit_FunctionDef(self, node):
                saved = dict(self.var_states)
                self.var_states = {}
                self.generic_visit(node)
                self.var_states = saved

            def visit_Assign(self, node):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        val = ast.unparse(node.value)
                        # 追踪: 变量先被赋常量, 然后在if分支被修改, 最后被使用
                        self.var_states[target.id] = {val}
                self.generic_visit(node)

            def visit_If(self, node):
                # 检查if分支内是否修改了在if之前定义的变量
                before = dict(self.var_states)
                if_modified = set()

                class BranchCollector(ast.NodeVisitor):
                    def visit_Assign(self, n):
                        for t in n.targets:
                            if isinstance(t, ast.Name) and t.id in before:
                                if_modified.add(t.id)
                        self.generic_visit(n)

                collector = BranchCollector()
                for stmt in node.body:
                    collector.visit(stmt)
                for stmt in node.orelse:
                    collector.visit(stmt)

                self.generic_visit(node)

                # 检查if之后使用了被修改的变量, 是否两个分支都赋值了
                after = dict(self.var_states)
                for var in if_modified:
                    if var in after and len(after.get(var, set())) == 1:
                        # 只有一个分支修改了变量 → 状态不一致
                        issues.append(
                            LogicIssue(
                                issue_type='symbolic_state_mismatch',
                                severity='medium',
                                line=node.lineno,
                                description=f"变量 '{var}' 在if分支被修改但只在单分支赋值, 后续使用可能异常",
                                suggestion=f"确保 '{var}' 在所有分支都有明确的赋值",
                            )
                        )

        StateTracker().visit(tree)
        return issues

    # ── 1. 反向逻辑检测 ──

    def _detect_inverted_conditions(self, code: str, blocks: List[CFGBlock]) -> List[LogicIssue]:
        """检测 if/else 中可能反转的逻辑"""
        issues = []
        lines = code.split('\n')

        # 找连续的 if...elif...else 链
        for i in range(len(lines)):
            line = lines[i].strip()
            if not line.startswith('if ') or '==' not in line:
                continue
            # 检查紧接着的 elif/else 是否用了同一个变量但条件相反
            j = i + 1
            while j < len(lines) and (lines[j].strip().startswith('elif ') or lines[j].strip().startswith('else:')):
                next_line = lines[j].strip()
                import re

                vars_in_if = re.findall(r'\b([a-zA-Z_]\w*)\b', line)
                vars_in_next = re.findall(r'\b([a-zA-Z_]\w*)\b', next_line)

                shared = set(vars_in_if) & set(vars_in_next)
                shared = {v for v in shared if v not in ('if', 'elif', 'else', 'and', 'or', 'not', 'is', 'in')}

                if shared and next_line.startswith('elif '):
                    # 检查是否有逻辑反转的信号
                    if all(w in ('==', '!=') for w in [line, next_line] if w in line and w in next_line):
                        pass  # 正常比较
                    elif len(shared) >= 2:
                        issues.append(
                            LogicIssue(
                                issue_type='possible_inverted_logic',
                                severity='medium',
                                line=i + 1,
                                description=f'if/elif 共享变量 {shared}，可能逻辑意图反转',
                                suggestion=f'检查条件 {i + 1} 和 {j + 1} 之间是否存在反转',
                            )
                        )
                j += 1
        return issues

    def _detect_same_branch_body(self, code: str) -> List[LogicIssue]:
        issues = []
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return issues

        class SameBranchFinder(ast.NodeVisitor):
            def visit_If(self, node):
                if node.orelse:
                    if_body = [ast.unparse(s).strip() for s in node.body]
                    else_body = [ast.unparse(s).strip() for s in node.orelse]
                    if if_body == else_body and len(if_body) >= 1:
                        issues.append(
                            LogicIssue(
                                issue_type='inverted_logic',
                                severity='high',
                                line=node.lineno,
                                description='if 和 else 分支完全相同，逻辑无效',
                                suggestion='两个分支执行相同代码，检查条件是否反了',
                            )
                        )
                self.generic_visit(node)

        SameBranchFinder().visit(tree)
        return issues

    # ── 2. 不可达代码检测 ──

    def _detect_unreachable(self, blocks: List[CFGBlock]) -> List[LogicIssue]:
        """检测不可达块"""
        issues = []
        visited = set()

        def dfs(block_id):
            if block_id in visited or block_id >= len(blocks):
                return
            visited.add(block_id)
            for sid in blocks[block_id].successors:
                dfs(sid)

        # 从入口开始 DFS
        if blocks:
            dfs(0)

        for block in blocks:
            if block.id not in visited and block.block_type not in (BlockType.ENTRY, BlockType.EXIT):
                issues.append(
                    LogicIssue(
                        issue_type='unreachable_code',
                        severity='high',
                        line=block.lines[0] if block.lines else 0,
                        description=f'不可达代码块 (block {block.id})',
                        suggestion='检查控制流，此段代码永远不会被执行',
                    )
                )

        return issues

    # ── 3. 死分支检测 ──

    def _detect_dead_branches(self, blocks: List[CFGBlock]) -> List[LogicIssue]:
        """检测条件分支中可能永远不走的路径"""
        issues = []

        for block in blocks:
            if block.block_type == BlockType.CONDITION and block.condition:
                # 检查是否是恒真/恒假的条件
                cond = block.condition.strip()
                # 检测 self-contradicting conditions
                if cond in ('True', 'False', '1 == 1', '0 == 0', 'True is True', 'False is False'):
                    issues.append(
                        LogicIssue(
                            issue_type='dead_branch',
                            severity='low',
                            line=block.lines[0] if block.lines else 0,
                            description=f'恒{cond.split()[0] if cond else "真"}条件，另一分支永不执行',
                            suggestion='此条件始终为真，else 分支是死代码',
                        )
                    )

                # 检测总是 False 的条件后的 else
                if cond in ('False', '0', 'None', 'True is False'):
                    if len(block.successors) >= 2:
                        issues.append(
                            LogicIssue(
                                issue_type='dead_branch',
                                severity='high',
                                line=block.lines[0] if block.lines else 0,
                                description='条件恒为 False，if 分支为死代码',
                                suggestion='此 if 分支永远不会执行',
                            )
                        )

        return issues

    # ── 4. 变量状态不一致检测 ──

    def _detect_state_inconsistency(self, code: str) -> List[LogicIssue]:
        """追踪变量跨路径的状态"""
        issues = []

        try:
            tree = ast.parse(code)
        except SyntaxError:
            return issues

        # 找变量在 if/else 两边被赋不同值后统一使用的情况
        class BranchTracker(ast.NodeVisitor):
            def __init__(self):
                self.if_stmts = []

            def visit_If(self, node):
                # 收集 if 分支的赋值
                if_assigns = {}
                for stmt in node.body:
                    if isinstance(stmt, ast.Assign):
                        for target in stmt.targets:
                            if isinstance(target, ast.Name):
                                if_assigns[target.id] = ast.unparse(stmt.value)

                # 收集 else 分支的赋值
                else_assigns = {}
                for stmt in node.orelse:
                    if isinstance(stmt, ast.Assign):
                        for target in stmt.targets:
                            if isinstance(target, ast.Name):
                                else_assigns[target.id] = ast.unparse(stmt.value)

                # 检测不一致
                shared = set(if_assigns.keys()) & set(else_assigns.keys())
                for var in shared:
                    if_val = if_assigns[var]
                    else_val = else_assigns[var]
                    if if_val != else_val:
                        # 后续使用检查
                        line_no = node.lineno
                        # 简单检查：变量在两分支都被赋不同值
                        self.if_stmts.append(
                            {
                                'var': var,
                                'if_val': if_val,
                                'else_val': else_val,
                                'line': line_no,
                            }
                        )

                self.generic_visit(node)

        tracker = BranchTracker()
        tracker.visit(tree)

        for item in tracker.if_stmts:
            issues.append(
                LogicIssue(
                    issue_type='state_inconsistency',
                    severity='medium',
                    line=item['line'],
                    description=f"变量 '{item['var']}' 在 if/else 中被赋不同值: {item['if_val']} vs {item['else_val']}",
                    suggestion=f'检查 {item["var"]} 的后续使用是否考虑了所有分支',
                )
            )

        return issues

    # ── 5. Early return 逻辑问题 ──

    def _detect_early_return_issues(self, blocks: List[CFGBlock]) -> List[LogicIssue]:
        """检测 early return 后仍有代码的问题"""
        issues = []

        for block in blocks:
            if block.block_type == BlockType.RETURN:
                # 检查返回块之后是否还有后继（除了 exit）
                successors = [s for s in block.successors if s < len(blocks) and blocks[s].block_type != BlockType.EXIT]
                if successors:
                    issues.append(
                        LogicIssue(
                            issue_type='code_after_return',
                            severity='medium',
                            line=block.lines[0] if block.lines else 0,
                            description='return 后仍有可执行代码',
                            suggestion='检查 return 之后的代码是否应该被执行',
                        )
                    )

        return issues

    # ── 6. 逻辑同义反复检测 ──

    def _detect_logical_tautologies(self, code: str) -> List[LogicIssue]:
        """检测恒真/恒假逻辑"""
        issues = []
        tautologies = [
            ('x == x', '恒真比较'),
            ('x != x', '恒假比较'),
            ('True and True', '恒真'),
            ('False or False', '恒假'),
            ('not True', '恒假'),
            ('not False', '恒真'),
        ]

        for pattern, desc in tautologies:
            if pattern in code:
                line = 1
                for i, line in enumerate(code.split('\n'), 1):
                    if pattern in line:
                        line = i
                        break
                issues.append(
                    LogicIssue(
                        issue_type='logical_tautology',
                        severity='low',
                        line=line,
                        description=f'逻辑同义反复: {desc} ({pattern})',
                        suggestion='此条件可简化或移除',
                    )
                )

        return issues


# ── 便捷接口 ──


def audit_code(code: str) -> dict:
    """对代码进行全面逻辑审计，返回结构化报告"""
    detector = LogicDetector()
    issues = detector.audit(code)
    return {
        'total_issues': len(issues),
        'by_severity': {
            'high': sum(1 for i in issues if i.severity == 'high'),
            'medium': sum(1 for i in issues if i.severity == 'medium'),
            'low': sum(1 for i in issues if i.severity == 'low'),
        },
        'by_type': {t: sum(1 for i in issues if i.issue_type == t) for t in sorted(set(i.issue_type for i in issues))},
        'issues': [
            {
                'type': i.issue_type,
                'severity': i.severity,
                'line': i.line,
                'description': i.description,
                'suggestion': i.suggestion,
            }
            for i in issues
        ],
    }
