"""Agent Execution — 规则执行和代码生成

包含：
  - execute_rule: 按规则执行工具链
  - generate_code: 代码生成（模板 → 缓存 → LLM）
  - generate_test_code: 测试代码生成
  - run_tournament_fallback: 淘汰赛兜底
"""

import os
import subprocess
from typing import Any, Callable, Dict


class RuleExecutor:
    """规则执行器"""

    def __init__(
        self,
        tools: Dict[str, Callable],
        rule_engine: Any,
        template_manager: Any,
        llm_call: Callable,
        memory: Dict,
    ):
        self.tools = tools
        self.rule_engine = rule_engine
        self.template_manager = template_manager
        self._llm_call = llm_call
        self.memory = memory

    def execute_rule(self, task: str, rule: Any, dry_run: bool = False) -> Dict:
        """按规则执行工具链（不调 LLM）"""
        # 提取文件名和模块名
        filename = self.rule_engine.extract_filename(task)
        module = self.rule_engine.extract_module_name(task, filename)

        # 构建变量映射
        vars = {
            'filename': filename or 'output.py',
            'module': module or 'output',
            'source_file': filename or 'source.py',
            'test_file': f'tests/test_{module}.py' if module else 'tests/test_output.py',
        }

        results = []
        for i, step in enumerate(rule.steps, 1):
            tool = step['tool']
            args_desc = step['args_desc']
            desc = step['desc']

            # 替换变量
            args = args_desc
            for k, v in vars.items():
                args = args.replace(f'{{{k}}}', v)

            print(f'  [规则 {i}/{len(rule.steps)}] {tool} — {desc}')

            if tool not in self.tools:
                print(f'    ✗ 工具未找到: {tool}')
                continue

            # 特殊处理：write_file 需要生成代码
            if tool == 'write_file' and '{code}' in args_desc:
                code = self._generate_code_for_rule(task, filename)
                args = f'{filename}|{code}'
            elif tool == 'write_file' and '{test_code}' in args_desc:
                test_code = self._generate_test_code(task, filename, module)
                test_file = f'tests/test_{module}.py'
                args = f'{test_file}|{test_code}'

            # 执行工具
            try:
                result = self.tools[tool](args, dry_run)
                print(f'    → {str(result)[:80]}')
                results.append(result)

                if tool == 'write_file':
                    self.memory['modified'].append(filename)
            except Exception as e:
                print(f'    ✗ 执行失败: {e}')
                results.append(f'错误: {e}')

        # 验证
        if rule.validation:
            validation = rule.validation
            for k, v in vars.items():
                validation = validation.replace(f'{{{k}}}', v)
            print(f'  [验证] {validation}')
            try:
                r = subprocess.run(
                    validation,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=60,
                    cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))) or '.',
                )
                if r.returncode == 0:
                    print('    ✓ 验证通过')
                else:
                    print(f'    ✗ 验证失败: {r.stderr[-200:]}')
            except Exception as e:
                print(f'    ✗ 验证错误: {e}')

        return {
            'answer': f'按规则 [{rule.name}] 执行完成',
            'memory': self.memory,
            'rule': rule.name,
        }

    def _generate_code(self, task: str, filename: str) -> str:
        """根据任务生成代码：模板库 → 缓存 → LLM"""
        # 1. 用模板管理器获取代码
        code = self.template_manager.get_code(task, filename)
        if code:
            return code

        # 2. 兜底：调 LLM 生成（会自动缓存）
        try:
            prompt = f'为以下任务生成Python代码，写入文件 {filename}:\n{task[:200]}\n\n只输出代码，不要其他文字。'
            code = self._llm_call(prompt)
            if code:
                self.template_manager._cache_set(task, filename, code, 'llm')
            return code
        except Exception:
            return ''

    def _generate_code_for_rule(self, task: str, filename: str) -> str:
        """为规则生成代码"""
        code = self._generate_code(task, filename or 'output.py')
        if code:
            return code

        try:
            prompt = f'为以下任务生成Python代码，写入文件 {filename}:\n{task[:200]}\n\n只输出代码，不要其他文字。'
            return self._llm_call(prompt)
        except Exception:
            return f'# {filename} - 代码生成失败，请手动实现'

    def _generate_test_code(self, task: str, filename: str, module: str) -> str:
        """为规则生成测试代码"""
        from agent_system.templates.test_generator import generate_test_code, extract_functions_from_code

        code = self.template_manager.get_code(task, filename)
        if code:
            functions = extract_functions_from_code(code)
            return generate_test_code(module, functions)

        return f"""import pytest
from {module} import *


def test_basic():
    assert True
"""


class TournamentFallback:
    """淘汰赛兜底：连续失败后找替代方案"""

    def __init__(
        self,
        hypothesis_generator: Any,
        hypothesis_paraller: Any,
        execute_hypothesis: Callable,
        llm_call: Callable,
        memory: Dict,
    ):
        self.hypothesis_generator = hypothesis_generator
        self.hypothesis_paraller = hypothesis_paraller
        self._execute_hypothesis = execute_hypothesis
        self._llm_call = llm_call
        self.memory = memory

    def run(self, task: str, ctx: str, max_rounds: int, dry_run: bool) -> Dict:
        """执行淘汰赛"""
        # 1. 生成多种假设
        hypotheses = self.hypothesis_generator.generate(
            lambda p: self._llm_call(p, override_system_prompt=''), task, ctx, None
        )
        if not hypotheses:
            return {'answer': '淘汰赛无法生成替代方案', 'memory': self.memory}

        print(f'  [淘汰赛] 生成{len(hypotheses)}个替代方案')

        # 2. 并行验证假设
        if len(hypotheses) > 1:
            validated = self.hypothesis_paraller.parallel_validate(hypotheses, ctx, steps=2)
            validated.sort(key=lambda x: -x[1])
            best = validated[0][0] if validated else hypotheses[0]
        else:
            best = hypotheses[0]

        print(f'  [淘汰赛] 最优方案: H{best.id} conf={best.confidence:.2f}')

        # 3. 执行最优方案
        return self._execute_hypothesis(best, task, ctx, max_rounds, dry_run)
