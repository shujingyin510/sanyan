"""三言 Sanyan — 内置三态逻辑的中文编程语言

模块化安装:
    pip install sanyan           # 完整版（所有功能）
    pip install sanyan[core]     # 核心语言（解释器 + 标准库）
    pip install sanyan[sugar]    # 糖语法解析器
    pip install sanyan[vm]       # 字节码 VM
    pip install sanyan[llvmgen]  # LLVM 编译器
    pip install sanyan[lsp]      # IDE 支持（LSP + DAP）
    pip install sanyan[tools]    # 独立工具（格式化器/交叉编译器）
    pip install sanyan[dev]      # 开发依赖（pytest/ruff/mypy）
"""

from __future__ import annotations

__version__ = '3.22.0'
