"""系统操作：命令执行、环境变量、路径"""

import os
import sys
import subprocess
from ternary_core import TritValue
from values import SanyanRuntimeError, SanyanSyntaxError
from ops.registry import register, register_alias


def op_exec(evaluator, args):
    """执行(命令) — 执行系统命令并返回输出"""
    if not args:
        raise SanyanSyntaxError('执行 需要一个命令字符串')
    cmd = args[0] if isinstance(args[0], str) else str(evaluator.eval(args[0]))
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        out = result.stdout
        if result.returncode != 0:
            out += result.stderr
        return out
    except subprocess.TimeoutExpired:
        raise SanyanRuntimeError('命令执行超时')
    except Exception as e:
        raise SanyanRuntimeError(f'命令执行失败: {e}')


def op_getenv(evaluator, args):
    """环境变量(名) — 获取环境变量值"""
    if not args:
        raise SanyanSyntaxError('环境变量 需要一个变量名')
    name = args[0] if isinstance(args[0], str) else str(evaluator.eval(args[0]))
    return os.environ.get(name, '')


def op_setenv(evaluator, args):
    """设环境变量(名, 值) — 设置环境变量"""
    if len(args) < 2:
        raise SanyanSyntaxError('设环境变量 需要 变量名 和 值')
    name = args[0] if isinstance(args[0], str) else str(evaluator.eval(args[0]))
    val = args[1] if isinstance(args[1], str) else str(evaluator.eval(args[1]))
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
    except Exception as e:
        raise SanyanRuntimeError(f'列出目录失败: {e}')


def op_exists(evaluator, args):
    """存在?(路径) — 检查文件或目录是否存在"""
    if not args:
        return TritValue(0)
    path = args[0] if isinstance(args[0], str) else str(evaluator.eval(args[0]))
    return TritValue(1 if os.path.exists(path) else 0)


def op_isfile(evaluator, args):
    """是文件?(路径) — 检查路径是否为文件"""
    if not args:
        return TritValue(0)
    path = args[0] if isinstance(args[0], str) else str(evaluator.eval(args[0]))
    return TritValue(1 if os.path.isfile(path) else 0)


def op_isdir(evaluator, args):
    """是目录?(路径) — 检查路径是否为目录"""
    if not args:
        return TritValue(0)
    path = args[0] if isinstance(args[0], str) else str(evaluator.eval(args[0]))
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
