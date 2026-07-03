"""P2 任务挖掘：从仓库找 concrete、可验证的小任务，喂给自更新闭环（self_update.py）。

北极星 P2「自造任务」。来源三类，按**可验证性**排序：
  1. failing_test  —— pytest 输出里的 FAILED/ERROR 项（oracle 天然可判：转绿且基线不退）
  2. todo          —— 源码里的 TODO/FIXME/HACK/XXX 注释
  3. long_function —— 超长 Python 函数（重构候选；oracle = 套件不退 + 差分一致）
纯静态、零 LLM。产出 `MinedTask`，`prompt()` 生成给 agent 的中文任务书（内嵌红线①文案：
不得删测试/跳测试来"修复"）。
"""

from __future__ import annotations

import ast
import io
import os
import re
import tokenize
from dataclasses import dataclass
from typing import Iterator, List, Sequence, Tuple

SKIP_DIRS = {
    '.git',
    '__pycache__',
    'build',
    'dist',
    'node_modules',
    '.pytest_cache',
    '.ruff_cache',
    'sanyan.egg-info',
    'sanyan-vscode',
}

_FAILED_RE = re.compile(r'^(?:FAILED|ERROR)\s+([^\s:]+)::(\S+)', re.M)
_TODO_RE = re.compile(r'#\s*(TODO|FIXME|HACK|XXX)\b[:：]?\s*(.{0,120})', re.I)


@dataclass(frozen=True)
class MinedTask:
    kind: str  # 'failing_test' | 'todo' | 'long_function'
    path: str  # 仓库相对路径
    line: int
    title: str
    detail: str = ''
    hints: str = ''  # long_function: 静态分解计划（候选提取块行区间）

    def prompt(self) -> str:
        """给 agent 的任务书。红线①：修复失败测试不允许靠删/跳测试。"""
        if self.kind == 'failing_test':
            return (
                f'修复失败的测试 {self.detail}（文件 {self.path}）。'
                f'只允许修产品代码或该测试确实过时的断言；**不得删除、跳过或弱化测试**。'
            )
        if self.kind == 'todo':
            return f'完成 {self.path}:{self.line} 的待办注释：{self.title}。保持现有测试全绿。'
        base = (
            f'重构 {self.path}:{self.line} 的超长函数 {self.title}（{self.detail}），'
            f'拆成更小的函数：行为不变、保留原函数名，重构后 {self.title} 本体必须明显变短'
            f'（提取的辅助函数要真正被调用），现有测试全绿。不得修改 tests/ 目录下的任何文件。'
        )
        if self.hints:
            # 静态分解计划：把"自己设计重构方案"降维成"按给定方案执行"（弱模型的质变）
            base += f' 可优先提取的候选块：{self.hints}。'
        return base


def mine_failing_tests(pytest_output: str) -> List[MinedTask]:
    """从 pytest 输出解析 FAILED/ERROR 项。空文本 → 空列表（不猜）。"""
    tasks = []
    seen = set()
    for m in _FAILED_RE.finditer(pytest_output or ''):
        path, test = m.group(1), m.group(2)
        node = f'{path}::{test}'
        if node not in seen:
            seen.add(node)
            tasks.append(MinedTask('failing_test', path, 0, f'修复 {test}', detail=node))
    return tasks


def _walk_files(root: str, exts: Sequence[str]):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if fn.endswith(tuple(exts)):
                yield os.path.join(dirpath, fn)


def _py_comments(text: str) -> Iterator[Tuple[int, str]]:
    """产出 .py 源码里**真注释** token 的 (行号, 注释文本)。

    字符串字面量里的 "# TODO"（测试夹具、提示词模板等）不是注释，不产出——
    首跑实测这类假阳性占了 TODO 挖掘近半（如 test_task_mining 自己的夹具串）。
    """
    try:
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            if tok.type == tokenize.COMMENT:
                yield tok.start[0], tok.string
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return  # 语法坏的文件跳过（与 mine_long_functions 的 ast 失败同策略）


def mine_todos(root: str, *, exts: Sequence[str] = ('.py',), limit: int = 50) -> List[MinedTask]:
    """扫描 TODO/FIXME/HACK/XXX 注释（.py 经 tokenize 只认真注释；其他扩展逐行正则）。"""
    tasks: List[MinedTask] = []
    for fp in _walk_files(root, exts):
        rel = os.path.relpath(fp, root)
        try:
            with open(fp, encoding='utf-8', errors='replace') as f:
                text = f.read()
        except OSError:
            continue
        if fp.endswith('.py'):
            found: Iterator[Tuple[int, str]] = _py_comments(text)
        else:
            found = ((i, ln) for i, ln in enumerate(text.splitlines(), 1))
        for lineno, chunk in found:
            m = _TODO_RE.search(chunk)
            if m:
                tasks.append(MinedTask('todo', rel, lineno, m.group(2).strip() or m.group(1).upper()))
                if len(tasks) >= limit:
                    return tasks
    return tasks


_BLOCK_NAMES = {ast.If: '条件块', ast.For: '循环块', ast.While: '循环块', ast.Try: '异常处理块', ast.With: '上下文块'}


def _block_hints(node, min_span: int = 8, top: int = 5) -> str:
    """函数体内直接子块的行区间清单——喂给 agent 的静态分解计划。"""
    out = []
    for child in node.body:
        name = _BLOCK_NAMES.get(type(child))
        if name is None:
            continue
        end = getattr(child, 'end_lineno', None) or child.lineno
        span = end - child.lineno + 1
        if span >= min_span:
            out.append(f'L{child.lineno}-{end}（{name}，{span}行）')
    return '、'.join(out[:top])


def mine_long_functions(root: str, *, max_lines: int = 80, limit: int = 30) -> List[MinedTask]:
    """AST 扫描超长 Python 函数（重构候选），按长度降序。"""
    tasks: List[MinedTask] = []
    for fp in _walk_files(root, ('.py',)):
        rel = os.path.relpath(fp, root)
        try:
            with open(fp, encoding='utf-8', errors='replace') as f:
                tree = ast.parse(f.read())
        except (SyntaxError, ValueError, OSError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                span = (getattr(node, 'end_lineno', None) or node.lineno) - node.lineno + 1
                if span > max_lines:
                    tasks.append(
                        MinedTask(
                            'long_function', rel, node.lineno, node.name, detail=f'{span} 行', hints=_block_hints(node)
                        )
                    )
    tasks.sort(key=lambda t: -int(t.detail.split()[0]))
    return tasks[:limit]


def mine_all(root: str, *, pytest_output: str = '', max_lines: int = 80) -> List[MinedTask]:
    """汇总全部来源，按可验证性排序：failing_test > todo > long_function（同类保持原序）。"""
    order = {'failing_test': 0, 'todo': 1, 'long_function': 2}
    tasks = mine_failing_tests(pytest_output) + mine_todos(root) + mine_long_functions(root, max_lines=max_lines)
    return sorted(tasks, key=lambda t: order[t.kind])
