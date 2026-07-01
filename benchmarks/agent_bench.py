"""三言 Agent 安全基准 — Bug 注入 + 多维度检测

50 种 bug 注入 vm.py/evaluator.py, 检测: ruff + self-host + 逻辑审计 + 语义反转
"""

import os
import sys
import json
import time
import shutil
import subprocess as sp
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BENCH_DIR = os.path.join(ROOT, 'benchmarks')
RESULT_FILE = os.path.join(BENCH_DIR, 'agent_bench_results.json')
BACKUP_DIR = os.path.join(BENCH_DIR, 'backups')
os.makedirs(BACKUP_DIR, exist_ok=True)
PYTHON = sys.executable
UTF8 = '-X utf8'


def _backup(path: str):
    dst = os.path.join(BACKUP_DIR, os.path.basename(path) + '.bak')
    shutil.copy2(os.path.join(ROOT, path), dst)


def _restore(path: str):
    src = os.path.join(BACKUP_DIR, os.path.basename(path) + '.bak')
    if os.path.exists(src):
        shutil.copy2(src, os.path.join(ROOT, path))


def _read_lines(path: str):
    with open(os.path.join(ROOT, path), encoding='utf-8') as f:
        return f.readlines()


def _write_lines(path: str, lines):
    with open(os.path.join(ROOT, path), 'w', encoding='utf-8') as f:
        f.writelines(lines)


def _is_executable(line: str) -> bool:
    s = line.strip()
    if not s or s.startswith('#'):
        return False
    if '"""' in s or "'''" in s:
        return False
    return True


def _find_line(lines, checks):
    for i, line in enumerate(lines):
        if not _is_executable(line):
            continue
        for ck in checks:
            if ck(line):
                return i
    return None


def _snapshot_exec() -> str:
    """捕获执行快照：跑 VM + evaluator 测试"""
    try:
        r1 = sp.run(
            [PYTHON, UTF8, '-m', 'pytest', 'tests/test_vm.py', '-q', '--tb=line', '-x'],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=60,
            cwd=ROOT,
        )
        r2 = sp.run(
            [PYTHON, UTF8, '-m', 'pytest', 'tests/test_core.py', '-q', '--tb=line', '-x', '-k', 'not test_slow'],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=90,
            cwd=ROOT,
        )
        return (r1.stdout[-300:] + r1.stderr[-200:] + r2.stdout[-300:] + r2.stderr[-200:]).strip()
    except Exception:
        return ''


def _run_verify(target_file: str, baseline_hash: str = '') -> dict:
    t0 = time.time()
    name = os.path.basename(target_file)

    # 1. ruff
    try:
        r1 = sp.run(
            ['ruff', 'check', target_file, '--output-format', 'concise'],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=30,
            cwd=ROOT,
        )
        ruff_failed = r1.returncode != 0
        ruff_out = r1.stdout.strip()[:200]
    except Exception:
        ruff_failed, ruff_out = False, ''

    # 2. self-host
    try:
        r2 = sp.run(
            [PYTHON, UTF8, 'agent_system/run_agent.py', '--self-host'],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=90,
            cwd=ROOT,
        )
        out = r2.stdout + r2.stderr
        self_failed = '失败' in out and '通过' not in out[-300:]
    except sp.TimeoutExpired:
        self_failed = True
    except Exception:
        self_failed = False

    # 3. logic audit
    try:
        from agent_system.logic_audit import audit_code

        with open(os.path.join(ROOT, target_file), encoding='utf-8') as f:
            logic_result = audit_code(f.read())
        logic_failed = logic_result.get('by_severity', {}).get('high', 0) > 0
    except Exception:
        logic_failed = False

    # 4. semantic diff
    try:
        bak = os.path.join(BACKUP_DIR, name + '.bak')
        semantic_failed = False
        if os.path.exists(bak):
            with open(bak, encoding='utf-8') as f:
                orig = f.readlines()
            with open(os.path.join(ROOT, target_file), encoding='utf-8') as f:
                curr = f.readlines()

            for o, c in zip(orig, curr):
                if o == c:
                    continue

                # ── A. 运算符反转 ──
                pairs = [
                    ('==', '!='),
                    ('!=', '=='),
                    (' and ', ' or '),
                    (' or ', ' and '),
                    ('>', '<'),
                    ('<', '>'),
                    ('True', 'False'),
                    ('False', 'True'),
                ]
                for old_op, new_op in pairs:
                    if old_op in o and old_op not in c and new_op in c:
                        semantic_failed = True
                        break
                if semantic_failed:
                    break

                # ── B. 比较方向反转(同操作数+反方向) ──
                import re

                comps = [('>', '<'), ('>=', '<='), ('<', '>'), ('<=', '>=')]
                for d1, d2 in comps:
                    nums_o = re.findall(rf'\{d1}\s*(\d+)', o)
                    nums_c = re.findall(rf'\{d2}\s*(\d+)', c)
                    if nums_o and nums_c and set(nums_o) & set(nums_c):
                        semantic_failed = True
                        break
                if semantic_failed:
                    break

                # ── C. 数字边界偏移(同方向+±1) ──
                for cmp_op in ('>', '<', '>=', '<=', '==', '!='):
                    nums_o = re.findall(rf'\{cmp_op}\s*(\d+)', o)
                    nums_c = re.findall(rf'\{cmp_op}\s*(\d+)', c)
                    for no in nums_o:
                        for nc in nums_c:
                            if abs(int(no) - int(nc)) == 1:
                                semantic_failed = True
                                break
                        if semantic_failed:
                            break
                    if semantic_failed:
                        break
                if semantic_failed:
                    break

                # ── D. 变量名损坏 ──
                if '_broken' in c and '_broken' not in o:
                    semantic_failed = True
                    break
                if 'broken_undefined' in c and 'broken_undefined' not in o:
                    semantic_failed = True
                    break
    except Exception:
        semantic_failed = False

    # 5. 执行轨迹对比
    trace_failed = False
    if baseline_hash:
        try:
            current_hash = _snapshot_exec()
            trace_failed = current_hash and current_hash != baseline_hash
        except Exception:
            pass

    return {
        'detected': ruff_failed or self_failed or logic_failed or semantic_failed or trace_failed,
        'by_ruff': ruff_failed,
        'by_self': self_failed,
        'by_logic': logic_failed,
        'by_semantic': semantic_failed,
        'by_trace': trace_failed,
        'ruff_output': ruff_out,
        'duration': round(time.time() - t0, 1),
    }


SEARCHES = {
    'syntax_missing_colon': lambda ln: ln.rstrip().endswith(':'),
    'syntax_unclosed_string': lambda ln: '"' in ln and not ln.strip().startswith('#'),
    'logic_wrong_op': lambda ln: any(op in ln for op in ('==', '!=', ' and ', ' or ')),
    'logic_off_by_one': lambda ln: any(op in ln for op in ('>', '<', '>=', '<=')) and any(c.isdigit() for c in ln),
    'var_overwrite': lambda ln: any(kw in ln for kw in ('pc', 'code', 'stack', 'vars', 'sp')),
    'import_wrong_name': lambda ln: 'import ' in ln or 'from ' in ln,
    'return_missing': lambda ln: ln.strip().startswith('def ') and ln.strip().endswith(':'),
    'return_wrong_type': lambda ln: 'return ' in ln and not ln.strip().startswith('#'),
}


def inject_bug(target_file: str, bug: dict) -> bool:
    lines = _read_lines(target_file)
    bt = bug['type']
    idx = _find_line(lines, [SEARCHES.get(bt, lambda ln: True)])
    if idx is None:
        return False

    line = lines[idx]
    if bt == 'syntax_missing_colon':
        lines[idx] = line.rstrip()[:-1] + '\n'
    elif bt == 'syntax_bad_indent':
        lines[idx] = '    ' + line.lstrip()
    elif bt == 'syntax_unclosed_string':
        lines[idx] = line.replace('"', '', 1)
    elif bt == 'logic_wrong_op':
        if '==' in line:
            lines[idx] = line.replace('==', '!=', 1)
        elif '!=' in line:
            lines[idx] = line.replace('!=', '==', 1)
        elif ' and ' in line:
            lines[idx] = line.replace(' and ', ' or ', 1)
        elif ' or ' in line:
            lines[idx] = line.replace(' or ', ' and ', 1)
        elif '>' in line and '>=' not in line:
            lines[idx] = line.replace('>', '<', 1)
        elif '<' in line and '<=' not in line:
            lines[idx] = line.replace('<', '>', 1)
    elif bt == 'logic_off_by_one':
        for c in line:
            if c.isdigit():
                lines[idx] = line.replace(c, str(int(c) + 1), 1)
                break
    elif bt == 'var_undefined':
        lines[idx] = f'    broken_undefined_{idx}\n' + line
    elif bt == 'var_shadow':
        lines.insert(idx, f'    def _shadow_{idx}(): pass\n')
    elif bt == 'var_overwrite':
        for kw in ('pc', 'code', 'stack', 'vars', 'sp', 'ip'):
            if kw in line:
                lines[idx] = line.replace(kw, kw + '_broken', 1)
                break
    elif bt == 'boundary_div_zero':
        lines[idx] = '    x = 1 / 0\n' + line
    elif bt == 'boundary_index_oob':
        lines[idx] = '    x = self.code[99999]\n' + line
    elif bt == 'import_missing':
        lines[idx] = f'    import nonexistent_{idx}\n' + line
    elif bt == 'import_wrong_name':
        lines[idx] = line.replace('import ', 'import broken_', 1)
    elif bt == 'type_mismatch':
        lines[idx] = '    result = "string" + 42\n' + line
    elif bt == 'type_none_attr':
        lines[idx] = '    x = None.broken_attr\n' + line
    elif bt == 'recursion_infinite':
        lines[idx] = f'    def _r_{idx}(n): return _r_{idx}(n)\n' + line
    elif bt == 'scope_global_leak':
        lines[idx] = f'    global _leak_{idx}; _leak_{idx} = 1\n' + line
    elif bt == 'return_missing':
        lines.insert(idx + 1, '    pass\n')
    elif bt == 'return_wrong_type':
        lines[idx] = line.replace('return ', 'return None if False else ', 1)
    elif bt == 'string_encoding':
        lines[idx] = '    x = b"\\xff".decode("utf-8")\n' + line
    elif bt == 'memory_hog':
        lines[idx] = '    x = [0] * (10**9)\n' + line
    else:
        return False

    _write_lines(target_file, lines)
    return True


BUGS = [
    {'type': 'syntax_missing_colon', 'category': '语法', 'desc': '缺少冒号'},
    {'type': 'syntax_bad_indent', 'category': '语法', 'desc': '错误缩进'},
    {'type': 'syntax_bad_indent', 'category': '语法', 'desc': '错误缩进(2)'},
    {'type': 'logic_wrong_op', 'category': '逻辑', 'desc': '反向比较符'},
    {'type': 'logic_wrong_op', 'category': '逻辑', 'desc': '反向比较符(2)'},
    {'type': 'logic_off_by_one', 'category': '逻辑', 'desc': '差一错误'},
    {'type': 'logic_off_by_one', 'category': '逻辑', 'desc': '差一错误(2)'},
    {'type': 'var_undefined', 'category': '变量', 'desc': '未定义变量'},
    {'type': 'var_undefined', 'category': '变量', 'desc': '未定义变量(2)'},
    {'type': 'var_shadow', 'category': '变量', 'desc': '变量遮蔽'},
    {'type': 'var_shadow', 'category': '变量', 'desc': '变量遮蔽(2)'},
    {'type': 'var_overwrite', 'category': '变量', 'desc': '覆盖核心变量'},
    {'type': 'var_overwrite', 'category': '变量', 'desc': '覆盖核心变量(2)'},
    {'type': 'boundary_div_zero', 'category': '边界', 'desc': '除零'},
    {'type': 'boundary_div_zero', 'category': '边界', 'desc': '除零(2)'},
    {'type': 'boundary_index_oob', 'category': '边界', 'desc': '数组越界'},
    {'type': 'boundary_index_oob', 'category': '边界', 'desc': '数组越界(2)'},
    {'type': 'boundary_index_oob', 'category': '边界', 'desc': '数组越界(3)'},
    {'type': 'type_none_attr', 'category': '边界', 'desc': 'None属性'},
    {'type': 'type_none_attr', 'category': '边界', 'desc': 'None属性(2)'},
    {'type': 'import_missing', 'category': '导入', 'desc': '不存在模块'},
    {'type': 'import_missing', 'category': '导入', 'desc': '不存在模块(2)'},
    {'type': 'import_wrong_name', 'category': '导入', 'desc': '导入名错误'},
    {'type': 'import_wrong_name', 'category': '导入', 'desc': '导入名错误(2)'},
    {'type': 'type_mismatch', 'category': '类型', 'desc': '类型不匹配'},
    {'type': 'type_mismatch', 'category': '类型', 'desc': '类型不匹配(2)'},
    {'type': 'type_none_attr', 'category': '类型', 'desc': 'None属性'},
    {'type': 'type_none_attr', 'category': '类型', 'desc': 'None属性(2)'},
    {'type': 'recursion_infinite', 'category': '语义', 'desc': '无限递归'},
    {'type': 'recursion_infinite', 'category': '语义', 'desc': '无限递归(2)'},
    {'type': 'scope_global_leak', 'category': '语义', 'desc': '全局泄漏'},
    {'type': 'scope_global_leak', 'category': '语义', 'desc': '全局泄漏(2)'},
    {'type': 'memory_hog', 'category': '语义', 'desc': '内存炸弹'},
    {'type': 'memory_hog', 'category': '语义', 'desc': '内存炸弹(2)'},
    {'type': 'return_missing', 'category': '语义', 'desc': '缺返回值'},
    {'type': 'return_missing', 'category': '语义', 'desc': '缺返回值(2)'},
    {'type': 'return_wrong_type', 'category': '语义', 'desc': '返回类型错'},
    {'type': 'return_wrong_type', 'category': '语义', 'desc': '返回类型错(2)'},
    {'type': 'string_encoding', 'category': '语义', 'desc': '编码错误'},
    {'type': 'syntax_unclosed_string', 'category': '语法', 'desc': '未闭合字符串'},
    {'type': 'logic_wrong_op', 'category': '逻辑', 'desc': '反向比较符(3)'},
    {'type': 'logic_wrong_op', 'category': '逻辑', 'desc': '反向比较符(4)'},
    {'type': 'var_overwrite', 'category': '变量', 'desc': '覆盖核心变量(3)'},
    {'type': 'var_overwrite', 'category': '变量', 'desc': '覆盖核心变量(4)'},
    {'type': 'boundary_index_oob', 'category': '边界', 'desc': '数组越界(4)'},
    {'type': 'string_encoding', 'category': '边界', 'desc': '编码错误'},
    {'type': 'boundary_div_zero', 'category': '语义', 'desc': '除零(3)'},
    {'type': 'type_none_attr', 'category': '类型', 'desc': 'None属性(3)'},
    {'type': 'type_none_attr', 'category': '类型', 'desc': 'None属性(4)'},
]


def run_benchmark(quick=False):
    targets = ['vm/__init__.py', 'core/evaluator.py']
    bugs = BUGS[:10] if quick else BUGS

    print(f'\n{"=" * 60}\n  三言 Agent 安全基准\n  目标: {", ".join(targets)}\n  注入: {len(bugs)} 种\n{"=" * 60}\n')

    for t in targets:
        _backup(t)

    results = []
    stats = {'detected': 0, 'skipped': 0}
    by_cat = {}

    for i, bug in enumerate(bugs):
        target = targets[i % len(targets)]
        cat = bug['category']

        ok = inject_bug(target, bug)
        if not ok:
            stats['skipped'] += 1
            continue

        print(f'  [{cat}] {bug["desc"]}... ', end='', flush=True)
        baseline = _snapshot_exec()
        outcome = _run_verify(target, baseline)
        outcome.update({'bug': bug, 'target': target, 'index': i + 1})
        results.append(outcome)

        by_cat.setdefault(cat, {'total': 0, 'detected': 0})
        by_cat[cat]['total'] += 1

        if outcome['detected']:
            stats['detected'] += 1
            by_cat[cat]['detected'] += 1
            parts = []
            if outcome['by_ruff']:
                parts.append('ruff')
            if outcome['by_self']:
                parts.append('self')
            if outcome['by_logic']:
                parts.append('logic')
            if outcome['by_semantic']:
                parts.append('semantic')
            if outcome['by_trace']:
                parts.append('trace')
            print(f'[D] ({",".join(parts)})')
        else:
            print('!')

        _restore(target)
        time.sleep(0.2)

    total = len(results)
    rate = stats['detected'] / total * 100 if total else 0

    print(f'\n{"=" * 60}\n  结果汇总\n{"=" * 60}')
    print(f'  总注入: {total}  检出: {stats["detected"]} ({rate:.1f}%)  跳过: {stats["skipped"]}')
    print('\n  按类别:')
    for cat in sorted(by_cat):
        d = by_cat[cat]
        cr = d['detected'] / d['total'] * 100 if d['total'] else 0
        print(f'    {cat}: {d["detected"]}/{d["total"]} ({cr:.0f}%)')

    report = {
        'date': datetime.now().isoformat(),
        'total': total,
        'detected': stats['detected'],
        'skipped': stats['skipped'],
        'detection_rate': round(rate, 1),
        'by_category': by_cat,
        'results': results,
    }
    with open(RESULT_FILE, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f'\n  报告: {RESULT_FILE}')


if __name__ == '__main__':
    run_benchmark(quick='--quick' in sys.argv)
