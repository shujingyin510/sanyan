"""Agent Learning Handler — 学习和经验管理

包含：
  - save_experience: 保存运行经验
  - lookup_style: 查学习记录
  - learn_from_task: 从任务学习风格
  - collect_change_details: 收集修改详情
  - infer_style_from_task: 推断风格
  - save_style_rule: 保存风格规则
  - batch_learn_from_git: 批量学习
"""

import json
import os
import re as _re
from datetime import datetime
from typing import Any, Callable, Dict, Optional


class LearningHandler:
    """学习和经验管理"""

    def __init__(
        self,
        experience_store: Any,
        git_batch_learner: Any,
        llm_call: Callable,
        memory: Dict,
    ):
        self.experience_store = experience_store
        self.git_batch_learner = git_batch_learner
        self._llm_call = llm_call
        self.memory = memory

    def save_experience(self, task: str, perf_report: Optional[Dict] = None):
        """保存本次运行经验到跨会话存储"""
        try:
            # 记录工具使用
            for entry in self.memory.get('history', []):
                tool = entry.get('tool', '')
                success = entry.get('trit', 0) == 1
                duration = entry.get('duration', 0)
                self.experience_store.record_tool_use(tool, success, duration)

            # 记录任务
            tool_chain = [e.get('tool', '') for e in self.memory.get('history', [])]
            success = bool(self.memory.get('modified'))
            duration = perf_report.get('total_duration', 0) if perf_report else 0
            self.experience_store.record_task(task, tool_chain, success, duration)

            # 记录失败模式
            for entry in self.memory.get('history', []):
                if entry.get('trit', 0) == -1:
                    self.experience_store.record_failure_pattern(
                        entry.get('tool', ''), entry.get('result', '')[:100], 'logic_error'
                    )
        except Exception:
            pass

    def lookup_style(self, task: str) -> str:
        """查学习记录，返回风格提示"""
        try:
            rules_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'learned_styles.md')
            if not os.path.exists(rules_file):
                return ''

            with open(rules_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # 提取关键词匹配
            task_keywords = set(_re.findall(r'[\u4e00-\u9fff]{2,}|[a-zA-Z_]\w{3,}', task.lower()))

            # 解析学习记录
            records = content.split('## 学习记录:')
            best_match = ''
            best_score = 0

            for record in records[1:]:  # 跳过第一个（空）
                # 提取记录关键词
                record_keywords = set()
                for line in record.split('\n'):
                    if line.startswith('- 关键词:'):
                        kw_str = line.split(':', 1)[1].strip()
                        record_keywords = set(kw_str.lower().split(', '))
                        break

                # 计算匹配分数
                if record_keywords and task_keywords:
                    overlap = len(task_keywords & record_keywords)
                    score = overlap / max(len(task_keywords), len(record_keywords))
                    if score > best_score:
                        best_score = score
                        # 提取风格信息
                        lines = record.strip().split('\n')
                        style_lines = []
                        for line in lines:
                            if line.startswith('- 模式:') or line.startswith('- 风格:') or line.startswith('- 约定:'):
                                style_lines.append(line)
                        best_match = ' | '.join(style_lines)

            if best_score > 0.3:  # 匹配度超过30%才返回
                return best_match
            return ''
        except Exception:
            return ''

    def learn_from_task(self, task: str):
        """从任务中学习项目风格，生成规则"""
        try:
            modified = self.memory.get('modified', [])
            if not modified:
                return

            # 构建学习提示
            files_str = ', '.join(set(modified))
            history = self.memory.get('history', [])
            tools_used = [e.get('tool', '') for e in history]

            # 收集修改详情
            change_details = self._collect_change_details(modified)

            # 尝试用 LLM 分析
            style = None
            try:
                prompt = f"""分析以下任务执行过程，提取项目风格和模式。

任务: {task[:200]}
修改的文件: {files_str}
使用的工具: {', '.join(tools_used[:10])}
修改详情:
{change_details[:500]}

请用 JSON 格式回答：
{{
  "pattern": "任务模式（如：创建模块、修复bug、重构）",
  "style": "代码风格（如：用类型注解、写docstring、用pytest）",
  "conventions": ["约定1", "约定2"],
  "keywords": ["关键词1", "关键词2"]
}}

只输出 JSON，不要其他文字。"""

                raw = self._llm_call(prompt)
                if raw and not raw.startswith('error'):
                    match = _re.search(r'\{.*\}', raw, _re.DOTALL)
                    if match:
                        style = json.loads(match.group())
            except Exception:
                pass

            # 如果 LLM 失败，用规则推断
            if not style:
                style = self._infer_style_from_task(task, modified, tools_used)

            if style:
                self._save_style_rule(task, style, change_details)
        except Exception:
            pass

    def _collect_change_details(self, modified: list) -> str:
        """收集修改详情：文件内容、函数名、行数"""
        details = []
        for filepath in set(modified):
            if not os.path.exists(filepath):
                continue
            try:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read(2000)  # 只读前2000字符

                # 提取函数名
                functions = _re.findall(r'def\s+(\w+)\s*\(', content)
                classes = _re.findall(r'class\s+(\w+)\s*[:\(]', content)

                # 统计行数
                lines = content.count('\n') + 1

                detail = f'文件: {filepath} ({lines}行)'
                if functions:
                    detail += f'\n  函数: {", ".join(functions[:10])}'
                if classes:
                    detail += f'\n  类: {", ".join(classes[:5])}'
                details.append(detail)
            except Exception:
                details.append(f'文件: {filepath} (读取失败)')

        return '\n'.join(details) if details else '无详情'

    def _infer_style_from_task(self, task: str, modified: list, tools_used: list) -> dict:
        """从任务推断风格（不调 LLM）"""
        pattern = '未知'
        code_style = 'Python'
        conventions = []
        keywords = []

        # 推断任务模式
        if any(w in task for w in ['新增', '创建', '写']):
            pattern = '创建模块'
        elif any(w in task for w in ['修复', 'fix', 'bug']):
            pattern = '修复bug'
        elif any(w in task for w in ['重构', 'refactor']):
            pattern = '重构'
        elif any(w in task for w in ['测试', 'test']):
            pattern = '写测试'

        # 推断代码风格
        if any('.py' in f for f in modified):
            code_style = 'Python'
        if any('.san' in f for f in modified):
            code_style = '三言'

        # 推断约定
        if 'run_shell' in tools_used:
            conventions.append('用shell验证')
        if 'write_file' in tools_used:
            conventions.append('写文件')
        if 'read_file' in tools_used:
            conventions.append('先读后改')

        # 提取关键词
        keywords = _re.findall(r'[\u4e00-\u9fff]{2,}|[a-zA-Z_]\w{3,}', task)[:5]

        return {
            'pattern': pattern,
            'style': code_style,
            'conventions': conventions,
            'keywords': keywords,
        }

    def _save_style_rule(self, task: str, style: Dict, change_details: str = ''):
        """保存风格规则到文件"""
        try:
            rules_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'learned_styles.md')

            # 生成新规则
            pattern = style.get('pattern', '未知')
            code_style = style.get('style', '未知')
            conventions = style.get('conventions', [])
            keywords = style.get('keywords', [])

            rule = f"""
## 学习记录: {task[:50]}
- 模式: {pattern}
- 风格: {code_style}
- 约定: {', '.join(conventions)}
- 关键词: {', '.join(keywords)}
- 时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}
- 修改详情:
{change_details if change_details else '  无详情'}
"""

            # 追加到文件
            with open(rules_file, 'a', encoding='utf-8') as f:
                f.write(rule)

            print(f'  [学习] 已记录项目风格: {pattern}')
        except Exception:
            pass

    def batch_learn_from_git(self, max_commits: int = 500) -> str:
        """从 git 历史批量学习项目风格"""
        try:
            styles = self.git_batch_learner.analyze_repo(max_commits)
            output_path = self.git_batch_learner.save_styles(styles)

            # 打印报告
            report = self.git_batch_learner.generate_style_report()
            print(report)

            return output_path
        except Exception as e:
            print(f'批量学习失败: {e}')
            return ''
