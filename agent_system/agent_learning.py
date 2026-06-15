"""跨会话学习 — 经验持久化 + 失败模式库 + 工具选择强化
P19: ExperienceStore — 跨会话经验持久化（SQLite）
P20: FailurePatternDB — 失败模式库 + 自动规避
P21: AdaptiveToolSelector — 基于历史的工具选择强化
"""

import json
import os
import sqlite3
import time
from collections import defaultdict
from typing import Dict, List, Tuple, Optional


class ExperienceStore:
    """跨会话经验持久化：工具成功率、失败模式、任务类型映射"""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'agent_experience.db')
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.db_path)
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS tool_stats (
                tool TEXT PRIMARY KEY,
                success INTEGER DEFAULT 0,
                fail INTEGER DEFAULT 0,
                total_time REAL DEFAULT 0,
                last_used REAL,
                updated_at REAL
            );
            CREATE TABLE IF NOT EXISTS failure_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tool TEXT,
                error_pattern TEXT,
                failure_mode TEXT,
                count INTEGER DEFAULT 1,
                first_seen REAL,
                last_seen REAL,
               解决方案 TEXT
            );
            CREATE TABLE IF NOT EXISTS task_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task TEXT,
                tool_chain TEXT,
                success INTEGER,
                duration REAL,
                created_at REAL
            );
            CREATE TABLE IF NOT EXISTS tool_recommendations (
                task_keyword TEXT,
                tool TEXT,
                score REAL,
                usage_count INTEGER DEFAULT 1,
                PRIMARY KEY (task_keyword, tool)
            );
        """)
        conn.commit()
        conn.close()

    def record_tool_use(self, tool: str, success: bool, duration: float = 0):
        """记录工具使用"""
        conn = sqlite3.connect(self.db_path)
        now = time.time()
        conn.execute(
            """
            INSERT INTO tool_stats (tool, success, fail, total_time, last_used, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(tool) DO UPDATE SET
                success = success + ?,
                fail = fail + ?,
                total_time = total_time + ?,
                last_used = ?,
                updated_at = ?
        """,
            (
                tool,
                1 if success else 0,
                0 if success else 1,
                duration,
                now,
                now,
                1 if success else 0,
                0 if success else 1,
                duration,
                now,
                now,
            ),
        )
        conn.commit()
        conn.close()

    def record_failure_pattern(self, tool: str, error: str, mode: str, solution: str = ''):
        """记录失败模式"""
        conn = sqlite3.connect(self.db_path)
        now = time.time()
        # 检查是否已存在相似模式
        existing = conn.execute(
            'SELECT id, count FROM failure_patterns WHERE tool=? AND error_pattern=?', (tool, error[:100])
        ).fetchone()

        if existing:
            conn.execute('UPDATE failure_patterns SET count=count+1, last_seen=? WHERE id=?', (now, existing[0]))
        else:
            conn.execute(
                'INSERT INTO failure_patterns (tool, error_pattern, failure_mode, first_seen, last_seen, 解决方案) VALUES (?, ?, ?, ?, ?, ?)',
                (tool, error[:100], mode, now, now, solution),
            )
        conn.commit()
        conn.close()

    def record_task(self, task: str, tool_chain: List[str], success: bool, duration: float):
        """记录任务执行"""
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            'INSERT INTO task_history (task, tool_chain, success, duration, created_at) VALUES (?, ?, ?, ?, ?)',
            (task[:500], json.dumps(tool_chain), 1 if success else 0, duration, time.time()),
        )
        conn.commit()
        conn.close()

    def get_tool_reliability(self, tool: str) -> float:
        """获取工具可靠性"""
        conn = sqlite3.connect(self.db_path)
        row = conn.execute('SELECT success, fail FROM tool_stats WHERE tool=?', (tool,)).fetchone()
        conn.close()
        if not row or (row[0] + row[1]) == 0:
            return 0.7
        return row[0] / (row[0] + row[1])

    def get_top_tools(self, limit: int = 10) -> List[Tuple[str, float]]:
        """获取最可靠的工具"""
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute(
            """
            SELECT tool, CAST(success AS REAL) / MAX(success + fail, 1) as reliability
            FROM tool_stats
            WHERE success + fail >= 3
            ORDER BY reliability DESC
            LIMIT ?
        """,
            (limit,),
        ).fetchall()
        conn.close()
        return rows

    def get_failure_patterns(self, tool: Optional[str] = None, limit: int = 20) -> List[Dict]:
        """获取失败模式"""
        conn = sqlite3.connect(self.db_path)
        if tool:
            rows = conn.execute(
                'SELECT tool, error_pattern, failure_mode, count, 解决方案 FROM failure_patterns WHERE tool=? ORDER BY count DESC LIMIT ?',
                (tool, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                'SELECT tool, error_pattern, failure_mode, count, 解决方案 FROM failure_patterns ORDER BY count DESC LIMIT ?',
                (limit,),
            ).fetchall()
        conn.close()
        return [{'tool': r[0], 'error': r[1], 'mode': r[2], 'count': r[3], 'solution': r[4]} for r in rows]

    def get_similar_tasks(self, task: str, limit: int = 5) -> List[Dict]:
        """查找相似任务的历史"""
        conn = sqlite3.connect(self.db_path)
        # 简单关键词匹配
        keywords = set(task.lower().split())
        rows = conn.execute(
            'SELECT task, tool_chain, success, duration FROM task_history ORDER BY created_at DESC LIMIT 100'
        ).fetchall()
        conn.close()

        scored = []
        for t, chain, success, duration in rows:
            t_keywords = set(t.lower().split())
            overlap = len(keywords & t_keywords) / max(len(keywords | t_keywords), 1)
            if overlap > 0.3:
                scored.append(
                    {
                        'task': t,
                        'tool_chain': json.loads(chain) if chain else [],
                        'success': bool(success),
                        'duration': duration,
                        'similarity': overlap,
                    }
                )
        scored.sort(key=lambda x: -x['similarity'])
        return scored[:limit]

    def update_recommendation(self, task_keyword: str, tool: str, success: bool):
        """更新工具推荐分数"""
        conn = sqlite3.connect(self.db_path)
        score = 1.0 if success else -0.5
        conn.execute(
            """
            INSERT INTO tool_recommendations (task_keyword, tool, score, usage_count)
            VALUES (?, ?, ?, 1)
            ON CONFLICT(task_keyword, tool) DO UPDATE SET
                score = score + ?,
                usage_count = usage_count + 1
        """,
            (task_keyword, tool, score, score),
        )
        conn.commit()
        conn.close()

    def get_recommendations(self, task_keyword: str, limit: int = 5) -> List[Tuple[str, float]]:
        """获取工具推荐"""
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute(
            """
            SELECT tool, score / usage_count as avg_score
            FROM tool_recommendations
            WHERE usage_count >= 2
            ORDER BY avg_score DESC
            LIMIT ?
        """,
            (limit,),
        ).fetchall()
        conn.close()
        return rows


class AdaptiveToolSelector:
    """基于历史的自适应工具选择"""

    def __init__(self, experience: ExperienceStore):
        self.experience = experience
        self._cache: Dict[str, List[Tuple[str, float]]] = {}

    def recommend(self, task: str, available_tools: List[str]) -> List[str]:
        """为任务推荐工具，按可靠性排序"""
        # 提取任务关键词
        keywords = task.lower().split()

        # 查询推荐
        all_recs = []
        for kw in keywords:
            recs = self.experience.get_recommendations(kw, limit=3)
            all_recs.extend(recs)

        # 合并分数
        tool_scores: Dict[str, float] = defaultdict(float)
        for tool, score in all_recs:
            if tool in available_tools:
                tool_scores[tool] += score

        # 添加基础可靠性
        for tool in available_tools:
            if tool not in tool_scores:
                tool_scores[tool] = self.experience.get_tool_reliability(tool)

        # 排序
        sorted_tools = sorted(tool_scores.items(), key=lambda x: -x[1])
        return [tool for tool, _ in sorted_tools]

    def should_avoid(self, tool: str) -> Tuple[bool, str]:
        """检查工具是否应该避免使用"""
        patterns = self.experience.get_failure_patterns(tool, limit=5)
        for p in patterns:
            if p['count'] >= 3:
                return True, f'该工具已连续失败{p["count"]}次: {p["error"]}'
        return False, ''

    def record_outcome(self, task: str, tool: str, success: bool, duration: float = 0):
        """记录工具使用结果"""
        self.experience.record_tool_use(tool, success, duration)
        # 更新推荐
        for kw in task.lower().split()[:3]:
            self.experience.update_recommendation(kw, tool, success)
