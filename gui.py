"""三言可视化编译器 — Dev-C++ 风格界面 (语法高亮 + 查找替换 + 调试集成)"""

import io
import os
import re
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk, scrolledtext
from typing import Any

import tomllib

with open('pyproject.toml', 'rb') as f:
    VERSION = tomllib.load(f)['project']['version']
from skin import SkinManager
from evaluator import SanyanEvaluator
from lexer import tokenize
from parser import parse
from sugar import SugarConverter
from preprocess import preprocess_includes
from ternary_core import TritValue
from runtime import BUILTIN_OPS


_KW = sorted(BUILTIN_OPS, key=len, reverse=True)
_KW_PAT = '|'.join(re.escape(k) for k in _KW)


class HighlightText(tk.Frame):
    """带行号 + 语法高亮的代码编辑器"""

    def __init__(self, master, **kwargs):
        super().__init__(master)
        self._highlighter_active = True
        self._after_id = None
        # 行号
        self.lineno = tk.Text(
            self,
            width=5,
            padx=4,
            pady=4,
            wrap='none',
            font=('Consolas', 11),
            takefocus=0,
            borderwidth=1,
            relief='sunken',
            bg='#f0f0f0',
            fg='#808080',
            state='disabled',
        )
        self.lineno.pack(side='left', fill='y')
        # 断点标示条
        self.bp_bar = tk.Text(
            self,
            width=2,
            padx=2,
            pady=4,
            wrap='none',
            font=('Consolas', 11),
            takefocus=0,
            borderwidth=1,
            relief='sunken',
            bg='#f0f0f0',
            fg='red',
            state='disabled',
            cursor='hand2',
        )
        self.bp_bar.pack(side='left', fill='y')
        self.bp_bar.bind('<Button-1>', self._toggle_breakpoint)
        self.breakpoints = set()
        # 编辑区
        self.text = tk.Text(
            self,
            wrap='none',
            font=('Consolas', 11),
            undo=True,
            tabs=4,
            padx=4,
            pady=4,
            borderwidth=1,
            relief='sunken',
            bg='white',
            fg='black',
            insertbackground='black',
            highlightthickness=0,
            **kwargs,
        )
        self.text.pack(side='right', fill='both', expand=True)
        self.text.bind('<<Modified>>', self._on_change)
        self.text.bind('<KeyRelease>', self._on_keyrelease)
        self.text.bind('<MouseWheel>', self._sync_scroll)
        self.text.bind('<Button-4>', self._sync_scroll)
        self.text.bind('<Button-5>', self._sync_scroll)
        self.lineno.bind('<MouseWheel>', lambda e: self.text.yview_scroll(-1 * (e.delta // 120), 'units'))
        self.bp_bar.bind('<MouseWheel>', lambda e: self.text.yview_scroll(-1 * (e.delta // 120), 'units'))
        # 高亮标签
        self.text.tag_config('hl_keyword', foreground='#0000ff')
        self.text.tag_config('hl_string', foreground='#008000')
        self.text.tag_config('hl_number', foreground='#ff8c00')
        self.text.tag_config('hl_comment', foreground='#808080')
        self.text.tag_config('hl_bracket', foreground='#8b0000', font=('Consolas', 11, 'bold'))
        self._setup_highlight_patterns()
        self._update_lineno()

    def _setup_highlight_patterns(self):
        self._hl_patterns = []
        self._hl_patterns.append(('hl_bracket', re.compile(r'[()（）\[\]{}]')))
        self._hl_patterns.append(('hl_comment', re.compile(r'#.*')))
        self._hl_patterns.append(('hl_string', re.compile(r'"[^"]*"|' + "'[^']*'")))
        self._hl_patterns.append(('hl_number', re.compile(r'\b\d+(\.\d+)?\b')))
        self._hl_patterns.append(('hl_keyword', re.compile(_KW_PAT)))

    def _highlight(self):
        if not self._highlighter_active:
            return
        for tag in ('hl_keyword', 'hl_string', 'hl_number', 'hl_comment', 'hl_bracket'):
            self.text.tag_remove(tag, '1.0', 'end')
        content = self.text.get('1.0', 'end-1c')
        for tag, pat in self._hl_patterns:
            for m in pat.finditer(content):
                start = f'1.0+{m.start()}c'
                end = f'1.0+{m.end()}c'
                try:
                    self.text.tag_add(tag, start, end)
                except tk.TclError:
                    pass

    def _debounce_highlight(self):
        if self._after_id:
            self.after_cancel(self._after_id)
        self._after_id = self.after(300, self._highlight)

    def _toggle_breakpoint(self, event):
        idx = self.bp_bar.index(f'@{event.x},{event.y}')
        line = int(idx.split('.')[0])
        if line in self.breakpoints:
            self.breakpoints.discard(line)
        else:
            self.breakpoints.add(line)
        self._update_breakpoints()

    def _update_breakpoints(self):
        self.bp_bar.config(state='normal')
        self.bp_bar.delete('1.0', 'end')
        total = int(self.text.index('end-1c').split('.')[0])
        for i in range(1, total + 1):
            marker = '●' if i in self.breakpoints else ' '
            self.bp_bar.insert('end', marker + '\n')
        self.bp_bar.config(state='disabled')

    def _update_lineno(self):
        lines = int(self.text.index('end-1c').split('.')[0])
        self.lineno.config(state='normal')
        self.lineno.delete('1.0', 'end')
        self.lineno.insert('1.0', '\n'.join(str(i) for i in range(1, lines + 1)))
        self.lineno.config(state='disabled')

    def _on_change(self, _=None):
        if self.text.edit_modified():
            self._update_lineno()
            self._update_breakpoints()
            self.text.edit_modified(False)

    def _on_keyrelease(self, event=None):
        if event and event.keysym in ('Up', 'Down', 'Left', 'Right', 'Home', 'End', 'Prior', 'Next'):
            return
        self._debounce_highlight()

    def _sync_scroll(self, _=None):
        frac = self.text.yview()[0]
        self.lineno.yview_moveto(frac)
        self.bp_bar.yview_moveto(frac)

    def get(self, *args):
        return self.text.get(*args)

    def delete(self, *args):
        return self.text.delete(*args)

    def insert(self, *args):
        return self.text.insert(*args)

    def bind(self, seq=None, func=None, add=None):
        return self.text.bind(seq, func, add)

    def edit_modified(self, *args):
        return self.text.edit_modified(*args)

    def edit_reset(self):
        self.text.edit_reset()

    def yview(self, *args):
        return self.text.yview(*args)

    def see(self, index):
        self.text.see(index)

    def mark_set(self, name, index):
        self.text.mark_set(name, index)

    def tag_add(self, *args):
        self.text.tag_add(*args)

    def tag_remove(self, *args):
        self.text.tag_remove(*args)

    def focus(self):
        self.text.focus()

    def get_sel(self):
        try:
            return self.text.index('sel.first'), self.text.index('sel.last')
        except tk.TclError:
            return None, None


class FindReplace(tk.Frame):
    """查找替换工具栏"""

    def __init__(self, master, editor):
        super().__init__(master, bg='#e8e8e8', bd=1, relief='raised')
        self.editor = editor
        self._match_indices = []
        self._current_match = -1
        self.pack_forget()
        tk.Label(self, text='查找:', bg='#e8e8e8').pack(side='left', padx=4)
        self.find_var = tk.StringVar()
        self.find_var.trace('w', lambda *a: self._update_matches())
        self.find_entry = tk.Entry(self, textvariable=self.find_var, width=25, font=('Consolas', 10))
        self.find_entry.pack(side='left', padx=2)
        self.find_entry.bind('<Return>', lambda e: self.find_next())
        self.find_entry.bind('<Escape>', lambda e: self.hide())
        self.match_label = tk.Label(self, text='', bg='#e8e8e8', fg='#666', width=8)
        self.match_label.pack(side='left')
        tk.Button(self, text='↓', command=self.find_next, width=3, bg='#e8e8e8', relief='raised', bd=1).pack(
            side='left', padx=1
        )
        tk.Button(self, text='↑', command=self.find_prev, width=3, bg='#e8e8e8', relief='raised', bd=1).pack(
            side='left', padx=1
        )
        tk.Label(self, text='替换:', bg='#e8e8e8').pack(side='left', padx=4)
        self.replace_var = tk.StringVar()
        tk.Entry(self, textvariable=self.replace_var, width=15, font=('Consolas', 10)).pack(side='left', padx=2)
        tk.Button(self, text='替换', command=self.replace_one, width=4, bg='#e8e8e8', relief='raised', bd=1).pack(
            side='left', padx=1
        )
        tk.Button(self, text='全部替换', command=self.replace_all, width=7, bg='#e8e8e8', relief='raised', bd=1).pack(
            side='left', padx=1
        )
        tk.Button(
            self, text='✕', command=self.hide, width=2, bg='#e8e8e8', relief='flat', bd=0, font=('Segoe UI', 8)
        ).pack(side='right')

    def show(self):
        self.editor.text.tag_remove('hl_find', '1.0', 'end')
        self.editor.text.tag_config('hl_find', background='yellow')
        self.editor.text.tag_config('hl_find_current', background='orange')
        self.pack(fill='x', before=self.editor)
        self.find_entry.focus()
        self.find_entry.select_range(0, 'end')

    def hide(self):
        self.editor.text.tag_remove('hl_find', '1.0', 'end')
        self.editor.text.tag_remove('hl_find_current', '1.0', 'end')
        self._match_indices = []
        self._current_match = -1
        self.pack_forget()
        self.editor.focus()

    def _update_matches(self):
        text = self.editor.text
        text.tag_remove('hl_find', '1.0', 'end')
        text.tag_remove('hl_find_current', '1.0', 'end')
        self._match_indices = []
        self._current_match = -1
        q = self.find_var.get()
        if not q:
            self.match_label.config(text='')
            return
        content = text.get('1.0', 'end-1c')
        pos = 0
        while True:
            idx = content.find(q, pos)
            if idx == -1:
                break
            start = f'1.0+{idx}c'
            end = f'1.0+{idx + len(q)}c'
            self._match_indices.append((start, end))
            text.tag_add('hl_find', start, end)
            pos = idx + 1
        cnt = len(self._match_indices)
        if cnt > 0:
            self._current_match = 0
            self.match_label.config(text=f'1/{cnt}')
            self._highlight_current()
        else:
            self.match_label.config(text='无结果')

    def _highlight_current(self):
        self.editor.text.tag_remove('hl_find_current', '1.0', 'end')
        if 0 <= self._current_match < len(self._match_indices):
            start, end = self._match_indices[self._current_match]
            self.editor.text.tag_add('hl_find_current', start, end)
            self.editor.text.see(start)
            self.editor.text.mark_set('insert', start)
            total = len(self._match_indices)
            self.match_label.config(text=f'{self._current_match + 1}/{total}')

    def find_next(self):
        if not self._match_indices:
            return
        self._current_match = (self._current_match + 1) % len(self._match_indices)
        self._highlight_current()

    def find_prev(self):
        if not self._match_indices:
            return
        self._current_match = (self._current_match - 1) % len(self._match_indices)
        self._highlight_current()

    def replace_one(self):
        old = self.find_var.get()
        new = self.replace_var.get()
        if not old or self._current_match < 0:
            return
        start, end = self._match_indices[self._current_match]
        self.editor.text.delete(start, end)
        self.editor.text.insert(start, new)
        self._update_matches()
        self.find_next()

    def replace_all(self):
        old = self.find_var.get()
        new = self.replace_var.get()
        if not old:
            return
        content = self.editor.text.get('1.0', 'end-1c')
        content = content.replace(old, new)
        self.editor.text.delete('1.0', 'end-1c')
        self.editor.text.insert('1.0', content)
        self._update_matches()


class SanyanIDE:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(f'三言 v{VERSION}')
        self.root.geometry('960x720')
        self.root.minsize(640, 520)
        self.current_file = None
        self.modified = False
        self._debug_mode = False
        self._build_ui()
        self.root.protocol('WM_DELETE_WINDOW', self._on_close)

    def _make_toolbar(self, parent):
        tb = tk.Frame(parent, relief='raised', bd=1, bg='#e8e8e8')

        def btn(parent, **kw):
            return tk.Button(parent, relief='raised', bd=1, bg='#e8e8e8', font=('微软雅黑', 8), padx=6, pady=1, **kw)

        btn(tb, text='新建', command=self._new_file).pack(side='left', padx=2, pady=2)
        btn(tb, text='打开', command=self._open_file).pack(side='left', padx=2, pady=2)
        btn(tb, text='保存', command=self._save_file).pack(side='left', padx=2, pady=2)
        tk.Frame(tb, width=4, relief='sunken', bd=1, bg='#c0c0c0').pack(side='left', fill='y', padx=4, pady=2)
        self._run_btn = btn(tb, text='▶ 运行', command=self._run_code)
        self._run_btn.pack(side='left', padx=2, pady=2)
        self._debug_btn = btn(tb, text='⚫ 调试', command=self._debug_run)
        self._debug_btn.pack(side='left', padx=2, pady=2)
        self._step_btn = btn(tb, text='↘ 单步', command=self._debug_step, state='disabled')
        self._step_btn.pack(side='left', padx=2, pady=2)
        self._cont_btn = btn(tb, text='▶ 继续', command=self._debug_continue, state='disabled')
        self._cont_btn.pack(side='left', padx=2, pady=2)
        tk.Frame(tb, width=4, relief='sunken', bd=1, bg='#c0c0c0').pack(side='left', fill='y', padx=4, pady=2)
        btn(tb, text='清空输出', command=self._clear_output).pack(side='left', padx=2, pady=2)
        return tb

    def _build_ui(self):
        self._build_menu()
        self._make_toolbar(self.root).pack(fill='x')
        main_pw = ttk.PanedWindow(self.root, orient='horizontal')
        main_pw.pack(fill='both', expand=True)
        left_frame = ttk.Frame(main_pw, width=180)
        ttk.Label(left_frame, text='  项目文件', font=('微软雅黑', 9, 'bold'), anchor='w', padding=(4, 2)).pack(
            fill='x'
        )
        self.file_tree = ttk.Treeview(left_frame, columns=(), show='tree', height=8)
        self.file_tree.pack(fill='both', expand=True)
        self._populate_tree()
        self.file_tree.bind('<Double-1>', self._on_tree_double)
        main_pw.add(left_frame, weight=0)
        right_frame = ttk.Frame(main_pw)
        main_pw.add(right_frame, weight=1)
        vert_pw = ttk.PanedWindow(right_frame, orient='vertical')
        vert_pw.pack(fill='both', expand=True)
        # 编辑器
        edit_frame = ttk.Frame(vert_pw)
        self.code_editor = HighlightText(edit_frame)
        self.code_editor.pack(fill='both', expand=True)
        self.code_editor.bind('<<Modified>>', self._on_modified)
        for key, cmd in [
            ('<Control-R>', self._run_code),
            ('<Control-r>', self._run_code),
            ('<Control-s>', self._save_file),
            ('<Control-S>', self._save_file),
            ('<Control-o>', self._open_file),
            ('<Control-O>', self._open_file),
            ('<Control-n>', self._new_file),
            ('<Control-N>', self._new_file),
            ('<Control-f>', self._show_find),
            ('<Control-F>', self._show_find),
            ('<F5>', self._run_code),
            ('<F6>', self._debug_run),
            ('<F10>', self._debug_step),
            ('<F8>', self._debug_continue),
        ]:
            self.code_editor.bind(key, lambda e, c=cmd: c())
        # 查找替换条
        self.find_bar = FindReplace(edit_frame, self.code_editor)
        vert_pw.add(edit_frame, weight=3)
        # 底部选项卡
        bottom_frame = ttk.Frame(vert_pw)
        self.notebook = ttk.Notebook(bottom_frame)
        self.notebook.pack(fill='both', expand=True)
        # 输出
        out_frame = ttk.Frame(self.notebook)
        self.output_text = scrolledtext.ScrolledText(
            out_frame,
            wrap='word',
            font=('Consolas', 10),
            state='disabled',
            bg='white',
            fg='black',
        )
        self.output_text.tag_config('error', foreground='red')
        self.output_text.pack(fill='both', expand=True)
        self.notebook.add(out_frame, text='  输出  ')
        # 编译日志
        log_frame = ttk.Frame(self.notebook)
        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            wrap='word',
            font=('Consolas', 10),
            state='disabled',
            bg='white',
            fg='black',
        )
        self.log_text.pack(fill='both', expand=True)
        self.notebook.add(log_frame, text='  编译日志  ')
        # 调试变量/监视
        debug_frame = ttk.Frame(self.notebook)
        self.debug_tree = ttk.Treeview(debug_frame, columns=('value',), show='headings', height=6)
        self.debug_tree.heading('#0', text='变量')
        self.debug_tree.heading('value', text='值')
        self.debug_tree.column('#0', width=120)
        self.debug_tree.column('value', width=200)
        self.debug_tree.pack(fill='both', expand=True)
        self.notebook.add(debug_frame, text='  调试变量  ')
        vert_pw.add(bottom_frame, weight=1)
        self.status_bar = tk.Label(self.root, text='  就绪', relief='sunken', anchor='w', bg='#e8e8e8', fg='black')
        self.status_bar.pack(fill='x')
        self._update_title()

    def _build_menu(self):
        menubar = tk.Menu(self.root, bg='#e8e8e8', fg='black')
        file_menu = tk.Menu(menubar, tearoff=0, bg='#e8e8e8', fg='black')
        file_menu.add_command(label='新建  Ctrl+N', command=self._new_file)
        file_menu.add_command(label='打开  Ctrl+O', command=self._open_file)
        file_menu.add_command(label='保存  Ctrl+S', command=self._save_file)
        file_menu.add_command(label='另存为...', command=self._save_as_file)
        file_menu.add_separator()
        file_menu.add_command(label='退出', command=self._on_close)
        menubar.add_cascade(label='文件', menu=file_menu)
        edit_menu = tk.Menu(menubar, tearoff=0, bg='#e8e8e8', fg='black')
        edit_menu.add_command(label='查找  Ctrl+F', command=self._show_find)
        menubar.add_cascade(label='编辑', menu=edit_menu)
        run_menu = tk.Menu(menubar, tearoff=0, bg='#e8e8e8', fg='black')
        run_menu.add_command(label='运行  F5', command=self._run_code)
        run_menu.add_command(label='调试  F6', command=self._debug_run)
        run_menu.add_command(label='单步  F10', command=self._debug_step)
        run_menu.add_command(label='跳转到行...', command=self._goto_line)
        menubar.add_cascade(label='运行', menu=run_menu)
        help_menu = tk.Menu(menubar, tearoff=0, bg='#e8e8e8', fg='black')
        help_menu.add_command(label='关于三言', command=self._show_about)
        menubar.add_cascade(label='帮助', menu=help_menu)
        self.root.config(menu=menubar)

    def _show_about(self):
        messagebox.showinfo('关于三言', f'三言 v{VERSION}\n\n中文三进制编程语言\n母语可定制 · 三态逻辑 · 万物互联')

    def _populate_tree(self):
        self.file_tree.delete(*self.file_tree.get_children())
        for root_dir in ('examples', 'stdlib'):
            if os.path.isdir(root_dir):
                parent = self.file_tree.insert('', 'end', text=root_dir, open=True, values=[root_dir])
                self._populate_subtree(parent, root_dir)

    def _populate_subtree(self, parent, path):
        try:
            entries = sorted(os.listdir(path))
        except OSError:
            return
        for entry in entries:
            full = os.path.join(path, entry)
            if os.path.isdir(full):
                node = self.file_tree.insert(parent, 'end', text=entry, values=[full])
                self.file_tree.insert(node, 'end', text='')  # dummy child for expand arrow
            elif entry.endswith('.san'):
                self.file_tree.insert(parent, 'end', text=entry, values=[full])

    def _expand_dir(self, parent, path):
        existing = self.file_tree.get_children(parent)
        if existing:
            first = existing[0]
            first_text = self.file_tree.item(first, 'text')
            if not first_text:
                # dummy child present — delete and populate
                self.file_tree.delete(*existing)
                self._populate_subtree(parent, path)

    def _on_tree_double(self, event):
        sel = self.file_tree.selection()
        if not sel:
            return
        item = sel[0]
        vals = self.file_tree.item(item, 'values')
        if not vals:
            return
        full = vals[0]
        if os.path.isdir(full):
            self._expand_dir(item, full)
        elif os.path.isfile(full) and full.endswith('.san'):
            self._open_file(full)

    def _show_find(self):
        self.find_bar.show()

    def _goto_line(self):
        d = tk.Toplevel(self.root)
        d.title('跳转到行')
        d.geometry('240x90')
        d.resizable(False, False)
        tk.Label(d, text='行号:').pack(pady=4)
        var = tk.StringVar()
        e = tk.Entry(d, textvariable=var, width=10, font=('Consolas', 11))
        e.pack(pady=4)
        e.focus()

        def go():
            try:
                line = int(var.get())
                self.code_editor.text.see(f'{line}.0')
                self.code_editor.text.mark_set('insert', f'{line}.0')
            except (ValueError, tk.TclError):
                pass
            d.destroy()

        e.bind('<Return>', lambda e: go())
        tk.Button(d, text='跳转', command=go, width=8).pack()

    def _update_title(self):
        name = os.path.basename(self.current_file) if self.current_file else '未命名'
        flag = ' *' if self.modified else ''
        mode = ' [调试]' if self._debug_mode else ''
        self.root.title(f'{name}{flag}{mode} - 三言 v{VERSION}')

    def _on_modified(self, _=None):
        if self.code_editor.edit_modified():
            self.modified = True
            self._update_title()
            self.code_editor.edit_modified(False)

    def _set_status(self, text):
        self.status_bar.config(text=f'  {text}')
        self.root.update_idletasks()

    def _log(self, text):
        self.log_text.config(state='normal')
        self.log_text.insert('end', text)
        self.log_text.see('end')
        self.log_text.config(state='disabled')

    def _write_output(self, text, tag=None):
        self.output_text.config(state='normal')
        if tag:
            self.output_text.insert('end', text, tag)
        else:
            self.output_text.insert('end', text)
        self.output_text.see('end')
        self.output_text.config(state='disabled')
        self.notebook.select(0)

    def _clear_output(self):
        self.output_text.config(state='normal')
        self.output_text.delete('1.0', 'end')
        self.output_text.config(state='disabled')

    def _new_file(self):
        if self.modified:
            if not messagebox.askyesno('三言', '当前内容未保存，确定新建？'):
                return
        self.code_editor.delete('1.0', 'end')
        self.current_file = None
        self.modified = False
        self._update_title()
        self._clear_output()
        self._set_status('新建文件')

    def _open_file(self, path=None):
        if not path:
            path = filedialog.askopenfilename(
                title='打开三言文件',
                filetypes=[('三言文件', '*.san'), ('所有文件', '*.*')],
            )
        if not path:
            return
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            messagebox.showerror('错误', f'无法打开文件:\n{e}')
            return
        self.code_editor.delete('1.0', 'end')
        self.code_editor.insert('1.0', content)
        self.code_editor.edit_reset()
        self.current_file = path
        self.modified = False
        self._update_title()
        self._clear_output()
        self._set_status(f'已打开: {path}')
        self._log(f'[打开] {path}\n')
        self.code_editor._highlight()

    def _save_file(self):
        if self.current_file:
            self._do_save(self.current_file)
        else:
            self._save_as_file()

    def _save_as_file(self):
        path = filedialog.asksaveasfilename(
            title='保存三言文件',
            defaultextension='.san',
            filetypes=[('三言文件', '*.san'), ('所有文件', '*.*')],
        )
        if path:
            self._do_save(path)

    def _do_save(self, path):
        try:
            content = self.code_editor.get('1.0', 'end-1c')
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
        except Exception as e:
            messagebox.showerror('错误', f'无法保存文件:\n{e}')
            return
        self.current_file = path
        self.modified = False
        self._update_title()
        self._set_status(f'已保存: {path}')
        self._log(f'[保存] {path}\n')

    def _run_code(self):
        self._debug_mode = False
        self._update_title()
        code = self.code_editor.get('1.0', 'end-1c')
        if not code.strip():
            self._write_output('错误: 没有代码可执行\n', 'error')
            return
        self._clear_output()
        self._set_status('编译运行中...')
        self.root.update()
        self._log('[运行] 开始执行...\n')
        self._write_output('===== 编译运行 =====\n\n')
        self._execute(code, debug=False)

    def _debug_run(self):
        self._debug_mode = True
        self._update_title()
        code = self.code_editor.get('1.0', 'end-1c')
        if not code.strip():
            self._write_output('错误: 没有代码可执行\n', 'error')
            return
        self._clear_output()
        self._debug_variables = {}
        self._debug_env = None
        self._debug_paused = False
        self._set_status('调试运行中...')
        self.root.update()
        self._log('[调试] 启动调试...\n')
        self._write_output('===== 调试模式 =====\n\n')
        self._step_btn.config(state='normal')
        self._cont_btn.config(state='normal')
        self._debug_btn.config(text='⚫ 停止调试', command=self._debug_stop)
        self._run_btn.config(state='disabled')
        self.code_editor.breakpoints.clear()
        self._execute_debug(code)

    def _debug_stop(self):
        self._debug_mode = False
        self._debug_env = None
        self._debug_paused = False
        self._update_title()
        self._step_btn.config(state='disabled')
        self._cont_btn.config(state='disabled')
        self._debug_btn.config(text='⚫ 调试', command=self._debug_run)
        self._run_btn.config(state='normal')
        self._set_status('调试已停止')

    def _debug_step(self):
        if self._debug_env and self._debug_paused:
            self._debug_paused = False
            self._debug_continue_execution()

    def _debug_continue(self):
        if self._debug_env:
            self._debug_paused = False
            self._debug_env.debug_mode = False
            self._debug_env._break_all = False
            self._debug_continue_execution()
            self._debug_env.debug_mode = True
            self._debug_env._break_all = True

    def _debug_continue_execution(self):
        self._set_status('调试运行中...')
        self.root.update()
        assert self._debug_env is not None
        try:
            result = self._debug_env.eval(self._debug_ast)
            if result is not None:
                self._write_output(f'结果: {self._format_value(result)}\n')
            self._write_output('\n===== 运行结束 =====\n')
            self._log('[调试] 运行结束\n')
            self._debug_stop()
        except Exception as e:
            self._write_output(f'运行错误: {e}\n', 'error')
            self._debug_stop()

    def _execute(self, code, debug=False):
        code = preprocess_includes(code)
        skin_mgr = SkinManager('chinese')
        env = SanyanEvaluator(skin_manager=skin_mgr)
        original_print = sys.stdout
        buf = io.StringIO()
        sys.stdout = buf
        try:
            ast: Any = None
            sugar_error = None
            try:
                ast = SugarConverter.convert(code, skin_mgr)
                if ast is not None:
                    self._log('[语法] sugar 语法解析成功\n')
            except SyntaxError as e:
                sugar_error = str(e)
                self._log(f'[语法] sugar 语法失败: {e}\n')
            if ast is None:
                tokens = tokenize(code)
                if tokens:
                    try:
                        ast = parse(tokens)
                        if ast is not None:
                            self._log('[语法] 原生语法解析成功\n')
                    except SyntaxError as e:
                        self._write_output(f'语法错误: {e}\n', 'error')
                        if sugar_error:
                            self._write_output(f'  (也尝试 sugar 语法: {sugar_error})\n', 'error')
                        self._log('[错误] 语法解析失败\n')
                        return
            if ast is None:
                self._write_output('代码为空\n')
                return
            self._log('[运行] AST 就绪\n')
            result = env.eval(ast)
            output = buf.getvalue()
            if output:
                self._write_output(output)
            if result is not None and not self._has_output(ast):
                self._write_output(f'结果: {self._format_value(result)}\n')
            self._log('[完成] 程序运行结束\n')
            self._write_output('\n===== 运行结束 =====\n')
        except Exception as e:
            self._write_output(f'运行错误: {e}\n', 'error')
            import traceback

            self._write_output(traceback.format_exc() + '\n', 'error')
            self._log(f'[错误] {e}\n')
        finally:
            sys.stdout = original_print

    def _execute_debug(self, code):
        code = preprocess_includes(code)
        skin_mgr = SkinManager('chinese')
        env = SanyanEvaluator(skin_manager=skin_mgr)
        original_print = sys.stdout
        buf = io.StringIO()
        sys.stdout = buf
        try:
            ast: Any = None
            try:
                ast = SugarConverter.convert(code, skin_mgr)
            except SyntaxError:
                pass
            if ast is None:
                tokens = tokenize(code)
                if tokens:
                    try:
                        ast = parse(tokens)
                    except SyntaxError as e:
                        self._write_output(f'语法错误: {e}\n', 'error')
                        self._debug_stop()
                        return
            if ast is None:
                self._write_output('代码为空\n')
                self._debug_stop()
                return
            self._debug_ast = ast
            self._debug_env = env
            env.debug_mode = True
            env._break_all = True
            for bp in self.code_editor.breakpoints:
                env.break_add(str(bp))
            self._debug_paused = True
            self._set_status('调试暂停 - 点击 单步/继续')
            self._write_output('调试器已就绪，点击「单步」逐行执行\n')
        except Exception as e:
            self._write_output(f'调试初始化错误: {e}\n', 'error')
            self._debug_stop()
        finally:
            sys.stdout = original_print

    def _has_output(self, node):
        if isinstance(node, list) and len(node) > 0:
            if node[0] in ('输出', '打印', 'print', '写出', '查', 'query', '调试', 'debug'):
                return True
            for child in node[1:]:
                if self._has_output(child):
                    return True
        return False

    def _format_value(self, value):
        from ops.io_ops import IOOps

        try:
            return IOOps.format_value(value)
        except Exception:
            if isinstance(value, TritValue):
                if value.is_float():
                    return str(value.to_float())
                return str(value.to_int())
            return str(value)

    def _on_close(self):
        if self.modified:
            if not messagebox.askyesno('三言', '内容未保存，确定退出？'):
                return
        self.root.destroy()

    def run(self):
        self.root.mainloop()


def main():
    app = SanyanIDE()
    if len(sys.argv) > 1:
        app._open_file(sys.argv[1])
    app.run()


if __name__ == '__main__':
    main()
