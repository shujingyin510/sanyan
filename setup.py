"""动态发现所有根目录模块，避免 pyproject.toml 手写 py-modules 列表。"""

import glob
from setuptools import setup

setup(
    py_modules=[f.replace('.py', '') for f in sorted(glob.glob('*.py')) if f not in ('setup.py',)],
)
