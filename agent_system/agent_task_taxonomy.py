"""Task Taxonomy — 任务分类体系

核心目标：不同任务用不同参数（条件最优）

组件：
  P65: TaskClassifier — 任务分类器
  P66: TaskProfile — 任务画像（类型/复杂度/历史最优配置）
  P67: MetaLearningDB — Meta-Learning数据库
  P68: ConditionalOptimizer — 条件优化器
"""

import json
import os
import sqlite3
import time
from typing import Dict, List, Optional

ROOT = os.path.dirname(os.path.abspath(__file__))


# ── Task Classifier ──


class TaskClassifier:
    """任务分类器：将任务映射到类型"""

    # 任务类型定义
    TASK_TYPES = {
        'bug_fix': {
            'keywords': ['修复', 'fix', 'bug', '错误', '报错', '异常', '崩溃'],
            'description': '修复代码错误',
            'default_config': {
                'simple_max_complexity': 4,
                'single_max_complexity': 8,
                'tournament_candidates': 2,
                'max_auto_fix': 5,
                'review_threshold': 0.7,
            },
        },
        'refactor': {
            'keywords': ['重构', 'refactor', '优化', '整理', '简化', '重写'],
            'description': '重构代码结构',
            'default_config': {
                'simple_max_complexity': 2,
                'single_max_complexity': 6,
                'tournament_candidates': 5,
                'max_auto_fix': 2,
                'review_threshold': 0.9,
            },
        },
        'performance': {
            'keywords': ['性能', 'performance', '加速', '优化', '瓶颈', '慢'],
            'description': '性能优化',
            'default_config': {
                'simple_max_complexity': 3,
                'single_max_complexity': 7,
                'tournament_candidates': 8,
                'max_auto_fix': 3,
                'review_threshold': 0.95,
            },
        },
        'feature': {
            'keywords': ['新增', '添加', '实现', '功能', 'feature', 'create'],
            'description': '新增功能',
            'default_config': {
                'simple_max_complexity': 3,
                'single_max_complexity': 7,
                'tournament_candidates': 3,
                'max_auto_fix': 3,
                'review_threshold': 0.8,
            },
        },
        'analysis': {
            'keywords': ['分析', '查看', '理解', '搜索', '查找', '结构'],
            'description': '代码分析',
            'default_config': {
                'simple_max_complexity': 5,
                'single_max_complexity': 8,
                'tournament_candidates': 2,
                'max_auto_fix': 1,
                'review_threshold': 0.6,
            },
        },
        'test': {
            'keywords': ['测试', 'test', '验证', '检查', 'lint'],
            'description': '测试相关',
            'default_config': {
                'simple_max_complexity': 4,
                'single_max_complexity': 7,
                'tournament_candidates': 3,
                'max_auto_fix': 2,
                'review_threshold': 0.7,
            },
        },
        'documentation': {
            'keywords': ['文档', 'doc', '注释', '说明', 'README'],
            'description': '文档相关',
            'default_config': {
                'simple_max_complexity': 6,
                'single_max_complexity': 9,
                'tournament_candidates': 2,
                'max_auto_fix': 1,
                'review_threshold': 0.5,
            },
        },
    }

    def classify(self, task: str) -> Dict:
        """分类任务"""
        task_lower = task.lower()
        scores = {}

        for task_type, info in self.TASK_TYPES.items():
            score = 0
            for keyword in info['keywords']:
                if keyword in task_lower:
                    score += 1
            if score > 0:
                scores[task_type] = score

        if not scores:
            return {
                'type': 'general',
                'confidence': 0.5,
                'config': self.TASK_TYPES['feature']['default_config'],
            }

        best_type = max(scores, key=scores.get)
        confidence = min(1.0, scores[best_type] / 3)  # 3个关键词=满分

        return {
            'type': best_type,
            'confidence': confidence,
            'config': self.TASK_TYPES[best_type]['default_config'],
        }

    def get_all_types(self) -> List[Dict]:
        """获取所有任务类型"""
        return [
            {'type': k, 'description': v['description'], 'keywords': v['keywords'][:3]}
            for k, v in self.TASK_TYPES.items()
        ]


# ── Task Profile ──


class TaskProfile:
    """任务画像：类型/复杂度/历史最优配置"""

    def __init__(self, task: str, task_type: str, complexity: int = 5):
        self.task = task
        self.type = task_type
        self.complexity = complexity
        self.history: List[Dict] = []  # 历史执行记录

    def add_history(self, config: Dict, success: bool, duration: float, tokens: int):
        """添加历史记录"""
        self.history.append(
            {
                'config': config,
                'success': success,
                'duration': duration,
                'tokens': tokens,
                'time': time.time(),
            }
        )

    def get_best_config(self) -> Optional[Dict]:
        """获取历史最优配置"""
        if not self.history:
            return None

        # 找成功率最高的配置
        config_scores: Dict[str, Dict] = {}
        for h in self.history:
            config_key = json.dumps(h['config'], sort_keys=True)
            if config_key not in config_scores:
                config_scores[config_key] = {'successes': 0, 'total': 0, 'config': h['config']}
            config_scores[config_key]['total'] += 1
            if h['success']:
                config_scores[config_key]['successes'] += 1

        # 按成功率排序
        best = None
        best_rate = -1
        for key, stats in config_scores.items():
            rate = stats['successes'] / max(stats['total'], 1)
            if rate > best_rate and stats['total'] >= 3:  # 至少3次样本
                best_rate = rate
                best = stats['config']

        return best

    def to_dict(self) -> Dict:
        return {
            'task': self.task[:100],
            'type': self.type,
            'complexity': self.complexity,
            'history_count': len(self.history),
        }


# ── Meta-Learning DB ──


class MetaLearningDB:
    """Meta-Learning数据库：记录 参数→效果→场景"""

    DB_PATH = os.path.join(ROOT, 'agent_meta_learning.db')

    def __init__(self):
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.DB_PATH)
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS task_config_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_type TEXT,
                config_snapshot TEXT,
                success_count INTEGER DEFAULT 0,
                fail_count INTEGER DEFAULT 0,
                avg_duration REAL DEFAULT 0,
                avg_tokens INTEGER DEFAULT 0,
                last_used REAL,
                UNIQUE(task_type, config_snapshot)
            );
            CREATE TABLE IF NOT EXISTS task_evolution_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_type TEXT,
                parameter TEXT,
                old_value TEXT,
                new_value TEXT,
                improvement REAL,
                created_at REAL
            );
        """)
        conn.commit()
        conn.close()

    def record_execution(self, task_type: str, config: Dict, success: bool, duration: float = 0, tokens: int = 0):
        """记录执行结果"""
        config_key = json.dumps(config, sort_keys=True)

        conn = sqlite3.connect(self.DB_PATH)
        existing = conn.execute(
            'SELECT id, success_count, fail_count, avg_duration FROM task_config_stats WHERE task_type=? AND config_snapshot=?',
            (task_type, config_key),
        ).fetchone()

        if existing:
            total = existing[1] + existing[2] + 1
            new_success = existing[1] + (1 if success else 0)
            new_fail = existing[2] + (0 if success else 1)
            new_avg_dur = (existing[3] * (existing[1] + existing[2]) + duration) / total

            conn.execute(
                """
                UPDATE task_config_stats
                SET success_count=?, fail_count=?, avg_duration=?, last_used=?
                WHERE id=?
            """,
                (new_success, new_fail, new_avg_dur, time.time(), existing[0]),
            )
        else:
            conn.execute(
                """
                INSERT INTO task_config_stats
                (task_type, config_snapshot, success_count, fail_count, avg_duration, avg_tokens, last_used)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (task_type, config_key, 1 if success else 0, 0 if success else 1, duration, tokens, time.time()),
            )

        conn.commit()
        conn.close()

    def get_best_config(self, task_type: str, min_samples: int = 5) -> Optional[Dict]:
        """获取任务类型的最优配置"""
        conn = sqlite3.connect(self.DB_PATH)
        rows = conn.execute(
            """
            SELECT config_snapshot, success_count, fail_count
            FROM task_config_stats
            WHERE task_type=? AND success_count + fail_count >= ?
            ORDER BY CAST(success_count AS REAL) / (success_count + fail_count) DESC
            LIMIT 1
        """,
            (task_type, min_samples),
        ).fetchall()
        conn.close()

        if rows:
            return json.loads(rows[0][0])
        return None

    def get_task_stats(self, task_type: str) -> Dict:
        """获取任务类型统计"""
        conn = sqlite3.connect(self.DB_PATH)
        rows = conn.execute(
            """
            SELECT config_snapshot, success_count, fail_count, avg_duration
            FROM task_config_stats
            WHERE task_type=?
            ORDER BY success_count + fail_count DESC
        """,
            (task_type,),
        ).fetchall()
        conn.close()

        total_success = sum(r[1] for r in rows)
        total_fail = sum(r[2] for r in rows)
        total = total_success + total_fail

        return {
            'task_type': task_type,
            'total_executions': total,
            'success_rate': total_success / max(total, 1),
            'config_count': len(rows),
            'configs': [
                {
                    'config': json.loads(r[0]),
                    'success_rate': r[1] / max(r[1] + r[2], 1),
                    'executions': r[1] + r[2],
                }
                for r in rows[:5]
            ],
        }

    def get_all_stats(self) -> Dict:
        """获取所有任务类型统计"""
        conn = sqlite3.connect(self.DB_PATH)
        rows = conn.execute("""
            SELECT task_type, SUM(success_count), SUM(fail_count), COUNT(*)
            FROM task_config_stats
            GROUP BY task_type
        """).fetchall()
        conn.close()

        return {
            r[0]: {
                'total': r[1] + r[2],
                'success_rate': r[1] / max(r[1] + r[2], 1),
                'config_count': r[3],
            }
            for r in rows
        }


# ── Conditional Optimizer ──


class ConditionalOptimizer:
    """条件优化器：根据任务类型选择最优配置"""

    def __init__(self):
        self.classifier = TaskClassifier()
        self.meta_db = MetaLearningDB()

    def get_optimal_config(self, task: str) -> Dict:
        """获取任务的最优配置"""
        # 1. 分类任务
        classification = self.classifier.classify(task)
        task_type = classification['type']

        # 2. 查询Meta-Learning DB
        best_config = self.meta_db.get_best_config(task_type, min_samples=3)

        if best_config:
            return {
                'config': best_config,
                'source': 'meta_learning',
                'task_type': task_type,
                'confidence': classification['confidence'],
            }

        # 3. 使用默认配置
        return {
            'config': classification['config'],
            'source': 'default',
            'task_type': task_type,
            'confidence': classification['confidence'],
        }

    def record_execution(self, task: str, config: Dict, success: bool, duration: float = 0, tokens: int = 0):
        """记录执行结果"""
        classification = self.classifier.classify(task)
        self.meta_db.record_execution(classification['type'], config, success, duration, tokens)

    def summary(self) -> str:
        stats = self.meta_db.get_all_stats()
        lines = ['Meta-Learning DB:']
        for task_type, s in stats.items():
            lines.append(f'  {task_type}: {s["total"]}次, SR={s["success_rate"]:.1%}, {s["config_count"]}种配置')
        return '\n'.join(lines) if lines else '  (无数据)'


# ── 整合 ──


class TaskTaxonomySystem:
    """Task Taxonomy 系统"""

    def __init__(self):
        self.classifier = TaskClassifier()
        self.optimizer = ConditionalOptimizer()
        self._history: List[Dict] = []

    def classify_task(self, task: str) -> Dict:
        """分类任务"""
        return self.classifier.classify(task)

    def get_optimal_config(self, task: str) -> Dict:
        """获取最优配置"""
        return self.optimizer.get_optimal_config(task)

    def record_execution(self, task: str, config: Dict, success: bool, duration: float = 0, tokens: int = 0):
        """记录执行"""
        self.optimizer.record_execution(task, config, success, duration, tokens)

    def run_cycle(self, task: str, config: Dict, success: bool, duration: float = 0, tokens: int = 0) -> Dict:
        """运行一次分类+优化循环"""
        # 1. 分类
        classification = self.classifier.classify(task)

        # 2. 获取最优配置
        optimal = self.get_optimal_config(task)

        # 3. 记录
        self.record_execution(task, config, success, duration, tokens)

        result = {
            'task': task[:50],
            'type': classification['type'],
            'confidence': classification['confidence'],
            'config_source': optimal['source'],
            'success': success,
        }

        self._history.append(result)
        return result

    def summary(self) -> str:
        stats = self.optimizer.meta_db.get_all_stats()
        lines = [
            'Task Taxonomy System:',
            f'  任务类型: {len(self.classifier.TASK_TYPES)}',
            f'  执行历史: {len(self._history)}',
        ]
        for task_type, s in stats.items():
            lines.append(f'  {task_type}: {s["total"]}次, SR={s["success_rate"]:.1%}')
        return '\n'.join(lines)
