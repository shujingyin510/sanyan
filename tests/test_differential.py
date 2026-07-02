"""差分验证器（P2 oracle 前置修复）：fail-closed + 真差分 + 代码走文件。

旧版三雷（见 REFACTOR_PLAN 2026-07-01）：代码当 CLI 参数传给只吃文件路径的 main.py
→ 两后端全崩；全崩时 outputs 为空 → consistent 保持默认 True（假绿 100%）；
两个"后端"实为同一默认 VM（假差分）。
"""

import os
from types import SimpleNamespace

from agent_system.agent_evolution import DifferentialVerifier

CASE = [{'input': '(输出 (加 1 2))', 'expected': '3'}]


def _runner(by_backend):
    """按后端（有无 --eval）出结果的假 runner；顺带断言代码以真实存在的 .san 文件传入。"""

    def run(cmd, **kw):
        san = cmd[-1]
        assert san.endswith('.san') and os.path.exists(san)
        rc, out = by_backend['python' if '--eval' in cmd else 'vm']
        return SimpleNamespace(returncode=rc, stdout=out, stderr='')

    return run


def test_all_backends_fail_is_inconsistent(tmp_path):
    v = DifferentialVerifier(cwd=str(tmp_path), runner=_runner({'python': (1, ''), 'vm': (1, '')}))
    r = v.verify_consistency(CASE)
    assert r['consistent'] == 0 and r['success_rate'] == 0.0  # 旧版这里假绿 = 1.0


def test_single_backend_failure_is_inconsistent(tmp_path):
    v = DifferentialVerifier(cwd=str(tmp_path), runner=_runner({'python': (0, '3\n'), 'vm': (1, 'boom')}))
    assert v.verify_consistency(CASE)['consistent'] == 0


def test_agreement_is_consistent(tmp_path):
    v = DifferentialVerifier(cwd=str(tmp_path), runner=_runner({'python': (0, '3\n'), 'vm': (0, '3\n')}))
    r = v.verify_consistency(CASE)
    assert r['consistent'] == 1 and r['success_rate'] == 1.0


def test_disagreement_is_inconsistent(tmp_path):
    v = DifferentialVerifier(cwd=str(tmp_path), runner=_runner({'python': (0, '3\n'), 'vm': (0, '4\n')}))
    assert v.verify_consistency(CASE)['consistent'] == 0


def test_backends_are_really_different():
    args = [b['args'] for b in DifferentialVerifier.BACKENDS.values()]
    assert ['--eval'] in args and [] in args  # 求值器 vs 默认 VM，不再是同一引擎


def test_normalize_strips_noise_and_maps_echoes():
    n = DifferentialVerifier._normalize
    assert n('[OK] 编译 x → build\\y.bin: 12 字节, 0 变量\n3\n') == '3'  # VM：去编译噪音
    assert n('  => 3（三进制: +0）\n[OK] 编译 x → y\n') == '3'  # eval：数字回显还原
    assert n('  => 是\n') == '是'  # eval：字符串回显（无三进制注记）
    assert n('结果: 10\n') == '10'  # eval：另一种回显形态
    assert n('') == ''


def test_real_backends_agree_e2e():
    """真跑两个后端（--eval 求值器 + 默认字节码 VM），全部内置用例应一致。

    含多顶层表达式用例——它守护 parse_program 修复（此前 VM 只编译第一条语句）。
    """
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    r = DifferentialVerifier(cwd=root).verify_consistency()
    assert r['total'] == 5 and r['consistent'] == 5, r
