"""Agent Execution Panel — 三栏 TUI (文件树 | Chat+Agent | 三态+规则+工具链)"""
import os, sys, time, json, threading, queue
from datetime import datetime

try:
    from rich.layout import Layout
    from rich.panel import Panel
    from rich.table import Table
    from rich.tree import Tree
    from rich.text import Text
    from rich.live import Live
    from rich.console import Console, Group
    from rich.columns import Columns
    from rich import box
    HAS_RICH = True
except ImportError:
    HAS_RICH = False


class AgentPanel:
    """Agent 执行可视化面板"""

    def __init__(self, project_root=None):
        self.root = project_root or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.state = {
            'ternary': {'trit': '—', 'conf': 0.0, 'cog': '等待中', 'history': []},
            'rule': {'name': '—', 'matched': False, 'steps': []},
            'tools': [],
            'trace': [],
            'chat': [],
            'agent_output': '',
            'file_tree': [],
            'status': '就绪',
            'ur': 1.0,
        }
        self.console = Console()

    def update_ternary(self, trit, conf, cog, display=''):
        h = self.state['ternary']['history']
        h.append({'trit': trit, 'conf': conf, 'cog': cog, 'display': display})
        if len(h) > 8:
            h.pop(0)
        self.state['ternary'].update({'trit': trit, 'conf': conf, 'cog': cog})
        self.state['ur'] = conf

    def update_rule(self, name, steps=None):
        self.state['rule'] = {'name': name, 'matched': bool(name != '—'), 'steps': steps or []}

    def update_tool(self, tool, desc, result='', trit='', conf=0):
        self.state['tools'].append({'tool': tool, 'desc': desc, 'result': str(result)[:60], 'trit': trit, 'conf': conf})
        if len(self.state['tools']) > 6:
            self.state['tools'].pop(0)

    def update_trace(self, msg):
        t = datetime.now().strftime('%H:%M:%S')
        self.state['trace'].append(f'[{t}] {msg}')
        if len(self.state['trace']) > 10:
            self.state['trace'].pop(0)

    def update_chat(self, role, msg):
        prefix = '🧑' if role == 'user' else '🤖'
        self.state['chat'].append(f'{prefix} {msg[:120]}')
        if len(self.state['chat']) > 4:
            self.state['chat'].pop(0)

    def update_output(self, text):
        self.state['agent_output'] = text

    def build_file_tree(self, max_depth=2):
        def _walk(path, depth=0):
            if depth > max_depth or path.startswith('.'):
                return None
            try:
                entries = sorted(os.listdir(path))
            except PermissionError:
                return None
            node = Tree(os.path.basename(path) or path, guide_style='dim')
            dirs = [e for e in entries if os.path.isdir(os.path.join(path, e)) and not e.startswith('.')]
            files = [e for e in entries if os.path.isfile(os.path.join(path, e)) and not e.startswith('.')]
            for d in dirs[:8]:
                sub = _walk(os.path.join(path, d), depth + 1)
                if sub:
                    node.add(sub)
            for f in files[:15]:
                style = 'green' if f.endswith('.py') else ('blue' if f.endswith('.san') else 'white')
                node.add(f'[{style}]{f}[/{style}]')
            return node

        tree = Tree(f'📁 {os.path.basename(self.root)}', guide_style='bold')
        dirs = [d for d in sorted(os.listdir(self.root)) if os.path.isdir(os.path.join(self.root, d)) and not d.startswith('.') and d not in ('__pycache__', '.git', '.github', 'node_modules')]
        for d in dirs[:10]:
            sub = _walk(os.path.join(self.root, d))
            if sub:
                tree.add(sub)
        return tree

    def render(self):
        if not HAS_RICH:
            return self._render_text()

        s = self.state
        t = s['ternary']

        # ── 左侧: 文件树 + 执行追踪 ──
        left_panels = [self.build_file_tree()]
        if s['trace']:
            trace_text = '\n'.join(s['trace'][-8:])
            left_panels.append(Panel(trace_text, title='📋 Execution Trace', border_style='dim'))

        # ── 中间: Chat + Agent Output ──
        center_top = ''
        if s['chat']:
            center_top = '\n'.join(s['chat'][-4:])
        center_bottom = s['agent_output'][:500] if s['agent_output'] else '等待任务输入...'

        center = Group(
            Panel(center_top or '输入任务开始...', title='💬 Chat', border_style='cyan'),
            Panel(center_bottom, title='📤 Agent Output', border_style='green'),
        )

        # ── 右侧: 三态 + 规则 + 工具链 ──
        # 三态
        trit_symbol = {'真': '●●●', '假': '○○○', '可能': '◐◐◐', '—': '———'}
        trit_color = {'真': 'green', '假': 'red', '可能': 'yellow', '—': 'dim'}
        symbol = trit_symbol.get(t['trit'], '———')
        color = trit_color.get(t['trit'], 'dim')
        ternary_panel = Panel(
            f'[{color}]{symbol} {t["cog"]}[/{color}]\n置信度: {t["conf"]:.2f} | UR: {s["ur"]:.2f}',
            title='🔮 Ternary State', border_style=color,
        )

        # 规则
        r = s['rule']
        rule_text = f'匹配: {r["name"]}\n步骤数: {len(r["steps"])}' if r['matched'] else '未匹配规则'
        rule_panel = Panel(rule_text, title='📏 Rule Hit', border_style='blue' if r['matched'] else 'dim')

        # 工具链
        tool_lines = []
        for tk in s['tools'][-5:]:
            ts = {'真': '✅', '假': '❌', '可能': '⚠️', '': ''}.get(tk.get('trit', ''), '')
            tool_lines.append(f'{ts} {tk["tool"]}: {tk["desc"][:30]}')
        tool_panel = Panel('\n'.join(tool_lines) or '…', title='🔧 Tool Chain', border_style='yellow')

        right = Group(ternary_panel, rule_panel, tool_panel)

        layout = Layout()
        layout.split_row(
            Layout(Group(*left_panels), name='left', ratio=1),
            Layout(center, name='center', ratio=2),
            Layout(right, name='right', ratio=1),
        )

        return Panel(layout, title=f'🤖 Sanyan Agent Panel | {s["status"]}', border_style='bold magenta')

    def _render_text(self):
        """Fallback: 纯文本渲染"""
        s = self.state
        t = s['ternary']
        lines = [
            f'╔══ Sanyan Agent Panel ══ {s["status"]} ══╗',
            f'║ 三态: {t["cog"]} conf={t["conf"]:.2f} UR={s["ur"]:.2f}',
            f'║ 规则: {s["rule"]["name"]}',
            f'║ 工具: {len(s["tools"])} 步',
            f'║ 输出: {s["agent_output"][:80]}',
            f'╚{"═"*40}╝',
        ]
        return '\n'.join(lines)


class AgentPanelServer:
    """后台线程收集 Agent 状态，供 TUI 轮询"""

    def __init__(self):
        self.panel = AgentPanel()
        self._queue = queue.Queue()

    def send(self, event_type, **data):
        self._queue.put({'type': event_type, 'data': data, 'ts': time.time()})

    def _process(self):
        while not self._queue.empty():
            evt = self._queue.get_nowait()
            t = evt['type']
            d = evt['data']
            if t == 'ternary':
                self.panel.update_ternary(**d)
            elif t == 'rule':
                self.panel.update_rule(**d)
            elif t == 'tool':
                self.panel.update_tool(**d)
            elif t == 'trace':
                self.panel.update_trace(**d)
            elif t == 'chat':
                self.panel.update_chat(**d)
            elif t == 'output':
                self.panel.update_output(**d)


# ── CLI ──
if __name__ == '__main__':
    if not HAS_RICH:
        print('需要 pip install rich')
        sys.exit(1)

    # Demo mode
    panel = AgentPanel()
    console = Console()

    # Simulate agent execution
    panel.update_chat('user', '在src下新建utils.py，实现计时器')
    panel.update_trace('收到任务')
    panel.update_rule('创建Python模块', ['write_file', 'write_file(test)', 'run_shell'])
    panel.update_trace('规则匹配: 创建Python模块')

    panel.update_tool('write_file', '创建 utils.py', '已写入 src/utils.py')
    panel.update_ternary('真', 0.81, 'AFFIRM', '真 ●●● [0.81]')
    panel.update_trace('工具执行: write_file → 成功')

    panel.update_tool('write_file', '创建测试', '已写入 tests/test_utils.py', '真', 0.66)
    panel.update_ternary('真', 0.66, 'AFFIRM', '真 ●●● [0.66]')
    panel.update_trace('工具执行: write_file(test) → 成功')

    panel.update_tool('run_shell', '运行测试', '. [100%]', '真', 0.53)
    panel.update_ternary('真', 0.53, 'AFFIRM', '真 ●●● [0.53]')
    panel.update_trace('验证通过 ✓')

    panel.update_output('按规则 [创建Python模块] 执行完成\nsrc/utils.py 已创建，测试通过')
    panel.state['status'] = '完成 ✅'

    with Live(panel.render(), console=console, refresh_per_second=4, screen=True) as live:
        for _ in range(30):
            time.sleep(0.1)
            live.update(panel.render())
