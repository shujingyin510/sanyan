"""LSP 语言服务器测试"""

import sys
import os
import json
import subprocess
import unittest
import threading
import queue
import time


def _encode_msg(msg: dict) -> bytes:
    body = json.dumps(msg, ensure_ascii=False)
    header = f'Content-Length: {len(body.encode("utf-8"))}\r\n\r\n'
    return header.encode() + body.encode()


class LspClient:
    """简化的 LSP 客户端，支持后台读取所有消息。"""

    def __init__(self, script_path):
        self.proc = subprocess.Popen(
            [sys.executable, script_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self._msg_queue = queue.Queue()
        self._reader_thread = threading.Thread(target=self._reader, daemon=True)
        self._reader_thread.start()
        self._req_id = 0

    def _reader(self):
        """后台线程持续读取所有消息。"""
        while self.proc.poll() is None:
            try:
                header_line = self.proc.stdout.readline()
                if not header_line:
                    break
                header = header_line.decode().strip()
                if not header.startswith('Content-Length: '):
                    continue
                length = int(header[len('Content-Length: ') :])
                self.proc.stdout.readline()  # empty line
                body = self.proc.stdout.read(length).decode()
                self._msg_queue.put(json.loads(body))
            except (IOError, OSError, json.JSONDecodeError):
                break

    def send_request(self, method, params=None):
        self._req_id += 1
        msg = {'jsonrpc': '2.0', 'id': self._req_id, 'method': method}
        if params is not None:
            msg['params'] = params
        self.proc.stdin.write(_encode_msg(msg))
        self.proc.stdin.flush()
        return self._req_id

    def send_notification(self, method, params=None):
        msg = {'jsonrpc': '2.0', 'method': method}
        if params is not None:
            msg['params'] = params
        self.proc.stdin.write(_encode_msg(msg))
        self.proc.stdin.flush()

    def wait_for_response(self, req_id, timeout=5):
        """等待指定 id 的响应，跳过中间的通知。"""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                msg = self._msg_queue.get(timeout=0.5)
            except queue.Empty:
                continue
            if msg.get('id') == req_id:
                return msg
            # 通知消息（无 id）直接丢弃
        return None

    def close(self):
        self.send_notification('shutdown')
        self.proc.terminate()
        self.proc.wait(timeout=5)


class TestLspServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        script = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'lsp_server.py')
        cls.client = LspClient(script)
        req_id = cls.client.send_request(
            'initialize',
            {
                'processId': None,
                'capabilities': {},
            },
        )
        cls.init_resp = cls.client.wait_for_response(req_id)

    @classmethod
    def tearDownClass(cls):
        cls.client.close()

    def test_initialize_response(self):
        self.assertIsNotNone(self.init_resp)
        self.assertIn('capabilities', self.init_resp.get('result', {}))

    def test_completion(self):
        req_id = self.client.send_request(
            'textDocument/completion',
            {
                'textDocument': {'uri': 'file:///test.san'},
                'position': {'line': 0, 'character': 0},
            },
        )
        resp = self.client.wait_for_response(req_id)
        self.assertIsNotNone(resp)
        self.assertIsNotNone(resp.get('result'))

    def test_hover(self):
        req_id = self.client.send_request(
            'textDocument/hover',
            {
                'textDocument': {'uri': 'file:///test.san'},
                'position': {'line': 0, 'character': 0},
            },
        )
        resp = self.client.wait_for_response(req_id)
        self.assertIsNotNone(resp)

    def test_definition(self):
        req_id = self.client.send_request(
            'textDocument/definition',
            {
                'textDocument': {'uri': 'file:///test.san'},
                'position': {'line': 0, 'character': 0},
            },
        )
        resp = self.client.wait_for_response(req_id)
        self.assertIsNotNone(resp)

    def test_signature_help(self):
        req_id = self.client.send_request(
            'textDocument/signatureHelp',
            {
                'textDocument': {'uri': 'file:///test.san'},
                'position': {'line': 0, 'character': 0},
            },
        )
        resp = self.client.wait_for_response(req_id)
        self.assertIsNotNone(resp)

    def test_did_open_no_crash(self):
        self.client.send_notification(
            'textDocument/didOpen',
            {
                'textDocument': {
                    'uri': 'file:///test_doc.san',
                    'languageId': 'sanyan',
                    'version': 1,
                    'text': '设 x = 10\n输出(x)\n',
                }
            },
        )
        # 不返回响应，只是确认不崩溃


if __name__ == '__main__':
    unittest.main()
