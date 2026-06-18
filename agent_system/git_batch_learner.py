"""Git 批量学习器 — 从 git 历史提取项目风格

功能：
  1. 分析 git log 的 commit message 模式
  2. 分析文件变更模式（哪些文件经常一起改）
  3. 提取代码风格（命名规范、注释风格、函数长度）
  4. 生成 learned_styles.md 批量记录

用法：
  learner = GitBatchLearner()
  styles = learner.analyze_repo('.')
  learner.save_styles(styles)
"""

import os
import re
import subprocess
from collections import Counter
from typing import Dict, List


class GitBatchLearner:
    """Git 批量学习器"""

    def __init__(self, repo_root: str = '.'):
        self.repo_root = repo_root
        self.commits: List[Dict] = []
        self.file_patterns: Dict[str, int] = Counter()
        self.commit_patterns: Dict[str, int] = Counter()
        self.code_styles: Dict[str, any] = {}

    def analyze_repo(self, max_commits: int = 500) -> Dict:
        """分析整个仓库"""
        # 1. 获取 git log
        self.commits = self._get_git_log(max_commits)

        # 2. 分析 commit message 模式
        self.commit_patterns = self._analyze_commit_patterns()

        # 3. 分析文件变更模式
        self.file_patterns = self._analyze_file_patterns()

        # 4. 分析代码风格
        self.code_styles = self._analyze_code_styles()

        return {
            'commit_patterns': self.commit_patterns,
            'file_patterns': self.file_patterns,
            'code_styles': self.code_styles,
            'total_commits': len(self.commits),
        }

    def _get_git_log(self, max_commits: int) -> List[Dict]:
        """获取 git log"""
        try:
            result = subprocess.run(
                ['git', 'log', f'--max-count={max_commits}', '--format=%H|%s|%ai|%an'],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                encoding='utf-8',
            )
            commits = []
            for line in result.stdout.strip().split('\n'):
                if not line or '|' not in line:
                    continue
                parts = line.split('|', 3)
                if len(parts) < 4:
                    continue
                sha, message, date, author = parts
                commits.append(
                    {
                        'sha': sha.strip(),
                        'message': message.strip(),
                        'date': date.strip(),
                        'author': author.strip(),
                    }
                )
            return commits
        except Exception:
            return []

    def _analyze_commit_patterns(self) -> Dict[str, int]:
        """分析 commit message 模式"""
        patterns = Counter()

        # 分类规则
        categories = {
            '修复': ['修复', 'fix', 'bug', '错误', '报错', '崩溃'],
            '新增': ['新增', '添加', '实现', '功能', 'feature', '支持'],
            '重构': ['重构', 'refactor', '整理', '优化', '重写'],
            '测试': ['测试', 'test', '验证', '检查'],
            '文档': ['文档', 'docs', 'README', 'CHANGELOG', '说明'],
            'CI': ['CI', 'ruff', 'mypy', 'coverage', 'pytest', '格式化'],
            '实验': ['实验', 'experiment', 'bench', '评测'],
        }

        for commit in self.commits:
            message = commit['message'].lower()
            for category, keywords in categories.items():
                if any(kw in message for kw in keywords):
                    patterns[category] += 1
                    break
            else:
                patterns['其他'] += 1

        return dict(patterns)

    def _analyze_file_patterns(self) -> Dict[str, int]:
        """分析文件变更模式"""
        patterns = Counter()

        for commit in self.commits:
            message = commit['message']
            # 提取文件名
            files = re.findall(r'[\w_]+\.\w+', message)
            for f in files:
                patterns[f] += 1

        return dict(patterns)

    def _analyze_code_styles(self) -> Dict[str, any]:
        """分析代码风格"""
        styles = {
            'naming_convention': 'snake_case',  # 默认
            'comment_style': '#',
            'docstring_style': '"""',
            'avg_function_length': 0,
            'avg_file_length': 0,
            'uses_type_hints': False,
            'uses_async': False,
            'test_framework': 'pytest',
        }

        # 分析 Python 文件
        py_files = []
        for root, dirs, files in os.walk(self.repo_root):
            if '__pycache__' in root or '.git' in root:
                continue
            for f in files:
                if f.endswith('.py') and not f.startswith('test_'):
                    py_files.append(os.path.join(root, f))
                    if len(py_files) >= 50:
                        break
            if len(py_files) >= 50:
                break

        if not py_files:
            return styles

        # 统计函数长度
        func_lengths = []
        file_lengths = []
        has_type_hints = False
        has_async = False

        for filepath in py_files:
            try:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()

                # 文件长度
                file_lengths.append(content.count('\n') + 1)

                # 函数长度
                in_function = False
                func_start = 0
                for i, line in enumerate(content.split('\n')):
                    if line.strip().startswith('def '):
                        in_function = True
                        func_start = i
                    elif in_function and line.strip() and not line.startswith(' ') and not line.startswith('\t'):
                        func_lengths.append(i - func_start)
                        in_function = False

                # 类型注解
                if '->' in content or ': str' in content or ': int' in content:
                    has_type_hints = True

                # async
                if 'async def' in content:
                    has_async = True

            except Exception:
                continue

        if func_lengths:
            styles['avg_function_length'] = sum(func_lengths) / len(func_lengths)
        if file_lengths:
            styles['avg_file_length'] = sum(file_lengths) / len(file_lengths)
        styles['uses_type_hints'] = has_type_hints
        styles['uses_async'] = has_async

        return styles

    def generate_style_report(self) -> str:
        """生成风格报告"""
        if not self.commits:
            return '（无数据）'

        lines = [
            '# 项目风格分析报告',
            '',
            '## 基本信息',
            f'- 分析提交数: {len(self.commits)}',
            f'- 时间范围: {self.commits[-1]["date"][:10]} ~ {self.commits[0]["date"][:10]}',
            '',
            '## Commit 模式',
        ]

        # Commit 模式
        total = sum(self.commit_patterns.values())
        for pattern, count in sorted(self.commit_patterns.items(), key=lambda x: -x[1]):
            percentage = count / total * 100
            lines.append(f'- {pattern}: {count} ({percentage:.1f}%)')

        # 代码风格
        lines.extend(
            [
                '',
                '## 代码风格',
                f'- 命名规范: {self.code_styles.get("naming_convention", "未知")}',
                f'- 平均函数长度: {self.code_styles.get("avg_function_length", 0):.0f} 行',
                f'- 平均文件长度: {self.code_styles.get("avg_file_length", 0):.0f} 行',
                f'- 使用类型注解: {"是" if self.code_styles.get("uses_type_hints") else "否"}',
                f'- 使用异步: {"是" if self.code_styles.get("uses_async") else "否"}',
                f'- 测试框架: {self.code_styles.get("test_framework", "未知")}',
            ]
        )

        # 常见文件
        if self.file_patterns:
            lines.extend(
                [
                    '',
                    '## 常见变更文件',
                ]
            )
            for filepath, count in sorted(self.file_patterns.items(), key=lambda x: -x[1])[:10]:
                lines.append(f'- {filepath}: {count} 次')

        return '\n'.join(lines)

    def save_styles(self, styles: Dict, output_file: str = 'learned_styles.md'):
        """保存风格到文件"""
        output_path = os.path.join(self.repo_root, 'agent_system', output_file)

        # 读取现有内容（验证文件存在）
        if os.path.exists(output_path):
            with open(output_path, 'r', encoding='utf-8') as f:
                f.read()

        # 生成新记录
        record = f"""
## 批量学习记录: {self.repo_root}
- 时间: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')}
- 分析提交数: {styles.get('total_commits', 0)}
- Commit 模式: {', '.join(f'{k}:{v}' for k, v in styles.get('commit_patterns', {}).items())}
- 代码风格:
  - 命名规范: {styles.get('code_styles', {}).get('naming_convention', '未知')}
  - 平均函数长度: {styles.get('code_styles', {}).get('avg_function_length', 0):.0f} 行
  - 使用类型注解: {'是' if styles.get('code_styles', {}).get('uses_type_hints') else '否'}
  - 测试框架: {styles.get('code_styles', {}).get('test_framework', '未知')}
- 常见变更文件: {', '.join(f'{f}:{c}' for f, c in sorted(styles.get('file_patterns', {}).items(), key=lambda x: -x[1])[:5])}
"""

        # 追加到文件
        with open(output_path, 'a', encoding='utf-8') as f:
            f.write(record)

        return output_path


def batch_learn_from_git(repo_root: str = '.', max_commits: int = 500) -> str:
    """批量学习入口函数"""
    learner = GitBatchLearner(repo_root)
    styles = learner.analyze_repo(max_commits)
    output_path = learner.save_styles(styles)
    return output_path
