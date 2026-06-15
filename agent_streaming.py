"""流式响应支持 — LLM边生成边显示 + 可中断
P28: StreamingLLM — 流式LLM调用
P29: InterruptibleStream — 可中断流处理
P30: ProgressiveDisplay — 渐进式显示
"""

import json
import sys
import threading
import time
import urllib.request
import urllib.error
from typing import Callable


class StreamingLLM:
    """流式LLM调用：支持边生成边输出"""

    def __init__(self, api_key: str, model: str = 'deepseek-v4-pro', url: str = '', provider: str = 'deepseek'):
        self.api_key = api_key
        self.model = model
        self.url = url
        self.provider = provider
        self._interrupted = False
        self._buffer = []
        self._lock = threading.Lock()

    def interrupt(self):
        """中断流式输出"""
        self._interrupted = True

    def reset(self):
        """重置中断状态"""
        self._interrupted = False
        self._buffer = []

    def stream_call(
        self, prompt: str, system_msg: str = '', on_token: Callable[[str], None] = None, timeout: int = 60
    ) -> str:
        """流式调用LLM，每生成一个token就回调

        Args:
            prompt: 用户输入
            system_msg: 系统消息
            on_token: 每个token的回调函数
            timeout: 超时秒数

        Returns:
            完整的响应文本
        """
        self.reset()

        if self.provider and 'gemini' in self.provider.lower():
            return self._stream_gemini(prompt, system_msg, on_token, timeout)
        else:
            return self._stream_openai(prompt, system_msg, on_token, timeout)

    def _stream_openai(self, prompt, system_msg, on_token, timeout):
        """OpenAI兼容API流式调用"""
        url = self.url or 'https://api.deepseek.com/v1/chat/completions'
        body = json.dumps(
            {
                'model': self.model,
                'max_tokens': 4096,
                'temperature': 0.7,
                'stream': True,
                'messages': [
                    {'role': 'system', 'content': system_msg},
                    {'role': 'user', 'content': prompt},
                ],
            },
            ensure_ascii=False,
        ).encode('utf-8')

        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.api_key}',
        }

        try:
            req = urllib.request.Request(url, data=body, headers=headers, method='POST')
            resp = urllib.request.urlopen(req, timeout=timeout)

            full_response = []

            for line in resp:
                if self._interrupted:
                    break

                line = line.decode('utf-8').strip()
                if not line or not line.startswith('data:'):
                    continue

                data_str = line[5:].strip()
                if data_str == '[DONE]':
                    break

                try:
                    data = json.loads(data_str)
                    delta = data.get('choices', [{}])[0].get('delta', {})
                    content = delta.get('content', '')
                    if content:
                        full_response.append(content)
                        if on_token:
                            on_token(content)
                except json.JSONDecodeError:
                    continue

            return ''.join(full_response)

        except Exception as e:
            return f'流式调用失败: {e}'

    def _stream_gemini(self, prompt, system_msg, on_token, timeout):
        """Gemini流式调用"""
        url = f'https://generativelanguage.googleapis.com/v1beta/models/{self.model}:streamGenerateContent?key={self.api_key}'
        body = json.dumps(
            {
                'system_instruction': {'parts': [{'text': system_msg}]},
                'contents': [{'parts': [{'text': prompt}]}],
                'generationConfig': {'temperature': 0.7},
            },
            ensure_ascii=False,
        ).encode('utf-8')

        headers = {'Content-Type': 'application/json'}

        try:
            req = urllib.request.Request(url, data=body, headers=headers, method='POST')
            resp = urllib.request.urlopen(req, timeout=timeout)

            full_response = []
            for line in resp:
                if self._interrupted:
                    break

                try:
                    data = json.loads(line.decode('utf-8'))
                    text = data['candidates'][0]['content']['parts'][0]['text']
                    full_response.append(text)
                    if on_token:
                        on_token(text)
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue

            return ''.join(full_response)

        except Exception as e:
            return f'流式调用失败: {e}'


class InterruptibleStream:
    """可中断流处理：支持用户中途打断"""

    def __init__(self):
        self._interrupted = False
        self._results = []
        self._lock = threading.Lock()

    def process_stream(self, stream_fn: Callable, on_item: Callable = None, timeout: float = 30) -> list:
        """处理流，支持中断"""
        self._interrupted = False
        self._results = []

        result_holder = [None]
        error_holder = [None]

        def worker():
            try:
                result_holder[0] = stream_fn()
            except Exception as e:
                error_holder[0] = e

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

        start_time = time.time()
        while thread.is_alive():
            if self._interrupted:
                break
            if time.time() - start_time > timeout:
                break
            time.sleep(0.1)

        if error_holder[0]:
            raise error_holder[0]

        return result_holder[0]

    def interrupt(self):
        """中断处理"""
        self._interrupted = True

    @property
    def is_interrupted(self):
        return self._interrupted


class ProgressiveDisplay:
    """渐进式显示：终端实时输出"""

    def __init__(self, use_ansi: bool = True):
        self.use_ansi = use_ansi
        self._current_line = ''

    def update(self, text: str):
        """更新当前行显示"""
        if self.use_ansi:
            sys.stdout.write(f'\r\033[K{text}')
            sys.stdout.flush()
        else:
            sys.stdout.write(text)
            sys.stdout.flush()
        self._current_line = text

    def finish(self, final_text: str = ''):
        """完成显示"""
        if self.use_ansi:
            sys.stdout.write('\n')
            sys.stdout.flush()
        if final_text:
            print(final_text)

    def show_progress(self, current: int, total: int, prefix: str = ''):
        """显示进度"""
        pct = int(current / max(total, 1) * 100)
        bar_len = 20
        filled = int(bar_len * current / max(total, 1))
        bar = '█' * filled + '░' * (bar_len - filled)
        self.update(f'{prefix} [{bar}] {pct}% ({current}/{total})')
