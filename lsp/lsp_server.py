"""三言语言服务器 (LSP) — 提供代码补全、诊断、悬停提示、跳转定义、签名帮助。

用法: python lsp/lsp_server.py  然后编辑器连接 stdio LSP。

此文件为入口点，实现在 lsp/ 包中。
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lsp.handler import main

if __name__ == '__main__':
    main()
