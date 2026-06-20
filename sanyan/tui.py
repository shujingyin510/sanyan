"""SanYan TUI — 三栏布局 (文件树 | Chat | 三态面板)"""
from textual.app import App, ComposeResult
from textual.widgets import Footer, Input, Static, TextArea, Tree
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from pathlib import Path

ROOT = Path(__file__).parent.parent


class FileTree(Tree):
    """左侧可展开文件树"""

    def __init__(self, *args, **kwargs):
        super().__init__("📁 sanyan", *args, **kwargs)
        self._populate(ROOT, self.root)

    def _populate(self, path: Path, parent):
        try:
            entries = sorted(path.iterdir())
        except PermissionError:
            return
        dirs = [e for e in entries if e.is_dir() and not e.name.startswith(".")
                and e.name not in ("__pycache__", ".git", ".github", "node_modules", "build", "dist")]
        files = [e for e in entries if e.is_file() and not e.name.startswith(".")
                 and e.suffix in (".py", ".san", ".md", ".txt", ".toml", ".json", ".yml", ".yaml", ".cfg")]
        for d in dirs[:12]:
            branch = parent.add(f"📁 {d.name}/", expand=False)
            self._populate(d, branch)
        for f in files[:10]:
            icon = "🐍" if f.suffix == ".py" else ("📜" if f.suffix == ".san" else "📄")
            parent.add_leaf(f"{icon} {f.name}")


class TernaryPanel(Static):
    """右侧三态面板"""
    state = reactive("就绪")
    trit = reactive("—")
    conf = reactive(0.0)
    rule = reactive("—")
    tools = reactive([])
    ur = reactive(1.0)

    def render(self):
        symbol = {"真": "●●●", "假": "○○○", "可能": "◐◐◐", "—": "———"}
        tool_lines = "\n".join(f"  {'✓' if t.get('ok') else '✗'} {t['name']}" for t in self.tools[-5:]) or "…"
        return (
            f"[bold magenta]✦ SanYan[/]\n"
            f"[green]{symbol.get(self.trit, '---')} {self.state}[/]\n"
            f"conf={self.conf:.2f}  UR={self.ur:.2f}\n"
            f"Rule: {self.rule}\n"
            f"[dim]{tool_lines}[/]\n"
            f"[dim]v3.42.0[/]"
        )


class SanyanTUI(App):
    CSS = """
    #topbar { height: 1; dock: top; align: center middle; }
    #tree-btn { width: 5; min-width: 5; max-width: 5; }
    #panel-btn { width: 5; min-width: 5; max-width: 5; }
    #title-label { width: 1fr; content-align: center middle; }
    #left { width: 28; border: solid gray; }
    #left.hidden { width: 0; border: none; visibility: hidden; }
    #right { width: 30; border: solid gray; }
    #right.hidden { width: 0; border: none; visibility: hidden; }
    #chat { height: 1fr; }
    #input { dock: bottom; }
    """

    BINDINGS = [
        ("ctrl+b", "toggle_tree", "文件树"),
        ("ctrl+r", "toggle_panel", "三态面板"),
        ("ctrl+c", "copy", "复制"),
        ("ctrl+q", "quit", "退出"),
    ]

    def compose(self) -> ComposeResult:
        from textual.widgets import Button, Label

        with Horizontal(id="topbar"):
            yield Button("📁", id="tree-btn")
            yield Label(" SanYan v3.42.0", id="title-label")
            yield Button("⚡", id="panel-btn")
        with Horizontal():
            yield FileTree(id="left")
            with Vertical(id="center"):
                yield TextArea(id="chat", read_only=True, language=None)
                yield Input(id="input", placeholder="Ask SanYan...")
            yield TernaryPanel(id="right")
        yield Footer()

    def on_mount(self):
        chat = self.query_one("#chat", TextArea)
        chat.insert("SanYan Agent 就绪\n")

    def on_button_pressed(self, event):
        if event.button.id == "tree-btn":
            self.action_toggle_tree()
        elif event.button.id == "panel-btn":
            self.action_toggle_panel()

    def action_toggle_tree(self):
        self.query_one("#left").toggle_class("hidden")

    def action_toggle_panel(self):
        self.query_one("#right").toggle_class("hidden")

    def action_quit(self):
        self.exit()

    def action_copy(self):
        chat = self.query_one("#chat", TextArea)
        text = chat.selected_text or chat.text
        if text:
            import pyperclip
            pyperclip.copy(text[:5000])

    def on_input_submitted(self, event: Input.Submitted):
        task = event.value.strip()
        if not task:
            return
        chat = self.query_one("#chat", TextArea)
        panel = self.query_one("#right", TernaryPanel)
        inp = self.query_one("#input", Input)
        inp.clear()
        chat.insert(f"\n🧑 {task}\n")

        try:
            import sys
            sys.path.insert(0, str(ROOT))
            from run_agent import load_api_key, init_evaluator
            from agent_system.agent_runtime import AgentRuntime

            api_key = load_api_key()
            ev = init_evaluator(api_key)
            rt = AgentRuntime(ev, False)

            original = rt._run_core

            def wrapped(*a, **kw):
                result = original(*a, **kw)
                if isinstance(result, dict):
                    mem = result.get("memory", {})
                    hist = mem.get("history", [])
                    tools = [{"name": h.get("tool", "?"), "ok": h.get("trit", 0) == 1} for h in hist]
                    ts = result.get("ternary", "")
                    panel.tools = tools
                    panel.rule = result.get("rule", "—")
                    if "真" in str(ts):
                        panel.trit = "真"
                        panel.state = "AFFIRM"
                    elif "假" in str(ts):
                        panel.trit = "假"
                        panel.state = "NEGATE"
                    else:
                        panel.trit = "可能"
                        panel.state = "UNCERT"
                    answer = result.get("answer", str(result))[:500]
                    chat.insert(f"🤖 {answer}\n")
                return result

            rt._run_core = wrapped
            panel.state = "执行中..."
            rt.run(task, max_rounds=5)

        except Exception as e:
            chat.insert(f"错误: {e}\n")


if __name__ == "__main__":
    SanyanTUI().run()
