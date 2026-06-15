"""工具依赖图 + 能力注册表 + 工具元数据 + 自发现
P1: ToolDependencyGraph — 工具链合法性预校验
P9: ToolCapabilityRegistry + TaskCapabilityExtractor — 能力匹配
P12: ToolMetadata — 工具元数据（参数类型、副作用、成本）
P13: ToolAutoDiscovery — 自动扫描 ops/*.py 注册工具
"""

import os
import glob as _glob
import re as _re
from typing import Any, Dict, List, Optional, Set, Tuple


class ToolDependencyGraph:
    """P1: 工具依赖图 — 校验工具链顺序合法性"""

    REQUIRES = {
        'analyze': ['read_file'],
        'replace_in_file': ['read_file'],
        'replace_all': ['read_file', 'search_code'],
        'write_file': ['read_file'],
        'run_test': [],
    }
    CONFLICTS = {
        ('write_file', 'dry_run'),
        ('replace_in_file', 'dry_run'),
    }

    def validate_chain(self, tools: List[str]) -> Tuple[bool, str]:
        """校验工具链：前置依赖是否满足，是否有冲突"""
        used: Set[str] = set()
        for t in tools:
            for req in self.REQUIRES.get(t, []):
                if req not in used:
                    return False, f'{t} 需要先执行 {req}'
            for a, b in self.CONFLICTS:
                if a in used and b == t:
                    return False, f'{t} 与 {a} 冲突'
            used.add(t)
        return True, ''

    def filter_valid(self, candidates: List[List[str]]) -> List[List[str]]:
        """过滤出合法的工具链"""
        return [c for c in candidates if self.validate_chain(c)[0]]

    def get_prerequisites(self, tool: str) -> List[str]:
        """获取工具的前置依赖"""
        return self.REQUIRES.get(tool, [])

    def would_conflict(self, used_tools: Set[str], candidate: str) -> bool:
        """检查候选工具是否与已用工具冲突"""
        for a, b in self.CONFLICTS:
            if a in used_tools and b == candidate:
                return True
            if b in used_tools and a == candidate:
                return True
        return False


class ToolCapabilityRegistry:
    """P9: 工具能力注册表 — 工具能做什么"""

    TOOLS = {
        'analyze': {'capabilities': ['code_analysis', 'file_read']},
        'find_symbol': {'capabilities': ['symbol_search']},
        'read_file': {'capabilities': ['file_read']},
        'search_code': {'capabilities': ['symbol_search', 'code_analysis']},
        'replace_in_file': {'capabilities': ['code_modify']},
        'replace_all': {'capabilities': ['code_modify', 'batch_modify']},
        'write_file': {'capabilities': ['code_modify', 'file_write']},
        'list_files': {'capabilities': ['file_read']},
        'run_test': {'capabilities': ['testing', 'verification']},
        'git_diff': {'capabilities': ['version_control']},
        'git_status': {'capabilities': ['version_control']},
    }

    def get_capabilities(self, tool: str) -> List[str]:
        """获取工具的能力列表"""
        return self.TOOLS.get(tool, {}).get('capabilities', [])

    def is_suitable(self, tool: str, required_caps: List[str]) -> bool:
        """工具是否满足能力需求"""
        tool_caps = set(self.get_capabilities(tool))
        return bool(tool_caps & set(required_caps))

    def find_tools_for_caps(self, caps: List[str]) -> List[str]:
        """找到满足能力需求的所有工具"""
        result = []
        for tool, info in self.TOOLS.items():
            tool_caps = set(info.get('capabilities', []))
            if tool_caps & set(caps):
                result.append(tool)
        return result


class TaskCapabilityExtractor:
    """P9: 从任务描述推断能力需求 — 零 LLM 开销"""

    CAPABILITY_KEYWORDS = {
        'symbol_search': ['找到', '搜索', '查找', '定位', '调用点', '引用', '谁调用', '在哪'],
        'code_analysis': ['分析', '理解', '查看结构', '代码审查', '函数', '多少行', '结构'],
        'code_modify': ['修改', '替换', '重构', '新建', '删除', '修复', '改', '写'],
        'testing': ['测试', '跑测试', '验证', 'pytest', '单元测试'],
        'version_control': ['git', '提交', '差异', 'diff', 'status'],
        'batch_modify': ['批量', '全部替换', '全局', '所有文件'],
    }

    def __init__(self, registry: Optional[ToolCapabilityRegistry] = None):
        self.registry = registry or ToolCapabilityRegistry()

    def extract(self, task: str) -> List[str]:
        """从任务描述提取所需能力"""
        caps = []
        for cap, keywords in self.CAPABILITY_KEYWORDS.items():
            if any(k in task for k in keywords):
                caps.append(cap)
        return caps or ['file_read']

    def validate_chain(self, task: str, tool_chain: List[str]) -> bool:
        """校验工具链是否满足任务能力需求"""
        need = set(self.extract(task))
        have = set()
        for t in tool_chain:
            have.update(self.registry.get_capabilities(t))
        return need.issubset(have)

    def suggest_tools(self, task: str) -> List[str]:
        """为任务推荐工具"""
        caps = self.extract(task)
        return self.registry.find_tools_for_caps(caps)


# ── P12: 工具元数据 ──


class ToolMetadata:
    """工具元数据：参数类型、副作用、成本、并行安全性"""

    def __init__(self):
        self._meta: Dict[str, Dict[str, Any]] = {}

    def register(
        self,
        name: str,
        params: List[str] = None,
        side_effects: List[str] = None,
        cost: float = 1.0,
        parallel_safe: bool = True,
        category: str = 'general',
    ):
        """注册工具元数据"""
        self._meta[name] = {
            'params': params or [],
            'side_effects': side_effects or [],
            'cost': cost,
            'parallel_safe': parallel_safe,
            'category': category,
        }

    def get(self, name: str) -> Dict[str, Any]:
        """获取工具元数据"""
        return self._meta.get(
            name,
            {
                'params': [],
                'side_effects': [],
                'cost': 1.0,
                'parallel_safe': True,
                'category': 'general',
            },
        )

    def is_parallel_safe(self, name: str) -> bool:
        """工具是否可以并行执行"""
        return self._meta.get(name, {}).get('parallel_safe', True)

    def get_parallel_group(self, tools: List[str]) -> List[List[str]]:
        """将工具分组：可并行的放一组"""
        groups: List[List[str]] = []
        current_group: List[str] = []
        for t in tools:
            meta = self.get(t)
            if meta.get('parallel_safe', True) and not meta.get('side_effects'):
                current_group.append(t)
            else:
                if current_group:
                    groups.append(current_group)
                    current_group = []
                groups.append([t])
        if current_group:
            groups.append(current_group)
        return groups

    def estimate_cost(self, tools: List[str]) -> float:
        """估算工具链总成本"""
        return sum(self.get(t).get('cost', 1.0) for t in tools)


# 预注册内置工具元数据
_BUILTIN_META = {
    'analyze': {'params': ['path'], 'side_effects': [], 'cost': 0.5, 'parallel_safe': True, 'category': 'read'},
    'find_symbol': {'params': ['name'], 'side_effects': [], 'cost': 0.5, 'parallel_safe': True, 'category': 'read'},
    'read_file': {
        'params': ['path', 'start', 'count'],
        'side_effects': [],
        'cost': 0.3,
        'parallel_safe': True,
        'category': 'read',
    },
    'search_code': {'params': ['keyword'], 'side_effects': [], 'cost': 0.5, 'parallel_safe': True, 'category': 'read'},
    'list_files': {'params': ['pattern'], 'side_effects': [], 'cost': 0.2, 'parallel_safe': True, 'category': 'read'},
    'replace_in_file': {
        'params': ['path', 'old', 'new'],
        'side_effects': ['file_write'],
        'cost': 1.0,
        'parallel_safe': False,
        'category': 'write',
    },
    'replace_all': {
        'params': ['pattern', 'old', 'new'],
        'side_effects': ['file_write'],
        'cost': 2.0,
        'parallel_safe': False,
        'category': 'write',
    },
    'write_file': {
        'params': ['path', 'content'],
        'side_effects': ['file_write'],
        'cost': 1.0,
        'parallel_safe': False,
        'category': 'write',
    },
    'run_test': {
        'params': ['test_file'],
        'side_effects': ['subprocess'],
        'cost': 2.0,
        'parallel_safe': True,
        'category': 'test',
    },
    'git_diff': {'params': [], 'side_effects': ['subprocess'], 'cost': 0.3, 'parallel_safe': True, 'category': 'vcs'},
    'git_status': {'params': [], 'side_effects': ['subprocess'], 'cost': 0.2, 'parallel_safe': True, 'category': 'vcs'},
    'git_stash': {
        'params': [],
        'side_effects': ['subprocess', 'file_write'],
        'cost': 0.5,
        'parallel_safe': False,
        'category': 'vcs',
    },
    'git_reset_hard': {
        'params': [],
        'side_effects': ['subprocess', 'file_write'],
        'cost': 1.0,
        'parallel_safe': False,
        'category': 'vcs',
    },
    'git_commit_auto': {
        'params': ['msg'],
        'side_effects': ['subprocess', 'file_write'],
        'cost': 0.5,
        'parallel_safe': False,
        'category': 'vcs',
    },
    'done': {'params': ['answer'], 'side_effects': [], 'cost': 0.1, 'parallel_safe': True, 'category': 'control'},
}

DEFAULT_TOOL_META = ToolMetadata()
for _name, _info in _BUILTIN_META.items():
    DEFAULT_TOOL_META.register(_name, **_info)


# ── P13: 工具自发现 ──


class ToolAutoDiscovery:
    """自动扫描 ops/*.py 注册工具，提取函数签名"""

    IGNORE_PATTERNS = {'__pycache__', '.pyc', '__init__'}

    def __init__(self, ops_dir: str = 'ops'):
        self.ops_dir = ops_dir
        self._discovered: Dict[str, Dict[str, Any]] = {}

    def scan(self) -> Dict[str, Dict[str, Any]]:
        """扫描 ops/*.py，提取 def 函数和 register 调用"""
        if self._discovered:
            return self._discovered

        ops_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), self.ops_dir)
        if not os.path.isdir(ops_path):
            return self._discovered

        for fp in _glob.glob(os.path.join(ops_path, '*.py')):
            basename = os.path.basename(fp)
            if any(p in basename for p in self.IGNORE_PATTERNS):
                continue
            try:
                with open(fp, encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                self._extract_from_file(fp, content)
            except Exception:
                pass
        return self._discovered

    def _extract_from_file(self, fp: str, content: str):
        """从单个文件提取工具注册信息"""
        module = os.path.basename(fp).replace('.py', '')

        # 匹配 register('name', func) 或 _ra('name', 'target')
        register_pattern = _re.compile(r"""register\(\s*['"]([^'"]+)['"]|_ra\(\s*['"]([^'"]+)['"]""")
        for m in register_pattern.finditer(content):
            name = m.group(1) or m.group(2)
            if name and name not in self._discovered:
                self._discovered[name] = {
                    'source': fp,
                    'module': module,
                    'category': self._infer_category(module),
                }

        # 匹配 def 函数定义
        func_pattern = _re.compile(r'def\s+(_?\w+)\s*\(')
        for m in func_pattern.finditer(content):
            fname = m.group(1)
            if fname.startswith('_') and not fname.startswith('__'):
                # 内部函数，跳过
                continue
            if fname not in self._discovered:
                self._discovered[fname] = {
                    'source': fp,
                    'module': module,
                    'category': self._infer_category(module),
                }

    def _infer_category(self, module_name: str) -> str:
        """从模块名推断类别"""
        category_map = {
            'arithmetic': 'math',
            'math_funcs': 'math',
            'math_extra': 'math',
            'comparison': 'logic',
            'logic': 'logic',
            'string': 'string',
            'unicode': 'string',
            'list': 'container',
            'dict': 'container',
            'file': 'io',
            'io': 'io',
            'net': 'network',
            'http': 'network',
            'json': 'data',
            'csv': 'data',
            'regex': 'data',
            'time': 'system',
            'random': 'system',
            'crypto': 'security',
            'sandbox': 'security',
            'concurrent': 'concurrency',
            'iot': 'iot',
            'device': 'iot',
            'type': 'type',
            'control': 'control',
            'package': 'package',
        }
        for key, cat in category_map.items():
            if key in module_name:
                return cat
        return 'general'

    def get_tools(self) -> Dict[str, Dict[str, Any]]:
        """获取发现的工具"""
        return self.scan()

    def get_tools_by_category(self, category: str) -> List[str]:
        """按类别获取工具"""
        return [name for name, info in self._discovered.items() if info.get('category') == category]
