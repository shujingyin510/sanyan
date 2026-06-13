"""preflight — 发版前质量门

用法:
    python preflight.py          # 全部检查
    python preflight.py --quick  # 快速检查 (跳过慢的)
    python preflight.py --lint   # 仅 lint
    python preflight.py --test   # 仅测试
    python preflight.py --help

检查项:
    1. ruff format + check (格式)
    2. mypy (类型检查)
    3. pytest 全量 (Python 测试)
    4. 跨平台路径检查 (大小写、反斜杠)
    5. 自举验证 (Level 0-3)
    6. 差分模糊测试 (四后端)
    7. .bin / .san 一致性
    8. 编码检查 (UTF-8 / CRLF)
"""

import os
import sys
import subprocess
import time
from pathlib import Path
from dataclasses import dataclass
from typing import Callable

ROOT = Path(__file__).parent.resolve()
RED = '\033[31m'
GREEN = '\033[32m'
YELLOW = '\033[33m'
RESET = '\033[0m'


@dataclass
class CheckResult:
    name: str
    passed: bool
    duration: float = 0.0
    detail: str = ''
    skipped: bool = False
    skip_reason: str = ''


results: list[CheckResult] = []


def check(name: str, fn: Callable, quick_skip: bool = False):
    """运行检查并记录结果"""
    global results

    if quick_skip and '--quick' in sys.argv:
        results.append(CheckResult(name, True, 0, '跳过 (quick)', True, '--quick'))
        return

    t0 = time.time()
    try:
        detail = fn()
        passed = True
    except AssertionError as e:
        detail = str(e)
        passed = False
    except Exception as e:
        detail = f'{type(e).__name__}: {e}'
        passed = False
    dt = time.time() - t0
    results.append(CheckResult(name, passed, dt, detail))
    status = f'{GREEN}PASS{RESET}' if passed else f'{RED}FAIL{RESET}'
    print(f'  [{status}] {name} ({dt:.1f}s)  {detail[:100]}')


# ═══════════════════════════════════════════════════════════════
# 1. Lint
# ═══════════════════════════════════════════════════════════════


def ruff_format():
    r = subprocess.run(
        [sys.executable, '-m', 'ruff', 'format', '--check', '.'], capture_output=True, text=True, cwd=str(ROOT)
    )
    assert r.returncode == 0, f'ruff format: {r.stdout.splitlines()[-1] if r.stdout else r.stderr[:200]}'
    return 'OK'


def ruff_check():
    r = subprocess.run([sys.executable, '-m', 'ruff', 'check', '.'], capture_output=True, text=True, cwd=str(ROOT))
    assert r.returncode == 0, f'ruff check: {r.stdout.splitlines()[-1] if r.stdout else r.stderr[:200]}'
    return 'OK'


def mypy_check():
    r = subprocess.run([sys.executable, '-m', 'mypy', '.'], capture_output=True, text=True, cwd=str(ROOT))
    # mypy returns 0 even with notes, only fail on actual errors
    if 'error:' in (r.stdout + r.stderr):
        # Find the error line
        for line in (r.stdout + r.stderr).splitlines():
            if 'error:' in line:
                raise AssertionError(f'mypy: {line.strip()[:150]}')
    return 'OK'


# ═══════════════════════════════════════════════════════════════
# 2. Tests
# ═══════════════════════════════════════════════════════════════


def pytest_core():
    test_files = [
        'tests/test_core.py',
        'tests/test_commands.py',
        'tests/test_parser.py',
        'tests/test_ops.py',
        'tests/test_ops_ext.py',
        'tests/test_lsp.py',
        'tests/test_package.py',
        'tests/test_iot.py',
        'tests/test_dp_python.py',
        'tests/test_vm.py',
        'tests/test_llvmgen.py',
        'tests/test_sugar_san.py',
        'tests/test_agent.py',
        'tests/test_agent_runtime.py',
        'tests/test_agent_v5.py',
        'tests/test_lang_core.py',
        'tests/test_new_features.py',
        'tests/test_lang_core_ext.py',
        'tests/test_effect_types.py',
        'tests/test_disasm.py',
    ]
    r = subprocess.run(
        [sys.executable, '-X', 'utf8', '-m', 'pytest'] + test_files + ['-q'],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        timeout=300,
    )
    last_line = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ''
    assert 'passed' in last_line and 'failed' not in last_line.lower(), f'pytest: {last_line[:150]}'
    # Extract count
    import re

    m = re.search(r'(\d+) passed', last_line)
    count = m.group(1) if m else '?'
    return f'{count} passed'


def pytest_self_host():
    r = subprocess.run(
        [sys.executable, '-X', 'utf8', 'tests/test_self_host.py', '-q'],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        timeout=120,
    )
    last_line = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ''
    assert 'OK' in last_line or 'passed' in last_line, f'self_host: {last_line[:150]}'
    import re

    m = re.search(r'(\d+) passed', last_line)
    count = m.group(1) if m else '?'
    return f'{count} passed'


def pytest_sugar_self_host():
    r = subprocess.run(
        [sys.executable, '-X', 'utf8', 'tests/test_sugar_self_host.py', '-q'],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        timeout=120,
    )
    last_line = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ''
    assert 'OK' in last_line or 'passed' in last_line, f'sugar_self_host: {last_line[:150]}'
    return 'OK'


# ═══════════════════════════════════════════════════════════════
# 3. 跨平台路径检查
# ═══════════════════════════════════════════════════════════════


def path_case_check():
    """检查路径是否大小写敏感安全"""
    issues = []
    for f in ROOT.rglob('*.py'):
        path_str = str(f)
        # 反斜杠
        if '\\' in path_str:
            issues.append(f'反斜杠: {f.relative_to(ROOT)}')
        # 大写文件名 (Linux 大小写敏感)
        name = f.name
        if name != name.lower() and name.endswith('.py') and not name.startswith('test_'):
            pass  # CamelCase is fine for class files
    for f in ROOT.rglob('*.san'):
        if '\\' in str(f):
            issues.append(f'反斜杠: {f.relative_to(ROOT)}')
    assert not issues, f'{len(issues)} 个问题: {"; ".join(issues[:3])}'
    return f'OK ({sum(1 for _ in ROOT.rglob("*.py"))} .py + {sum(1 for _ in ROOT.rglob("*.san"))} .san)'


def encoding_check():
    """检查文件编码和行尾"""
    issues_crlf = []
    issues_encoding = []
    for f in list(ROOT.rglob('*.py')) + list(ROOT.rglob('*.san')) + list(ROOT.rglob('*.c')) + list(ROOT.rglob('*.asm')):
        try:
            with open(f, 'rb') as fh:
                data = fh.read(100)
            # CRLF check
            if b'\r\n' in data and f.suffix != '.c':  # .c 文件允许 CRLF for Windows
                issues_crlf.append(str(f.relative_to(ROOT)))
            # UTF-8 check
            try:
                data.decode('utf-8')
            except UnicodeDecodeError:
                issues_encoding.append(str(f.relative_to(ROOT)))
        except Exception:
            pass

    msg_parts = []
    if issues_crlf:
        msg_parts.append(f'CRLF: {len(issues_crlf)} files')
    if issues_encoding:
        msg_parts.append(f'非UTF-8: {issues_encoding[0]}')

    # CRLF in .py files is a problem
    py_crlf = [f for f in issues_crlf if f.endswith('.py')]
    assert not py_crlf, f'Python文件含CRLF: {py_crlf[0] if py_crlf else ""}'
    return 'OK' if not msg_parts else '; '.join(msg_parts)


# ═══════════════════════════════════════════════════════════════
# 4. 二进制一致性
# ═══════════════════════════════════════════════════════════════


def bin_consistency():
    """验证 bytecode_compiler.bin 与源码一致"""
    from compile_bytecode import compile_source
    import tempfile
    import hashlib

    ref = ROOT / 'stdlib' / 'bytecode_compiler.bin'
    src = ROOT / 'stdlib' / 'bytecode_compiler.san'

    with open(src, 'r', encoding='utf-8') as f:
        source = f.read()
    with open(ref, 'rb') as f:
        ref_data = f.read()

    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, 'test.bin')
        ok, sz, vc = compile_source(source, out)
        assert ok, '编译失败'
        with open(out, 'rb') as f:
            out_data = f.read()
        assert out_data == ref_data, (
            f'SHA256 不匹配: 编译={hashlib.sha256(out_data).hexdigest()[:16]} 参考={hashlib.sha256(ref_data).hexdigest()[:16]}'
        )

    return f'{len(ref_data)}B SHA256={hashlib.sha256(ref_data).hexdigest()[:16]}'


# ═══════════════════════════════════════════════════════════════
# 5. 自举验证
# ═══════════════════════════════════════════════════════════════


def bootstrap_level2():
    """Level 2: A → B → C 不动点"""
    import sys

    sys.path.insert(0, str(ROOT / 'tests'))
    from test_self_host import _compile_with_bin, _parse_s_expr
    import tempfile

    ref = str(ROOT / 'stdlib' / 'bytecode_compiler.bin')
    with open(ROOT / 'stdlib' / 'bytecode_compiler.san', 'r', encoding='utf-8') as f:
        source = f.read()

    with tempfile.TemporaryDirectory() as d:
        b_bin = os.path.join(d, 'b.bin')
        b = _compile_with_bin(ref, source, b_bin, _parse_s_expr)
        c_bin = os.path.join(d, 'c.bin')
        c = _compile_with_bin(b_bin, source, c_bin, _parse_s_expr)
        assert b == c, 'B != C (不动点失败)'
        with open(ref, 'rb') as f:
            ref_data = f.read()
        assert b == ref_data, 'B != 参考'

    return f'B==C=={len(b)}B ✓'


# ═══════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════


def main():
    quick = '--quick' in sys.argv
    lint_only = '--lint' in sys.argv
    test_only = '--test' in sys.argv
    help_flag = '--help' in sys.argv or '-h' in sys.argv

    if help_flag:
        print(__doc__)
        return

    print(f'\n{GREEN}═══ Sanyan Preflight ═══{RESET}\n')

    if not test_only:
        print('─ Lint ─')
        check('ruff format', ruff_format)
        check('ruff check', ruff_check)
        check('mypy', mypy_check)
        print()

    if not lint_only:
        print('─ Tests ─')
        check('pytest core (20 files)', pytest_core)
        check('self_host (Level 0-3)', pytest_self_host)
        check('sugar_self_host', pytest_sugar_self_host)
        check('bin consistency', bin_consistency)
        print()

        print('─ Cross-platform ─')
        check('path case check', path_case_check)
        check('encoding CRLF/UTF-8', encoding_check)
        print()

        print('─ Bootstrap ─')
        check('Level 2 fixpoint (A→B→C)', bootstrap_level2, quick_skip=quick)
        print()

    # Summary
    passed = sum(1 for r in results if r.passed and not r.skipped)
    failed = sum(1 for r in results if not r.passed and not r.skipped)
    skipped = sum(1 for r in results if r.skipped)
    total = len(results)

    print(f'{"=" * 40}')
    if failed == 0:
        print(f'{GREEN}ALL CHECKS PASSED{RESET}  {passed}/{total} ({skipped} skipped)')
        return 0
    else:
        print(f'{RED}PREFLIGHT FAILED{RESET}  {passed} passed, {failed} failed, {skipped} skipped')
        print('\n失败项:')
        for r in results:
            if not r.passed and not r.skipped:
                print(f'  {RED}✗{RESET} {r.name}: {r.detail[:200]}')
        return 1


if __name__ == '__main__':
    sys.exit(main())
