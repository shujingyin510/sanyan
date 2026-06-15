"""三言 Agent 自动验证脚本 — 完整自主循环

代码变化 → 跑全量测试 → 通过则自动提交 / 失败则 stash 回退

用法:  python -X utf8 auto_verify.py
      或 git post-commit hook 自动调用
"""

import os
import sys
import subprocess as sp

ROOT = os.path.dirname(os.path.abspath(__file__))


def run(cmd, timeout=300):
    return sp.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=ROOT)


def main():
    print('=' * 50)
    print('  三言 Agent 自动验证')
    print('=' * 50)

    # 1. 跑全量测试
    print('\n[1/3] 运行 preflight --quick...')
    r = run([sys.executable, '-X', 'utf8', 'preflight.py', '--quick'], timeout=300)
    print(r.stdout[-500:] if len(r.stdout) > 500 else r.stdout)
    if r.returncode != 0:
        print(f'\n[2/3] 测试失败 (exit={r.returncode})，Agent 介入修复...')
        r2 = run(
            [
                sys.executable,
                '-X',
                'utf8',
                'run_agent.py',
                '--auto',
                '测试失败：' + r.stdout[-500:].strip() + '。分析失败原因并修复代码。',
            ],
            timeout=300,
        )
        print(r2.stdout[-300:] if len(r2.stdout) > 300 else r2.stdout)
        # 再测一次
        r3 = run([sys.executable, '-X', 'utf8', 'preflight.py', '--quick'], timeout=300)
        if r3.returncode != 0:
            print('\n[3/3] Agent 修复后仍失败，git stash 回退...')
            run(['git', 'stash', '-m', 'agent自动修复失败-回退现场'])
            print('  已回退，失败现场保留在 stash 中，等待人工介入。')
            return 1
    else:
        print('\n[2/3] 测试通过。')

    # 3. 自动提交
    print('\n[3/3] 自动提交...')
    r = run(['git', 'add', '-A'])
    r = run(['git', 'commit', '-m', 'agent自动验证通过并提交'])
    print(f'  {r.stdout.strip() or r.stderr.strip() or "已提交"}')
    print('\n  ======== 自主循环完成 ========')
    return 0


if __name__ == '__main__':
    sys.exit(main())
