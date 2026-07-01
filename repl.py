"""REPL 交互环境与演示程序"""

import os
from typing import Any
from lexer import tokenize
from parser import parse

from sanyan import __version__ as VERSION
from evaluator import SanyanEvaluator
from sugar import SugarConverter
from skin import SkinManager
from runtime import BUILTIN_OPS
from ops.io_ops import IOOps

try:
    from colorama import init, Fore, Style

    init(autoreset=True)
    _COLOR = True
except ImportError:
    _COLOR = False


def _c(text: str, color: str = '') -> str:
    """简单着色包装。"""
    if not _COLOR:
        return text
    color_map = {
        'green': Fore.GREEN,
        'red': Fore.RED,
        'yellow': Fore.YELLOW,
        'blue': Fore.BLUE,
        'cyan': Fore.CYAN,
        'magenta': Fore.MAGENTA,
        'reset': Style.RESET_ALL,
    }
    return color_map.get(color, '') + text + Style.RESET_ALL  # type: ignore[no-any-return]


def _color_value(value) -> str:
    """根据值类型着色输出。"""
    try:
        from ternary_core import TritValue

        if value is None:
            return _c('无', 'cyan')
        if isinstance(value, TritValue):
            n = value.to_int()
            if n > 0:
                return _c(str(n), 'green')
            elif n < 0:
                return _c(str(n), 'red')
            else:
                return _c(str(n), 'yellow')
        if isinstance(value, str):
            return _c(repr(value), 'cyan')
        if isinstance(value, (int, float)):
            return _c(str(value), 'blue')
        if isinstance(value, list):
            return _c(f'[{len(value)} 项]', 'yellow')
        return str(value)
    except ImportError:
        return str(value)


# REPL 历史记录
_history_file = os.path.expanduser(os.path.join(os.path.expanduser('~'), '.sanyan_history'))
_state_file = os.path.expanduser(os.path.join(os.path.expanduser('~'), '.sanyan_state.json'))


# 加载 REPL 持久化状态（变量和命令）
def _load_state(env):
    """从文件恢复 REPL 状态（变量和命令定义）。"""
    if not os.path.exists(_state_file):
        return
    try:
        import json

        with open(_state_file, 'r', encoding='utf-8') as f:
            state = json.load(f)
        # 只恢复简单值（int/float/str），跳过函数和对象
        for k, v in state.get('vars', {}).items():
            try:
                from ternary_core import TritValue

                if isinstance(v, float) or (isinstance(v, int) and not isinstance(v, bool)):
                    env.set_var(k, TritValue(v))
                elif isinstance(v, str):
                    env.set_var(k, v)
            except Exception:
                pass
        print(f'[已恢复 {len(state.get("vars", {}))} 个变量]')
    except Exception:
        pass


def _save_state(env):
    """保存 REPL 状态到文件（仅保存简单值变量）。"""
    try:
        import json

        state: dict = {'vars': {}}
        for k, v in env.all_scoped_vars().items():
            if k.startswith('_'):
                continue
            from ternary_core import TritValue

            if isinstance(v, TritValue):
                if v.is_float():
                    state['vars'][k] = v.to_float()
                else:
                    state['vars'][k] = v.to_int()
            elif isinstance(v, (int, float)):
                state['vars'][k] = v
            elif isinstance(v, str) and len(v) < 1000:
                state['vars'][k] = v
        with open(_state_file, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


readline: Any = None
try:
    import readline as _rl

    readline = _rl
except ImportError:
    try:
        import pyreadline3 as readline  # type: ignore[no-redef]
    except ImportError:
        pass

if readline is not None:
    readline.set_history_length(1000)
    if os.path.exists(_history_file):
        readline.read_history_file(_history_file)


def demo(skin_mgr: SkinManager) -> None:
    print(f'\n========== 三言 v{VERSION} 演示 ==========')
    env = SanyanEvaluator(skin_manager=skin_mgr)

    # 1. 智能设备控制
    env.eval(['fn', '设置设备', ['对象', '状态'], ['context', '对象', '状态']])
    print('1. 智能设备控制')
    env.eval(['设置设备', '灯.亮'])
    env.eval(['query', '灯'])
    env.eval(['设置设备', '窗帘.关'])
    env.eval(['query', '窗帘'])

    # 2. 晚安模式
    print('\n2. 晚安模式（自定义命令）')
    env.eval(['fn', '晚安', [], ['do', ['设置设备', '灯.灭'], ['设置设备', '窗帘.关']]])
    env.eval(['晚安'])
    env.eval(['query', '灯'])
    env.eval(['query', '窗帘'])

    # 3. 数学运算与比较
    print('\n3. 数学运算与比较')
    env.eval(['set', 'a', 10])
    env.eval(['print', ['add', 'a', 5]])
    env.eval(['print', ['gt', 'a', 3]])

    # 4. 条件分支
    print('\n4. 条件分支')
    env.eval(['if', ['gt', 'a', 5], ['print', 1], ['print', 0]])

    # 5. 循环
    print('\n5. 循环')
    env.eval(['set', 'i', 0])
    env.eval(['loop', ['lt', 'i', 3], ['do', ['print', 'i'], ['set', 'i', ['add', 'i', 1]]]])

    # 6. 数学函数
    print('\n6. 数学函数')
    env.eval(['print', ['abs', -5]])
    env.eval(['print', ['sqrt', 81]])
    env.eval(['print', ['random', 1, 10]])

    # 7. 字符串拼接（注意字符串参数需要双引号）
    print('\n7. 字符串拼接')
    env.eval(['concat', '"你好"', '"世界"'])
    env.eval(['print', ['length', '"hello"']])

    print('========== 演示结束 ==========\n')


_BUILTIN_KEYWORDS = sorted(
    BUILTIN_OPS
    | {
        '再若',
        '否则',
        '真',
        '假',
        '可能',
        '开',
        '关',
        '守',
        '切换中文',
        '切换英文',
        '退出',
    }
)


def _make_completer(env):
    def completer(text, state):
        matches = []
        # 内置关键字
        for kw in _BUILTIN_KEYWORDS:
            if kw.startswith(text):
                matches.append(kw)
        # 当前变量名
        for name in env.all_scoped_vars():
            if name.startswith(text):
                matches.append(name)
        # 当前命令名
        for name in env.commands:
            if name.startswith(text):
                matches.append(name)
        # REPL 命令
        for cmd in [
            ':lang',
            ':maxloop',
            ':step',
            ':continue',
            ':break',
            ':unbreak',
            ':watch',
            ':unwatch',
            ':profile',
            ':types',
            ':help',
            'exit',
            '退出',
            '帮助',
        ]:
            if cmd.startswith(text):
                matches.append(cmd)
        matches.sort()
        if state < len(matches):
            return matches[state]
        return None

    return completer


def repl() -> None:
    skin_mgr = SkinManager('chinese')
    env = SanyanEvaluator(skin_manager=skin_mgr)

    # 设置自动补全
    if readline:
        readline.set_completer(_make_completer(env))
        readline.parse_and_bind('tab: complete')

    print(f'三言 v{VERSION} REPL (母语可定制)')
    print('输入 :lang english 切换英文，:lang chinese 切换中文')
    print('输入 :step 单步调试  :break <函数名> 添加断点  :watch <变量> 监视变量')
    print('输入 :profile 查看性能 :types 查看类型  exit/退出 离开，Tab 键自动补全')
    _load_state(env)  # 恢复上次会话的变量
    while True:
        try:
            code = input('三言> ').strip()
        except (KeyboardInterrupt, EOFError):
            print()
            break
        try:
            code = code.replace('\u3000', ' ')  # 全角空格 → 半角空格
            if not code:
                continue
            if code in ('（退出）', '退出', '（exit）', 'exit'):
                break
            if code in ('切换中文', '（切换中文）'):
                skin_mgr.switch_skin('chinese')
                print(f'皮肤已切换至 {skin_mgr.lang}')
                continue
            if code in ('切换英文', '（切换英文）'):
                skin_mgr.switch_skin('english')
                print(f'皮肤已切换至 {skin_mgr.lang}')
                continue
            if code.startswith(':maxloop'):
                parts = code.split()
                if len(parts) == 2 and parts[1].isdigit():
                    env.max_loop_steps = int(parts[1])
                    print(f'最大循环步数已设为: {env.max_loop_steps}')
                continue
            if code.startswith(':lang'):
                parts = code.split()
                if len(parts) == 2:
                    lang = parts[1]
                    if lang in ('chinese', 'english', '中文', '英文'):
                        skin_mgr.switch_skin(lang)
                        print(f'皮肤已切换至 {skin_mgr.lang}')
                    else:
                        print('支持的语言：chinese/中文, english/英文')
                continue
            if code == ':step':
                env.debug_mode = not env.debug_mode
                env._break_all = env.debug_mode
                print(f'单步模式: {"开" if env.debug_mode else "关"}')
                continue
            if code == ':continue' or code == ':c':
                env.debug_mode = False
                env._break_all = False
                print('调试模式: 关')
                continue
            if code.startswith(':break'):
                parts = code.split(maxsplit=1)
                if len(parts) == 2:
                    env.break_add(parts[1])
                    print(f'断点已添加: {parts[1]}')
                else:
                    print('用法: :break <函数名>')
                continue
            if code.startswith(':unbreak'):
                parts = code.split(maxsplit=1)
                if len(parts) == 2:
                    env.break_remove(parts[1])
                    print(f'断点已移除: {parts[1]}')
                continue
            if code.startswith(':watch'):
                parts = code.split(maxsplit=1)
                if len(parts) == 2:
                    env.watch_add(parts[1])
                    print(f'监视已添加: {parts[1]}')
                else:
                    print('用法: :watch <变量名>')
                continue
            if code.startswith(':unwatch'):
                parts = code.split(maxsplit=1)
                if len(parts) == 2:
                    env.watch_remove(parts[1])
                    print(f'监视已移除: {parts[1]}')
                continue
            if code == ':profile':
                if env._profiling:
                    print(env.profile_report())
                else:
                    env.profile_start()
                    print('性能追踪已开启')
                continue
            if code == ':types':
                type_env = env.type_env
                if type_env._scopes:
                    current_scope = type_env._scopes[-1]
                    if current_scope:
                        print('当前作用域类型:')
                        for name, type_name in current_scope.items():
                            print(f'  {name}: {type_env.format_type(type_name)}')
                    else:
                        print('当前作用域无变量')
                continue
            if code in (':help', '帮助'):
                print('可用命令:')
                print('  :lang <语言>      切换语言 (chinese/english)')
                print('  :maxloop <次数>   设置最大循环步数')
                print('  :step             切换单步调试模式')
                print('  :continue         继续执行')
                print('  :break <函数名>   添加断点')
                print('  :unbreak <函数名> 移除断点')
                print('  :watch <变量>     监视变量')
                print('  :unwatch <变量>   移除监视')
                print('  :profile          查看性能报告')
                print('  :types            查看当前作用域类型')
                print('  :help             显示此帮助')
                print('  exit/退出         退出 REPL')
                print()
                print('快捷键:')
                print('  Tab               自动补全')
                print('  Ctrl+C            中断当前操作')
                print('  Ctrl+D            退出 REPL')
                continue

            # 多行输入支持
            while True:
                if code.rstrip().endswith('{') or code.rstrip().endswith('（'):
                    pass
                else:
                    left_p = code.count('(') + code.count('（')
                    right_p = code.count(')') + code.count('）')
                    left_b = code.count('{')
                    right_b = code.count('}')
                    if left_p == right_p and left_b == right_b:
                        break
                try:
                    next_line = input('...   ').strip()
                except (KeyboardInterrupt, EOFError):
                    break
                if not next_line:
                    continue
                code += '\n' + next_line

            # 优先尝试糖语法，失败静默回退原生解析
            ast = None
            try:
                ast = SugarConverter.convert(code, skin_mgr)
            except SyntaxError:
                pass

            if ast is None:
                tokens = tokenize(code)
                if tokens:
                    try:
                        ast = parse(tokens)  # type: ignore[assignment]
                    except SyntaxError as e:
                        print(f'  语法错误: {e}')
                        continue

            if ast is None:
                continue

            env._source = code  # 设置源码用于错误信息显示
            result = env.eval(ast)

            if result is not None:
                should_print = True
                if isinstance(ast, list) and len(ast) > 0:
                    no_print_ops = (
                        'print',
                        'query',
                        '查',
                        '输出',
                        'if',
                        'loop',
                        'for',
                        'fn',
                        '定义',
                        'try',
                        '连接',
                        'concat',
                        '映射',
                        '过滤',
                        '归并',
                    )
                    if ast[0] in no_print_ops:
                        should_print = False
                    elif ast[0] == 'do' and len(ast) > 1:
                        last_stmt = ast[-1]
                        if isinstance(last_stmt, list) and len(last_stmt) > 0 and last_stmt[0] in no_print_ops:
                            should_print = False
                if should_print:
                    try:
                        formatted = IOOps.format_value(result)
                        colored = _color_value(result)
                        print(f'  => {colored}' if _COLOR else f'  => {formatted}')
                    except Exception:
                        print(f'  => {result}')
        except KeyboardInterrupt:
            print('\n  操作已中断。')
        except Exception as e:
            print(f'  {_c("错误", "red")}: {e}')
            print(f'    输入内容: {code}')

    # 保存历史记录
    if readline:
        try:
            readline.write_history_file(_history_file)
        except (IOError, OSError):
            pass
    _save_state(env)  # 保存当前变量到文件
