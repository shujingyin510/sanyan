"""P2 任务挖掘：三类来源、可验证性排序、任务书含红线①文案。"""

from agent_system.task_mining import mine_all, mine_failing_tests, mine_long_functions, mine_todos

PYTEST_OUT = """
FAILED tests/test_a.py::test_x - AssertionError: 1 != 2
ERROR tests/test_b.py::test_y
FAILED tests/test_a.py::test_x - 重复行应去重
12 failed, 3 passed in 2s
"""


def test_mine_failing_tests_parses_and_dedups():
    tasks = mine_failing_tests(PYTEST_OUT)
    assert [t.detail for t in tasks] == ['tests/test_a.py::test_x', 'tests/test_b.py::test_y']
    assert all(t.kind == 'failing_test' for t in tasks)
    assert mine_failing_tests('') == []


def test_failing_test_prompt_forbids_deleting_tests():
    t = mine_failing_tests(PYTEST_OUT)[0]
    assert '不得删除' in t.prompt()  # 红线①：不许靠删/跳/弱化测试来"修复"


def test_mine_todos_scans_and_skips_artifact_dirs(tmp_path):
    (tmp_path / 'a.py').write_text('x = 1  # TODO: 修这个\n# FIXME 那个\n', encoding='utf-8')
    cache = tmp_path / '__pycache__'
    cache.mkdir()
    (cache / 'b.py').write_text('# TODO: 不该被扫到\n', encoding='utf-8')
    tasks = mine_todos(str(tmp_path))
    assert [(t.line, t.title) for t in tasks] == [(1, '修这个'), (2, '那个')]


def test_todo_in_string_literal_is_not_mined(tmp_path):
    # 首跑抓到的假阳性回归守护：字符串字面量里的待办标记（夹具/模板串）不是任务
    (tmp_path / 'a.py').write_text("x = '# TODO 不是任务'\ny = 2  # TODO 真任务\n", encoding='utf-8')
    tasks = mine_todos(str(tmp_path))
    assert [(t.line, t.title) for t in tasks] == [(2, '真任务')]


def test_mine_long_functions(tmp_path):
    body = '\n'.join(f'    x{i} = {i}' for i in range(90))
    (tmp_path / 'big.py').write_text(f'def huge():\n{body}\n\n\ndef tiny():\n    pass\n', encoding='utf-8')
    tasks = mine_long_functions(str(tmp_path), max_lines=80)
    assert [t.title for t in tasks] == ['huge']
    assert tasks[0].kind == 'long_function' and tasks[0].line == 1


def test_mine_long_functions_uncapped_by_default(tmp_path):
    # 0705 实录回归钉：旧默认 limit=30 让排 31 名开外的 --pick 靶子凭空蒸发——
    # 任务身份随无关改动漂移（新增代码把别的函数喂长，既有目标就出榜）。默认全量。
    for i in range(33):
        body = '\n'.join(f'    x{j} = {j}' for j in range(85 + i))
        (tmp_path / f'm{i}.py').write_text(f'def fn{i}():\n{body}\n', encoding='utf-8')
    tasks = mine_long_functions(str(tmp_path), max_lines=80)
    assert len(tasks) == 33  # 不截断
    assert mine_long_functions(str(tmp_path), max_lines=80, limit=5)[4].title  # 显式 limit 仍可用


def test_long_function_hints_static_plan(tmp_path):
    # P3：挖掘时静态列出函数体的候选提取块（行区间），任务书降维成"按方案执行"
    if_body = '\n'.join(f'        y{i} = {i}' for i in range(10))
    tail = '\n'.join(f'    z{i} = {i}' for i in range(75))
    (tmp_path / 'big.py').write_text(f'def huge(v):\n    if v:\n{if_body}\n{tail}\n', encoding='utf-8')
    t = mine_long_functions(str(tmp_path), max_lines=80)[0]
    assert '条件块' in t.hints and t.hints.startswith('L2-')
    assert '候选块' in t.prompt() and '条件块' in t.prompt()


def test_mine_all_orders_by_verifiability(tmp_path):
    (tmp_path / 'a.py').write_text('# TODO: 一个待办\n', encoding='utf-8')
    tasks = mine_all(str(tmp_path), pytest_output='FAILED tests/t.py::test_z - x')
    assert [t.kind for t in tasks] == ['failing_test', 'todo']
