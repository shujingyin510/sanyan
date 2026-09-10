"""Agent 测试包：把仓库根锚进 sys.path，保证 `from agent_system...` / `from core...` 可导入。

历史：测试原在 tests/ 根下，dirname(dirname(__file__)) 即仓库根；迁入 tests/agent/ 后
多数文件的 path 插入会少一层，这里统一补齐，避免逐文件改。
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# 手动 LLM 探针，不进 pytest 收集（与 tests/conftest.py 双保险）
collect_ignore = ['test_deadloop.py']
