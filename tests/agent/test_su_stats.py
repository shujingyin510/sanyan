"""失败数据库（su_stats）：日志解析与死因分类的回归钉。"""

from agent_system.su_stats import classify_reason, parse_validate_log, report

_SAMPLE = """任务书: 重构 ops/control_ops.py:308 的超长函数 ternary_match（94 行），拆成更小的函数 用 read_file 查看（范围读 路径|起始行|行数，输出每行带 "N│" 行号）
agent 日志: C:/不存在/x.log
—— 候选 1/2 ——
✗ 候选 1 已回滚: oracle 未过: oracle#0 拒绝: ternary_match 未变短: 94 行 ≥ 基线 94 行
—— 被拒改动 stat ——
 ops/control_ops.py | 77 +++++++++
 1 file changed, 67 insertions(+), 1 deletion(-)
—— 候选 2/2 ——
✗ 候选 2 已回滚: 无改动（edit_fn 未产生 diff）
║  工具步骤: 11                                             ║
║  LLM调用:  23                                             ║
║  Token用量: 68375                                          ║
║  输出预览: 总执行时间超过900秒                                    ║
EXIT=1
"""


def test_parse_blocks_and_fields(tmp_path):
    p = tmp_path / 'su-validate-x.log'
    p.write_text(_SAMPLE, encoding='utf-8')
    recs = parse_validate_log(str(p))
    assert len(recs) == 2
    a, b = recs
    assert a['mode'] == 'candidates' and a['idx'] == 1 and a['task'] == 'ternary_match'
    assert a['reason_class'] == '未变短' and a['ins'] == 67 and a['dels'] == 1
    assert a['runbook'] == 'v2-行号'
    assert b['reason_class'] == '无改动' and b['llm_calls'] == 23 and b['tokens'] == 68375
    assert b['stop'].startswith('总执行时间超过900秒')
    assert a['noise'] is None  # agent 日志不存在 → 噪音未知，不崩


def test_classify_priority():
    assert classify_reason('big 重写而非搬运：2 行原始语句消失（守恒检查）: x') == '守恒'
    assert classify_reason('调用了模块内解析不到的名字: _x') == '解析不到'
    assert classify_reason('未变短: 94 行 ≥ 基线 94 行；辅助函数嵌套在目标函数内部') == '嵌套'
    assert classify_reason('失败数 4 > 基线 0；失败用例: t') == 'pytest'
    assert classify_reason('触碰考官域: tests/x.py（红线①，fail-closed）') == '考官域'


def test_report_smoke(tmp_path):
    p = tmp_path / 'su-validate-y.log'
    p.write_text(_SAMPLE, encoding='utf-8')
    txt = report(parse_validate_log(str(p)))
    assert '真候选 1' in txt and '未变短' in txt and 'v2-行号' in txt
