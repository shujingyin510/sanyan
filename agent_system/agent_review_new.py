"""Reviewer Agent + Patch历史数据库 + 测试生成

三层补全:
    P50: ReviewerAgent — 独立代码审查
    P51: PatchHistory — Patch历史数据库（收益/风险/回滚率）
    P52: TestGenerator — 测试用例生成
"""

import json
import os
import sqlite3
import time
from typing import Dict

ROOT = os.path.dirname(os.path.abspath(__file__))


# ── Reviewer Agent ──


class ReviewerAgent:
    """独立代码审查Agent：Coder的Patch必须通过审查才能接受"""

    DB_PATH = os.path.join(ROOT, 'agent_review_history.db')

    # 审查规则
    RULES = {
        'no_critical_changes': {
            'check': lambda p: not any(k in p.get('target', '') for k in ['agent.san', 'decision.san']),
            'reason': '禁止修改Agent核心决策文件',
            'severity': 'block',
        },
        'no_magic_numbers': {
            'check': lambda p: not any(c.isdigit() and len(c) > 3 for c in p.get('after', '').split()),
            'reason': '避免硬编码魔法数字',
            'severity': 'warn',
        },
        'no_empty_rationale': {
            'check': lambda p: bool(p.get('rationale', '').strip()),
            'reason': '补丁必须有修改理由',
            'severity': 'block',
        },
        'max_lines_changed': {
            'check': lambda p: len(p.get('after', '').split('\n')) <= 20,
            'reason': '单次变更不超过20行',
            'severity': 'block',
        },
        'has_expected': {
            'check': lambda p: bool(p.get('expected', '').strip()),
            'reason': '补丁必须有预期收益',
            'severity': 'warn',
        },
        'no_delete_all': {
            'check': lambda p: not (p.get('action') == 'delete' and len(p.get('before', '').split('\n')) > 10),
            'reason': '禁止删除超过10行的代码块',
            'severity': 'block',
        },
        # 对抗补丁检测
        'no_redundant_cache': {
            'check': lambda p: (
                not (
                    '缓存' in p.get('rationale', '')
                    and (
                        p.get('after', '').count('cache') > p.get('before', '').count('cache') + 2
                        or p.get('after', '').count('_cache') > p.get('before', '').count('_cache') + 1
                    )
                )
            ),
            'reason': '禁止无意义缓存（缓存变量异常增加）',
            'severity': 'block',
        },
        'no_redundant_computation': {
            'check': lambda p: (
                not (
                    p.get('after', '').count('(') > p.get('before', '').count('(') * 1.5
                    and '优化' in p.get('rationale', '')
                )
            ),
            'reason': '禁止重复计算（函数调用数量异常增加）',
            'severity': 'block',
        },
        'no_wrong_inline': {
            'check': lambda p: (
                not ('内联' in p.get('rationale', '') and len(p.get('after', '')) > len(p.get('before', '')) * 2)
            ),
            'reason': '禁止错误内联（代码膨胀超过2倍）',
            'severity': 'block',
        },
        'no_wrong_loop_unroll': {
            'check': lambda p: (
                not (
                    '循环' in p.get('rationale', '')
                    and p.get('after', '').count('for') > p.get('before', '').count('for') + 3
                )
            ),
            'reason': '禁止错误循环展开（for循环数量异常增加）',
            'severity': 'block',
        },
        'no_code_bloat': {
            'check': lambda p: (
                len(p.get('after', '')) <= len(p.get('before', '')) * 1.5 or len(p.get('after', '')) < 500
            ),
            'reason': '禁止代码膨胀（超过1.5倍或500字符）',
            'severity': 'warn',
        },
    }

    def __init__(self):
        self._init_db()

    def _init_db(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.DB_PATH)
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS review_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patch_target TEXT,
                patch_action TEXT,
                patch_rationale TEXT,
                verdict TEXT,
                reasons TEXT,
                reviewer_score REAL,
                created_at REAL
            );
        """)
        conn.commit()
        conn.close()

    def review(self, patch_dict: Dict) -> Dict:
        """审查补丁"""
        issues = []
        block = False

        for rule_name, rule in self.RULES.items():
            try:
                passed = rule['check'](patch_dict)
                if not passed:
                    issues.append(
                        {
                            'rule': rule_name,
                            'reason': rule['reason'],
                            'severity': rule['severity'],
                        }
                    )
                    if rule['severity'] == 'block':
                        block = True
            except Exception:
                pass

        # 计算审查分数
        total_rules = len(self.RULES)
        passed_rules = total_rules - len(issues)
        score = passed_rules / total_rules if total_rules > 0 else 0

        # 最终裁决
        if block:
            verdict = 'reject'
        elif len(issues) > 2:
            verdict = 'revise'
        else:
            verdict = 'approve'

        result = {
            'verdict': verdict,
            'score': score,
            'issues': issues,
            'total_rules': total_rules,
            'passed_rules': passed_rules,
        }

        # 记录审查历史
        self._record_review(patch_dict, result)

        return result

    def _record_review(self, patch_dict: Dict, result: Dict):
        """记录审查历史"""
        conn = sqlite3.connect(self.DB_PATH)
        conn.execute(
            """
            INSERT INTO review_history
            (patch_target, patch_action, patch_rationale, verdict, reasons, reviewer_score, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
                patch_dict.get('target', ''),
                patch_dict.get('action', ''),
                patch_dict.get('rationale', ''),
                result['verdict'],
                json.dumps(result['issues'], ensure_ascii=False),
                result['score'],
                time.time(),
            ),
        )
        conn.commit()
        conn.close()

    def get_stats(self) -> Dict:
        """获取审查统计"""
        conn = sqlite3.connect(self.DB_PATH)
        rows = conn.execute('SELECT verdict, COUNT(*) FROM review_history GROUP BY verdict').fetchall()
        total = conn.execute('SELECT COUNT(*) FROM review_history').fetchone()[0]
        conn.close()

        stats = {'total': total}
        for verdict, count in rows:
            stats[verdict] = count
        return stats

    def summary(self) -> str:
        stats = self.get_stats()
        approve_rate = stats.get('approve', 0) / max(stats['total'], 1)
        return (
            f'审查: {stats["total"]}次 | '
            f'通过: {stats.get("approve", 0)} ({approve_rate:.0%}) | '
            f'拒绝: {stats.get("reject", 0)} | '
            f'修改: {stats.get("revise", 0)}'
        )


# ── Patch历史数据库 ──
