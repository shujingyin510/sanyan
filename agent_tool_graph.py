"""工具依赖图 + 能力注册表
P1: ToolDependencyGraph — 工具链合法性预校验
P9: ToolCapabilityRegistry + TaskCapabilityExtractor — 能力匹配
"""

from typing import Optional

from typing import List, Set, Tuple


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
