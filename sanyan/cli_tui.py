"""SanYan CLI — 原生终端 TUI (零框架，Ctrl+C 可控)"""

import os
import sys
import time
import threading
from pathlib import Path

ROOT = Path(__file__).parent.parent
os.system('')  # 启用 ANSI


def ansi(x, y, text):
    """移动光标到 (y,x) 并输出文本"""
    # Textual-like: x is column, y is row
    sys.stdout.write(f'\033[{y};{x}H{text}\033[K')
    sys.stdout.flush()


def clear():
    sys.stdout.write('\033[2J\033[H')
    sys.stdout.flush()


def file_tree():
    lines = []

    def walk(path, depth=0):
        if depth > 2 or path.name.startswith('.'):
            return
        try:
            entries = sorted(path.iterdir())
        except PermissionError:
            return
        indent = '  ' * depth
        dirs = [
            e
            for e in entries
            if e.is_dir()
            and not e.name.startswith('.')
            and e.name not in ('__pycache__', '.git', '.github', 'node_modules', 'build', 'dist')
        ]
        files = [
            e for e in entries if e.is_file() and not e.name.startswith('.') and e.suffix in ('.py', '.san', '.md')
        ]
        for d in dirs[:8]:
            lines.append(f'{indent}📁 {d.name}/')
            walk(d, depth + 1)
        for f in files[:5]:
            icon = '🐍' if f.suffix == '.py' else '📄'
            lines.append(f'{indent}  {icon} {f.name}')

    walk(ROOT)
    return lines


def draw_frame(chat_lines, ternary_state, input_buf):
    """绘制三栏布局"""
    w, h = os.get_terminal_size()
    clear()

    # 顶栏
    ansi(1, 1, f' {"─" * (w - 2)}')
    ansi(2, 1, f' 📁 {"SanYan v3.42.0":^{w - 10}} ⚡ │')

    # 左栏 (0-27): 文件树
    tree = file_tree()
    for i in range(min(h - 6, len(tree))):
        ansi(1, 4 + i, f' {tree[i]:<26} │')

    # 右栏 (w-30, w): 三态面板
    rx = w - 30
    t = ternary_state
    ansi(rx, 4, '✦ SanYan')
    ansi(rx, 5, f'{t["symbol"]} {t["state"]}')
    ansi(rx, 6, f'conf={t["conf"]:.2f}  UR={t["ur"]:.2f}')
    ansi(rx, 7, f'Rule: {t["rule"]}')
    for i, tool in enumerate(t['tools'][-5:]):
        ok = '✓' if tool.get('ok') else '✗'
        ansi(rx, 8 + i, f'  {ok} {tool["name"]}')
    ansi(rx, 14, 'v3.42.0')

    # 中栏: 对话 (28, w-30)
    cx = 29
    cw = w - 60
    for i, line in enumerate(chat_lines[-(h - 7) :]):
        text = line[:cw]
        ansi(cx, 4 + i, text)

    # 底部输入
    ansi(1, h, f'│{"─" * (w - 2)}│')
    ansi(1, h - 1, f'│ Ask SanYan...: {input_buf}{" " * (cw - len(input_buf) - 20)}│')

    sys.stdout.write(f'\033[{h - 1};{22 + len(input_buf)}H')
    sys.stdout.flush()


def run():
    import msvcrt

    chat = []
    tern = {'symbol': '———', 'state': '就绪', 'conf': 0.0, 'ur': 1.0, 'rule': '—', 'tools': []}
    buf = ''
    _running = True
    _dirty = True
    _last_chat_len = 0
    _last_tern = {}
    _last_buf = ''

    def agent_thread(task):
        nonlocal _dirty
        try:
            sys.path.insert(0, str(ROOT))
            from agent_system.run_agent import load_api_key, init_evaluator
            from agent_system.agent_runtime import AgentRuntime

            api_key = load_api_key()
            ev = init_evaluator(api_key)
            rt = AgentRuntime(ev, False)

            original = rt._run_core

            def wrapped(*a, **kw):
                nonlocal _dirty
                result = original(*a, **kw)
                if isinstance(result, dict):
                    mem = result.get('memory', {})
                    hist = mem.get('history', [])
                    tern['tools'] = [{'name': h.get('tool', '?'), 'ok': h.get('trit', 0) == 1} for h in hist]
                    ts = result.get('ternary', '')
                    tern['rule'] = result.get('rule', '—')
                    if '真' in str(ts):
                        tern['symbol'] = '●●●'
                        tern['state'] = 'AFFIRM'
                    elif '假' in str(ts):
                        tern['symbol'] = '○○○'
                        tern['state'] = 'NEGATE'
                    else:
                        tern['symbol'] = '◐◐◐'
                        tern['state'] = 'UNCERT'
                    answer = result.get('answer', str(result))[:300]
                    chat.append(f'🤖 {answer}')
                    _dirty = True
                return result

            rt._run_core = wrapped
            tern['state'] = '执行中...'
            _dirty = True
            rt.run(task, max_rounds=5)
            tern['state'] = '就绪'
            _dirty = True
        except Exception as e:
            chat.append(f'❌ {e}')
            tern['state'] = '错误'
            _dirty = True

    clear()
    while _running:
        # 只在有变化时重绘
        changed = _dirty or buf != _last_buf or len(chat) != _last_chat_len or str(tern) != str(_last_tern)
        if changed:
            draw_frame(chat, tern, buf)
            _last_chat_len = len(chat)
            _last_tern = dict(tern)
            _last_buf = buf
            _dirty = False

        # 非阻塞读取键盘
        if msvcrt.kbhit():
            ch = msvcrt.getch()
            if ch == b'\r':  # Enter
                if buf.strip():
                    task = buf.strip()
                    chat.append(f'🧑 {task}')
                    buf = ''
                    _dirty = True
                    threading.Thread(target=agent_thread, args=(task,), daemon=True).start()
            elif ch == b'\x08':  # Backspace
                buf = buf[:-1]
            elif ch == b'\x1b':  # ESC
                buf = ''
            elif ch == b'\x03':  # Ctrl+C
                chat.append('[Ctrl+C] 忽略')
                _dirty = True
            elif ch == b'\x04':  # Ctrl+D
                _running = False
                break
            elif len(ch) == 1 and 32 <= ch[0] <= 126:
                buf += ch.decode('ascii', errors='replace')

        time.sleep(0.05)

    clear()
    print('SanYan 退出')


if __name__ == '__main__':
    run()
