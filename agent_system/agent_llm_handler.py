"""Agent LLM Handler — LLM 调用和工具解析

包含：
  - llm_call: LLM 调用（多提供商 + 重试 + 超时 + UR 检测）
  - parse_tool: 工具调用解析
  - extract_key: 结果提取
  - extract_module: 模块名提取
"""

import json as _json
import os
import time as _time
import urllib.error as _err
import urllib.request as _req
from typing import Optional, Tuple


class LLMHandler:
    """LLM 调用和工具解析"""

    def __init__(
        self,
        ev=None,
        profiler=None,
        ur_monitor=None,
        system_prompt: Optional[str] = None,
    ):
        self.ev = ev
        self.profiler = profiler
        self.ur_monitor = ur_monitor
        self._system_prompt = system_prompt

    def llm_call(self, prompt: str, override_system_prompt: Optional[str] = None) -> str:
        """LLM 调用：多提供商 + 重试 + 超时 + UR 检测"""
        # 安全获取配置
        model = self._get_config('模型名', 'deepseek-v4-pro')
        url = self._get_config('模型URL', '')
        key = self._get_config('API密钥', os.environ.get('SANYAN_API_KEY', ''))
        provider = self._get_config('模型提供商', 'deepseek')
        timeout = self._get_timeout()

        # ── 本地模型 ──
        if provider in ('local', '本地'):
            return self._local_call(model, prompt, override_system_prompt)

        # 如果 URL 为空，根据 provider 构建默认 URL
        if not url:
            provider_urls = {
                'deepseek': 'https://api.deepseek.com/v1/chat/completions',
                'openai': 'https://api.openai.com/v1/chat/completions',
                'anthropic': 'https://api.anthropic.com/v1/messages',
                'gemini': f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent',
                'qwen': 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions',
                'glm': 'https://open.bigmodel.cn/api/paas/v4/chat/completions',
                'moonshot': 'https://api.moonshot.cn/v1/chat/completions',
            }
            url = provider_urls.get(provider, provider_urls['deepseek'])

        # 获取 system prompt
        sys_msg = override_system_prompt if override_system_prompt is not None else self._system_prompt
        if sys_msg is None:
            sys_msg = self._default_system_prompt()

        # 构建请求
        if provider and 'gemini' in str(provider).lower():
            body, headers, parser = self._build_gemini_request(model, key, sys_msg, prompt)
        else:
            body, headers, parser = self._build_openai_request(model, key, sys_msg, prompt, timeout)

        # 重试 3 次
        for attempt in range(3):
            try:
                req = _req.Request(url, data=body, headers=headers, method='POST')
                resp = _json.loads(_req.urlopen(req, timeout=timeout).read().decode('utf-8'))
                text, tokens = parser(resp)

                # 记录 token 用量
                if tokens > 0 and self.profiler:
                    self.profiler.record_llm_call(0, tokens)

                # UR 退化检测
                if self.ur_monitor:
                    should_stop, ur, reason = self.ur_monitor.check(text)
                    if should_stop:
                        print(f'  [UR] {reason}')
                        return f'error|LLM退化: {reason}'

                return text.strip()
            except (_err.HTTPError, _err.URLError, OSError):
                if attempt < 2:
                    _time.sleep(1.0 * (attempt + 1))
                continue
            except Exception:
                break

        return 'error|LLM调用失败(3次重试)'

    def _local_call(self, model: str, prompt: str, override_system_prompt=None) -> str:
        """本地模型调用（HuggingFace transformers + 本地缓存）"""
        try:
            from agent_system.agent_llm import LocalProvider

            # 懒初始化并缓存
            if not hasattr(self, '_local_provider'):
                self._local_provider = LocalProvider(model_name=model)
                self._local_provider._load_model()
            provider = self._local_provider

            sys_msg = override_system_prompt if override_system_prompt else self._system_prompt
            if sys_msg is None:
                sys_msg = self._default_system_prompt()

            response = provider.chat(
                [
                    {'role': 'system', 'content': sys_msg},
                    {'role': 'user', 'content': prompt},
                ]
            )
            # chat() 返回 dict {'content': text, ...}，提取文本
            if isinstance(response, dict):
                return response.get('content', str(response))
            return str(response)
        except Exception as e:
            return f'error|本地模型调用失败: {e}'

    def _get_config(self, key: str, default: str) -> str:
        """安全获取配置（优先 evaluator，其次环境变量）"""
        try:
            value = getattr(self.ev, 'get_var', lambda x: '')(key)
            if value:
                return value.strip()
        except Exception:
            pass

        # 环境变量回退
        env_map = {
            'API密钥': 'SANYAN_API_KEY',
            '模型名': 'LLM_MODEL',
            '模型URL': 'LLM_URL',
            '模型提供商': 'LLM_PROVIDER',
        }
        env_key = env_map.get(key)
        if env_key:
            env_value = os.environ.get(env_key, '')
            if env_value:
                return env_value.strip()

        return default

    def _get_timeout(self) -> int:
        """获取超时时间"""
        try:
            raw = getattr(self.ev, 'get_var', lambda x: 60)('超时秒数')
            if hasattr(raw, 'to_payload'):
                return int(float(str(raw.to_payload())))
            return int(str(raw))
        except Exception:
            return 60

    def _default_system_prompt(self) -> str:
        """默认 system prompt"""
        return (
            '你是三言(Sanyan)编程助手，一个中文DSL语言的工具型Agent。\n'
            '你的任务：根据用户输入选一个工具执行。\n'
            '\n'
            '工具与参数:\n'
            '  analyze(path)          — 分析文件结构\n'
            '  find_symbol(name)      — 查找符号定义/引用\n'
            '  read_file(path,start,count) — 读文件(行号可选)\n'
            '  search_code(keyword)   — 搜索代码\n'
            '  replace_in_file(path,old,new) — 单次替换\n'
            '  replace_all(pattern,old,new)  — 批量替换\n'
            '  write_file(path,content)— 写入文件\n'
            '  list_files(pattern)     — 列出文件(可选模式)\n'
            '  run_test(test_file)     — 运行测试\n'
            '  run_shell(cmd)          — 执行shell命令\n'
            '  git_diff                — 查看git差异\n'
            '  git_status              — 查看git状态\n'
            '  done(answer)            — 任务完成，输出最终答案\n'
            '\n'
            '输出格式（严格，只输出一个JSON对象，独占一行）:\n'
            '  {"tool":"工具名", "args":{"参数名":"值"}}\n'
        )

    def _code_generation_prompt(self) -> str:
        """代码生成 system prompt"""
        return (
            '你是一个代码生成器。只输出Python代码，不要输出其他内容。\n'
            '不要输出JSON、不要输出解释、不要输出markdown。\n'
            '直接输出可运行的Python代码。\n'
        )

    def _build_gemini_request(self, model: str, key: str, sys_msg: str, prompt: str) -> tuple:
        """构建 Gemini 请求"""
        body = _json.dumps(
            {
                'system_instruction': {'parts': [{'text': sys_msg}]},
                'contents': [{'parts': [{'text': prompt}]}],
                'generationConfig': {'temperature': 0.7},
            },
            ensure_ascii=False,
        ).encode('utf-8')
        headers = {'Content-Type': 'application/json'}

        def parser(d):
            text = d['candidates'][0]['content']['parts'][0]['text']
            tokens = d.get('usageMetadata', {}).get('totalTokenCount', 0)
            return text, tokens

        return body, headers, parser

    def _build_openai_request(self, model: str, key: str, sys_msg: str, prompt: str, timeout: int) -> tuple:
        """构建 OpenAI 兼容请求"""
        body = _json.dumps(
            {
                'model': model,
                'max_tokens': 4096,
                'temperature': 0.7,
                'thinking': {'type': 'enabled', 'budget_tokens': 2048},
                'messages': [
                    {'role': 'system', 'content': sys_msg},
                    {'role': 'user', 'content': prompt},
                ],
            },
            ensure_ascii=False,
        ).encode('utf-8')
        headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {key}'}

        def parser(d):
            msg = d['choices'][0]['message']
            text = msg.get('content') or msg.get('reasoning_content') or ''
            tokens = d.get('usage', {}).get('total_tokens', 0)
            return text, tokens

        return body, headers, parser

    def parse_tool(self, raw: str) -> Tuple[str, str]:
        """解析工具调用"""
        raw = raw.strip().replace('---END---', '').strip()

        # 1: bracket-counting JSON extraction
        start = raw.find('{')
        if start >= 0:
            depth = 0
            for i in range(start, len(raw)):
                if raw[i] == '{':
                    depth += 1
                elif raw[i] == '}':
                    depth -= 1
                    if depth == 0:
                        candidate = raw[start : i + 1]
                        try:
                            # 修复 JSON 中的换行符
                            candidate = self._fix_json_newlines(candidate)
                            data = _json.loads(candidate)
                            tool = data.get('tool', '')
                            args = data.get('args', {})
                            if tool:
                                if isinstance(args, str):
                                    return tool, args
                                if isinstance(args, dict):
                                    # 特殊处理 write_file 的 content 参数
                                    if tool == 'write_file' and 'content' in args:
                                        path = args.get('path', '')
                                        content = args['content']
                                        return tool, f'{path}|{content}'

                                    ordered = []
                                    for key in (
                                        'path',
                                        'name',
                                        'keyword',
                                        'content',
                                        'answer',
                                        'old',
                                        'new',
                                        'pattern',
                                        'start',
                                        'count',
                                        'test_file',
                                    ):
                                        if key in args:
                                            ordered.append(str(args[key]))
                                    if ordered:
                                        return tool, '|'.join(ordered)
                                    return tool, _json.dumps(args, ensure_ascii=False)
                                return tool, ''
                        except (_json.JSONDecodeError, KeyError):
                            pass
                        break

        # 2: fallback pipe format
        if '|' in raw:
            parts = raw.split('|', 1)
            return parts[0].strip(), parts[1].strip() if len(parts) > 1 else ''

        if raw.startswith('done'):
            return 'done', raw.split('|', 1)[1] if '|' in raw else ''

        # 3: keyword heuristic
        if 'def' in raw or '函数' in raw or '结构' in raw:
            return 'analyze', 'run_agent.py'

        return raw, ''

    def _fix_json_newlines(self, s: str) -> str:
        """修复 JSON 字符串中的换行符"""
        # 将字符串值中的实际换行符替换为转义的 \n
        result = []
        in_string = False
        escape_next = False

        for char in s:
            if escape_next:
                result.append(char)
                escape_next = False
            elif char == '\\':
                result.append(char)
                escape_next = True
            elif char == '"':
                in_string = not in_string
                result.append(char)
            elif in_string and char == '\n':
                result.append('\\n')
            elif in_string and char == '\r':
                result.append('\\r')
            elif in_string and char == '\t':
                result.append('\\t')
            else:
                result.append(char)

        return ''.join(result)

    def extract_key(self, result) -> str:
        """从结果中提取关键信息"""
        result_str = str(result)
        for marker in ['⚠', '符号 ']:
            idx = result_str.find(marker)
            if idx >= 0:
                end = result_str.find('\n', idx)
                return result_str[idx:end] if end > 0 else result_str[idx : idx + 300]
        for marker in ['共替换', '已替换']:
            idx = result_str.find(marker)
            if idx >= 0:
                return result_str[idx : idx + 200]
        return result_str[:300]

    def extract_module(self, params: str) -> str:
        """从工具参数中提取模块名"""
        if not params:
            return ''
        path = params.split('|')[0]
        if '.' in path:
            return path.rsplit('.', 1)[0]
        return path
