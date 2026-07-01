"""边界情况与覆盖率补充测试（统一入口）

合并原 test_coverage_boost*.py 的测试，按模块分组。
运行: python -m pytest tests/test_edge_cases.py -v
"""

import unittest

# ── 从各 boost 文件导入测试类 ──
from tests.test_coverage_boost import *  # noqa: F401, F403
from tests.test_coverage_boost2 import *  # noqa: F401, F403
from tests.test_coverage_boost3 import *  # noqa: F401, F403
from tests.test_coverage_boost4 import *  # noqa: F401, F403
from tests.test_coverage_boost5 import *  # noqa: F401, F403
from tests.test_coverage_boost6 import *  # noqa: F401, F403
from tests.test_coverage_boost7 import *  # noqa: F401, F403
from tests.test_coverage_boost8 import *  # noqa: F401, F403


if __name__ == '__main__':
    unittest.main()
