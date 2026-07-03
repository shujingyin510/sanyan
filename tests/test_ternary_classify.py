"""三态引擎 classify：读类工具失败判定只看错误信封（前缀区），不嗅探内容负载。

P2 探针#8 回归守护：read_file 读回的函数体含 error/失败 字样（控制流代码的
常态），全文嗅探把一次成功读取判成高置信 NEGATE(0.85×0.90=0.77)，保护门控
当场 block 断轮 —— agent 永远无法阅读任何含错误处理逻辑的代码。
"""

from core.ternary_engine import TernaryEngine


def test_read_payload_with_error_words_is_affirm():
    e = TernaryEngine()
    body = "def ternary_match(x):\n    if x is None:\n        raise ValueError('匹配失败: error')\n"
    assert e.classify('read_file', body) == 'AFFIRM'
    assert e.classify('search_code', 'vm.py:12: print("fail traceback")') == 'AFFIRM'


def test_read_tool_error_envelope_is_uncert():
    e = TernaryEngine()
    assert e.classify('read_file', '读文件错误: [Errno 2] No such file or directory') == 'UNCERT'
    assert e.classify('read_file', '(空: 文件共10行, 起始行308超界)') == 'UNCERT'
    assert e.classify('search_code', '未找到: def foo') == 'UNCERT'
    assert e.classify('read_file', '') == 'UNCERT'  # 空负载无信息量


def test_non_read_tools_keep_failure_sniffing():
    e = TernaryEngine()
    assert e.classify('run_test', 'FAIL test_foo') == 'NEGATE'
    assert e.classify('run_shell', 'x error y') == 'NEGATE'
    assert e.classify('replace_in_file', '已替换 3 处') == 'AFFIRM'
    assert e.classify('replace_in_file', '未找到 "旧文本"') == 'UNCERT'
