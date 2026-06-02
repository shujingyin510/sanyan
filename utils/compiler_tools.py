"""编译器工具探测：统一查找 gcc/llc/clang 等工具路径。

用法:
    from utils.compiler_tools import find_cc, find_llc, find_bash, run_in_shell
"""

from __future__ import annotations

import os
import subprocess
import sys


def find_cc() -> str | None:
    """查找可用的 C 编译器。返回路径或 None。

    优先级: CC 环境变量 > PATH > MSYS2_PATH 环境变量 > 硬编码路径
    """
    # 0. 环境变量直接指定
    for env_var in ('CC', 'GCC_PATH', 'SANYAN_CC'):
        cc_env = os.environ.get(env_var, '')
        if cc_env and os.path.exists(cc_env):
            return cc_env

    # 1. PATH 中查找
    for cc in ['gcc', 'clang', 'cc']:
        try:
            subprocess.run([cc, '--version'], capture_output=True, timeout=5, check=False)
            return cc
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue

    # 2. MSYS2_PATH 环境变量 + 自动探测 Windows MSYS2 路径
    if sys.platform == 'win32':
        base = os.environ.get('MSYS2_PATH', '')
        msys2_paths = []
        if base:
            msys2_paths = [
                os.path.join(base, 'mingw64', 'bin', 'gcc.exe'),
                os.path.join(base, 'ucrt64', 'bin', 'gcc.exe'),
            ]
        msys2_paths += [
            r'C:\msys64\mingw64\bin\gcc.exe',
            r'C:\msys64\ucrt64\bin\gcc.exe',
            r'D:\msys64\mingw64\bin\gcc.exe',
            r'D:\msys64\ucrt64\bin\gcc.exe',
        ]
        for p in msys2_paths:
            if os.path.exists(p):
                return p

    return None


def find_llc() -> str | None:
    """查找 llc 工具。返回路径或 None。

    优先级: LLC_PATH 环境变量 > PATH > MSYS2_PATH 环境变量 > 硬编码路径
    """
    # 0. 环境变量直接指定
    for env_var in ('LLC_PATH', 'SANYAN_LLC'):
        llc_env = os.environ.get(env_var, '')
        if llc_env and os.path.exists(llc_env):
            return llc_env

    # 1. PATH 中查找
    for llc in ['llc', 'llc.exe']:
        try:
            subprocess.run([llc, '--version'], capture_output=True, timeout=5, check=False)
            return llc
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue

    # 2. MSYS2_PATH 环境变量 + 自动探测
    if sys.platform == 'win32':
        base = os.environ.get('MSYS2_PATH', '')
        msys2_paths = []
        if base:
            msys2_paths = [
                os.path.join(base, 'ucrt64', 'bin', 'llc.exe'),
                os.path.join(base, 'mingw64', 'bin', 'llc.exe'),
            ]
        msys2_paths += [
            r'D:\msys64\ucrt64\bin\llc.exe',
            r'D:\msys64\mingw64\bin\llc.exe',
            r'C:\msys64\ucrt64\bin\llc.exe',
        ]
        for p in msys2_paths:
            if os.path.exists(p):
                return p

    return None


def find_bash() -> str | None:
    """查找 bash（优先级: BASH_PATH 环境变量 > MSYS2_PATH > PATH > 硬编码路径）。"""
    # 0. 环境变量
    for env_var in ('BASH_PATH', 'SANYAN_BASH'):
        bash_env = os.environ.get(env_var, '')
        if bash_env and os.path.exists(bash_env):
            return bash_env

    if sys.platform != 'win32':
        for bash in ['/bin/bash', '/usr/bin/bash']:
            if os.path.exists(bash):
                return bash
        return None

    # Windows: MSYS2_PATH 环境变量 + 自动探测
    base = os.environ.get('MSYS2_PATH', '')
    msys2_paths = []
    if base:
        msys2_paths = [os.path.join(base, 'usr', 'bin', 'bash.exe')]
    msys2_paths += [
        r'D:\msys64\usr\bin\bash.exe',
        r'C:\msys64\usr\bin\bash.exe',
    ]
    for p in msys2_paths:
        if os.path.exists(p):
            return p
    return None


def run_in_shell(cmd: str, timeout: int = 30, check: bool = True) -> subprocess.CompletedProcess:
    """跨平台执行命令。Windows 用 MSYS2 bash，Linux/macOS 直接执行。"""
    bash = find_bash()
    if bash:
        return subprocess.run(
            [bash, '-lc', cmd],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=check,
        )
    # Linux/macOS: 直接执行
    return subprocess.run(
        cmd,
        shell=True,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=check,
    )


def win_to_posix(path: str) -> str:
    """Windows 路径转 POSIX 格式（D:\\xxx → /d/xxx）。Linux/macOS 原样返回。"""
    if sys.platform != 'win32':
        return path
    p = path.replace('\\', '/')
    if len(p) >= 2 and p[1] == ':':
        p = '/' + p[0].lower() + p[2:]
    return p
