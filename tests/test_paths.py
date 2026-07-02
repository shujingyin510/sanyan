"""规范数据目录 paths.py：AGENT_DATA_DIR 优先，缺省为 agent_system/ 源码目录。"""

import os

from agent_system import paths


def test_env_override_and_db_path(tmp_path, monkeypatch):
    monkeypatch.setenv('AGENT_DATA_DIR', str(tmp_path))
    assert paths.data_dir() == str(tmp_path)
    assert paths.db_path('x.db') == os.path.join(str(tmp_path), 'x.db')


def test_creates_missing_dir(tmp_path, monkeypatch):
    target = tmp_path / 'sub' / 'data'
    monkeypatch.setenv('AGENT_DATA_DIR', str(target))
    assert paths.data_dir() == str(target)
    assert os.path.isdir(target)


def test_default_is_package_dir(monkeypatch):
    monkeypatch.delenv('AGENT_DATA_DIR', raising=False)
    assert paths.data_dir() == os.path.dirname(os.path.abspath(paths.__file__))
