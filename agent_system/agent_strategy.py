"""策略自优化系统 — Prompt进化 + Tool学习 + 策略切换 + A/B Rollout
P37: PromptEvolver — Prompt自进化（变体生成+选择+淘汰）
P38: ToolSelectionLearner — 工具选择学习（历史成功率+任务类型映射）
P39: StrategySwitcher — 策略切换（任务复杂度→策略选择）
P40: ABRollout — A/B测试（多策略并行+赢家选择）
"""

import os
import random
import sqlite3
import time
from collections import defaultdict
from typing import Dict, List, Optional, Optional


class PromptEvolver:
    """Prompt自进化：变体生成 + 成功率追踪 + 自动选择"""

    DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'agent_prompt_evolution.db')

    def __init__(self):
        self._init_db()
        self._current_variant = self._load_current_variant()

    def _init_db(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.DB_PATH)
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS prompt_variants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                content TEXT,
                created_at REAL,
                is_active INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS prompt_trials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                variant_id INTEGER,
                task TEXT,
                success INTEGER,
                duration REAL,
                tokens INTEGER,
                created_at REAL,
                FOREIGN KEY (variant_id) REFERENCES prompt_variants(id)
            );
        """)
        conn.commit()
        conn.close()

    def _load_current_variant(self) -> str:
        """加载当前活跃的prompt变体"""
        conn = sqlite3.connect(self.DB_PATH)
        row = conn.execute('SELECT content FROM prompt_variants WHERE is_active=1 LIMIT 1').fetchone()
        conn.close()
        return row[0] if row else ''

    def register_variant(self, name: str, content: str):
        """注册新的prompt变体"""
        conn = sqlite3.connect(self.DB_PATH)
        conn.execute(
            'INSERT OR REPLACE INTO prompt_variants (name, content, created_at) VALUES (?, ?, ?)',
            (name, content, time.time()),
        )
        conn.commit()
        conn.close()

    def activate_variant(self, name: str):
        """激活指定变体"""
        conn = sqlite3.connect(self.DB_PATH)
        conn.execute('UPDATE prompt_variants SET is_active=0')
        conn.execute('UPDATE prompt_variants SET is_active=1 WHERE name=?', (name,))
        conn.commit()
        conn.close()
        self._current_variant = self._load_current_variant()

    def record_trial(self, variant_name: str, task: str, success: bool, duration: float = 0, tokens: int = 0):
        """记录一次试验"""
        conn = sqlite3.connect(self.DB_PATH)
        row = conn.execute('SELECT id FROM prompt_variants WHERE name=?', (variant_name,)).fetchone()
        if row:
            conn.execute(
                'INSERT INTO prompt_trials (variant_id, task, success, duration, tokens, created_at) VALUES (?, ?, ?, ?, ?, ?)',
                (row[0], task[:500], 1 if success else 0, duration, tokens, time.time()),
            )
        conn.commit()
        conn.close()

    def get_stats(self, variant_name: Optional[str] = None) -> Dict:
        """获取变体统计"""
        conn = sqlite3.connect(self.DB_PATH)
        if variant_name:
            row = conn.execute('SELECT id FROM prompt_variants WHERE name=?', (variant_name,)).fetchone()
            if row:
                trials = conn.execute(
                    'SELECT success, duration, tokens FROM prompt_trials WHERE variant_id=?', (row[0],)
                ).fetchall()
            else:
                trials = []
        else:
            trials = conn.execute("""
                SELECT t.success, t.duration, t.tokens
                FROM prompt_trials p
                JOIN prompt_variants v ON p.variant_id = v.id
                WHERE v.is_active = 1
            """).fetchall()
        conn.close()

        if not trials:
            return {'trials': 0, 'success_rate': 0, 'avg_duration': 0, 'avg_tokens': 0}

        successes = sum(1 for s, _, _ in trials if s)
        return {
            'trials': len(trials),
            'success_rate': successes / len(trials),
            'avg_duration': sum(d for _, d, _ in trials) / len(trials),
            'avg_tokens': sum(t for _, _, t in trials) / len(trials),
        }

    def select_best_variant(self) -> str:
        """选择表现最好的变体"""
        conn = sqlite3.connect(self.DB_PATH)
        variants = conn.execute('SELECT name FROM prompt_variants').fetchall()
        conn.close()

        if not variants:
            return ''

        best_name = ''
        best_score = -1

        for (name,) in variants:
            stats = self.get_stats(name)
            if stats['trials'] < 3:
                score = 0.5  # 新变体默认分
            else:
                # 综合评分：成功率 * 0.7 + 速度奖励 * 0.2 + Token效率 * 0.1
                speed_bonus = max(0, 1 - stats['avg_duration'] / 60)
                token_bonus = max(0, 1 - stats['avg_tokens'] / 4096)
                score = stats['success_rate'] * 0.7 + speed_bonus * 0.2 + token_bonus * 0.1

            if score > best_score:
                best_score = score
                best_name = name

        return best_name

    def auto_evolve(self):
        """自动进化：选择最优变体并激活"""
        best = self.select_best_variant()
        if best:
            self.activate_variant(best)
        return best

    def generate_variant(self, base_content: str, mutation_rate: float = 0.1) -> str:
        """生成新变体（基于基础内容的变异）"""
        lines = base_content.split('\n')
        mutated = []
        for line in lines:
            if random.random() < mutation_rate and line.strip():
                # 简单变异：调整语气
                if '必须' in line:
                    line = line.replace('必须', '应该')
                elif '应该' in line:
                    line = line.replace('应该', '可以')
                elif '不要' in line:
                    line = line.replace('不要', '尽量避免')
            mutated.append(line)
        return '\n'.join(mutated)


class ToolSelectionLearner:
    """工具选择学习：任务类型→工具映射 + 成功率追踪"""

    DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'agent_tool_learning.db')

    def __init__(self):
        self._init_db()

    def _init_db(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.DB_PATH)
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS tool_task_stats (
                tool TEXT,
                task_type TEXT,
                success INTEGER DEFAULT 0,
                fail INTEGER DEFAULT 0,
                total_duration REAL DEFAULT 0,
                PRIMARY KEY (tool, task_type)
            );
            CREATE TABLE IF NOT EXISTS tool_recommendations (
                task_keyword TEXT,
                tool TEXT,
                score REAL DEFAULT 0,
                usage_count INTEGER DEFAULT 0,
                PRIMARY KEY (task_keyword, tool)
            );
        """)
        conn.commit()
        conn.close()

    def classify_task(self, task: str) -> str:
        """任务分类"""
        task_lower = task.lower()
        if any(w in task_lower for w in ['分析', '查看', '结构', '多少行', '函数']):
            return 'analysis'
        elif any(w in task_lower for w in ['修复', '改', '修', '替换', 'bug']):
            return 'fix'
        elif any(w in task_lower for w in ['新增', '加', '实现', '创建', '写']):
            return 'create'
        elif any(w in task_lower for w in ['测试', '验证', '跑']):
            return 'test'
        elif any(w in task_lower for w in ['搜索', '查找', '找', '在哪', '定义']):
            return 'search'
        elif any(w in task_lower for w in ['重构', '优化', '整理']):
            return 'refactor'
        else:
            return 'general'

    def record_outcome(self, tool: str, task: str, success: bool, duration: float = 0):
        """记录工具使用结果"""
        task_type = self.classify_task(task)
        conn = sqlite3.connect(self.DB_PATH)
        conn.execute(
            """
            INSERT INTO tool_task_stats (tool, task_type, success, fail, total_duration)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(tool, task_type) DO UPDATE SET
                success = success + ?,
                fail = fail + ?,
                total_duration = total_duration + ?
        """,
            (
                tool,
                task_type,
                1 if success else 0,
                0 if success else 1,
                duration,
                1 if success else 0,
                0 if success else 1,
                duration,
            ),
        )
        conn.commit()
        conn.close()

    def get_tool_score(self, tool: str, task_type: str) -> float:
        """获取工具在特定任务类型下的得分"""
        conn = sqlite3.connect(self.DB_PATH)
        row = conn.execute(
            'SELECT success, fail FROM tool_task_stats WHERE tool=? AND task_type=?', (tool, task_type)
        ).fetchone()
        conn.close()

        if not row or (row[0] + row[1]) == 0:
            return 0.5  # 默认分

        total = row[0] + row[1]
        row[0] / total

        # 贝叶斯平滑：避免小样本偏差
        prior = 0.5
        prior_weight = 3
        smoothed = (prior * prior_weight + row[0]) / (prior_weight + total)

        return smoothed

    def recommend_tools(self, task: str, available_tools: List[str]) -> List[str]:
        """为任务推荐工具，按得分排序"""
        task_type = self.classify_task(task)
        scored = []
        for tool in available_tools:
            score = self.get_tool_score(tool, task_type)
            scored.append((score, tool))
        scored.sort(key=lambda x: -x[0])
        return [tool for _, tool in scored]

    def get_stats(self) -> Dict:
        """获取学习统计"""
        conn = sqlite3.connect(self.DB_PATH)
        rows = conn.execute("""
            SELECT tool, task_type, success, fail
            FROM tool_task_stats
            WHERE success + fail >= 3
            ORDER BY success * 1.0 / (success + fail) DESC
            LIMIT 20
        """).fetchall()
        conn.close()

        return [
            {
                'tool': tool,
                'task_type': task_type,
                'success_rate': success / (success + fail) if (success + fail) > 0 else 0,
                'total': success + fail,
            }
            for tool, task_type, success, fail in rows
        ]


class StrategySwitcher:
    """策略切换：任务复杂度→策略选择"""

    STRATEGIES = {
        'direct': {
            'description': '直接工具调用，不走LLM',
            'max_rounds': 1,
            'use_llm': False,
        },
        'single': {
            'description': '单次假设+验证',
            'max_rounds': 3,
            'use_llm': True,
            'hypothesis_count': 1,
        },
        'tournament': {
            'description': '多假设+锦标赛',
            'max_rounds': 5,
            'use_llm': True,
            'hypothesis_count': 3,
        },
        'parallel': {
            'description': '多假设+并行验证',
            'max_rounds': 8,
            'use_llm': True,
            'hypothesis_count': 3,
            'parallel': True,
        },
    }

    def __init__(self):
        self._task_history: List[Dict] = []

    def classify_complexity(self, task: str) -> str:
        """任务复杂度分类"""
        task_lower = task.lower()

        # 简单任务：查文件、搜符号、看状态
        simple_patterns = ['看看', '查看', '列出', '多少', '在哪', '是什么', 'git']
        if any(p in task_lower for p in simple_patterns):
            return 'simple'

        # 中等任务：修bug、加功能（单文件）
        medium_patterns = ['修复', '改', '加', '修', '替换', '修改']
        has_file = any(ext in task_lower for ext in ['.py', '.san', '.md'])
        if any(p in task_lower for p in medium_patterns) and has_file:
            return 'medium'

        # 复杂任务：重构、多文件、新系统
        complex_patterns = ['重构', '优化', '实现', '创建', '新增', '系统', '框架']
        if any(p in task_lower for p in complex_patterns):
            return 'complex'

        # 默认中等
        return 'medium'

    def select_strategy(self, task: str) -> Dict:
        """根据任务选择策略"""
        complexity = self.classify_complexity(task)

        strategy_map = {
            'simple': 'direct',
            'medium': 'single',
            'complex': 'tournament',
        }

        strategy_name = strategy_map.get(complexity, 'single')
        strategy = self.STRATEGIES[strategy_name].copy()
        strategy['name'] = strategy_name
        strategy['complexity'] = complexity

        return strategy

    def record_outcome(self, task: str, strategy: str, success: bool, duration: float):
        """记录策略效果"""
        self._task_history.append(
            {
                'task': task[:200],
                'strategy': strategy,
                'success': success,
                'duration': duration,
                'time': time.time(),
            }
        )

    def get_stats(self) -> Dict:
        """策略统计"""
        if not self._task_history:
            return {}

        stats = defaultdict(lambda: {'success': 0, 'fail': 0, 'total_duration': 0})
        for h in self._task_history:
            s = stats[h['strategy']]
            if h['success']:
                s['success'] += 1
            else:
                s['fail'] += 1
            s['total_duration'] += h['duration']

        result = {}
        for strategy, s in stats.items():
            total = s['success'] + s['fail']
            result[strategy] = {
                'success_rate': s['success'] / total if total > 0 else 0,
                'total': total,
                'avg_duration': s['total_duration'] / total if total > 0 else 0,
            }
        return result


class ABRollout:
    """A/B测试：多策略并行+赢家选择"""

    def __init__(self):
        self._experiments: Dict[str, Dict] = {}
        self._results: List[Dict] = []

    def create_experiment(self, name: str, variants: List[Dict], traffic_split: List[float] = None):
        """创建实验

        Args:
            name: 实验名
            variants: 变体列表 [{'name': 'A', 'config': {...}}, ...]
            traffic_split: 流量分配 [0.5, 0.5]
        """
        if traffic_split is None:
            traffic_split = [1.0 / len(variants)] * len(variants)

        self._experiments[name] = {
            'variants': variants,
            'traffic_split': traffic_split,
            'created_at': time.time(),
            'active': True,
        }

    def assign_variant(self, experiment_name: str) -> Dict:
        """为新任务分配变体"""
        if experiment_name not in self._experiments:
            return {}

        exp = self._experiments[experiment_name]
        if not exp['active']:
            return {}

        # 按流量比例随机选择
        r = random.random()
        cumulative = 0
        for i, split in enumerate(exp['traffic_split']):
            cumulative += split
            if r <= cumulative:
                return exp['variants'][i]

        return exp['variants'][-1]

    def record_result(self, experiment_name: str, variant_name: str, task: str, success: bool, metrics: Dict = None):
        """记录实验结果"""
        self._results.append(
            {
                'experiment': experiment_name,
                'variant': variant_name,
                'task': task[:200],
                'success': success,
                'metrics': metrics or {},
                'time': time.time(),
            }
        )

    def get_winner(self, experiment_name: str) -> Optional[str]:
        """选择赢家"""
        exp_results = [r for r in self._results if r['experiment'] == experiment_name]
        if not exp_results:
            return None

        # 按变体统计
        variant_stats = defaultdict(lambda: {'success': 0, 'total': 0})
        for r in exp_results:
            vs = variant_stats[r['variant']]
            vs['total'] += 1
            if r['success']:
                vs['success'] += 1

        # 选择成功率最高的
        best_variant = None
        best_rate = -1
        for variant, stats in variant_stats.items():
            rate = stats['success'] / stats['total'] if stats['total'] > 0 else 0
            if rate > best_rate:
                best_rate = rate
                best_variant = variant

        return best_variant

    def get_stats(self, experiment_name: Optional[str] = None) -> Dict:
        """获取实验统计"""
        results = self._results
        if experiment_name:
            results = [r for r in results if r['experiment'] == experiment_name]

        if not results:
            return {}

        # 按实验分组
        exp_stats = defaultdict(lambda: defaultdict(lambda: {'success': 0, 'total': 0}))
        for r in results:
            vs = exp_stats[r['experiment']][r['variant']]
            vs['total'] += 1
            if r['success']:
                vs['success'] += 1

        # 格式化输出
        output = {}
        for exp, variants in exp_stats.items():
            output[exp] = {}
            for variant, stats in variants.items():
                output[exp][variant] = {
                    'success_rate': stats['success'] / stats['total'] if stats['total'] > 0 else 0,
                    'total': stats['total'],
                }
        return output
