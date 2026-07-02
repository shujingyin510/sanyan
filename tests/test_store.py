"""阶段 2：单一存储层 store.py —— schema_version + 非破坏旧库迁移。"""

import os
import sqlite3


def test_schema_version_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv('AGENT_DATA_DIR', str(tmp_path))
    from agent_system import store

    conn = store.connect()
    assert store.get_version(conn, 'experience') == 0
    store.set_version(conn, 'experience', 3)
    assert store.get_version(conn, 'experience') == 3
    conn.close()


def test_adopt_legacy_copies_nondestructively(tmp_path, monkeypatch):
    monkeypatch.setenv('AGENT_DATA_DIR', str(tmp_path))
    from agent_system import paths, store

    legacy = paths.db_path('legacy_demo.db')
    lc = sqlite3.connect(legacy)
    lc.execute('CREATE TABLE t (a INTEGER, b TEXT)')
    lc.execute('INSERT INTO t VALUES (1, "x")')
    lc.commit()
    lc.close()

    conn = store.connect()
    conn.execute('CREATE TABLE t (a INTEGER, b TEXT)')
    conn.commit()
    assert store.adopt_legacy(conn, 'legacy_demo.db', ['t']) == 1
    assert conn.execute('SELECT a, b FROM t').fetchall() == [(1, 'x')]
    conn.close()
    assert os.path.exists(legacy)  # 旧库保留，可回滚


def test_adopt_skips_when_target_nonempty(tmp_path, monkeypatch):
    monkeypatch.setenv('AGENT_DATA_DIR', str(tmp_path))
    from agent_system import paths, store

    legacy = paths.db_path('legacy2.db')
    lc = sqlite3.connect(legacy)
    lc.execute('CREATE TABLE t (a)')
    lc.execute('INSERT INTO t VALUES (99)')
    lc.commit()
    lc.close()

    conn = store.connect()
    conn.execute('CREATE TABLE t (a)')
    conn.execute('INSERT INTO t VALUES (1)')
    conn.commit()
    assert store.adopt_legacy(conn, 'legacy2.db', ['t']) == 0  # 目标非空 → 跳过
    assert conn.execute('SELECT a FROM t').fetchall() == [(1,)]
    conn.close()


def test_experience_store_merges_into_agent_db(tmp_path, monkeypatch):
    monkeypatch.setenv('AGENT_DATA_DIR', str(tmp_path))
    from agent_system import paths, store
    from agent_system.agent_learning import ExperienceStore

    # 旧的独立 agent_experience.db 里先攒下经验
    legacy_path = paths.db_path('agent_experience.db')
    legacy = ExperienceStore(db_path=legacy_path)  # 显式路径 → 不触发迁移
    legacy.record_tool_use('read_file', True, 0.1)
    legacy.record_tool_use('read_file', True, 0.1)

    # 默认构造 → agent.db，应把历史经验搬过来
    s = ExperienceStore()
    assert os.path.basename(s.db_path) == store.AGENT_DB
    assert s.get_tool_reliability('read_file') == 1.0  # 迁移成功
    assert os.path.exists(legacy_path)  # 旧库保留

    # schema 版本已记
    conn = sqlite3.connect(s.db_path)
    assert store.get_version(conn, 'experience') == 1
    conn.close()


def test_domain_layer_merges_into_agent_db(tmp_path, monkeypatch):
    """阶段 2 续：DomainKnowledgeLayer（活读路径）也非破坏并入 agent.db。"""
    monkeypatch.setenv('AGENT_DATA_DIR', str(tmp_path))
    import json
    import time
    from agent_system import paths, store
    from agent_system.agent_domain import DomainKnowledgeLayer

    # 旧独立 domain_knowledge.db 里先攒缓存
    legacy_path = paths.db_path('domain_knowledge.db')
    lc = sqlite3.connect(legacy_path)
    lc.execute(
        'CREATE TABLE domain_cache (domain TEXT PRIMARY KEY, knowledge TEXT, created_at REAL, hit_count INTEGER DEFAULT 0)'
    )
    lc.execute('INSERT INTO domain_cache VALUES (?,?,?,0)', ('web_app', json.dumps({'x': 1}), time.time()))
    lc.commit()
    lc.close()

    # 默认构造 → agent.db，应把历史缓存搬来（且与 ExperienceStore 同库不冲突）
    d = DomainKnowledgeLayer()
    assert os.path.basename(d.db_path) == store.AGENT_DB
    assert d._cache_get('web_app') == {'x': 1}  # 迁移成功
    assert os.path.exists(legacy_path)  # 旧库保留可回滚

    conn = sqlite3.connect(d.db_path)
    assert store.get_version(conn, 'domain') == 1
    conn.close()
