"""安全沙箱增强 — 权限控制 + 命令过滤 + 文件系统隔离
P16: AgentSandbox — 细粒度权限控制
P17: CommandFilter — 命令黑名单/白名单
P18: FileSystemGuard — 文件系统访问守卫
"""

import os
import fnmatch
from typing import Any, Dict, List, Set


class CommandFilter:
    """命令过滤器：黑名单/白名单"""

    DEFAULT_BLACKLIST = [
        'rm -rf',
        'rm -r /',
        'del /f',
        'format',
        'mkfs',
        'DROP TABLE',
        'DELETE FROM',
        'TRUNCATE',
        'sudo',
        'su -',
        'chmod 777',
        'chown',
        '> /dev/sda',
        'dd if=',
        ':(){',
        'fork',
        '$(',
        '`',
        '${',
        '%(',
        'eval(',
        'exec(',
        'os.system',
        'subprocess.call',
        '__import__',
    ]

    DEFAULT_WHITELIST = [
        'python',
        'pip',
        'git',
        'ls',
        'cat',
        'head',
        'tail',
        'grep',
        'find',
        'wc',
        'echo',
        'mkdir',
        'touch',
        'cp',
        'mv',
    ]

    def __init__(self):
        self.blacklist = list(self.DEFAULT_BLACKLIST)
        self.whitelist = list(self.DEFAULT_WHITELIST)
        self._custom_blacklist: List[str] = []
        self._custom_whitelist: List[str] = []

    def add_blacklist(self, pattern: str):
        """添加黑名单模式"""
        self._custom_blacklist.append(pattern)

    def add_whitelist(self, pattern: str):
        """添加白名单模式"""
        self._custom_whitelist.append(pattern)

    def check(self, command: str) -> tuple[bool, str]:
        """检查命令是否安全，返回 (是否安全, 原因)"""
        cmd_lower = command.lower().strip()

        # 自定义黑名单优先
        for pattern in self._custom_blacklist:
            if pattern.lower() in cmd_lower:
                return False, f'自定义黑名单匹配: {pattern}'

        # 默认黑名单
        for pattern in self.blacklist:
            if pattern.lower() in cmd_lower:
                return False, f'黑名单匹配: {pattern}'

        return True, ''


class FileSystemGuard:
    """文件系统访问守卫：路径白名单 + 深度限制"""

    def __init__(self, allowed_roots: List[str] = None, blocked_patterns: List[str] = None, max_depth: int = 10):
        self.allowed_roots = allowed_roots or [os.getcwd()]
        self.blocked_patterns = blocked_patterns or [
            '*.env',
            '*.key',
            '*.pem',
            '*.p12',
            'credentials.*',
            'secrets.*',
            '/etc/passwd',
            '/etc/shadow',
        ]
        self.max_depth = max_depth
        self._modified_files: Set[str] = set()

    def check_read(self, path: str) -> tuple[bool, str]:
        """检查读取权限"""
        abs_path = os.path.abspath(path)

        # 检查深度
        depth = abs_path.count(os.sep)
        if depth > self.max_depth:
            return False, f'路径深度超限: {depth} > {self.max_depth}'

        # 检查模式
        for pattern in self.blocked_patterns:
            if fnmatch.fnmatch(os.path.basename(abs_path), pattern):
                return False, f'禁止访问: {pattern}'

        return True, ''

    def check_write(self, path: str) -> tuple[bool, str]:
        """检查写入权限"""
        abs_path = os.path.abspath(path)

        # 检查是否在允许的根目录下
        in_allowed = False
        for root in self.allowed_roots:
            try:
                if os.path.commonpath([abs_path, root]) == root:
                    in_allowed = True
                    break
            except ValueError:
                pass

        if not in_allowed:
            return False, f'写入路径不在允许范围内: {abs_path}'

        # 检查模式
        for pattern in self.blocked_patterns:
            if fnmatch.fnmatch(os.path.basename(abs_path), pattern):
                return False, f'禁止写入: {pattern}'

        return True, ''

    def record_modified(self, path: str):
        """记录修改的文件"""
        self._modified_files.add(os.path.abspath(path))

    def get_modified_files(self) -> List[str]:
        """获取修改过的文件列表"""
        return list(self._modified_files)

    def reset(self):
        """重置修改记录"""
        self._modified_files.clear()


class AgentSandbox:
    """Agent 沙箱：统一权限控制"""

    def __init__(self, allowed_roots: List[str] = None, read_only: bool = False, network_allowed: bool = True):
        self.command_filter = CommandFilter()
        self.fs_guard = FileSystemGuard(allowed_roots=allowed_roots)
        self.read_only = read_only
        self.network_allowed = network_allowed
        self._audit_log: List[Dict[str, Any]] = []

    def check_tool(self, tool: str, params: str, dry_run: bool = False) -> tuple[bool, str]:
        """检查工具调用是否安全"""
        # 干跑模式下所有写操作都安全
        if dry_run:
            return True, ''

        # 读操作检查
        read_tools = {'analyze', 'find_symbol', 'read_file', 'search_code', 'list_files', 'git_diff', 'git_status'}
        if tool in read_tools:
            return True, ''

        # 写操作检查
        write_tools = {'write_file', 'replace_in_file', 'replace_all'}
        if tool in write_tools:
            if self.read_only:
                return False, '沙箱处于只读模式'
            # 提取文件路径
            parts = str(params).split('|')
            if parts:
                path = parts[0].strip()
                ok, reason = self.fs_guard.check_write(path)
                if not ok:
                    return False, reason

        # Git 操作检查
        if tool.startswith('git_'):
            ok, reason = self.command_filter.check(f'git {params}')
            if not ok:
                return False, reason

        # 网络操作检查
        if tool in ('http_request', 'net_request') and not self.network_allowed:
            return False, '网络访问被禁用'

        return True, ''

    def audit(self, tool: str, params: str, result: str, allowed: bool):
        """审计日志"""
        self._audit_log.append(
            {
                'tool': tool,
                'params': str(params)[:200],
                'result': str(result)[:200],
                'allowed': allowed,
            }
        )

    def get_audit_log(self, limit: int = 50) -> List[Dict[str, Any]]:
        """获取审计日志"""
        return self._audit_log[-limit:]

    def summary(self) -> str:
        """沙箱状态摘要"""
        total = len(self._audit_log)
        blocked = sum(1 for e in self._audit_log if not e['allowed'])
        modified = len(self.fs_guard.get_modified_files())
        return f'审计: {total}次操作, {blocked}次拦截, {modified}个文件修改'
