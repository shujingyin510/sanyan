"""agent 工具层：read_file 范围读取的参数语义。

P2 探针#7 抓到的根因回归守护：模型发「路径|起始行|行数」（如 308|100），
旧实现把第三段当"结束行"，切片 [307:100] 永远为空——模型每轮读到虚空、
在同一区域原地打转直到被 UR 判死，replace_in_file 无从谈起。
"""

import os

from agent_system.agent_tools import _read_file_direct_simple


def _mk(tmp_path, n=500):
    p = tmp_path / 'f.py'
    p.write_text('\n'.join(f'line{i}' for i in range(1, n + 1)) + '\n', encoding='utf-8')
    return str(p)


def test_range_count_semantics(tmp_path):
    # 第三段 < 起始行 → 行数语义：308|100 = 第308行起100行
    p = _mk(tmp_path)
    out = _read_file_direct_simple(f'{p}|308|100')
    assert out.startswith('308│line308\n')
    assert '407│line407' in out and 'line408' not in out


def test_range_end_semantics(tmp_path):
    # 第三段 > 起始行 → 结束行语义：308|320 = 第308~320行
    p = _mk(tmp_path)
    out = _read_file_direct_simple(f'{p}|308|320')
    assert out.startswith('308│line308\n')
    assert '320│line320' in out and 'line321' not in out


def test_range_start_beyond_eof_reports(tmp_path):
    # 起始行超界：给可诊断信息而非静默空串（空串曾被三态引擎标 AFFIRM）
    p = _mk(tmp_path, n=10)
    out = _read_file_direct_simple(f'{p}|308|100')
    assert '超界' in out and '共10行' in out


def test_range_line_numbers_are_absolute(tmp_path):
    # 0707 第九轮实录：范围读无行号，模型两次原话抱怨"没显示具体行号"，
    # 顶推推荐的 replace_lines 要坐标而工具不给——行号必须是文件绝对行号
    p = _mk(tmp_path, n=20)
    out = _read_file_direct_simple(f'{p}|5|3')
    assert out == '5│line5\n6│line6\n7│line7\n'


def test_whole_file_default(tmp_path):
    # 全文件读保持无行号（行号只在范围读时给，坐标语义与 起始行|行数 绑定）
    p = _mk(tmp_path, n=5)
    out = _read_file_direct_simple(p)
    assert out.startswith('line1\n') and 'line5' in out


# ── P3 底层优化：语法守卫 / 未找到诊断 / 行区间替换 ──────────────────────────


def _mk_py(tmp_path, src='def foo():\n    a = 1\n    return a\n'):
    p = tmp_path / 'm.py'
    p.write_text(src, encoding='utf-8')
    return str(p), src


def test_replace_syntax_guard_reverts(tmp_path):
    # 把文件改出语法错误还报"已替换"成功，agent 拿着 AFFIRM 走到 oracle 才发现
    # 文件废了（P3 三连拒实录之一）——守卫必须自动还原并给出行号
    from agent_system.agent_tools import _replace_in_file_direct

    p, src = _mk_py(tmp_path)
    out = _replace_in_file_direct(f'{p}|    return a|    return (a')
    assert '语法错误' in out and '已自动还原' in out
    assert open(p, encoding='utf-8').read() == src  # 原文完好


def test_replace_not_found_gives_closest_snippet(tmp_path):
    # 抄错一个空格不再只回"未找到"，附上文件里最接近的原文供修正
    from agent_system.agent_tools import _replace_in_file_direct

    p, _ = _mk_py(tmp_path)
    out = _replace_in_file_direct(f'{p}|    a=1|    a=2')  # 空格抄丢了（且非原文子串）
    assert '未找到' in out and '最接近的原文' in out and 'a = 1' in out


def test_write_file_new_broken_py_is_deleted(tmp_path):
    from agent_system.agent_tools import _write_file_direct_simple

    p = str(tmp_path / 'new.py')
    out = _write_file_direct_simple(f'{p}|def broken(:')
    assert '语法错误' in out and not os.path.exists(p)


def test_replace_lines_basic(tmp_path):
    from agent_system.agent_tools import _replace_lines_direct

    p, _ = _mk_py(tmp_path)
    out = _replace_lines_direct(f'{p}|2|3|    b = 2\\n    return b')
    assert '已替换' in out and '第2-3行' in out
    assert open(p, encoding='utf-8').read() == 'def foo():\n    b = 2\n    return b\n'


def test_replace_lines_syntax_guard(tmp_path):
    from agent_system.agent_tools import _replace_lines_direct

    p, src = _mk_py(tmp_path)
    out = _replace_lines_direct(f'{p}|2|3|broken(')
    assert '语法错误' in out and open(p, encoding='utf-8').read() == src


def test_replace_lines_bad_range(tmp_path):
    from agent_system.agent_tools import _replace_lines_direct

    p, _ = _mk_py(tmp_path)
    assert '行区间无效' in _replace_lines_direct(f'{p}|5|99|x = 1')
    assert '格式' in _replace_lines_direct(f'{p}|2|3')


# ── 0707 第九轮：行号前缀剥除（read_file 带行号后，模型会把 "N│" 抄进 old/new）──


def test_replace_strips_copied_lineno_prefixes(tmp_path):
    # old 原文未命中但剥掉 N│ 前缀后命中 → 自动剥除（old 与 new 同剥），结果注明
    from agent_system.agent_tools import _replace_in_file_direct

    p, _ = _mk_py(tmp_path)
    out = _replace_in_file_direct(f'{p}|2│    a = 1|2│    a = 2')
    assert '已替换' in out and '行号前缀已剥除' in out
    assert open(p, encoding='utf-8').read() == 'def foo():\n    a = 2\n    return a\n'


def test_replace_verbatim_hit_never_strips(tmp_path):
    # 原文直接命中时不做任何剥除——文件里真实存在的 "N│" 内容不被误伤
    from agent_system.agent_tools import _replace_in_file_direct

    src = "def foo():\n    s = '3│x'\n    return s\n"
    p = tmp_path / 'm.py'
    p.write_text(src, encoding='utf-8')
    out = _replace_in_file_direct(f"{p}|    s = '3│x'|    s = '3│y'")
    assert '已替换' in out and '剥除' not in out
    assert "'3│y'" in open(p, encoding='utf-8').read()


def test_replace_lines_strips_lineno_prefixes_in_new(tmp_path):
    # 模型把带行号的 read_file 输出整段抄来当 new —— 前缀剥掉后落盘
    from agent_system.agent_tools import _replace_lines_direct

    p, _ = _mk_py(tmp_path)
    out = _replace_lines_direct(f'{p}|2|3|2│    b = 2\\n3│    return b')
    assert '已替换' in out
    assert open(p, encoding='utf-8').read() == 'def foo():\n    b = 2\n    return b\n'
