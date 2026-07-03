"""agent 工具层：read_file 范围读取的参数语义。

P2 探针#7 抓到的根因回归守护：模型发「路径|起始行|行数」（如 308|100），
旧实现把第三段当"结束行"，切片 [307:100] 永远为空——模型每轮读到虚空、
在同一区域原地打转直到被 UR 判死，replace_in_file 无从谈起。
"""

from agent_system.agent_tools import _read_file_direct_simple


def _mk(tmp_path, n=500):
    p = tmp_path / 'f.py'
    p.write_text('\n'.join(f'line{i}' for i in range(1, n + 1)) + '\n', encoding='utf-8')
    return str(p)


def test_range_count_semantics(tmp_path):
    # 第三段 < 起始行 → 行数语义：308|100 = 第308行起100行
    p = _mk(tmp_path)
    out = _read_file_direct_simple(f'{p}|308|100')
    assert out.startswith('line308\n')
    assert 'line407' in out and 'line408' not in out


def test_range_end_semantics(tmp_path):
    # 第三段 > 起始行 → 结束行语义：308|320 = 第308~320行
    p = _mk(tmp_path)
    out = _read_file_direct_simple(f'{p}|308|320')
    assert out.startswith('line308\n')
    assert 'line320' in out and 'line321' not in out


def test_range_start_beyond_eof_reports(tmp_path):
    # 起始行超界：给可诊断信息而非静默空串（空串曾被三态引擎标 AFFIRM）
    p = _mk(tmp_path, n=10)
    out = _read_file_direct_simple(f'{p}|308|100')
    assert '超界' in out and '共10行' in out


def test_whole_file_default(tmp_path):
    p = _mk(tmp_path, n=5)
    out = _read_file_direct_simple(p)
    assert out.startswith('line1\n') and 'line5' in out
