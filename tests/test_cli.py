"""sanyan 统一 CLI 测试 — 参数解析、版本一致性、rich 降级。

覆盖 sanyan/cli.py：命令模式解析、动态版本号（回归曾硬编码 v3.36.0）、
rich 缺失时的纯文本降级。子进程冒烟验证 --help / version 真能跑通。
"""

import io
import os
import sys
import subprocess
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sanyan import __version__
from sanyan import cli

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestCLIVersion(unittest.TestCase):
    """版本号必须跟随 sanyan.__version__，不得再硬编码。"""

    def test_version_is_dynamic(self):
        self.assertEqual(cli.VERSION, f'v{__version__}')

    def test_version_not_stale_literal(self):
        # 回归：cli.py 曾硬编码 VERSION = 'v3.36.0'，与真实版本脱节
        self.assertNotEqual(cli.VERSION, 'v3.36.0')

    def test_cmd_version_prints_current_version(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = cli.cmd_version(None)
        self.assertIn(__version__, buf.getvalue())
        self.assertIn(rc, (0, None))


class TestCLIParser(unittest.TestCase):
    """命令模式各子命令解析正确。"""

    def setUp(self):
        self.parser = cli._build_parser()

    def test_version_subcommand(self):
        self.assertEqual(self.parser.parse_args(['version']).command, 'version')

    def test_repl_subcommand(self):
        self.assertEqual(self.parser.parse_args(['repl']).command, 'repl')

    def test_compile_args(self):
        a = self.parser.parse_args(['compile', 'demo.san', '-o', 'out.bin'])
        self.assertEqual(a.command, 'compile')
        self.assertEqual(a.file, 'demo.san')
        self.assertEqual(a.output, 'out.bin')

    def test_run_args(self):
        a = self.parser.parse_args(['run', 'demo.san'])
        self.assertEqual(a.command, 'run')
        self.assertEqual(a.file, 'demo.san')

    def test_agent_run_args(self):
        a = self.parser.parse_args(['agent', 'run', '分析代码'])
        self.assertEqual(a.command, 'agent')
        self.assertEqual(a.agent_command, 'run')
        self.assertEqual(a.task, '分析代码')

    def test_package_install_args(self):
        a = self.parser.parse_args(['package', 'install', 'http_client'])
        self.assertEqual(a.command, 'package')
        self.assertEqual(a.package_command, 'install')
        self.assertEqual(a.name, 'http_client')

    def test_bench_flags(self):
        a = self.parser.parse_args(['bench', '--quick', '--type', 'safety'])
        self.assertEqual(a.command, 'bench')
        self.assertTrue(a.quick)
        self.assertEqual(a.type, 'safety')

    def test_bench_type_rejects_unknown(self):
        with self.assertRaises(SystemExit):
            self.parser.parse_args(['bench', '--type', '不存在'])


class TestPlainConsole(unittest.TestCase):
    """rich 缺失时的降级控制台：剥除 markup、正常换行。"""

    def test_strip_markup(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            cli._PlainConsole().print('[green]OK[/] done [bold cyan]x[/]')
        out = buf.getvalue()
        self.assertIn('OK', out)
        self.assertIn('done', out)
        for tag in ('[green]', '[/]', '[bold cyan]'):
            self.assertNotIn(tag, out)

    def test_empty_print_newline(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            cli._PlainConsole().print()
        self.assertEqual(buf.getvalue(), '\n')

    def test_console_is_printable(self):
        self.assertTrue(hasattr(cli._console(), 'print'))


class TestCLISubprocess(unittest.TestCase):
    """真起进程验证入口可跑通（不依赖 rich 是否安装）。"""

    def _run(self, *cli_args, timeout=60):
        # 子进程以 -X utf8 输出 UTF-8；显式按 UTF-8 解码，
        # 否则在 GBK locale 的 Windows（含 CI windows-latest）上 text=True 会解码崩溃
        return subprocess.run(
            [sys.executable, '-X', 'utf8', '-m', 'sanyan.cli', *cli_args],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=timeout,
        )

    def test_help_runs(self):
        r = self._run('--help')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('sanyan', r.stdout.lower())

    def test_version_subprocess_shows_version(self):
        r = self._run('version')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(__version__, r.stdout)


if __name__ == '__main__':
    unittest.main(verbosity=2)
