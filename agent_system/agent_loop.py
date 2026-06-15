"""Agent 自主循环 — 连续监控 + 自动验证 + 安全阀 + 健康监控

用法:
    python -X utf8 agent_loop.py              # 交互模式
    python -X utf8 agent_loop.py --watch       # 文件监控模式
    python -X utf8 agent_loop.py --continuous   # 连续循环模式
    python -X utf8 agent_loop.py --max-cycles 5 # 最大循环次数
    python -X utf8 agent_loop.py --status       # 查看统计和健康状态
"""

import os
import sys
import time
import subprocess as sp
import argparse
from pathlib import Path

from agent_system.agent_loop_monitor import LoopLogger, LoopStats, HealthMonitor, RollbackVerifier

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WATCH_EXTS = {'.py', '.san', '.sasm'}
COOLDOWN_SECS = 30  # 冷却时间，防止无限循环
MAX_CYCLES = 10  # 默认最大循环次数
MAX_AUTO_FIX = 3  # Agent 自动修复最大次数


def run_cmd(cmd, timeout=300):
    """执行命令"""
    return sp.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=ROOT)


def get_changed_files():
    """获取当前修改的文件"""
    r = run_cmd(['git', 'status', '--porcelain'])
    files = []
    for line in r.stdout.strip().split('\n'):
        if line and len(line) > 3:
            path = line[3:].strip()
            ext = Path(path).suffix
            if ext in WATCH_EXTS:
                files.append(path)
    return files


def get_file_mtimes():
    """获取所有监控文件的修改时间"""
    mtimes = {}
    for ext in WATCH_EXTS:
        for f in Path(ROOT).rglob(f'*{ext}'):
            if '__pycache__' not in str(f) and '.pyc' not in str(f):
                try:
                    mtimes[str(f.relative_to(ROOT))] = f.stat().st_mtime
                except OSError:
                    pass
    return mtimes


def run_preflight():
    """运行 preflight 检查"""
    print('[preflight] 运行检查...')
    r = run_cmd([sys.executable, '-X', 'utf8', 'preflight.py', '--quick'], timeout=180)
    return r.returncode == 0, r.stdout[-500:]


def agent_fix(failure_output):
    """Agent 自动修复"""
    print('[agent-fix] Agent 介入修复...')
    r = run_cmd(
        [
            sys.executable,
            '-X',
            'utf8',
            'run_agent.py',
            '--auto',
            '测试失败：' + failure_output[:500] + '。分析失败原因并修复代码。',
        ],
        timeout=300,
    )
    return r.returncode == 0, r.stdout[-300:]


def git_commit(msg):
    """自动提交"""
    run_cmd(['git', 'add', '-A'])
    r = run_cmd(['git', 'commit', '-m', msg])
    return r.returncode == 0


def git_stash(msg):
    """保存现场并回退"""
    run_cmd(['git', 'stash', '-m', msg])
    print(f'  [stash] {msg}')


def verification_cycle(cycle_num, auto_fix_count, logger=None, stats=None, health=None):
    """单次验证循环，返回 (成功, auto_fix_count)"""
    cycle_start = time.time()
    print(f'\n{"=" * 50}')
    print(f'  验证循环 #{cycle_num}')
    print(f'{"=" * 50}')

    # 获取修改的文件
    changed = get_changed_files()
    if logger:
        logger.log_cycle_start(cycle_num, changed)

    # 1. 跑 preflight
    ok, output = run_preflight()
    if logger:
        logger.log_preflight_result(ok, output)

    if ok:
        print('[preflight] ✓ 通过')
        # 自动提交
        commit_ok = git_commit(f'agent自动验证通过 (cycle #{cycle_num})')
        if logger:
            logger.log_commit(commit_ok, f'agent自动验证通过 (cycle #{cycle_num})')
        if commit_ok:
            print('[commit] ✓ 已提交')

        duration = time.time() - cycle_start
        if health:
            health.record_activity(cycle_num, True)
        if stats:
            stats.record_cycle(True, duration)
        if logger:
            logger.log_cycle_end(cycle_num, True, duration)
        return True, auto_fix_count

    # 2. 失败 → Agent 修复
    print(f'[preflight] ✗ 失败 (attempt {auto_fix_count + 1}/{MAX_AUTO_FIX})')
    if auto_fix_count >= MAX_AUTO_FIX:
        print(f'[limit] Agent 修复次数已达上限 ({MAX_AUTO_FIX})，停止循环')
        git_stash(f'agent自动修复失败-超过上限{MAX_AUTO_FIX}次')
        if logger:
            logger.log_stash(f'agent自动修复失败-超过上限{MAX_AUTO_FIX}次')
        duration = time.time() - cycle_start
        if health:
            health.record_activity(cycle_num, False)
        if stats:
            stats.record_cycle(False, duration, auto_fix_count, 0)
        if logger:
            logger.log_cycle_end(cycle_num, False, duration)
        return False, auto_fix_count

    fix_ok, fix_output = agent_fix(output)
    if logger:
        logger.log_agent_fix(auto_fix_count + 1, fix_ok, fix_output)

    if not fix_ok:
        print('[agent-fix] ✗ Agent 修复失败')
        git_stash('agent修复执行失败')
        if logger:
            logger.log_stash('agent修复执行失败')
        duration = time.time() - cycle_start
        if health:
            health.record_activity(cycle_num, False)
        if stats:
            stats.record_cycle(False, duration, 1, 0)
        if logger:
            logger.log_cycle_end(cycle_num, False, duration)
        return False, auto_fix_count + 1

    # 3. 修复后再测
    ok2, output2 = run_preflight()
    if logger:
        logger.log_preflight_result(ok2, output2)

    if ok2:
        print('[retest] ✓ 修复后通过')
        commit_ok = git_commit(f'agent自动修复并验证通过 (cycle #{cycle_num})')
        if logger:
            logger.log_commit(commit_ok, f'agent自动修复并验证通过 (cycle #{cycle_num})')
        if commit_ok:
            print('[commit] ✓ 已提交')
        duration = time.time() - cycle_start
        if health:
            health.record_activity(cycle_num, True)
        if stats:
            stats.record_cycle(True, duration, 1, 1)
        if logger:
            logger.log_cycle_end(cycle_num, True, duration)
        return True, auto_fix_count + 1

    # 4. 修复后仍失败
    print('[retest] ✗ 修复后仍失败')
    git_stash('agent修复后仍失败-回退现场')
    if logger:
        logger.log_stash('agent修复后仍失败-回退现场')
    duration = time.time() - cycle_start
    if health:
        health.record_activity(cycle_num, False)
    if stats:
        stats.record_cycle(False, duration, 1, 0)
    if logger:
        logger.log_cycle_end(cycle_num, False, duration)
    return False, auto_fix_count + 1


def watch_mode(max_cycles=MAX_CYCLES):
    """文件监控模式：检测到变化自动触发验证"""
    # 初始化监控
    logger = LoopLogger()
    stats = LoopStats()
    health = HealthMonitor()

    print(f'[watch] 监控文件变化，最大循环 {max_cycles} 次')
    print(f'[watch] 监控扩展名: {WATCH_EXTS}')
    print(f'[watch] 冷却时间: {COOLDOWN_SECS}s')
    print(f'[watch] 健康状态: {health.get_status()}')
    print('[watch] 按 Ctrl+C 停止\n')

    last_mtimes = get_file_mtimes()
    cycle = 0
    auto_fix_count = 0
    last_cycle_time = 0

    try:
        while cycle < max_cycles:
            time.sleep(2)  # 2秒检查一次

            # 健康检查
            if health.is_stuck():
                print('\n[health] 检测到循环卡住，自动恢复...')
                health.reset()
                continue

            # 检测文件变化
            current_mtimes = get_file_mtimes()
            changed = []
            for f, mt in current_mtimes.items():
                if f not in last_mtimes or mt > last_mtimes[f]:
                    changed.append(f)

            if not changed:
                continue

            # 冷却检查
            now = time.time()
            if now - last_cycle_time < COOLDOWN_SECS:
                remaining = COOLDOWN_SECS - (now - last_cycle_time)
                print(f'[watch] 检测到变化: {", ".join(changed[:3])}，冷却中 ({remaining:.0f}s)')
                continue

            print(f'\n[watch] 检测到变化: {", ".join(changed[:5])}')
            cycle += 1
            last_cycle_time = now
            last_mtimes = current_mtimes

            success, auto_fix_count = verification_cycle(cycle, auto_fix_count, logger, stats, health)
            if not success:
                print(f'\n[loop] 循环终止，失败 {cycle} 次')
                break

            if cycle >= max_cycles:
                print(f'\n[loop] 达到最大循环次数 ({max_cycles})')
                break

    except KeyboardInterrupt:
        print('\n[watch] 用户中断')

    print(f'\n[summary] 完成 {cycle} 次循环，Agent 修复 {auto_fix_count} 次')
    print(f'[stats] {stats.summary()}')
    print(f'[health] {health.summary()}')


def continuous_mode(max_cycles=MAX_CYCLES):
    """连续循环模式：持续运行验证"""
    # 初始化监控
    logger = LoopLogger()
    stats = LoopStats()
    health = HealthMonitor()

    print(f'[continuous] 连续循环模式，最大 {max_cycles} 次')
    print(f'[continuous] 健康状态: {health.get_status()}')
    print('[continuous] 按 Ctrl+C 停止\n')

    cycle = 0
    auto_fix_count = 0

    try:
        while cycle < max_cycles:
            # 健康检查
            if health.is_stuck():
                print('\n[health] 检测到循环卡住，自动恢复...')
                health.reset()
                continue

            cycle += 1
            success, auto_fix_count = verification_cycle(cycle, auto_fix_count, logger, stats, health)

            if not success:
                print('\n[loop] 循环终止')
                break

            # 等待下一次循环
            print(f'\n[loop] 等待 {COOLDOWN_SECS}s 后继续...')
            time.sleep(COOLDOWN_SECS)

    except KeyboardInterrupt:
        print('\n[continuous] 用户中断')

    print(f'\n[summary] 完成 {cycle} 次循环，Agent 修复 {auto_fix_count} 次')
    print(f'[stats] {stats.summary()}')
    print(f'[health] {health.summary()}')


def show_status():
    """显示统计和健康状态"""
    logger = LoopLogger()
    stats = LoopStats()
    health = HealthMonitor()
    verifier = RollbackVerifier()

    print('=' * 50)
    print('  Agent 自主循环状态')
    print('=' * 50)

    # 统计
    print(f'\n[统计] {stats.summary()}')

    # 健康
    print(f'\n[健康] {health.summary()}')

    # 回滚状态
    rollback = verifier.verify_after_rollback()
    print(f'\n[回滚] 工作区干净: {rollback["clean"]}')
    if rollback['agent_stashes']:
        print(f'  待处理 stash: {len(rollback["agent_stashes"])}')
        for s in rollback['agent_stashes'][:3]:
            print(f'    - {s}')

    # 最近日志
    recent = logger.read_recent(5)
    if recent:
        print(f'\n[最近日志] (共{len(recent)}条)')
        for entry in recent:
            event = entry.get('event', '?')
            time_str = entry.get('time', '?')[:19]
            print(f'  {time_str} {event}')


def interactive_mode():
    """交互模式：手动触发验证"""
    print('[interactive] 交互模式')
    print('  命令: run / watch / status / quit')

    cycle = 0
    auto_fix_count = 0

    while True:
        try:
            cmd = input('\n> ').strip().lower()
        except (EOFError, KeyboardInterrupt):
            print('\n再见')
            break

        if cmd in ('quit', 'exit', 'q'):
            break
        elif cmd in ('run', 'r'):
            cycle += 1
            success, auto_fix_count = verification_cycle(cycle, auto_fix_count)
        elif cmd in ('watch', 'w'):
            watch_mode(max_cycles=5)
        elif cmd in ('status', 's'):
            show_status()
        elif cmd in ('help', 'h'):
            print('  run/r   - 运行一次验证')
            print('  watch/w - 启动文件监控')
            print('  status/s - 查看统计和健康状态')
            print('  quit/q  - 退出')
        else:
            print(f'未知命令: {cmd}，输入 help 查看帮助')


def main():
    parser = argparse.ArgumentParser(description='Agent 自主循环')
    parser.add_argument('--watch', action='store_true', help='文件监控模式')
    parser.add_argument('--continuous', action='store_true', help='连续循环模式')
    parser.add_argument('--status', action='store_true', help='查看统计和健康状态')
    parser.add_argument('--max-cycles', type=int, default=MAX_CYCLES, help='最大循环次数')
    args = parser.parse_args()

    if args.status:
        show_status()
    elif args.watch:
        watch_mode(args.max_cycles)
    elif args.continuous:
        continuous_mode(args.max_cycles)
    else:
        interactive_mode()


if __name__ == '__main__':
    main()
