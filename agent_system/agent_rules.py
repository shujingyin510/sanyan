"""Agent Rules Engine — 按规则执行，不调 LLM 选工具

流程：
  1. 读取 agent_rules.md
  2. 匹配任务到规则
  3. 按规则工具链执行（不调 LLM）
  4. 无匹配规则时，LLM 生成新规则 → 用户审批 → 执行

优势：
  - 减少 LLM 调用（从每步调 LLM 变成 0 次）
  - 工具链正确（规则是人工/LLM 审核过的）
  - 可追溯（规则文件可查看）
"""

import os
import re
from typing import Dict, List, Optional


RULES_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'agent_rules.md')


class AgentRule:
    """单条规则"""

    def __init__(self, name: str, pattern: str, steps: List[Dict], validation: str):
        self.name = name
        self.pattern = pattern
        self.steps = steps  # [{'tool': 'write_file', 'desc': '创建文件'}, ...]
        self.validation = validation

    def match(self, task: str) -> bool:
        """检查任务是否匹配此规则"""
        try:
            return bool(re.search(self.pattern, task, re.IGNORECASE))
        except re.error:
            return self.pattern.lower() in task.lower()


class RuleEngine:
    """规则引擎：读取规则 → 匹配 → 执行"""

    def __init__(self, rules_file: Optional[str] = None):
        self.rules_file = rules_file or RULES_FILE
        self.rules: List[AgentRule] = []
        self._load_rules()

    def _load_rules(self):
        """从 agent_rules.md 加载规则"""
        if not os.path.exists(self.rules_file):
            return

        with open(self.rules_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # 解析规则块
        blocks = re.split(r'^## 规则：', content, flags=re.MULTILINE)
        for block in blocks[1:]:  # 跳过第一个（标题）
            rule = self._parse_rule_block(block)
            if rule:
                self.rules.append(rule)

    def _parse_rule_block(self, block: str) -> Optional[AgentRule]:
        """解析单个规则块"""
        lines = block.strip().split('\n')
        if not lines:
            return None

        name = lines[0].strip()
        pattern = ''
        steps = []
        validation = ''

        for line in lines[1:]:
            line = line.strip()
            if line.startswith('匹配：') or line.startswith('匹配:'):
                pattern = line.split('：', 1)[-1].split(':', 1)[-1].strip()
            elif line.startswith('验证：') or line.startswith('验证:'):
                validation = line.split('：', 1)[-1].split(':', 1)[-1].strip()
            elif re.match(r'^\d+\.', line):
                # 工具步骤：1. write_file({filename}|{code}) — 创建文件
                match = re.match(r'^\d+\.\s+(\w+)\((.*?)\)\s*[—\-]\s*(.*)', line)
                if match:
                    tool = match.group(1)
                    args_desc = match.group(2)
                    desc = match.group(3)
                    steps.append({'tool': tool, 'args_desc': args_desc, 'desc': desc})

        if name and pattern and steps:
            return AgentRule(name, pattern, steps, validation)
        return None

    def match_rule(self, task: str) -> Optional[AgentRule]:
        """匹配任务到规则"""
        for rule in self.rules:
            if rule.match(task):
                return rule
        return None

    def get_rules_summary(self) -> str:
        """获取规则摘要"""
        if not self.rules:
            return '（无规则）'
        lines = [f'共 {len(self.rules)} 条规则：']
        for rule in self.rules:
            lines.append(f'  - {rule.name}: {rule.pattern}')
        return '\n'.join(lines)

    def format_rule_for_prompt(self, rule: AgentRule) -> str:
        """格式化规则，注入 LLM 上下文"""
        steps = '\n'.join(f'  {i + 1}. {s["tool"]}({s["args_desc"]}) — {s["desc"]}' for i, s in enumerate(rule.steps))
        return f'[规则] {rule.name}\n工具链:\n{steps}\n验证: {rule.validation}'

    def extract_filename(self, task: str, rule: Optional[AgentRule] = None) -> Optional[str]:
        """从任务中提取文件名"""
        # 匹配 .py 文件
        match = re.search(r'[\w_]+\.py', task)
        if match:
            return match.group(0)
        return None

    def extract_module_name(self, task: str, filename: Optional[str] = None) -> Optional[str]:
        """提取模块名（用于测试文件名）"""
        if filename:
            return filename.replace('.py', '')
        match = re.search(r'(\w+)\.py', task)
        if match:
            return match.group(1)
        return None
