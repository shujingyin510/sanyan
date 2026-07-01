"""AST 解析器 — 理解代码结构，精准加载上下文

功能：
  1. 解析 Python 文件的 AST
  2. 提取函数、类、导入、变量定义
  3. 构建文件依赖图（谁导入谁）
  4. 给定任务，找出所有相关文件

用法：
  parser = ASTParser()
  info = parser.parse_file('core/evaluator.py')
  related = parser.find_related_files('修复 evaluator 的类型错误')
"""

import ast
import os
import re
from typing import Dict, List, Optional, Set


class FileInfo:
    """文件信息"""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.functions: List[str] = []
        self.classes: List[str] = []
        self.imports: List[str] = []
        self.from_imports: Dict[str, List[str]] = {}  # module → [names]
        self.variables: List[str] = []
        self.lines: int = 0
        self.error: Optional[str] = None


class ASTParser:
    """AST 解析器"""

    def __init__(self):
        self._cache: Dict[str, FileInfo] = {}
        self._dep_graph: Dict[str, Set[str]] = {}  # file → {files it imports from}
        self._reverse_graph: Dict[str, Set[str]] = {}  # file → {files that import it}

    def parse_file(self, filepath: str) -> FileInfo:
        """解析单个文件"""
        if filepath in self._cache:
            return self._cache[filepath]

        info = FileInfo(filepath)

        if not os.path.exists(filepath):
            info.error = '文件不存在'
            return info

        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            info.lines = content.count('\n') + 1

            # 尝试 AST 解析
            try:
                tree = ast.parse(content)
                self._extract_from_ast(tree, info)
            except SyntaxError:
                # AST 解析失败，用正则提取
                self._extract_from_regex(content, info)

        except Exception as e:
            info.error = str(e)

        self._cache[filepath] = info
        return info

    def _extract_from_ast(self, tree: ast.AST, info: FileInfo):
        """从 AST 提取信息"""
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                info.functions.append(node.name)
            elif isinstance(node, ast.AsyncFunctionDef):
                info.functions.append(node.name)
            elif isinstance(node, ast.ClassDef):
                info.classes.append(node.name)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    info.imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ''
                names = [alias.name for alias in node.names]
                info.from_imports[module] = names
                info.imports.append(module)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        info.variables.append(target.id)

    def _extract_from_regex(self, content: str, info: FileInfo):
        """用正则提取信息（AST 解析失败时的兜底）"""
        # 函数
        info.functions = re.findall(r'def\s+(\w+)\s*\(', content)

        # 类
        info.classes = re.findall(r'class\s+(\w+)\s*[:\(]', content)

        # 导入
        for match in re.finditer(r'^import\s+(.+)$', content, re.MULTILINE):
            info.imports.append(match.group(1).strip())

        for match in re.finditer(r'^from\s+(\S+)\s+import', content, re.MULTILINE):
            info.imports.append(match.group(1).strip())

    def build_dependency_graph(self, root: str = '.'):
        """构建依赖图"""
        import glob as _glob

        files = _glob.glob(os.path.join(root, '**/*.py'), recursive=True)

        for filepath in files:
            if '__pycache__' in filepath:
                continue
            info = self.parse_file(filepath)
            if info.imports:
                self._dep_graph[filepath] = set()
                for imp in info.imports:
                    # 转换导入名到文件路径
                    resolved = self._resolve_import(imp, filepath, root)
                    if resolved:
                        self._dep_graph[filepath].add(resolved)
                        # 反向图
                        if resolved not in self._reverse_graph:
                            self._reverse_graph[resolved] = set()
                        self._reverse_graph[resolved].add(filepath)

    def _resolve_import(self, import_name: str, from_file: str, root: str) -> Optional[str]:
        """将导入名解析为文件路径"""
        # 处理相对导入
        if import_name.startswith('.'):
            base_dir = os.path.dirname(from_file)
            parts = import_name.lstrip('.').split('.')
            if parts:
                candidate = os.path.join(base_dir, *parts) + '.py'
                if os.path.exists(candidate):
                    return candidate

        # 处理绝对导入
        parts = import_name.split('.')
        candidate = os.path.join(root, *parts) + '.py'
        if os.path.exists(candidate):
            return candidate

        # 处理包导入
        candidate = os.path.join(root, *parts, '__init__.py')
        if os.path.exists(candidate):
            return candidate

        return None

    def find_related_files(self, task: str, root: str = '.', max_depth: int = 2) -> List[str]:
        """根据任务找出所有相关文件"""
        # 提取任务中提到的文件名
        mentioned_files = self._extract_filenames(task)

        # 找到直接提到的文件
        direct_files = set()
        for filename in mentioned_files:
            # 搜索文件
            for filepath in self._cache.keys():
                if filepath.endswith(filename):
                    direct_files.add(filepath)

        # 如果没找到，尝试模糊匹配
        if not direct_files:
            keywords = re.findall(r'[\u4e00-\u9fff]{2,}|[a-zA-Z_]\w{3,}', task)
            for filepath in self._cache.keys():
                for kw in keywords:
                    if kw.lower() in filepath.lower():
                        direct_files.add(filepath)
                        break

        # 扩展依赖
        related = set(direct_files)
        for _ in range(max_depth):
            new_files = set()
            for filepath in related:
                # 正向依赖
                if filepath in self._dep_graph:
                    new_files.update(self._dep_graph[filepath])
                # 反向依赖（谁依赖我）
                if filepath in self._reverse_graph:
                    new_files.update(self._reverse_graph[filepath])
            related.update(new_files)

        return list(related)

    def _extract_filenames(self, task: str) -> List[str]:
        """从任务中提取文件名"""
        return re.findall(r'[\w_]+\.py', task)

    def get_file_summary(self, filepath: str) -> str:
        """获取文件摘要"""
        info = self.parse_file(filepath)

        lines = [f'{filepath} ({info.lines}行)']
        if info.functions:
            lines.append(f'  函数: {", ".join(info.functions[:10])}')
        if info.classes:
            lines.append(f'  类: {", ".join(info.classes[:5])}')
        if info.imports:
            lines.append(f'  导入: {", ".join(info.imports[:5])}')

        return '\n'.join(lines)

    def get_context_for_task(self, task: str, root: str = '.', max_files: int = 5) -> str:
        """为任务生成上下文（相关文件的内容摘要）"""
        # 构建依赖图
        if not self._dep_graph:
            self.build_dependency_graph(root)

        # 找相关文件
        related = self.find_related_files(task, root)

        if not related:
            return ''

        # 按相关性排序（提到的文件优先）
        mentioned = self._extract_filenames(task)
        related.sort(
            key=lambda f: (
                0 if any(m in f for m in mentioned) else 1,
                -self._cache.get(f, FileInfo(f)).lines,
            )
        )

        # 生成上下文
        context_parts = ['[相关文件]']
        for filepath in related[:max_files]:
            summary = self.get_file_summary(filepath)
            context_parts.append(summary)

            # 读取文件内容（截断）
            try:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read(1000)
                context_parts.append(f'  内容预览:\n{content[:500]}...')
            except Exception:
                pass

        return '\n'.join(context_parts)
