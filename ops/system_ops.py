"""系统操作：命令执行、环境变量、路径"""

import os
import sys
import subprocess
from core.ternary_core import TritValue
from core.values import SanyanRuntimeError, SanyanSyntaxError
from ops.registry import register, register_alias

EXEC_TIMEOUT = 30


def _arg_str(evaluator, a) -> str:
    """字符串参数提取：sugar 解析产物的字面量**带引号**（如 '"NAME"'），必须经 eval
    去引号；裸原子（核心 S-式路径）直接用。曾因生取带引号名字，agent_policy.san 的
    环境变量("SANYAN_API_KEY") 永远取空、占位符密钥上位（密钥注入反模式当年正是
    给这个 bug 打的补丁）。"""
    if isinstance(a, str) and not (len(a) >= 2 and a[0] == '"' and a[-1] == '"'):
        return a
    return str(evaluator.eval(a))


def op_exec(evaluator, args):
    """执行(命令) — 执行系统命令并返回输出"""
    if not args:
        raise SanyanSyntaxError('执行 需要一个命令字符串')
    cmd = args[0] if isinstance(args[0], str) else str(evaluator.eval(args[0]))
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, errors='replace', timeout=EXEC_TIMEOUT)
        out = result.stdout or ''
        if result.returncode != 0:
            out += result.stderr or ''
        return out
    except subprocess.TimeoutExpired:
        raise SanyanRuntimeError('命令执行超时')
    except (OSError, ValueError) as e:
        raise SanyanRuntimeError(f'命令执行失败: {e}')


def op_getenv(evaluator, args):
    """环境变量(名) — 获取环境变量值"""
    if not args:
        raise SanyanSyntaxError('环境变量 需要一个变量名')
    name = _arg_str(evaluator, args[0])
    return os.environ.get(name, '')


def op_setenv(evaluator, args):
    """设环境变量(名, 值) — 设置环境变量"""
    if len(args) < 2:
        raise SanyanSyntaxError('设环境变量 需要 变量名 和 值')
    name = _arg_str(evaluator, args[0])
    val = _arg_str(evaluator, args[1])
    os.environ[name] = val
    return TritValue(0)


def op_cwd(evaluator, args):
    """当前路径() — 返回当前工作目录"""
    return os.getcwd()


def op_listdir(evaluator, args):
    """列出目录(路径) — 返回目录中的文件列表"""
    path = '.'
    if args:
        path = args[0] if isinstance(args[0], str) else str(evaluator.eval(args[0]))
    try:
        return os.listdir(path)
    except OSError as e:
        raise SanyanRuntimeError(f'列出目录失败: {e}')


def op_exists(evaluator, args):
    """存在?(路径) — 检查文件或目录是否存在"""
    if not args:
        return TritValue(0)
    val = evaluator.eval(args[0])
    path = str(val) if not isinstance(val, str) else val
    return TritValue(1 if os.path.exists(path) else 0)


def op_isfile(evaluator, args):
    """是文件?(路径) — 检查路径是否为文件"""
    if not args:
        return TritValue(0)
    val = evaluator.eval(args[0])
    path = str(val) if not isinstance(val, str) else val
    return TritValue(1 if os.path.isfile(path) else 0)


def op_isdir(evaluator, args):
    """是目录?(路径) — 检查路径是否为目录"""
    if not args:
        return TritValue(0)
    val = evaluator.eval(args[0])
    path = str(val) if not isinstance(val, str) else val
    return TritValue(1 if os.path.isdir(path) else 0)


def op_pid(evaluator, args):
    """进程号() — 返回当前进程 PID"""
    return TritValue(os.getpid())


def op_platform(evaluator, args):
    """平台() — 返回操作系统名"""
    return sys.platform


register('执行', op_exec)
register('环境变量', op_getenv)
register('设环境变量', op_setenv)
register('当前路径', op_cwd)
register('列出目录', op_listdir)
register('存在', op_exists)
register('是文件', op_isfile)
register('是目录', op_isdir)
register('进程号', op_pid)
register('平台', op_platform)

register_alias('exec', '执行')
register_alias('getenv', '环境变量')
register_alias('setenv', '设环境变量')
register_alias('cwd', '当前路径')
register_alias('listdir', '列出目录')
register_alias('exists', '存在')
register_alias('isfile', '是文件')
register_alias('isdir', '是目录')
register_alias('pid', '进程号')
register_alias('platform', '平台')
