"""Web IDE 原型：浏览器内编辑器 + REPL

用法:
    python web_ide.py [--port 8080]

启动后在浏览器打开 http://localhost:8080
"""

import http.server
import json
import os
import threading
import webbrowser

# 项目根目录
ROOT = os.path.dirname(os.path.abspath(__file__))

# 全局求值器实例（线程安全）
_evaluator_lock = threading.Lock()
_evaluator = None


def _get_evaluator():
    global _evaluator
    if _evaluator is None:
        from evaluator import SanyanEvaluator
        from skin import SkinManager

        _evaluator = SanyanEvaluator(skin_manager=SkinManager('chinese'))
    return _evaluator


def _execute_code(code: str) -> dict:
    """执行三言代码，返回结果。"""
    from sugar import SugarConverter
    from values import SanyanError

    with _evaluator_lock:
        env = _get_evaluator()
        env._source = code

        try:
            ast = SugarConverter.convert(code, env.skin_manager)
            if ast is None:
                return {'success': False, 'error': '语法错误: 无法解析代码'}
            result = env.eval(ast)
            return {
                'success': True,
                'result': str(result) if result is not None else '无',
            }
        except SanyanError as e:
            return {'success': False, 'error': f'执行错误: {e}'}
        except Exception as e:
            return {'success': False, 'error': f'系统错误: {e}'}


# HTML 页面模板
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>三言 Web IDE</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
            background: #1e1e1e;
            color: #d4d4d4;
            height: 100vh;
            display: flex;
            flex-direction: column;
        }
        header {
            background: #252526;
            padding: 10px 20px;
            border-bottom: 1px solid #3c3c3c;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        header h1 {
            font-size: 18px;
            color: #569cd6;
        }
        header .version {
            color: #808080;
            font-size: 12px;
        }
        .container {
            display: flex;
            flex: 1;
            overflow: hidden;
        }
        .editor-panel {
            flex: 1;
            display: flex;
            flex-direction: column;
            border-right: 1px solid #3c3c3c;
        }
        .panel-header {
            background: #2d2d2d;
            padding: 8px 15px;
            border-bottom: 1px solid #3c3c3c;
            font-size: 12px;
            color: #808080;
        }
        .editor {
            flex: 1;
            padding: 15px;
            background: #1e1e1e;
            color: #d4d4d4;
            font-family: inherit;
            font-size: 14px;
            line-height: 1.5;
            border: none;
            outline: none;
            resize: none;
            tab-size: 4;
        }
        .output-panel {
            flex: 1;
            display: flex;
            flex-direction: column;
        }
        .output {
            flex: 1;
            padding: 15px;
            background: #1e1e1e;
            overflow-y: auto;
            font-size: 14px;
            line-height: 1.5;
        }
        .output .line {
            margin-bottom: 5px;
        }
        .output .prompt {
            color: #569cd6;
        }
        .output .result {
            color: #b5cea8;
        }
        .output .error {
            color: #f44747;
        }
        .toolbar {
            background: #2d2d2d;
            padding: 8px 15px;
            border-top: 1px solid #3c3c3c;
            display: flex;
            gap: 10px;
        }
        button {
            background: #0e639c;
            color: white;
            border: none;
            padding: 6px 15px;
            border-radius: 3px;
            cursor: pointer;
            font-size: 12px;
        }
        button:hover {
            background: #1177bb;
        }
        button.secondary {
            background: #3c3c3c;
        }
        button.secondary:hover {
            background: #505050;
        }
        .repl-input {
            display: flex;
            padding: 10px 15px;
            background: #252526;
            border-top: 1px solid #3c3c3c;
        }
        .repl-input span {
            color: #569cd6;
            margin-right: 10px;
            line-height: 30px;
        }
        .repl-input input {
            flex: 1;
            background: #1e1e1e;
            color: #d4d4d4;
            border: 1px solid #3c3c3c;
            padding: 5px 10px;
            font-family: inherit;
            font-size: 14px;
            outline: none;
        }
        .repl-input input:focus {
            border-color: #0e639c;
        }
        .status-bar {
            background: #007acc;
            padding: 3px 10px;
            font-size: 11px;
            display: flex;
            justify-content: space-between;
        }
        .examples {
            padding: 10px;
            background: #2d2d2d;
            border-top: 1px solid #3c3c3c;
        }
        .examples button {
            margin-right: 5px;
            margin-bottom: 5px;
            background: #3c3c3c;
            font-size: 11px;
            padding: 4px 10px;
        }
    </style>
</head>
<body>
    <header>
        <h1>三言 Web IDE</h1>
        <span class="version">v3.50</span>
    </header>
    <div class="container">
        <div class="editor-panel">
            <div class="panel-header">编辑器</div>
            <textarea class="editor" id="editor" spellcheck="false">// 在此编写三言代码
设 x = 10
输出(加 x 5)
</textarea>
            <div class="toolbar">
                <button onclick="runCode()">▶ 运行 (Ctrl+Enter)</button>
                <button class="secondary" onclick="clearOutput()">清空输出</button>
                <button class="secondary" onclick="saveFile()">保存</button>
                <button class="secondary" onclick="loadFile()">加载</button>
                <button class="secondary" onclick="loadExample('hello')">Hello</button>
                <button class="secondary" onclick="loadExample('loop')">循环</button>
                <button class="secondary" onclick="loadExample('function')">函数</button>
                <button class="secondary" onclick="loadExample('ternary')">三态</button>
                <button class="secondary" onclick="loadExample('list')">列表</button>
            </div>
        </div>
        <div class="output-panel">
            <div class="panel-header">输出</div>
            <div class="output" id="output"></div>
            <div class="repl-input">
                <span>三言&gt;</span>
                <input type="text" id="repl-input" placeholder="输入表达式按回车..."
                       onkeydown="if(event.key==='Enter')replExec()">
            </div>
        </div>
    </div>
    <div class="status-bar">
        <span id="status">就绪</span>
        <span>UTF-8 | 三言</span>
    </div>

    <script>
        const editor = document.getElementById('editor');
        const output = document.getElementById('output');
        const replInput = document.getElementById('repl-input');
        const status = document.getElementById('status');

        // 快捷键
        editor.addEventListener('keydown', (e) => {
            if (e.ctrlKey && e.key === 'Enter') {
                e.preventDefault();
                runCode();
            }
            // Tab 缩进
            if (e.key === 'Tab') {
                e.preventDefault();
                const start = editor.selectionStart;
                const end = editor.selectionEnd;
                editor.value = editor.value.substring(0, start) + '    ' + editor.value.substring(end);
                editor.selectionStart = editor.selectionEnd = start + 4;
            }
        });

        async function runCode() {
            const code = editor.value.trim();
            if (!code) return;

            appendOutput('三言> ' + code.substring(0, 50) + (code.length > 50 ? '...' : ''), 'prompt');
            status.textContent = '执行中...';

            try {
                const resp = await fetch('/execute', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({code: code})
                });
                const data = await resp.json();

                if (data.success) {
                    appendOutput('=> ' + data.result, 'result');
                } else {
                    appendOutput(data.error, 'error');
                }
            } catch (err) {
                appendOutput('网络错误: ' + err, 'error');
            }

            status.textContent = '就绪';
        }

        async function replExec() {
            const code = replInput.value.trim();
            if (!code) return;

            replInput.value = '';
            appendOutput('三言> ' + code, 'prompt');

            try {
                const resp = await fetch('/execute', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({code: code})
                });
                const data = await resp.json();

                if (data.success) {
                    appendOutput('=> ' + data.result, 'result');
                } else {
                    appendOutput(data.error, 'error');
                }
            } catch (err) {
                appendOutput('网络错误: ' + err, 'error');
            }
        }

        function appendOutput(text, cls) {
            const line = document.createElement('div');
            line.className = 'line ' + cls;
            line.textContent = text;
            output.appendChild(line);
            output.scrollTop = output.scrollHeight;
        }

        function clearOutput() {
            output.innerHTML = '';
        }

        function loadExample(name) {
            const examples = {
                hello: '输出("你好，世界！")',
                loop: '设 i = 0\\n循环 (小于 i 5) {\\n    输出(连接 "第 " (转字符串 i) " 次")\\n    设 i (加 i 1)\\n}',
                function: '定义 斐波那契 (n) {\\n    若 (小于等于 n 1) { 返回(n) }\\n    返回(加 (斐波那契 (减 n 1)) (斐波那契 (减 n 2)))\\n}\\n输出(斐波那契 10)',
                ternary: '设 光线 = 可能\\n若 (光线 == 真) {\\n    输出("光照充足")\\n} 再若 (光线 == 假) {\\n    输出("光照不足")\\n} 否则 {\\n    输出("光照不稳")\\n}',
                list: '设 列表 = [1, 2, 3, 4, 5]\\n输出(映射 列表 (函数(x) { 返回(乘 x x) }))'
            };
            editor.value = examples[name] || '';
        }

        // 文件保存
        function saveFile() {
            const code = editor.value;
            const blob = new Blob([code], {type: 'text/plain'});
            const a = document.createElement('a');
            a.href = URL.createObjectURL(blob);
            a.download = 'program.san';
            a.click();
        }

        // 文件加载
        function loadFile() {
            const input = document.createElement('input');
            input.type = 'file';
            input.accept = '.san,.txt';
            input.onchange = (e) => {
                const file = e.target.files[0];
                if (file) {
                    const reader = new FileReader();
                    reader.onload = (ev) => {
                        editor.value = ev.target.result;
                    };
                    reader.readAsText(file);
                }
            };
            input.click();
        }
    </script>
</body>
</html>"""


class SanyanHTTPHandler(http.server.BaseHTTPRequestHandler):
    """HTTP 请求处理器。"""

    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            self._serve_html()
        elif self.path == '/health':
            self._serve_json({'status': 'ok'})
        else:
            self._serve_error(404, 'Not Found')

    def do_POST(self):
        if self.path == '/execute':
            self._handle_execute()
        else:
            self._serve_error(404, 'Not Found')

    def _serve_html(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(HTML_TEMPLATE.encode('utf-8'))

    def _serve_json(self, data: dict):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))

    def _serve_error(self, code: int, message: str):
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.end_headers()
        self.wfile.write(json.dumps({'error': message}).encode('utf-8'))

    def _handle_execute(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode('utf-8'))
            code = data.get('code', '')
            result = _execute_code(code)
            self._serve_json(result)
        except Exception as e:
            self._serve_json({'success': False, 'error': f'请求错误: {e}'})

    def log_message(self, format, *args):
        """禁用默认日志（避免污染控制台）。"""
        pass


def main():
    import argparse

    parser = argparse.ArgumentParser(description='三言 Web IDE')
    parser.add_argument('--port', type=int, default=8080, help='端口号 (默认 8080)')
    parser.add_argument('--host', default='localhost', help='主机名 (默认 localhost)')
    parser.add_argument('--open', action='store_true', help='自动打开浏览器')
    args = parser.parse_args()

    server = http.server.HTTPServer((args.host, args.port), SanyanHTTPHandler)
    print(f'三言 Web IDE 已启动: http://{args.host}:{args.port}')
    print('按 Ctrl+C 停止服务器')

    if args.open:
        threading.Timer(1.0, lambda: webbrowser.open(f'http://{args.host}:{args.port}')).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n服务器已停止')
        server.server_close()


if __name__ == '__main__':
    main()
