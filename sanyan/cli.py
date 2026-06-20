"""三言统一 CLI — git/cargo 风格命令模式

配色: 深蓝主色 + 绿色成功 + 红色失败 + 黄色警告
"""

import sys
import os
import argparse
import subprocess as sp

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYTHON = sys.executable
UTF8 = '-X utf8'
VERSION = 'v3.36.0'

SYMBOL_OK = '[green]OK[/]'
SYMBOL_FAIL = '[red]FAIL[/]'
SYMBOL_RUN = '[cyan]>[/]'


def _console():
    from rich.console import Console

    return Console(highlight=False)


def _run_py(script, *args, timeout=300, label=''):
    c = _console()
    if label:
        c.print(f'  {SYMBOL_RUN} {label}...')
    cmd = [PYTHON, UTF8, script] + list(args)
    try:
        rc = sp.call(cmd, cwd=ROOT, timeout=timeout)
    except sp.TimeoutExpired:
        c.print(f'  {SYMBOL_FAIL} [red]超时[/] ({timeout}s)')
        return 1
    except KeyboardInterrupt:
        c.print('\n  [yellow]已取消[/]')
        return 130
    return rc


# ── Agent ──


def cmd_agent_run(args):
    from run_agent import main as agent_main

    sys.argv = ['run_agent.py', args.task]
    agent_main()


def cmd_agent_evolve(args):
    c = _console()
    c.print('\n[bold cyan]═══ Agent 自主改代码闭环 ═══[/]\n')
    rc = _run_py('run_agent.py', '--code-evolve')
    c.print(f'\n  {SYMBOL_OK if rc == 0 else SYMBOL_FAIL} 退出码: {rc}')
    return rc


def cmd_agent_auto_evolve(args):
    c = _console()
    c.print('\n[bold cyan]═══ 自动化进化闭环 ═══[/]\n')
    return _run_py('run_agent.py', '--auto-evolve')


def cmd_agent_validate(args):
    c = _console()
    c.print('\n[bold cyan]═══ 进化仿真验证 ═══[/]\n')
    return _run_py('run_agent.py', '--validate')


def cmd_agent_dashboard(args):
    c = _console()
    c.print('\n[bold cyan]═══ 进化仪表盘 TUI ═══[/]')
    c.print('  [dim]q 退出 | r 刷新[/]')
    from sanyan.dashboard_tui import run

    run()


def cmd_agent_chat(args):
    from sanyan.chat_tui import run

    run()


def cmd_agent_tui(args):
    from sanyan.tui import SanyanTUI

    SanyanTUI().run()


def cmd_bench(args):
    import sys as _sys

    _sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    c = _console()
    bench_type = args.type or 'safety'
    if bench_type == 'honesty':
        c.print('\n[bold cyan]═══ Agent 诚实度基准 ═══[/]\n')
        from benchmarks.honesty_bench import run_benchmark

        run_benchmark(quick=args.quick)
    elif bench_type == 'safety':
        c.print('\n[bold cyan]═══ Agent 安全基准测试 ═══[/]\n')
        from benchmarks.agent_bench import run_benchmark

        run_benchmark(quick=args.quick)
    else:
        c.print('\n[bold cyan]═══ Agent 全量基准测试 ═══[/]\n')
        from benchmarks.agent_bench import run_benchmark as run_safety
        from benchmarks.honesty_bench import run_benchmark as run_honesty

        run_safety(quick=args.quick)
        c.print()
        run_honesty(quick=args.quick)
    return 0


def cmd_agent_self_host(args):
    c = _console()
    c.print('\n[bold cyan]═══ 自举验证 ═══[/]\n')
    return _run_py('run_agent.py', '--self-host')


def cmd_agent_review_evolve(args):
    c = _console()
    c.print('\n[bold cyan]═══ 带审查进化闭环 ═══[/]\n')
    return _run_py('run_agent.py', '--review-evolve')


# ── 编译/运行 ──


def cmd_compile(args):
    out = args.output or args.file.replace('.san', '.bin')
    c = _console()
    c.print(f'  compile [cyan]{args.file}[/] → [cyan]{out}[/]')
    rc = _run_py('sanyanc.py', args.file, '-o', out)
    if rc == 0:
        size = os.path.getsize(os.path.join(ROOT, out)) if os.path.exists(out) else 0
        c.print(f'  {SYMBOL_OK} [green]{out}[/] ({size} 字节)')
    return rc


def cmd_run(args):
    c = _console()
    c.print(f'  run [cyan]{args.file}[/]')
    if args.file.endswith('.bin'):
        return _run_py('main.py', '--vm', args.file)
    return _run_py('main.py', args.file)


def cmd_repl(args):
    c = _console()
    c.print(f'\n[bold]三言 REPL[/]  [dim]{VERSION}[/]\n')
    return _run_py('main.py')


# ── 版本 ──


def cmd_version(args):
    from rich.table import Table
    from rich.panel import Panel

    c = _console()
    c.print()
    table = Table(show_header=False, box=None, padding=(0, 4))
    table.add_column(style='cyan')
    table.add_column(style='white')
    table.add_row('三言 Sanyan', VERSION)
    table.add_row('Python', sys.version.split()[0])
    table.add_row('GitHub', 'github.com/shujingyin510/sanyan')
    c.print(Panel(table, border_style='cyan'))
    c.print()


# ── 包管理 ──


def cmd_package_install(args):
    c = _console()
    c.print(f'  install [cyan]{args.name}[/]...')
    return _run_py('sanyanc.py', '--install', args.name)


def cmd_package_search(args):
    return _run_py('sanyanc.py', '--search', args.keyword)


def cmd_package_list(args):
    return _run_py('sanyanc.py', '--list')


# ── 主入口 ──


def _build_parser():
    # No-op: rich detects terminal

    parser = argparse.ArgumentParser(
        prog='sanyan',
        description='三言统一 CLI — 编程语言 + Agent + 工具链',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest='command', title='命令', metavar='')

    # Agent
    agent = sub.add_parser('agent', help='Agent 操作', description='三言 Agent — 认知运行时 + 自主进化')
    agent_sub = agent.add_subparsers(dest='agent_command', metavar='', title='Agent 子命令')
    p = agent_sub.add_parser('run', help='单次 Agent 提问')
    p.add_argument('task', help='任务描述')
    p = agent_sub.add_parser('evolve', help='Agent 自主改代码闭环')
    p = agent_sub.add_parser('auto-evolve', help='自动化进化闭环')
    p = agent_sub.add_parser('validate', help='进化仿真验证（100随机+收敛+Reviewer）')
    p = agent_sub.add_parser('dashboard', help='进化仪表盘')
    p = agent_sub.add_parser('chat', help='多轮对话')
    p = agent_sub.add_parser('tui', help='交互式终端面板（三栏布局）')
    p = agent_sub.add_parser('self-host', help='自举验证')
    p = agent_sub.add_parser('review-evolve', help='带审查的进化闭环')

    # 编译/运行
    p = sub.add_parser('compile', help='编译 .san → .bin')
    p.add_argument('file', help='源文件 (.san)')
    p.add_argument('-o', '--output', help='输出路径')
    p = sub.add_parser('run', help='运行 .san 或 .bin')
    p.add_argument('file', help='源文件或 .bin')
    sub.add_parser('repl', help='交互式 REPL')
    sub.add_parser('version', help='显示版本')

    # 基准测试
    p = sub.add_parser('bench', help='运行 Agent 基准测试（安全 + 诚实度）')
    p.add_argument('--quick', action='store_true', help='快速模式（各 10 题）')
    p.add_argument(
        '--type',
        choices=['safety', 'honesty', 'all'],
        default='all',
        help='测试类型: safety(安全) / honesty(诚实) / all(全量)',
    )

    # 包管理
    pkg = sub.add_parser('package', help='包管理', description='三言包管理器')
    pkg_sub = pkg.add_subparsers(dest='package_command', metavar='', title='包管理子命令')
    p = pkg_sub.add_parser('install', help='安装包')
    p.add_argument('name', help='包名')
    p = pkg_sub.add_parser('search', help='搜索包')
    p.add_argument('keyword', help='关键词')
    pkg_sub.add_parser('list', help='列出已安装')

    return parser


def main():
    parser = _build_parser()

    if len(sys.argv) == 1:
        from rich.console import Console
        from rich.panel import Panel

        c = Console(highlight=False)
        c.print()
        c.print(
            Panel(
                f'版本: {VERSION}\n'
                f'定位: 编程语言 + 认知运行时 + 自主进化 Agent\n\n'
                f'[bold]快速开始:[/]\n'
                f'  sanyan repl                 [dim]交互式 REPL[/]\n'
                f'  sanyan agent run "任务"     [dim]单次 Agent 提问[/]\n'
                f'  sanyan agent evolve        [dim]Agent 自主改代码闭环[/]\n'
                f'  sanyan agent chat          [dim]多轮对话[/]\n'
                f'  sanyan compile demo.san    [dim]编译 .san → .bin[/]\n'
                f'  sanyan --help              [dim]完整命令列表[/]',
                title='三言 Sanyan',
                border_style='cyan',
                padding=(1, 2),
            )
        )
        c.print()
        return 0

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    dispatch = {
        'agent': lambda a: {
            'run': cmd_agent_run,
            'evolve': cmd_agent_evolve,
            'auto-evolve': cmd_agent_auto_evolve,
            'validate': cmd_agent_validate,
            'dashboard': cmd_agent_dashboard,
            'self-host': cmd_agent_self_host,
            'review-evolve': cmd_agent_review_evolve,
            'chat': cmd_agent_chat,
        }[a.agent_command or 'run'](a),
        'bench': cmd_bench,
        'compile': cmd_compile,
        'run': cmd_run,
        'repl': cmd_repl,
        'version': cmd_version,
        'package': lambda a: {
            'install': cmd_package_install,
            'search': cmd_package_search,
            'list': cmd_package_list,
        }[a.package_command or 'list'](a),
    }
    return dispatch[args.command](args)


if __name__ == '__main__':
    main()
