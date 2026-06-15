"""Phase 2: 资源统一管控 — 经验+Token+压缩+缓存+可观测+成本+回放
P5: SemanticCache
P6: Prompt Cache (部署侧)
P7: MetricsCollector
P10: CostPredictor
P11: ReplayEngine + ActionLog
"""

import json
import math
import time
import uuid
from typing import Any, Dict, List, Optional, Optional


# ── P7: 可观测性 ──


class MetricsCollector:
    """P7: 指标收集器 — 全链路可观测"""

    def __init__(self, log_path: str = '.agent_metrics.jsonl'):
        self.log_path = log_path
        self.predicted_cost: List[int] = []
        self.actual_cost: List[int] = []
        self.llm_compare_calls = 0
        self.total_compares = 0
        self.cache_hits = 0
        self.early_deaths = 0
        self.total_hypotheses = 0
        self.failure_mode_counts: Dict[str, int] = {}
        self.prediction_errors: List[float] = []
        self.start_time = time.time()

    def record_compare(self, method: str):
        self.total_compares += 1
        if method == 'llm':
            self.llm_compare_calls += 1

    def record_early_death(self):
        self.early_deaths += 1

    def record_cache_hit(self):
        self.cache_hits += 1

    def record_failure(self, mode: str):
        self.failure_mode_counts[mode] = self.failure_mode_counts.get(mode, 0) + 1

    def record_cost(self, predicted: float, actual: int):
        self.predicted_cost.append(int(predicted))
        self.actual_cost.append(actual)
        self.prediction_errors.append(abs(predicted - actual))

    def report(self) -> str:
        elapsed = time.time() - self.start_time
        parts = [
            f'运行时间: {elapsed:.1f}s',
            f'假设总数: {self.total_hypotheses}',
            f'早停数: {self.early_deaths}',
            f'缓存命中: {self.cache_hits}',
            f'LLM比较: {self.llm_compare_calls}/{self.total_compares}',
        ]
        if self.prediction_errors:
            mae = sum(self.prediction_errors) / len(self.prediction_errors)
            parts.append(f'成本预测MAE: {mae:.2f}')
        if self.failure_mode_counts:
            parts.append(f'失败分布: {self.failure_mode_counts}')
        return ' | '.join(parts)

    def save(self):
        data = {
            'predicted_cost': self.predicted_cost,
            'actual_cost': self.actual_cost,
            'llm_compare_calls': self.llm_compare_calls,
            'cache_hits': self.cache_hits,
            'early_deaths': self.early_deaths,
            'failure_mode_counts': self.failure_mode_counts,
        }
        try:
            with open(self.log_path, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass


# ── P5: 语义缓存 ──


class SemanticCache:
    """P5: 语义缓存 — 相似任务直接复用"""

    SIMILARITY_THRESHOLD = 0.92
    MAX_SIZE = 1000

    def __init__(self):
        self._cache: Dict[str, Dict] = {}

    def _keyword_overlap(self, a: str, b: str) -> float:
        """简单关键词重叠度"""
        kw_a = set(a.lower().split())
        kw_b = set(b.lower().split())
        if not kw_a or not kw_b:
            return 0.0
        return len(kw_a & kw_b) / len(kw_a | kw_b)

    def lookup(self, task: str) -> Optional[str]:
        """查找缓存"""
        best_score = 0.0
        best_result = None
        for key, entry in self._cache.items():
            score = self._keyword_overlap(task, entry['task'])
            if score > best_score:
                best_score = score
                best_result = entry['result']
        if best_score >= self.SIMILARITY_THRESHOLD:
            return best_result
        return None

    def store(self, task: str, result: str):
        """存储缓存"""
        if len(self._cache) >= self.MAX_SIZE:
            # 淘汰最早的
            oldest = min(self._cache.keys(), key=lambda k: self._cache[k]['time'])
            del self._cache[oldest]
        self._cache[task[:100]] = {
            'task': task,
            'result': result,
            'time': time.time(),
        }


# ── P10: 成本预测器 ──


class CostPredictor:
    """P10: 成本预测器 — 用历史数据预测工具链步数"""

    def __init__(self):
        self._history: List[Dict] = []

    def record(self, task: str, tool_chain: List[str], actual_steps: int):
        """记录一次执行"""
        self._history.append(
            {
                'task_len': len(task),
                'tool_count': len(tool_chain),
                'actual_steps': actual_steps,
            }
        )

    def predict(self, task: str, tool_chain: List[str]) -> float:
        """预测步数"""
        if not self._history:
            return max(1, len(tool_chain))
        # 简单平均：类似任务的历史平均步数
        task_len = len(task)
        similar = [h for h in self._history if abs(h['task_len'] - task_len) < 50]
        if similar:
            return sum(h['actual_steps'] for h in similar) / len(similar)
        return max(1, len(tool_chain))

    def train(self):
        """重训（当前用简单统计，未来可换模型）"""
        pass


# ── P11: 执行回放 ──


class ActionLog:
    """单次运行的完整执行记录"""

    def __init__(self, run_id: str, task: str):
        self.run_id = run_id
        self.task = task
        self.actions: List[Dict] = []
        self.created_at = time.time()

    def add_action(self, step: int, tool: str, args: Any, result: Any, confidence: float):
        self.actions.append(
            {
                'step': step,
                'tool': tool,
                'args': str(args)[:200],
                'result': str(result)[:200],
                'confidence': confidence,
                'timestamp': time.time(),
            }
        )

    def to_dict(self) -> dict:
        return {
            'run_id': self.run_id,
            'task': self.task,
            'actions': self.actions,
            'created_at': self.created_at,
        }


class ReplayEngine:
    """P11: 执行回放引擎 — 完整运行记录 + diff 对比"""

    def __init__(self, log_path: str = '.agent_log.jsonl'):
        self.log_path = log_path
        self.logs: Dict[str, ActionLog] = {}

    def record_action(self, run_id: str, step: int, tool: str, args: Any, result: Any, confidence: float):
        """记录一步操作"""
        if run_id not in self.logs:
            self.logs[run_id] = ActionLog(run_id, '')
        self.logs[run_id].add_action(step, tool, args, result, confidence)

    def create_run(self, task: str) -> str:
        """创建一次运行记录"""
        run_id = str(uuid.uuid4())[:8]
        self.logs[run_id] = ActionLog(run_id, task)
        return run_id

    def replay(self, run_id: str) -> Optional[ActionLog]:
        """回放一次运行"""
        return self.logs.get(run_id)

    def diff_replay(self, run_id_a: str, run_id_b: str) -> str:
        """对比两次运行的差异"""
        a = self.logs.get(run_id_a)
        b = self.logs.get(run_id_b)
        if not a or not b:
            return '找不到运行记录'
        diffs = []
        max_len = max(len(a.actions), len(b.actions))
        for i in range(max_len):
            act_a = a.actions[i] if i < len(a.actions) else None
            act_b = b.actions[i] if i < len(b.actions) else None
            if act_a and act_b:
                if act_a['tool'] != act_b['tool']:
                    diffs.append(f'Step {i}: {act_a["tool"]} → {act_b["tool"]}')
            elif act_a and not act_b:
                diffs.append(f'Step {i}: {act_a["tool"]} (B无此步)')
            elif act_b and not act_a:
                diffs.append(f'Step {i}: {act_b["tool"]} (A无此步)')
        return '\n'.join(diffs) if diffs else '无差异'


# ── ResourceManager: 统一管控 ──


class ResourceManager:
    """Phase 2: 资源统一管控"""

    DEFAULT_RELIABILITY = 0.7
    TOKEN_HARD_LIMIT = 7000
    TOKEN_SOFT_LIMIT = 5000

    def __init__(self):
        self.tool_stats: Dict[str, Dict] = {}
        self.module_stats: Dict[str, Dict] = {}
        self.lambda_decay = 0.1
        self.total_tokens = 0
        self.call_count = 0
        self.semantic_cache = SemanticCache()
        self.metrics = MetricsCollector()
        self.cost_predictor = CostPredictor()
        self.replay_engine = ReplayEngine()

    def record_tool_use(self, tool: str, success: bool, module: str = '', failure_mode: str = 'unknown'):
        """记录工具使用"""
        if tool not in self.tool_stats:
            self.tool_stats[tool] = {'success': 0, 'fail': 0, 'last_used': time.time()}
        stats = self.tool_stats[tool]
        if success:
            stats['success'] += 1
        else:
            stats['fail'] += 1
        stats['last_used'] = time.time()

        if module:
            if module not in self.module_stats:
                self.module_stats[module] = {'error_count': 0, 'total_count': 0}
            mstats = self.module_stats[module]
            mstats['total_count'] += 1
            if not success:
                mstats['error_count'] += 1

        self.metrics.record_failure(failure_mode)

    def tool_reliability(self, tool: str) -> float:
        """工具可靠性：带时间衰减"""
        if tool not in self.tool_stats:
            return self.DEFAULT_RELIABILITY
        stats = self.tool_stats[tool]
        total = stats['success'] + stats['fail']
        if total == 0:
            return self.DEFAULT_RELIABILITY
        base = stats['success'] / total
        age_hours = (time.time() - stats['last_used']) / 3600
        decay = math.exp(-self.lambda_decay * age_hours)
        return base * decay + 0.5 * (1 - decay)

    def get_unreliable_tools(self, threshold: float = 0.3) -> List[str]:
        """获取低可靠性工具"""
        result = []
        for tool, stats in self.tool_stats.items():
            total = stats['success'] + stats['fail']
            if total >= 3 and self.tool_reliability(tool) < threshold:
                result.append(tool)
        return result

    def check_tokens(self, estimated: int) -> bool:
        """检查 token 预算"""
        return self.total_tokens + estimated <= self.TOKEN_HARD_LIMIT

    def spend_tokens(self, actual: int):
        """消耗 token"""
        self.total_tokens += actual
        self.call_count += 1

    def get_experience_context(self, tool: str = '', module: str = '') -> str:
        """获取经验上下文"""
        parts = []
        if tool and tool in self.tool_stats:
            rel = self.tool_reliability(tool)
            parts.append(f'[{tool} 可靠性={rel:.2f}]')
        unreliable = self.get_unreliable_tools()
        if unreliable:
            parts.append(f'[低可靠性: {", ".join(unreliable[:3])}]')
        return ' '.join(parts) if parts else ''

    def save(self, path: str = '.agent_experience.json'):
        """持久化经验"""
        data = {
            'tool_stats': self.tool_stats,
            'module_stats': self.module_stats,
            'lambda': self.lambda_decay,
        }
        try:
            with open(path, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def load(self, path: str = '.agent_experience.json'):
        """加载经验"""
        try:
            with open(path) as f:
                data = json.load(f)
            self.tool_stats = data.get('tool_stats', {})
            self.module_stats = data.get('module_stats', {})
            self.lambda_decay = data.get('lambda', 0.1)
        except Exception:
            pass
