"""Phase 2A: MetaConfig Evolution — 配置参数进化

核心目标：Agent学会如何验证参数（不是简单改参数）

组件:
    P53: ConfigSchema — 集中管理所有可进化参数
    P54: ConfigPatch — 结构化配置变更（parameter/old/new/reason/expected）
    P55: TaskReplay — 历史任务回放验证
    P56: TernaryVerdict — 三态裁决（TRUE/FALSE/UNKNOWN）
    P57: MetaConfigAgent — 配置进化Agent
"""

import json
import os
import sqlite3
import statistics
import time
from typing import Any, Callable, Dict, List

from agent_system.paths import db_path

ROOT = os.path.dirname(os.path.abspath(__file__))


# ── Config Schema ──


class ConfigSchema:
    """集中管理所有可进化参数"""

    # 当前配置
    DEFAULT_CONFIG = {
        'cooldown_seconds': {
            'value': 30,
            'type': 'int',
            'min': 5,
            'max': 120,
            'description': '验证循环冷却时间（秒）',
            'category': 'timing',
        },
        'max_lines_changed': {
            'value': 20,
            'type': 'int',
            'min': 5,
            'max': 50,
            'description': '单次变更最大行数',
            'category': 'mutation',
        },
        'max_files_per_patch': {
            'value': 1,
            'type': 'int',
            'min': 1,
            'max': 5,
            'description': '每个补丁最大文件数',
            'category': 'mutation',
        },
        'tournament_candidates': {
            'value': 3,
            'type': 'int',
            'min': 2,
            'max': 10,
            'description': '锦标赛候选数量',
            'category': 'evolution',
        },
        'review_threshold': {
            'value': 0.8,
            'type': 'float',
            'min': 0.5,
            'max': 1.0,
            'description': '审查通过阈值',
            'category': 'review',
        },
        'max_auto_fix': {
            'value': 3,
            'type': 'int',
            'min': 1,
            'max': 10,
            'description': 'Agent自动修复最大次数',
            'category': 'safety',
        },
        'max_cycles': {
            'value': 10,
            'type': 'int',
            'min': 1,
            'max': 100,
            'description': '最大进化循环次数',
            'category': 'evolution',
        },
    }

    DB_PATH = db_path('agent_config_history.db')

    def __init__(self):
        self._config = {k: v['value'] for k, v in self.DEFAULT_CONFIG.items()}
        self._init_db()

    def _init_db(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.DB_PATH)
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS config_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parameter TEXT,
                old_value TEXT,
                new_value TEXT,
                reason TEXT,
                expected_success_rate TEXT,
                expected_latency TEXT,
                actual_success_rate REAL,
                actual_latency REAL,
                verdict TEXT,
                created_at REAL
            );
        """)
        conn.commit()
        conn.close()

    def get(self, key: str) -> Any:
        """获取配置值"""
        return self._config.get(key)

    def set(self, key: str, value: Any):
        """设置配置值"""
        if key in self.DEFAULT_CONFIG:
            schema = self.DEFAULT_CONFIG[key]
            # 类型检查
            if schema['type'] == 'int':
                value = int(value)
            elif schema['type'] == 'float':
                value = float(value)
            # 范围检查
            value = max(schema['min'], min(schema['max'], value))
            self._config[key] = value

    def get_all(self) -> Dict[str, Any]:
        """获取所有配置"""
        return dict(self._config)

    def get_schema(self, key: str) -> Dict:
        """获取参数schema"""
        return self.DEFAULT_CONFIG.get(key, {})

    def get_all_parameters(self) -> List[Dict]:
        """获取所有可进化参数"""
        return [
            {
                'name': k,
                'current': v['value'],
                'type': v['type'],
                'min': v['min'],
                'max': v['max'],
                'description': v['description'],
                'category': v['category'],
            }
            for k, v in self.DEFAULT_CONFIG.items()
        ]


# ── Config Patch ──


class ConfigPatch:
    """结构化配置变更"""

    def __init__(self, parameter: str, old_value: Any, new_value: Any, reason: str, expected: Dict[str, str] = None):
        self.parameter = parameter
        self.old_value = old_value
        self.new_value = new_value
        self.reason = reason
        self.expected = expected or {}
        self.created_at = time.time()
        self.verdict = None  # TRUE/FALSE/UNKNOWN
        self.actual_metrics = None

    def to_dict(self) -> Dict:
        return {
            'parameter': self.parameter,
            'old': self.old_value,
            'new': self.new_value,
            'reason': self.reason,
            'expected': self.expected,
            'verdict': self.verdict,
        }

    @classmethod
    def from_dict(cls, d: Dict) -> 'ConfigPatch':
        return cls(
            parameter=d['parameter'],
            old_value=d['old'],
            new_value=d['new'],
            reason=d.get('reason', ''),
            expected=d.get('expected', {}),
        )

    def format(self) -> str:
        return f"""ConfigPatch {{
    parameter: {self.parameter}
    old: {self.old_value}
    new: {self.new_value}
    reason: {self.reason}
    expected: {json.dumps(self.expected, ensure_ascii=False)}
}}"""


# ── Task Replay ──


class TaskReplay:
    """历史任务回放验证"""

    DB_PATH = db_path('agent_task_replay.db')

    def __init__(self):
        self._init_db()

    def _init_db(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.DB_PATH)
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS task_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task TEXT,
                tool_chain TEXT,
                success INTEGER,
                duration REAL,
                tokens INTEGER,
                created_at REAL
            );
            CREATE TABLE IF NOT EXISTS replay_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER,
                config_snapshot TEXT,
                success INTEGER,
                duration REAL,
                tokens INTEGER,
                created_at REAL,
                FOREIGN KEY (task_id) REFERENCES task_history(id)
            );
        """)
        conn.commit()
        conn.close()

    def record_task(self, task: str, tool_chain: List[str], success: bool, duration: float = 0, tokens: int = 0):
        """记录任务"""
        conn = sqlite3.connect(self.DB_PATH)
        conn.execute(
            """
            INSERT INTO task_history (task, tool_chain, success, duration, tokens, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (task[:500], json.dumps(tool_chain), 1 if success else 0, duration, tokens, time.time()),
        )
        conn.commit()
        conn.close()

    def get_recent_tasks(self, n: int = 100) -> List[Dict]:
        """获取最近n个任务"""
        conn = sqlite3.connect(self.DB_PATH)
        rows = conn.execute(
            'SELECT id, task, tool_chain, success, duration, tokens FROM task_history ORDER BY created_at DESC LIMIT ?',
            (n,),
        ).fetchall()
        conn.close()

        return [
            {
                'id': r[0],
                'task': r[1],
                'tool_chain': json.loads(r[2]) if r[2] else [],
                'success': bool(r[3]),
                'duration': r[4],
                'tokens': r[5],
            }
            for r in rows
        ]

    def replay_with_config(self, tasks: List[Dict], config: Dict, mock_executor: Callable = None) -> Dict:
        """用指定配置回放任务"""
        if mock_executor is None:
            # 默认模拟执行器
            def mock_executor(task, cfg):
                return {
                    'success': True,
                    'duration': 1.0,
                    'tokens': 100,
                }

        results = []
        for task in tasks:
            result = mock_executor(task['task'], config)
            results.append(result)

        # 统计
        total = len(results)
        success_count = sum(1 for r in results if r['success'])
        avg_duration = statistics.mean([r['duration'] for r in results]) if results else 0
        avg_tokens = statistics.mean([r['tokens'] for r in results]) if results else 0

        return {
            'total': total,
            'success_rate': success_count / max(total, 1),
            'avg_duration': avg_duration,
            'avg_tokens': avg_tokens,
            'results': results,
        }


# ── Ternary Verdict ──


class TernaryVerdict:
    """三态裁决：统计显著性的工程版表达"""

    # 裁决阈值
    SUCCESS_RATE_THRESHOLD = 0.05  # 成功率变化超过5%才算显著
    LATENCY_THRESHOLD = 0.10  # 延迟变化超过10%才算显著
    TOKEN_THRESHOLD = 0.10  # Token变化超过10%才算显著

    def judge(self, baseline: Dict, current: Dict) -> Dict:
        """三态裁决

        Args:
            baseline: 基线指标 {success_rate, avg_duration, avg_tokens}
            current: 当前指标

        Returns:
            verdict: TRUE/FALSE/UNKNOWN
            reason: 裁决理由
            metrics: 详细指标
        """
        # 计算变化
        sr_change = current['success_rate'] - baseline['success_rate']
        dur_change = (current['avg_duration'] - baseline['avg_duration']) / max(baseline['avg_duration'], 0.001)
        tok_change = (current['avg_tokens'] - baseline['avg_tokens']) / max(baseline['avg_tokens'], 1)

        # 三态判断
        sr_improved = sr_change > self.SUCCESS_RATE_THRESHOLD
        sr_decreased = sr_change < -self.SUCCESS_RATE_THRESHOLD
        dur_improved = dur_change < -self.LATENCY_THRESHOLD
        tok_improved = tok_change < -self.TOKEN_THRESHOLD

        # TRUE: 成功率↑ + (延迟↓ 或 Token↓)
        if sr_improved and (dur_improved or tok_improved):
            return {
                'verdict': 'TRUE',
                'reason': f'成功率提升{sr_change:.1%}，性能改善',
                'metrics': {
                    'success_rate_change': sr_change,
                    'duration_change': dur_change,
                    'token_change': tok_change,
                },
            }

        # FALSE: 成功率↓
        if sr_decreased:
            return {
                'verdict': 'FALSE',
                'reason': f'成功率下降{sr_change:.1%}',
                'metrics': {
                    'success_rate_change': sr_change,
                    'duration_change': dur_change,
                    'token_change': tok_change,
                },
            }

        # UNKNOWN: 变化不显著
        return {
            'verdict': 'UNKNOWN',
            'reason': f'变化不显著 (SR:{sr_change:+.1%}, D:{dur_change:+.1%}, T:{tok_change:+.1%})',
            'metrics': {
                'success_rate_change': sr_change,
                'duration_change': dur_change,
                'token_change': tok_change,
            },
        }


# ── MetaConfig Agent ──


class MetaConfigAgent:
    """配置进化Agent：生成ConfigPatch + 验证 + 裁决"""

    def __init__(self):
        self.config = ConfigSchema()
        self.replay = TaskReplay()
        self.verdict_engine = TernaryVerdict()
        self._history: List[Dict] = []

    def propose_config_change(self, parameter: str, new_value: Any, reason: str) -> ConfigPatch:
        """提议配置变更"""
        old_value = self.config.get(parameter)
        schema = self.config.get_schema(parameter)

        if not schema:
            raise ValueError(f'未知参数: {parameter}')

        # 范围检查
        new_value = max(schema['min'], min(schema['max'], new_value))

        # 生成预期
        expected = self._estimate_expected(parameter, old_value, new_value)

        return ConfigPatch(
            parameter=parameter,
            old_value=old_value,
            new_value=new_value,
            reason=reason,
            expected=expected,
        )

    def _estimate_expected(self, parameter: str, old_value: Any, new_value: Any) -> Dict:
        """估算预期收益"""
        # 简单启发式
        if parameter == 'cooldown_seconds':
            if new_value < old_value:
                return {'success_rate': '+0%', 'latency': '-10%'}
            else:
                return {'success_rate': '+0%', 'latency': '+10%'}
        elif parameter == 'tournament_candidates':
            if new_value > old_value:
                return {'success_rate': '+5%', 'latency': '+20%'}
            else:
                return {'success_rate': '-2%', 'latency': '-15%'}
        elif parameter == 'max_lines_changed':
            if new_value > old_value:
                return {'success_rate': '+3%', 'latency': '+5%'}
            else:
                return {'success_rate': '-1%', 'latency': '-5%'}
        return {}

    def validate_config_change(self, patch: ConfigPatch, n_tasks: int = 50) -> Dict:
        """验证配置变更"""
        # 1. 获取历史任务
        tasks = self.replay.get_recent_tasks(n_tasks)
        if not tasks:
            return {'verdict': 'UNKNOWN', 'reason': '无历史任务可回放'}

        # 2. 基线回放
        baseline_config = self.config.get_all()
        baseline_result = self.replay.replay_with_config(tasks, baseline_config)

        # 3. 新配置回放
        new_config = {**baseline_config, patch.parameter: patch.new_value}
        new_result = self.replay.replay_with_config(tasks, new_config)

        # 4. 三态裁决
        verdict_result = self.verdict_engine.judge(baseline_result, new_result)

        # 5. 记录
        patch.verdict = verdict_result['verdict']
        patch.actual_metrics = verdict_result['metrics']

        self._record_config_change(patch, verdict_result)

        return {
            'patch': patch.to_dict(),
            'baseline': {
                'success_rate': baseline_result['success_rate'],
                'avg_duration': baseline_result['avg_duration'],
                'avg_tokens': baseline_result['avg_tokens'],
            },
            'current': {
                'success_rate': new_result['success_rate'],
                'avg_duration': new_result['avg_duration'],
                'avg_tokens': new_result['avg_tokens'],
            },
            'verdict': verdict_result,
        }

    def apply_config_change(self, patch: ConfigPatch) -> bool:
        """应用配置变更（仅当verdict=TRUE）"""
        if patch.verdict != 'TRUE':
            return False

        self.config.set(patch.parameter, patch.new_value)
        return True

    def _record_config_change(self, patch: ConfigPatch, verdict: Dict):
        """记录配置变更"""
        conn = sqlite3.connect(ConfigSchema.DB_PATH)
        conn.execute(
            """
            INSERT INTO config_history
            (parameter, old_value, new_value, reason, expected_success_rate, expected_latency,
             actual_success_rate, actual_latency, verdict, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                patch.parameter,
                str(patch.old_value),
                str(patch.new_value),
                patch.reason,
                patch.expected.get('success_rate', ''),
                patch.expected.get('latency', ''),
                verdict['metrics'].get('success_rate_change', 0),
                verdict['metrics'].get('duration_change', 0),
                verdict['verdict'],
                time.time(),
            ),
        )
        conn.commit()
        conn.close()

    def get_config_history(self) -> List[Dict]:
        """获取配置变更历史"""
        conn = sqlite3.connect(ConfigSchema.DB_PATH)
        rows = conn.execute(
            'SELECT parameter, old_value, new_value, reason, verdict, created_at FROM config_history ORDER BY created_at DESC LIMIT 20'
        ).fetchall()
        conn.close()

        return [
            {
                'parameter': r[0],
                'old': r[1],
                'new': r[2],
                'reason': r[3],
                'verdict': r[4],
                'time': r[5],
            }
            for r in rows
        ]

    def summary(self) -> str:
        """摘要"""
        history = self.get_config_history()
        accepted = sum(1 for h in history if h['verdict'] == 'TRUE')
        rejected = sum(1 for h in history if h['verdict'] == 'FALSE')
        unknown = sum(1 for h in history if h['verdict'] == 'UNKNOWN')

        return (
            f'MetaConfig Agent:\n'
            f'  参数数: {len(self.config.get_all_parameters())}\n'
            f'  变更历史: {len(history)}次\n'
            f'  接受: {accepted} | 拒绝: {rejected} | 未知: {unknown}\n'
            f'  当前配置: {json.dumps(self.config.get_all(), indent=2)}'
        )


# ── 整合 ──


class MetaConfigSystem:
    """MetaConfig 系统：整合所有组件"""

    def __init__(self):
        self.agent = MetaConfigAgent()

    def run_cycle(self, parameter: str, new_value: Any, reason: str) -> Dict:
        """运行一次配置进化循环"""
        print('\n═══ MetaConfig 循环 ═══')

        # 1. 提议变更
        patch = self.agent.propose_config_change(parameter, new_value, reason)
        print(f'提议: {patch.format()}')

        # 2. 验证
        print('验证中...')
        result = self.agent.validate_config_change(patch)

        # 3. 裁决
        verdict = result['verdict']['verdict']
        print(f'裁决: {verdict}')
        print(f'  原因: {result["verdict"]["reason"]}')
        print(f'  基线: 成功率 {result["baseline"]["success_rate"]:.1%}')
        print(f'  当前: 成功率 {result["current"]["success_rate"]:.1%}')

        # 4. 应用（仅TRUE）
        if verdict == 'TRUE':
            applied = self.agent.apply_config_change(patch)
            print(f'应用: {"成功" if applied else "失败"}')
        else:
            print(f'不应用: {verdict}')

        return result

    def run(self, proposals: List[Dict]) -> Dict:
        """运行多个配置变更"""
        results = []
        for p in proposals:
            result = self.run_cycle(p['parameter'], p['new_value'], p['reason'])
            results.append(result)

        return {
            'total': len(results),
            'accepted': sum(1 for r in results if r['verdict']['verdict'] == 'TRUE'),
            'rejected': sum(1 for r in results if r['verdict']['verdict'] == 'FALSE'),
            'unknown': sum(1 for r in results if r['verdict']['verdict'] == 'UNKNOWN'),
            'results': results,
        }

    def summary(self) -> str:
        return self.agent.summary()
