"""_run_reaped：超时杀整棵进程树、不被孙进程管道吊死。

P2 首跑实测事故的回归守护：agent 超时被杀后，它起的工具子进程（pytest）沦为
孤儿锁住 worktree，`git worktree remove` 吊死 30+ 分钟。timeout 必须落在整棵树上。
"""

import subprocess
import sys
import time

import pytest

from agent_system.self_update import _run_reaped


def test_reaped_normal_completion():
    r = _run_reaped(
        [sys.executable, '-c', 'print("ok")'],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert r.returncode == 0 and 'ok' in r.stdout


def test_reaped_timeout_kills_grandchild_and_returns_fast():
    # 子进程再起一个长睡孙进程且继承管道——旧实现里 communicate 会等孙进程的
    # 管道句柄关闭，超时形同虚设；杀树后必须快速返回。
    child_src = (
        'import subprocess, sys, time; '
        "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)']); "
        'time.sleep(120)'
    )
    t0 = time.time()
    with pytest.raises(subprocess.TimeoutExpired):
        _run_reaped(
            [sys.executable, '-c', child_src],
            capture_output=True,
            text=True,
            timeout=3,
        )
    assert time.time() - t0 < 60  # 旧实现会吊死到孙进程 120s 睡满
