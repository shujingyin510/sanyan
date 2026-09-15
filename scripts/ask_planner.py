#!/usr/bin/env python3
"""ask_planner.py — 规划咨询门客户端(Python 版,PowerShell 不可用时的等价入口)。

用法:
    python -X utf8 scripts/ask_planner.py "我计划做 X(文件清单/步骤/验收)"
    python -X utf8 scripts/ask_planner.py --no-wait "……"        # 只提交,拿 consultId
    python -X utf8 scripts/ask_planner.py --query <consultId>    # 稍后取答复
    python -X utf8 scripts/ask_planner.py --timeout 600 "……"    # 最长等 600 秒

安全约定(开源仓安全):
    - 本脚本**不含任何密钥**;令牌运行时从环境变量 DSH_PLANNER_TOKEN 或
      ~/.dsh-planner-token 读取,缺失即视为"顾问不可用"并优雅退出(返回 0)。
    - 咨询前先 GET /health 验明顾问身份(planner=dsh-local);验不过不采纳其意见。
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.request

BRIDGE = os.environ.get('DSH_PLANNER_BRIDGE', 'http://127.0.0.1:8790')
TOKEN_FILE = pathlib.Path(os.environ.get('DSH_PLANNER_TOKEN_FILE') or (pathlib.Path.home() / '.dsh-planner-token'))


def _token() -> str | None:
    """取共享令牌:环境变量优先,其次本地文件;都没有则返回 None。"""
    env = os.environ.get('DSH_PLANNER_TOKEN')
    if env and env.strip():
        return env.strip()
    try:
        text = TOKEN_FILE.read_text(encoding='utf-8').strip()
        return text or None
    except OSError:
        return None


def _request(path: str, method: str, token: str, payload: dict | None = None, timeout: float = 60.0):
    """带令牌的 JSON 请求。"""
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode('utf-8')
    req = urllib.request.Request(
        BRIDGE + path,
        data=data,
        headers={'Content-Type': 'application/json', 'X-Planner-Token': token},
        method=method,
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode('utf-8'))


def _print_answer(answer: str) -> None:
    """按统一格式打印顾问答复。"""
    print('===== 规划顾问答复 =====')
    print(answer)
    print('=========================')


def main() -> int:
    parser = argparse.ArgumentParser(description='向本地规划顾问(DSH 会话)咨询下一步计划')
    parser.add_argument('question', nargs='*', help='咨询内容')
    parser.add_argument('--timeout', type=int, default=300, help='最长等待秒数,默认 300')
    parser.add_argument('--no-wait', action='store_true', help='只提交,不等待')
    parser.add_argument('--query', help='按 consultId 查询已有咨询的答复')
    args = parser.parse_args()

    token = _token()
    if not token:
        print(f'规划顾问未配置(找不到 {TOKEN_FILE} 或 DSH_PLANNER_TOKEN)——跳过咨询,按原计划继续。')
        return 0

    # 验明顾问身份
    try:
        health = _request('/health', 'GET', token, timeout=10.0)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        print(f'规划顾问不可达({exc})——跳过咨询,按原计划继续。')
        return 0
    if health.get('planner') != 'dsh-local':
        print(f'8790 端口上的服务不是规划顾问(planner={health.get("planner")})——不采纳其意见。')
        return 0

    # 模式一:按 consultId 查询
    if args.query:
        try:
            r = _request(f'/consult/{args.query}', 'GET', token, timeout=30.0)
        except urllib.error.URLError as exc:
            print(f'查询失败:{exc}', file=sys.stderr)
            return 0
        if r.get('status') == 'answered':
            _print_answer(str(r.get('answer')))
            return 0
        waited = round(float(r.get('waitedMs', 0)) / 1000)
        print(f'状态: {r.get("status")}(consultId={r.get("consultId")},已等待 {waited} 秒)')
        if r.get('status') == 'pending':
            print(f'稍后再查: python -X utf8 scripts/ask_planner.py --query {r.get("consultId")}')
        return 0

    question = ' '.join(args.question).strip()
    if not question and not sys.stdin.isatty():
        question = sys.stdin.read().strip()
    if not question:
        print('没有收到问题。用法: python -X utf8 scripts/ask_planner.py "问题内容"', file=sys.stderr)
        return 2

    try:
        sub = _request('/consult', 'POST', token, {'question': question}, timeout=60.0)
    except urllib.error.URLError as exc:
        print(f'提交咨询失败({exc})——跳过咨询,按原计划继续。')
        return 0
    if not sub.get('ok'):
        print(f'提交失败: {sub.get("error")}')
        return 0

    consult_id = str(sub.get('consultId'))
    print(f'已提交咨询 consultId={consult_id},等待顾问答复(最多 {args.timeout} 秒)…')
    if args.no_wait:
        print(f'未等待。稍后取答复: python -X utf8 scripts/ask_planner.py --query {consult_id}')
        return 0

    deadline = time.monotonic() + args.timeout
    next_notice = time.monotonic() + 30
    while time.monotonic() < deadline:
        time.sleep(5)
        try:
            r = _request(f'/consult/{consult_id}', 'GET', token, timeout=30.0)
        except urllib.error.URLError:
            continue
        status = r.get('status')
        if status == 'answered':
            _print_answer(str(r.get('answer')))
            return 0
        if status in ('timeout', 'error'):
            print(f'顾问未能答复(status={status} {r.get("error") or ""})——按原计划继续。')
            return 0
        if time.monotonic() >= next_notice:
            waited = round(float(r.get('waitedMs', 0)) / 1000)
            print(f'  …顾问仍在处理(已等待 {waited} 秒)')
            next_notice = time.monotonic() + 30

    print(f'尚未收到答复(consultId={consult_id})。可继续做准备工作,稍后执行:')
    print(f'  python -X utf8 scripts/ask_planner.py --query {consult_id}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
