"""Agent TUI v2 — 交互式面板（输入+模型切换+文件树）"""
import os, sys, time, threading, queue, select

HAS_RICH = False
try:
    from rich.layout import Layout
    from rich.panel import Panel
    from rich.live import Live
    from rich.console import Console
    from rich.text import Text
    HAS_RICH = True
except ImportError:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class AgentTUI:
    def __init__(self):
        self.console = Console()
        self.state = {
            'ternary': {'cog': '就绪', 'trit': '—', 'conf': 0},
            'rule': {'name': '—', 'steps': 0},
            'tools': [],
            'trace': [],
            'chat': [],
            'output': '',
            'ur': 1.0,
            'status': '就绪 — 输入任务按 Enter',
            'model': 'deepseek-v4-pro',
            'input_buffer': '',
        }
        self._running = True
        self._agent_queue = queue.Queue()

    def _build_left(self):
        tree = self._file_tree()
        trace_lines = self.state['trace'][-6:] or ['等待任务...']
        return Panel(
            f'{tree}\n\n{Text(chr(10).join(trace_lines), style="dim")}',
            title='📁 Files', border_style='dim',
        )

    def _build_center(self):
        chat_lines = self.state['chat'][-8:] or ['输入任务开始...']
        output = self.state['output'][:600] or '等待 Agent 响应...\n\n按 Enter 输入任务 | Tab 切换模型 | Ctrl+C 退出'
        input_display = self.state['input_buffer'] or '>>> '
        return Panel(
            f'{"".join(chat_lines)}\n{"─"*50}\n{output}\n\n[bold cyan]{input_display}[/bold cyan]█',
            title=f'💬 Chat & Output [{self.state["model"]}]', border_style='cyan',
        )

    def _build_right(self):
        t = self.state['ternary']
        symbol = {'真': '●●●', '假': '○○○', '可能': '◐◐◐', '—': '———'}.get(t['trit'], '———')
        color = {'真': 'green', '假': 'red', '可能': 'yellow', '—': 'dim'}.get(t['trit'], 'dim')
        tri = Panel(f'[{color}]{symbol} {t["cog"]}[/{color}]\nconf={t["conf"]:.2f}  UR={self.state["ur"]:.2f}', title='🔮 Ternary', border_style=color)
        r = self.state['rule']
        rule = Panel(f'命中: {r["name"]}\n步骤: {r["steps"]}', title='📏 Rule', border_style='blue' if r['name'] != '—' else 'dim')
        tl = []
        for tk in self.state['tools'][-5:]:
            m = '✓' if tk.get('ok') else '✗'
            tl.append(f'{m} {tk["tool"]}')
        tools = Panel('\n'.join(tl) or '…', title='🔧 Tools', border_style='yellow')
        trace_lines = self.state['trace'][-3:] or []
        trace = Panel('\n'.join(trace_lines) or '…', title='📋 Trace', border_style='dim')
        return Panel(f'{tri}\n{rule}\n{tools}\n{trace}', title='⚡ State', border_style='bold magenta')

    def _file_tree(self):
        def _w(path, d=0):
            if d > 2 or os.path.basename(path).startswith('.'):
                return ''
            try:
                es = sorted(os.listdir(path))
            except PermissionError:
                return ''
            lines = []
            indent = '  ' * d
            dirs = [e for e in es if os.path.isdir(os.path.join(path, e)) and not e.startswith('.') and e not in ('__pycache__', '.git', '.github', 'node_modules', 'build', 'dist', 'snapshots', 'blobs', 'refs')]
            files = [e for e in es if os.path.isfile(os.path.join(path, e)) and not e.startswith('.') and not e.endswith(('.pyc', '.db', '.dll', '.bin', '.safetensors', '.obj', '.o', '.png', '.json', '.md', '.txt', '.xml', '.yml'))]
            for d2 in dirs[:8]:
                lines.append(f'{indent}📁 {d2}/')
            for f in files[:5]:
                icon = '🐍' if f.endswith('.py') else ('📜' if f.endswith('.san') else ('⚙️' if f.endswith(('.c', '.asm', '.h')) else '📄'))
                lines.append(f'{indent}  {icon} {f}')
            return '\n'.join(lines)
        return f'📁 sanyan\n{_w(ROOT)}'

    def render(self):
        layout = Layout()
        layout.split_row(
            Layout(self._build_left(), name='left', ratio=3),
            Layout(self._build_center(), name='center', ratio=4),
            Layout(self._build_right(), name='right', ratio=3),
        )
        return Panel(layout, title=f'🤖 Sanyan Agent — {self.state["status"]}', border_style='bold green')

    def input_loop(self):
        """后台线程：读取键盘输入"""
        import msvcrt
        buf = ''
        while self._running:
            if msvcrt.kbhit():
                ch = msvcrt.getch()
                if ch == b'\r':  # Enter
                    if buf.strip():
                        self._agent_queue.put(buf.strip())
                        self.state['chat'].append(f'🧑 {buf.strip()[:80]}')
                        if len(self.state['chat']) > 8:
                            self.state['chat'].pop(0)
                        self.state['status'] = f'执行: {buf.strip()[:30]}...'
                    buf = ''
                elif ch == b'\t':  # Tab — 切换模型
                    models = ['deepseek-v4-pro', 'qwen2.5-0.5b', 'gpt2']
                    cur = self.state['model']
                    idx = models.index(cur) if cur in models else 0
                    self.state['model'] = models[(idx + 1) % len(models)]
                    self.state['trace'].append(f'切换模型: {self.state["model"]}')
                elif ch == b'\x08':  # Backspace
                    buf = buf[:-1]
                elif ch == b'\x1b':  # ESC
                    buf = ''
                elif len(ch) == 1 and 32 <= ch[0] <= 126:  # printable
                    buf += ch.decode('ascii', errors='replace')
                self.state['input_buffer'] = buf
            time.sleep(0.05)

    def _run_agent_task(self, task):
        """执行 Agent 任务并更新状态"""
        sys.path.insert(0, ROOT)
        from run_agent import load_api_key, init_evaluator
        from agent_system.agent_runtime import AgentRuntime

        api_key = load_api_key()
        ev = init_evaluator(api_key)
        rt = AgentRuntime(ev)

        original_run = rt._run_core
        def _wrapped(*a, **kw):
            self.state['trace'].append('Agent._run_core 开始')
            result = original_run(*a, **kw)
            if isinstance(result, dict):
                mem = result.get('memory', {})
                hist = mem.get('history', [])
                for h in hist[-3:]:
                    tool = h.get('tool', '?')
                    trit = h.get('trit', 0)
                    self.state['tools'].append({'tool': tool, 'ok': trit == 1})
                    if len(self.state['tools']) > 8:
                        self.state['tools'].pop(0)
                ts = result.get('ternary', '')
                if '真' in str(ts):
                    self.state['ternary'] = {'trit': '真', 'conf': 0.8, 'cog': 'AFFIRM'}
                elif '假' in str(ts):
                    self.state['ternary'] = {'trit': '假', 'conf': 0.3, 'cog': 'NEGATE'}
                if result.get('rule'):
                    self.state['rule'] = {'name': result['rule'], 'steps': len(hist)}
                answer = result.get('answer', '')[:600]
                self.state['output'] = answer
                self.state['chat'].append(f'🤖 {answer[:80]}')
                if len(self.state['chat']) > 8:
                    self.state['chat'].pop(0)
            self.state['trace'].append('完成')
            self.state['status'] = '就绪'
            return result

        rt._run_core = _wrapped
        self.state['status'] = f'执行: {task[:30]}...'
        rt.run(task, max_rounds=5)


def run():
    if not HAS_RICH:
        print('pip install rich')
        return

    tui = AgentTUI()
    console = Console()

    # 启动输入线程
    input_thread = threading.Thread(target=tui.input_loop, daemon=True)
    input_thread.start()

    try:
        with Live(tui.render(), console=console, refresh_per_second=6, screen=True) as live:
            while True:
                time.sleep(0.1)
                # 处理 Agent 任务队列
                try:
                    task = tui._agent_queue.get_nowait()
                    tui._run_agent_task(task)
                except queue.Empty:
                    pass
                live.update(tui.render())
    except KeyboardInterrupt:
        tui._running = False
        print('\n退出')


if __name__ == '__main__':
    run()
