"""测试套件全局夹具。"""

import pytest

# test_deadloop.py 是手动探针脚本（import 即加载 agent.san 并真跑 LLM 死循环任务，
# 消耗 API 额度、耗时数分钟），绝不能进 pytest 收集。用法见其文件头：python tests/test_deadloop.py
collect_ignore = ['test_deadloop.py']


@pytest.fixture(autouse=True)
def _isolate_agent_data_dir(tmp_path, monkeypatch):
    """把 agent 规范数据目录（paths.data_dir，认 AGENT_DATA_DIR）隔离到每测试独立临时目录。

    使所有经 `paths.db_path` 的持久化（agent.db 及各默认库，含 ExperienceStore /
    DomainKnowledgeLayer——阶段 2 并库接线已重做）在测试间密封、零污染、无需手工清理。
    """
    monkeypatch.setenv('AGENT_DATA_DIR', str(tmp_path))
