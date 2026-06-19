"""Agent TUI — opencode 风格交互界面
用法: sanyan agent tui  或  python -X utf8 sanyan/agent_tui.py
"""
import os, sys, time, threading, queue
from datetime import datetime

HAS_RICH = False
try:
    from rich.layout import Layout
    from rich.panel import Panel
    from rich.table import Table
    from rich.tree import Tree
    from rich.text import Text
    from rich.live import Live
    from rich.console import Console
    from rich import box
    from rich.align import Align
    HAS_RICH = True
except ImportError:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class AgentTUI:
    def __init__(self):
        self.console = Console()
        self.state = {
            'ternary': {'cog': '就绪', 'trit': '—', 'conf': 0, 'history': []},
            'rule': {'name': '—', 'steps': 0},
            'tools': [],
            'trace': [],
            'chat': [],
            'output': '',
            'ur': 1.0,
            'status': '就绪 — 输入任务开始',
        }
        self._input_queue = queue.Queue()
        self._agent_thread = None

    def _build_left(self):
        tree = self._file_tree()
        trace_lines = self.state['trace'][-8:] or ['等待任务...']
        trace_text = '\n'.join(trace_lines)
        return Panel(
            f'{tree}\n\n{Text(trace_text, style="dim")}',
            title='📁 Files', border_style='dim',
        )

    def _build_center(self):
        chat_lines = self.state['chat'][-6:] or ['输入任务开始...']
        output = self.state['output'][:500] or '等待 Agent 响应...'
        return Panel(
            f'{"—"*40}\n{"".join(chat_lines)}\n{"—"*40}\n{output}',
            title='💬 Chat & Output', border_style='cyan',
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
        trace_lines = self.state['trace'][-4:] or []
        trace = Panel('\n'.join(trace_lines) or '…', title='📋 Trace', border_style='dim')
        return Panel(f'{tri}\n{rule}\n{tools}\n{trace}', title='⚡ State', border_style='bold magenta')

    def _file_tree(self, max_d=3):
        def _w(path, d=0, expanded=True):
            if d > max_d or os.path.basename(path).startswith('.'):
                return ''
            try:
                es = sorted(os.listdir(path))
            except PermissionError:
                return ''
            lines = []
            indent = '  ' * d
            dirs = [e for e in es if os.path.isdir(os.path.join(path, e)) and not e.startswith('.') and e not in ('__pycache__', '.git', '.github', 'node_modules', 'build', 'dist')]
            files = [e for e in es if os.path.isfile(os.path.join(path, e)) and not e.startswith('.') and not e.endswith(('.pyc', '.db', '.dll', '.bin', '.safetensors', '.obj', '.o', '.png', '.json', '.md'))]
            for d2 in dirs[:8]:
                marker = '▼' if expanded and d < max_d - 1 else '▶'
                lines.append(f'{indent}{marker} {d2}/')
                if expanded and d < max_d - 1:
                    sub = _w(os.path.join(path, d2), d + 1, expanded)
                    if sub:
                        lines.append(sub)
            for f in files[:6]:
                icon = '🐍' if f.endswith('.py') else ('📜' if f.endswith('.san') else ('⚙️' if f.endswith(('.c', '.asm', '.h')) else '📄'))
                lines.append(f'{indent}  {icon} {f}')
            return '\n'.join(lines)
        return f'📁 sanyan\n{_w(ROOT)}'

    def render(self):
        if not HAS_RICH:
            return '需要: pip install rich'
        layout = Layout()
        layout.split_row(
            Layout(self._build_left(), name='left', ratio=3),
            Layout(self._build_center(), name='center', ratio=4),
            Layout(self._build_right(), name='right', ratio=3),
        )
        return Panel(layout, title=f'🤖 Sanyan Agent — {self.state["status"]}', border_style='bold green')

    # ── 状态更新 API ──
    def log(self, msg):
        t = datetime.now().strftime('%H:%M:%S')
        self.state['trace'].append(f'[{t}] {msg}')
        if len(self.state['trace']) > 12:
            self.state['trace'].pop(0)
        self.state['status'] = msg[:40]

    def chat(self, role, msg):
        p = '🧑' if role == 'user' else '🤖'
        self.state['chat'].append(f'{p} {msg[:100]}')
        if len(self.state['chat']) > 8:
            self.state['chat'].pop(0)

    def ternary(self, trit, conf, cog):
        self.state['ternary'] = {'trit': trit, 'conf': conf, 'cog': cog}

    def rule(self, name, steps=0):
        self.state['rule'] = {'name': name, 'steps': steps}

    def tool(self, name, ok=True):
        self.state['tools'].append({'tool': name, 'ok': ok})
        if len(self.state['tools']) > 8:
            self.state['tools'].pop(0)

    def output(self, text):
        self.state['output'] = str(text)[:400]


class AgentTUIServer:
    """后台 Agent 执行，通过回调更新 TUI"""

    def __init__(self, tui):
        self.tui = tui
        self._queue = queue.Queue()

    def run_agent(self, task):
        """在后台线程运行 Agent"""
        def _run():
            self.tui.log('Agent 启动')
            self.tui.chat('user', task)

            # 导入 agent（延迟加载）
            sys.path.insert(0, ROOT)
            from run_agent import load_api_key, init_evaluator
            from agent_system.agent_runtime import AgentRuntime

            api_key = load_api_key()
            ev = init_evaluator(api_key)
            rt = AgentRuntime(ev)

            # 注入 TUI 回调
            original_execute = rt._run_core
            def _wrapped(*a, **kw):
                self.tui.log(f'执行开始: {task[:30]}')
                result = original_execute(*a, **kw)
                if isinstance(result, dict):
                    mem = result.get('memory', {})
                    hist = mem.get('history', [])
                    for h in hist[-3:]:
                        tool = h.get('tool', '?')
                        trit = h.get('trit', 0)
                        self.tui.tool(tool, trit == 1)
                    ts = result.get('ternary', '')
                    self.tui.ternary('真' if '真' in str(ts) else '—', 0.8, 'OK')
                    if result.get('rule'):
                        self.tui.rule(result['rule'])
                answer = result.get('answer', '') if isinstance(result, dict) else str(result)
                self.tui.output(str(answer)[:400])
                self.tui.chat('agent', str(answer)[:100])
                self.tui.log('完成')
                return result

            rt._run_core = _wrapped
            rt.run(task, max_rounds=5)

        threading.Thread(target=_run, daemon=True).start()


def run():
    """CLI 入口"""
    if not HAS_RICH:
        print('pip install rich')
        return

    tui = AgentTUI()
    server = AgentTUIServer(tui)

    console = Console()
    task = ' '.join(sys.argv[1:]) if len(sys.argv) > 1 else None

    with Live(tui.render(), console=console, refresh_per_second=4, screen=True) as live:
        if task:
            server.run_agent(task)
            for _ in range(120):  # 最多等 120 * 0.5 = 60秒
                time.sleep(0.5)
                live.update(tui.render())
        else:
            # 交互模式：等待输入
            tui.state['status'] = '等待输入任务...'
            live.update(tui.render())
            while True:
                try:
                    task = input('\n任务> ')
                    if not task:
                        break
                    server.run_agent(task)
                    for _ in range(120):
                        time.sleep(0.5)
                        live.update(tui.render())
                except (KeyboardInterrupt, EOFError):
                    break


if __name__ == '__main__':
    run()
