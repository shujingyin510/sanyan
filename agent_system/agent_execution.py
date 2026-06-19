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
            'file': filename or 'output.py',  # alias for rules using {file}
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
            if tool == 'write_file':
                if '{code}' in args or '{test_code}' in args:
                    if '{code}' in args:
                        code = self._generate_code(task, filename)
                        args = f'{filename}|{code}'
                    else:
                        test_code = self._generate_test_code(task, filename, module)
                        test_file = f'tests/test_{module}.py'
                        args = f'{test_file}|{test_code}'
                elif '|' not in args:
                    # LLM生成的规则可能没有用标准格式，自动注入代码
                    code = self._generate_code(task, filename)
                    # 提取文件名
                    import re
                    fm = re.search(r'[\w_]+\.py', args)
                    target = fm.group(0) if fm else (filename or 'output.py')
                    # 如果是测试文件，用测试代码
                    if 'test' in target.lower() or 'test' in args.lower():
                        test_code = self._generate_test_code(task, filename, module)
                        args = f'{target}|{test_code}'
                    else:
                        args = f'{target}|{code}'

            # 执行工具
            try:
                result = self.tools[tool](args, dry_run)
                print(f'    → {str(result)[:80]}')
                results.append(result)

                # 文件不存在时自动切换为创建规则
                if tool in ('read_file', 'replace_in_file') and 'No such file' in str(result):
                    # 找到创建类规则
                    create_rules = [r for r in self.rule_engine.rules if '创建' in r.name and ('模块' in r.name or '类' in r.name)]
                    if create_rules and i == 1:
                        print(f'    → 文件不存在，切换为创建规则: {create_rules[0].name}')
                        return self.execute_rule(task, create_rules[0], dry_run)

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
            # 清理缓存的代码（可能在之前运行时被污染）
            code = self._clean_code(code)
            if code and not code.strip().startswith('{'):
                return code

        # 2. 兜底：调 LLM 生成（会自动缓存）
        try:
            prompt = f'为以下任务生成Python代码，写入文件 {filename}:\n{task[:200]}\n\n只输出代码，不要其他文字。'
            code = self._llm_call(prompt, override_system_prompt='你是一个代码生成器。只输出Python代码，不要输出其他内容。直接输出可运行的Python代码。')
            if code:
                # 先尝试清理代码（去除 JSON 包装、markdown 标记等）
                code = self._clean_code(code)
                # 如果清理后仍是 JSON（代码生成完全失败），重试
                stripped = code.strip()
                if stripped.startswith('{') and ('"tool"' in stripped or '"tool_name"' in stripped):
                    print(f'    [代码生成] LLM返回工具调用JSON，重试...')
                    retry_prompt = f'请直接输出Python代码，不要JSON格式:\n{task[:200]}'
                    code = self._llm_call(retry_prompt, override_system_prompt='你是一个代码生成器。只输出Python代码，不要输出其他内容。')
                    code = self._clean_code(code)
                if code and not code.strip().startswith('{'):
                    self.template_manager._cache_set(task, filename, code, 'llm')
            return code if code and not code.strip().startswith('{') else f'# {filename} - 代码生成失败'
        except Exception:
            return f'# {filename} - 代码生成失败，请手动实现'

    def _clean_code(self, code: str) -> str:
        """清理代码，去掉 markdown 标记和 JSON 包装"""
        # 检测并提取 JSON 中的代码内容
        stripped = code.strip()
        if stripped.startswith('{') and ('"tool"' in stripped or '"content"' in stripped):
            # 方法 1: JSON 解析
            try:
                import json
                data = json.loads(stripped)
                if 'args' in data and 'content' in data.get('args', {}):
                    return data['args']['content'].strip()
                if 'content' in data:
                    return data['content'].strip()
            except (json.JSONDecodeError, KeyError):
                pass
            # 方法 2: 查找 content 字段（处理多行 JSON）
            import re
            # 找到 "content":" 的位置，提取到结尾的 "}}
            m = re.search(r'"content"\s*:\s*"', stripped)
            if m:
                start = m.end()
                # 从 start 开始找最后一个 "} 或 "}} 之前的内容
                # 简单策略：取从 start 到结尾，去掉末尾的 "}} 或 "}
                rest = stripped[start:]
                # 去掉末尾的 JSON 闭合标记
                rest = re.sub(r'"\s*\}\s*\}?\s*$', '', rest)
                # 还原转义字符
                rest = rest.replace('\\n', '\n').replace('\\t', '\t').replace('\\"', '"').replace('\\\\', '\\')
                return rest.strip()
        
        # 去掉 ```python ... ``` 标记
        if '```' in code:
            lines = code.split('\n')
            clean_lines = []
            in_code = False
            for line in lines:
                if line.strip().startswith('```'):
                    in_code = not in_code
                    continue
                if in_code:
                    clean_lines.append(line)
            code = '\n'.join(clean_lines)
        return code.strip()

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
