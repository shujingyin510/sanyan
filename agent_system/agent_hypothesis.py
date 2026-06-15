"""Phase 1: 多假设引擎 — 多样性控制 + 锦标赛 + 失败分类 + 自适应阈值
P2: 并行早停
P3: FailureMode + FailureClassifier
P4: ThresholdTuner
P8: DiversityController
"""

import time
from enum import Enum
from typing import Any, Callable, Dict, List, Tuple, Optional


# ── P3: 失败模式分类 ──


class FailureMode(Enum):
    SUCCESS = 'ok'
    EMPTY_RESULT = 'empty'
    TOOL_MISSING = 'missing'
    SCHEMA_ERROR = 'schema'
    TIMEOUT = 'timeout'
    LOGIC_ERROR = 'logic'
    LOGIC_LOOP = 'loop'
    UNKNOWN = 'unknown'


RETRY_STRATEGY = {
    FailureMode.EMPTY_RESULT: '换query或换工具',
    FailureMode.TOOL_MISSING: '从链中移除，替换等价工具',
    FailureMode.SCHEMA_ERROR: '修正参数后重试',
    FailureMode.TIMEOUT: '降级（拆任务）或跳过',
    FailureMode.LOGIC_ERROR: '换假设/换推理路径',
    FailureMode.LOGIC_LOOP: '熔断+换路径',
    FailureMode.UNKNOWN: '默认按LOGIC_ERROR处理',
}


class FailureClassifier:
    """P3: 失败模式分类器 — 区分6类失败"""

    def __init__(self):
        self._tool_history: Dict[str, List[str]] = {}

    def classify(self, tool: str, args: Any, result: Any) -> FailureMode:
        """分类工具执行结果"""
        result_str = str(result).lower() if result else ''

        if not result or result_str == '':
            return FailureMode.EMPTY_RESULT

        if 'not found' in result_str or '未找到' in result_str:
            return FailureMode.TOOL_MISSING

        if 'missing' in result_str or '格式' in result_str or '参数' in result_str:
            return FailureMode.SCHEMA_ERROR

        if 'timeout' in result_str or '超时' in result_str:
            return FailureMode.TIMEOUT

        if self._looks_logically_wrong(tool, result):
            return FailureMode.LOGIC_ERROR

        if self._detect_loop(tool, result):
            return FailureMode.LOGIC_LOOP

        if 'error' in result_str or '错误' in result_str or '失败' in result_str:
            return FailureMode.LOGIC_ERROR

        return FailureMode.SUCCESS

    def _looks_logically_wrong(self, tool: str, result: Any) -> bool:
        """检测逻辑错误：工具成功但结果不合理"""
        result_str = str(result)
        if tool == 'run_test' and ('FAIL' in result_str or '失败' in result_str):
            return True
        if tool in ('replace_in_file', 'replace_all') and '未找到' in result_str:
            return True
        if tool == 'analyze' and '错误' in result_str:
            return True
        return False

    def _detect_loop(self, tool: str, result: Any) -> bool:
        """检测循环：同一工具+相同结果连续出现3次"""
        key = f'{tool}:{str(result)[:50]}'
        if tool not in self._tool_history:
            self._tool_history[tool] = []
        history = self._tool_history[tool]
        history.append(key)
        if len(history) >= 3:
            if history[-1] == history[-2] == history[-3]:
                return True
        return False


# ── P8: 多样性控制 ──


class DiversityController:
    """P8: 假设多样性控制器 — 简单关键词去重"""

    SIMILARITY_THRESHOLD = 0.85

    def filter(self, hypotheses: list) -> list:
        """去重：相似假设只保留置信度最高的"""
        if len(hypotheses) <= 1:
            return hypotheses
        clusters: List[Dict] = []
        for h in hypotheses:
            keywords = set(h.description.lower().split())
            matched = False
            for cluster in clusters:
                overlap = len(keywords & cluster['keywords'])
                total = len(keywords | cluster['keywords'])
                if total > 0 and overlap / total > self.SIMILARITY_THRESHOLD:
                    cluster['members'].append(h)
                    matched = True
                    break
            if not matched:
                clusters.append({'keywords': keywords, 'members': [h]})
        return [max(c['members'], key=lambda x: x.confidence) for c in clusters]


# ── P4: 自适应阈值 ──


class ThresholdTuner:
    """P4: 自适应阈值 — 从历史数据自动调参"""

    def __init__(self, history_path: str = '.tournament_history.jsonl'):
        self.history: List[Dict] = []
        self.history_path = history_path
        self.default_confidence_gap = 0.3
        self.default_step_gap = 2
        self.default_collapse_threshold = 0.8

    def record_round(self, log_entry: Dict):
        """记录一轮锦标赛结果"""
        self.history.append(log_entry)

    def fit(self) -> Dict[str, float]:
        """每50轮重训，返回调整后的阈值"""
        if len(self.history) < 20:
            return {
                'confidence_gap': self.default_confidence_gap,
                'step_gap': self.default_step_gap,
                'collapse_threshold': self.default_collapse_threshold,
            }

        # 找 LLM 判断与规则判断不一致的轮次
        disagreements = [e for e in self.history if e.get('method') == 'llm' and e.get('rule_wrong')]

        if not disagreements:
            return {
                'confidence_gap': self.default_confidence_gap,
                'step_gap': self.default_step_gap,
                'collapse_threshold': self.default_collapse_threshold,
            }

        # 用不一致轮次的中位数更新阈值
        gaps = [abs(e.get('a_conf', 0) - e.get('b_conf', 0)) for e in disagreements]
        new_gap = max(0.1, sorted(gaps)[len(gaps) // 2] * 0.9) if gaps else self.default_confidence_gap

        return {
            'confidence_gap': new_gap,
            'step_gap': self.default_step_gap,
            'collapse_threshold': max(0.5, min(0.95, new_gap + 0.5)),
        }


# ── 假设 ──


class Hypothesis:
    """单个假设：方案描述 + 置信度 + 工具链 + 状态"""

    __slots__ = (
        'id',
        'description',
        'confidence',
        'trit',
        'tools_used',
        'evidence',
        'status',
        'estimated_cost',
        'created_at',
        'last_updated',
    )

    def __init__(self, hid: int, description: str, estimated_cost: float = 0, tools_used: Optional[List[str]] = None):
        self.id = hid
        self.description = description
        self.confidence = 0.5
        self.trit = 0
        self.tools_used: List[str] = tools_used if tools_used is not None else []
        self.evidence: List[Dict[str, Any]] = []
        self.status = 'pending'
        self.estimated_cost = estimated_cost
        self.created_at = time.time()
        self.last_updated = time.time()

    def update(self, tool: str, result: str, trit: int, conf: float, failure_mode: FailureMode = FailureMode.SUCCESS):
        """更新假设：记录工具结果，传播置信度"""
        self.tools_used.append(tool)
        self.evidence.append(
            {
                'tool': tool,
                'result': str(result)[:200],
                'trit': trit,
                'conf': conf,
                'mode': failure_mode,
                'time': time.time(),
            }
        )
        self.trit = trit
        self.confidence = min(0.99, max(0.01, self.confidence * conf))
        self.last_updated = time.time()

    def collapse_score(self) -> float:
        if not self.evidence:
            return 0.0
        recent = self.evidence[-3:]
        pos_count = sum(1 for e in recent if e['trit'] == 1)
        consistency = pos_count / len(recent) if recent else 0.5
        return self.confidence * consistency

    def is_dead(self, early_death_threshold: float = 0.2) -> bool:
        if self.confidence < early_death_threshold:
            return True
        if len(self.evidence) >= 3:
            recent_fail = sum(1 for e in self.evidence[-3:] if e['trit'] == -1)
            if recent_fail >= 2:
                return True
        return False

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'description': self.description,
            'confidence': round(self.confidence, 3),
            'trit': self.trit,
            'status': self.status,
            'tools': self.tools_used,
            'evidence_count': len(self.evidence),
            'cost': self.estimated_cost,
        }


# ── 假设生成器 ──


class HypothesisGenerator:
    """假设生成器：LLM生成 + 依赖图过滤 + 能力匹配 + 多样性去重"""

    DEFAULT_COUNT = 5

    def __init__(self, tool_graph=None, cap_registry=None):
        from agent_system.agent_tool_graph import ToolDependencyGraph, ToolCapabilityRegistry, TaskCapabilityExtractor

        self.tool_graph = tool_graph or ToolDependencyGraph()
        self.cap_registry = cap_registry or ToolCapabilityRegistry()
        self.cap_extractor = TaskCapabilityExtractor(self.cap_registry)
        self.diversity = DiversityController()
        self._next_id = 0

    def generate(
        self, llm_fn: Callable, task: str, context: Any, experience: Any = None, count: int = 5
    ) -> List[Hypothesis]:
        """生成假设：LLM → 过滤 → 构建 → 去重"""
        # 1. LLM 生成原始方案
        plans = self._llm_generate(llm_fn, task, context, count)
        # 2. P1: 依赖图过滤
        plans = self._filter_by_dependency(plans)
        # 3. P9: 能力匹配过滤
        plans = self._filter_by_capability(task, plans)
        # 4. 构建 Hypothesis
        hyps = [self._build_hypothesis(p) for p in plans]
        # 5. P8: 多样性去重
        hyps = self.diversity.filter(hyps)
        return hyps[:3]

    _KNOWN_TOOLS = {
        'analyze',
        'find_symbol',
        'read_file',
        'search_code',
        'replace_in_file',
        'replace_all',
        'write_file',
        'list_files',
        'run_test',
        'git_diff',
        'git_status',
        'git_stash',
        'git_reset_hard',
        'git_commit_auto',
        'done',
    }

    def _llm_generate(self, llm_fn, task, context, count) -> List[Dict]:
        """用 LLM 生成多个方案"""
        prompt = (
            f'你是三言编程助手，需要为以下任务设计{count}个不同的解法方案。\n'
            f'每个方案一行，格式严格为：方案简述 | 工具1,工具2(逗号分隔)\n'
            f'\n'
            f'任务: {task}\n'
            f'\n'
            f'可用工具(择需取用):\n'
            f'  analyze(分析文件) find_symbol(查符号) read_file(读文件)\n'
            f'  search_code(搜索) replace_in_file(替换) write_file(写入)\n'
            f'  list_files(列文件) run_test(跑测试)\n'
            f'  git_diff(git差异) git_status(git状态) git_stash(保存现场)\n'
            f'  git_reset_hard(回退) git_commit_auto(自动提交) done(直接回答)\n'
            f'\n'
            f'示例:\n'
            f'  任务: 看看项目结构\n'
            f'  浏览项目文件 | list_files\n'
            f'\n'
            f'  任务: 修复fib函数bug\n'
            f'  定位并修复fib | read_file,replace_in_file,run_test\n'
            f'\n'
            f'  任务: 介绍一下自己\n'
            f'  直接回答 | done\n'
            f'\n'
            f'现在请为任务"{task}"生成方案:'
        )
        try:
            raw = llm_fn(prompt)
            plans = []
            for line in raw.strip().split('\n'):
                line = line.strip()
                if not line or '|' not in line:
                    continue
                parts = line.split('|', 1)
                desc = parts[0].strip()
                tool_strs = [t.strip() for t in parts[1].split(',') if t.strip()] if len(parts) > 1 else []
                tools = [t for t in tool_strs if t in self._KNOWN_TOOLS]
                if desc and tools:
                    plans.append({'description': desc, 'tools': tools})
            return plans[:count]
        except Exception:
            return [{'description': task, 'tools': ['analyze', 'read_file']}]

    def _filter_by_dependency(self, plans: List[Dict]) -> List[Dict]:
        """P1: 依赖图过滤"""
        valid = []
        for p in plans:
            ok, _ = self.tool_graph.validate_chain(p.get('tools', []))
            if ok:
                valid.append(p)
        return valid or plans

    def _filter_by_capability(self, task: str, plans: List[Dict]) -> List[Dict]:
        """P9: 能力匹配过滤"""
        valid = []
        for p in plans:
            if self.cap_extractor.validate_chain(task, p.get('tools', [])):
                valid.append(p)
        return valid or plans

    def _build_hypothesis(self, plan: Dict) -> Hypothesis:
        tools = plan.get('tools', [])
        h = Hypothesis(self._next_id, plan['description'], estimated_cost=len(tools), tools_used=tools)
        self._next_id += 1
        return h


# ── 锦标赛 ──


class Tournament:
    """锦标赛：两阶段（并行早停 + 经典淘汰）+ P4 自适应阈值"""

    EARLY_DEATH_THRESHOLD = 0.2
    PARALLEL_STEPS = 2

    def __init__(self, llm_fn: Optional[Callable] = None, metrics: Any = None):
        self.llm = llm_fn
        self.metrics = metrics
        self.tuner = ThresholdTuner()
        self.failure_classifier = FailureClassifier()

    def run(self, candidates: List[Hypothesis], task: str, context: Any, executor: Any = None) -> Optional[Hypothesis]:
        """锦标赛主流程"""
        if not candidates:
            return None
        if len(candidates) == 1:
            return candidates[0]

        # 获取自适应阈值
        thresholds = self.tuner.fit()
        confidence_gap = thresholds['confidence_gap']

        # 阶段A: 并行早停 (P2)
        survivors = self._parallel_phase(candidates, executor, context) if executor else candidates[:]

        # 阶段B: 经典锦标赛
        pool = survivors[:]
        while len(pool) > 1:
            a, b = pool[0], pool[1]
            winner, loser, method, rule_wrong = self._compare(task, context, a, b, confidence_gap)
            loser.status = 'discarded'
            if self.metrics:
                self.metrics.record_compare(method)
            self.tuner.record_round(
                {
                    'method': method,
                    'rule_wrong': rule_wrong,
                    'a_conf': a.confidence,
                    'b_conf': b.confidence,
                }
            )
            pool = [winner] + pool[2:]

        return pool[0] if pool else None

    def _compare(
        self, task: str, context: Any, a: Hypothesis, b: Hypothesis, confidence_gap: float
    ) -> Tuple[Hypothesis, Hypothesis, str, bool]:
        """比较两个假设：规则优先，LLM兜底"""
        # 规则1: 置信度差距显著
        gap = a.confidence - b.confidence
        if abs(gap) > confidence_gap:
            if gap > 0:
                return a, b, 'rule_confidence', False
            return b, a, 'rule_confidence', False

        # 规则2: 步骤数差距显著
        diff = a.estimated_cost - b.estimated_cost
        if abs(diff) > 2:
            if diff > 0:
                return b, a, 'rule_cost', False
            return a, b, 'rule_cost', False

        # 兜底: LLM 比较
        if self.llm is not None:
            winner = self._llm_compare(task, context, a, b)
            if winner:
                if winner.id == a.id:
                    return a, b, 'llm', False
                return b, a, 'llm', False

        # 最终兜底: 置信度高的赢
        if a.confidence >= b.confidence:
            return a, b, 'fallback', True
        return b, a, 'fallback', True

    def _llm_compare(self, task: str, context: Any, a: Hypothesis, b: Hypothesis) -> Optional[Hypothesis]:
        """用 LLM 比较两个假设"""
        prompt = f'任务: {task}\n方案A: {a.description}\n方案B: {b.description}\n哪个方案更好？只回答 A 或 B'
        if self.llm is None:
            return None
        try:
            raw = self.llm(prompt).strip().upper()
            if 'A' in raw:
                return a
            if 'B' in raw:
                return b
        except Exception:
            pass
        return None

    def _parallel_phase(self, candidates, executor, context) -> List[Hypothesis]:
        """P2: 并行早停 — 每个假设执行2步，低置信度的提前淘汰"""
        survivors = []
        for h in candidates:
            for _ in range(self.PARALLEL_STEPS):
                if executor:
                    h = executor.advance(h, context)
            if h.confidence >= self.EARLY_DEATH_THRESHOLD:
                survivors.append(h)
            else:
                h.status = 'discarded_early'
                if self.metrics:
                    self.metrics.record_early_death()
        return survivors or candidates


# ── 假设执行器 ──


class HypothesisExecutor:
    """假设执行器：执行假设的工具链"""

    def __init__(self, tools: Dict[str, Callable], failure_classifier: FailureClassifier, experience: Any = None):
        self.tools = tools
        self.failure_classifier = failure_classifier
        self.experience = experience

    def advance(self, hypothesis: Hypothesis, context: Any) -> Hypothesis:
        """执行假设的下一步工具"""
        next_step = len(hypothesis.tools_used)
        if next_step >= len(hypothesis.description.split(',')):
            return hypothesis

        tool_name = hypothesis.tools_used[next_step] if next_step < len(hypothesis.tools_used) else None
        if not tool_name:
            # 从描述推断工具
            tools = self._infer_tools(hypothesis.description)
            tool_name = tools[next_step] if next_step < len(tools) else None
        if not tool_name or tool_name not in self.tools:
            hypothesis.confidence *= 0.5
            return hypothesis

        try:
            result = self.tools[tool_name](context.build() if hasattr(context, 'build') else '', False)
            mode = self.failure_classifier.classify(tool_name, {}, result)
            if mode == FailureMode.SUCCESS:
                trit, conf = 1, 0.9
            elif mode in (FailureMode.LOGIC_ERROR, FailureMode.LOGIC_LOOP):
                trit, conf = -1, 0.8
            else:
                trit, conf = 0, 0.4
            hypothesis.update(tool_name, result, trit, conf, mode)
        except Exception as e:
            hypothesis.update(tool_name, str(e), -1, 0.3, FailureMode.LOGIC_ERROR)

        return hypothesis

    def _infer_tools(self, description: str) -> List[str]:
        """从描述推断工具链"""
        from agent_system.agent_tool_graph import TaskCapabilityExtractor

        extractor = TaskCapabilityExtractor()
        return extractor.suggest_tools(description)
