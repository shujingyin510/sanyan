"""三言 Agent 多轮对话 — 上下文记忆 + 状态追踪

用法:    sanyan agent chat
         sanyan agent chat "第一轮问题"
"""

import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERSION = 'v3.36.0'


def _agent_ask(question: str, history: list) -> dict:
    """调用 AgentRuntime 单轮执行"""
    try:
        from agent_system.agent_runtime import AgentRuntime
        from evaluator import SanyanEvaluator

        e = SanyanEvaluator()
        rt = AgentRuntime(e, None)
        # 注入历史上下文
        if history:
            ctx = '\n'.join(
                f'[历史 {i + 1}] 用户: {h["q"][:200]}\nAgent: {str(h["a"])[:300]}' for i, h in enumerate(history[-5:])
            )
            question = f'{ctx}\n[当前] {question}'
        result = rt.run(question, max_rounds=10)
        return {
            'answer': result.get('answer', '(无回答)'),
            'ternary': result.get('ternary', ''),
            'memory': result.get('memory', {}),
        }
    except Exception as e:
        return {'answer': f'Agent 错误: {e}', 'ternary': '', 'memory': {}}


def run():
    from rich.console import Console
    from rich.panel import Panel
    from rich.markdown import Markdown

    console = Console(highlight=False)

    console.print()
    console.print(
        Panel(
            f'三言 Agent 多轮对话  {VERSION}\n\n'
            '输入问题开始对话。\n'
            '  [cyan]/exit[/]    退出\n'
            '  [cyan]/clear[/]  清空历史\n'
            '  [cyan]/status[/] 查看状态',
            title='Agent Chat',
            border_style='cyan',
            padding=(1, 2),
        )
    )
    console.print()

    history = []
    turn = 0

    while True:
        try:
            user_input = input('  [bold]你[/] > ').strip()
        except (EOFError, KeyboardInterrupt):
            console.print('\n[yellow]已退出[/]')
            break

        if not user_input:
            continue

        # 命令
        if user_input.startswith('/'):
            cmd = user_input[1:].strip().lower()
            if cmd in ('exit', 'quit', 'q'):
                break
            elif cmd == 'clear':
                history = []
                turn = 0
                console.print('  [dim]历史已清空[/]')
                continue
            elif cmd in ('status', 's'):
                console.print(f'  [dim]轮次: {turn} | 历史: {len(history)} 条[/]')
                continue
            else:
                console.print(f'  [yellow]未知命令: {cmd}[/]')
                continue

        turn += 1
        console.print()

        # Agent 处理
        with console.status(f'[cyan]思考中... (第{turn}轮)[/]', spinner='dots'):
            result = _agent_ask(user_input, history)

        answer = result.get('answer', '(无回答)')

        # 显示回答
        console.print(
            Panel(
                Markdown(str(answer)[:2000]),
                title=f'[bold cyan]Agent[/]  [dim]#{turn}[/]',
                border_style='cyan',
            )
        )

        # 状态行
        ternary = result.get('ternary', '')
        if ternary:
            console.print(f'  [dim]{ternary}[/]')
        console.print()

        # 保存历史
        history.append({'q': user_input, 'a': answer})


if __name__ == '__main__':
    run()
