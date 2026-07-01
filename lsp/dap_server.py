"""三言调试适配器协议 (DAP) 服务器。

支持 VS Code 断点、单步、变量查看。

用法: python dap_server.py  然后 VS Code 连接 stdio DAP。
"""

from __future__ import annotations
import json
import os
import sys
import threading
from typing import Any, Optional

_CONTENT_LENGTH_HEADER = 'Content-Length: '


class DapServer:
    """DAP 协议服务器：断点管理 + 执行控制。"""

    def __init__(self):
        self._seq = 0
        self._breakpoints: dict[str, list[dict]] = {}  # path → [line, line, ...]
        self._stopped = threading.Event()
        self._stopped.clear()
        self._paused = False
        self._running = False
        self._evaluator = None
        self._eval_thread = None
        self._step_mode: Optional[str] = None  # 'next', 'stepIn', None
        self._step_count = 0
        self._source_code: dict[str, str] = {}
        self._source_ast: dict[str, Any] = {}

    # --- LSP 基础 I/O ---

    def _send(self, msg: dict) -> None:
        body = json.dumps(msg, ensure_ascii=False)
        data = body.encode('utf-8')
        header = f'{_CONTENT_LENGTH_HEADER}{len(data)}\r\n\r\n'
        sys.stdout.buffer.write(header.encode() + data)
        sys.stdout.buffer.flush()

    def _send_event(self, event: str, body: dict | None = None) -> None:
        self._seq += 1
        msg: dict = {'type': 'event', 'seq': self._seq, 'event': event}
        if body:
            msg['body'] = body
        self._send(msg)

    def _send_response(self, request: dict, body: dict | None = None) -> None:
        self._seq += 1
        self._send(
            {
                'type': 'response',
                'seq': self._seq,
                'request_seq': request['seq'],
                'command': request['command'],
                'success': True,
                'body': body or {},
            }
        )

    def _read(self) -> Optional[dict]:
        headers = {}
        while True:
            line = sys.stdin.buffer.readline()
            if not line:
                return None
            line = line.decode('utf-8', errors='replace').strip()
            if not line:
                break
            if line.startswith(_CONTENT_LENGTH_HEADER):
                headers['content-length'] = int(line[len(_CONTENT_LENGTH_HEADER) :])
        length = headers.get('content-length', 0)
        if length == 0:
            return None
        body = sys.stdin.buffer.read(length).decode('utf-8', errors='replace')
        return json.loads(body)  # type: ignore[no-any-return]

    # --- Evaluator Hooks ---

    def _on_breakpoint(self, evaluator, cur_op: str, args: list) -> None:
        """在断点处暂停执行。"""
        path = getattr(evaluator, '_dap_source_path', '')
        line = getattr(evaluator, '_dap_line', 0)
        if path:
            breakpoints = self._breakpoints.get(path, [])
            for bp in breakpoints:
                if bp.get('verified') and bp['line'] == line:
                    break
            else:
                # 不是断点行，继续
                return

        self._paused = True
        self._send_event(
            'stopped',
            {
                'reason': 'breakpoint',
                'threadId': 1,
                'allThreadsStopped': True,
            },
        )
        # 等待继续
        self._stopped.wait()
        self._stopped.clear()
        self._paused = False

    def _on_step(self, evaluator, cur_op: str, args: list) -> None:
        """单步暂停。"""
        if self._step_mode == 'next' and self._step_count > 0:
            self._step_count -= 1
            return
        self._paused = True
        self._send_event(
            'stopped',
            {
                'reason': 'step',
                'threadId': 1,
                'allThreadsStopped': True,
            },
        )
        self._stopped.wait()
        self._stopped.clear()
        self._paused = False
        self._step_count = 0

    def _patch_evaluator(self, evaluator):
        """为求值器安装调试钩子。"""
        evaluator._dap_server = self
        evaluator._dap_source_path = ''
        evaluator._dap_line = 0

        orig_eval = evaluator.eval

        def debug_eval(node):
            if isinstance(node, list) and hasattr(node, 'line') and hasattr(node, 'col'):
                evaluator._dap_line = node.line + 1 if hasattr(node, 'line') else 0
            if self._step_mode:
                self._on_step(evaluator, str(node)[:40], [])
            if evaluator._dap_source_path:
                self._on_breakpoint(evaluator, str(node)[:40], [])
            return orig_eval(node)

        evaluator.eval = debug_eval

    # --- Request Handlers ---

    def _handle_initialize(self, request: dict) -> None:
        self._send_response(
            request,
            {
                'supportsConfigurationDoneRequest': True,
                'supportsSingleThreadExecutionRequests': False,
                'supportsStepInTargetsRequest': False,
            },
        )

    def _handle_set_breakpoints(self, request: dict) -> None:
        args = request.get('arguments', {})
        source = args.get('source', {})
        path = source.get('path', '')
        requested = args.get('breakpoints', [])
        breakpoints = []
        for bp in requested:
            breakpoints.append(
                {
                    'verified': True,
                    'line': bp['line'],
                }
            )
        self._breakpoints[path] = breakpoints
        self._send_response(request, {'breakpoints': breakpoints})

    def _handle_configuration_done(self, request: dict) -> None:
        self._send_response(request)
        # 启动执行线程
        if self._source_code:
            self._start_execution()

    def _handle_launch(self, request: dict) -> None:
        args = request.get('arguments', {})
        program = args.get('program', '')
        if program and os.path.exists(program):
            with open(program, 'r', encoding='utf-8') as f:
                self._source_code[program] = f.read()
        self._send_response(request)
        self._send_event('initialized')

    def _handle_threads(self, request: dict) -> None:
        self._send_response(
            request,
            {
                'threads': [{'id': 1, 'name': 'main'}],
            },
        )

    def _handle_stack_trace(self, request: dict) -> None:
        frames = []
        if self._evaluator:
            for i, (op, args) in enumerate(reversed(self._evaluator.call_stack)):
                fa = ', '.join(str(a) for a in args)
                frames.append(
                    {
                        'id': i,
                        'name': f'{op}({fa})',
                        'source': {'name': 'eval'},
                        'line': 0,
                        'column': 0,
                    }
                )
            if not frames:
                frames.append(
                    {
                        'id': 0,
                        'name': '<顶层>',
                        'source': {'name': 'eval'},
                        'line': 0,
                        'column': 0,
                    }
                )
        self._send_response(
            request,
            {
                'stackFrames': frames,
                'totalFrames': len(frames),
            },
        )

    def _handle_scopes(self, request: dict) -> None:
        self._send_response(
            request,
            {
                'scopes': [
                    {
                        'name': '局部变量',
                        'variablesReference': 1000,
                        'expensive': False,
                    }
                ],
            },
        )

    def _handle_variables(self, request: dict) -> None:
        variables = []
        if self._evaluator:
            for name in sorted(self._evaluator.all_scoped_vars()):
                try:
                    val = self._evaluator.get_var(name)
                    val_str = str(val)
                    if len(val_str) > 50:
                        val_str = val_str[:47] + '...'
                    variables.append(
                        {
                            'name': name,
                            'value': val_str,
                            'variablesReference': 0,
                        }
                    )
                except Exception:
                    pass
        self._send_response(request, {'variables': variables})

    def _handle_continue(self, request: dict) -> None:
        self._step_mode = None
        self._step_count = 0
        self._stopped.set()
        self._send_response(request, {'allThreadsContinued': True})

    def _handle_next(self, request: dict) -> None:
        self._step_mode = 'next'
        self._step_count = 1
        self._stopped.set()
        self._send_response(request)

    def _handle_step_in(self, request: dict) -> None:
        self._step_mode = 'stepIn'
        self._step_count = 0
        self._stopped.set()
        self._send_response(request)

    def _handle_disconnect(self, request: dict) -> None:
        self._stopped.set()
        self._send_response(request)

    # --- Execution ---

    def _start_execution(self) -> None:
        def run():
            try:
                from core.evaluator import SanyanEvaluator
                from core.skin import SkinManager
                from sugar import SugarConverter

                skin_mgr = SkinManager('chinese')
                evaluator = SanyanEvaluator(skin_manager=skin_mgr)
                self._patch_evaluator(evaluator)
                self._evaluator = evaluator

                for path, code in self._source_code.items():
                    evaluator._dap_source_path = path  # type: ignore[attr-defined]
                    ast = SugarConverter.convert(code, skin_mgr)
                    evaluator.eval(ast)

                self._send_event('exited', {'exitCode': 0})
            except Exception:
                self._send_event('exited', {'exitCode': 1})

        self._eval_thread = threading.Thread(target=run, daemon=True)
        self._eval_thread.start()

    # --- Dispatch Loop ---

    def run(self) -> None:
        handlers = {
            'initialize': self._handle_initialize,
            'launch': self._handle_launch,
            'setBreakpoints': self._handle_set_breakpoints,
            'configurationDone': self._handle_configuration_done,
            'threads': self._handle_threads,
            'stackTrace': self._handle_stack_trace,
            'scopes': self._handle_scopes,
            'variables': self._handle_variables,
            'continue': self._handle_continue,
            'next': self._handle_next,
            'stepIn': self._handle_step_in,
            'disconnect': self._handle_disconnect,
        }
        while True:
            msg = self._read()
            if msg is None:
                break
            if msg.get('type') == 'request':
                cmd = msg.get('command', '')
                handler = handlers.get(cmd)
                if handler:
                    handler(msg)
                else:
                    self._send(
                        {
                            'type': 'response',
                            'seq': self._seq,
                            'request_seq': msg['seq'],
                            'command': cmd,
                            'success': True,
                            'body': {},
                        }
                    )


if __name__ == '__main__':
    DapServer().run()
