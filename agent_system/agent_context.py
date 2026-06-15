"""智能上下文压缩 — 分层摘要 + 滑动窗口 + 重要性评分
P22: SmartContextCompressor — 多策略上下文压缩
P23: ImportanceScorer — 关键决策点识别与保留
P24: SlidingWindowBuffer — 滑动窗口 + 重要性缓冲
"""

import re
from collections import deque
from typing import Any, Dict, List, Tuple, Optional


class ImportanceScorer:
    """重要性评分器：识别关键决策点"""

    HIGH_IMPORTANCE_PATTERNS = [
        (r'error|错误|失败|异常', 2.0),
        (r'done|完成|成功|通过', 1.5),
        (r'replace|替换|修改|写入', 1.3),
        (r'测试|test|验证', 1.2),
        (r'决策|选择|方案|计划', 1.1),
        (r'发现|找到|定位|搜索', 1.0),
    ]

    LOW_IMPORTANCE_PATTERNS = [
        (r'分析|analyze|结构', 0.7),
        (r'列文件|list', 0.5),
        (r'git.*状态|git.*status', 0.4),
    ]

    def score(self, text: str) -> float:
        """计算文本重要性分数"""
        score = 1.0
        text_lower = text.lower()

        for pattern, multiplier in self.HIGH_IMPORTANCE_PATTERNS:
            if re.search(pattern, text_lower):
                score *= multiplier

        for pattern, multiplier in self.LOW_IMPORTANCE_PATTERNS:
            if re.search(pattern, text_lower):
                score *= multiplier

        # 长度惩罚：过长的文本可能不那么重要
        if len(text) > 500:
            score *= 0.8

        return score

    def rank_entries(self, entries: List[Dict[str, Any]]) -> List[Tuple[float, Dict]]:
        """对条目按重要性排序"""
        scored = []
        for entry in entries:
            text = str(entry.get('result', '')) + str(entry.get('params', ''))
            importance = self.score(text)
            scored.append((importance, entry))
        scored.sort(key=lambda x: -x[0])
        return scored


class SlidingWindowBuffer:
    """滑动窗口 + 重要性缓冲：保留最近N条 + 高重要性历史"""

    def __init__(self, window_size: int = 20, important_reserve: int = 5):
        self.window_size = window_size
        self.important_reserve = important_reserve
        self._buffer: deque = deque(maxlen=window_size)
        self._important: List[Dict] = []
        self.scorer = ImportanceScorer()

    def add(self, entry: Dict[str, Any]):
        """添加条目"""
        self._buffer.append(entry)

        # 检查是否重要
        text = str(entry.get('result', '')) + str(entry.get('params', ''))
        importance = self.scorer.score(text)
        if importance > 1.5:
            self._important.append({**entry, '_importance': importance})
            # 保持重要条目列表大小
            if len(self._important) > self.important_reserve * 2:
                self._important.sort(key=lambda x: -x.get('_importance', 0))
                self._important = self._important[: self.important_reserve]

    def get_recent(self, n: Optional[int] = None) -> List[Dict]:
        """获取最近N条"""
        n = n or self.window_size
        return list(self._buffer)[-n:]

    def get_important(self) -> List[Dict]:
        """获取重要历史条目"""
        return self._important[: self.important_reserve]

    def get_combined(self, max_entries: int = 30) -> List[Dict]:
        """获取组合视图：重要历史 + 最近窗口"""
        important = self.get_important()
        recent = self.get_recent(max_entries - len(important))

        # 去重（基于时间戳）
        seen = set()
        combined = []
        for entry in important + recent:
            key = (entry.get('tool', ''), entry.get('round', 0))
            if key not in seen:
                seen.add(key)
                combined.append(entry)

        return combined

    def compress(self) -> str:
        """压缩为摘要文本"""
        combined = self.get_combined()
        if not combined:
            return ''

        parts = []
        for entry in combined:
            tool = entry.get('tool', '?')
            result = str(entry.get('result', ''))[:100]
            importance = entry.get('_importance', 1.0)
            marker = '★' if importance > 1.5 else '·'
            parts.append(f'{marker} [{tool}] {result}')

        return '\n'.join(parts)


class SmartContextCompressor:
    """智能上下文压缩：多策略组合"""

    def __init__(self, max_tokens: int = 7000, window_size: int = 20):
        self.max_tokens = max_tokens
        self.window = SlidingWindowBuffer(window_size=window_size)
        self.scorer = ImportanceScorer()
        self._compression_count = 0

    def add_entry(self, tool: str, params: str, result: str, round_num: int = 0):
        """添加新条目"""
        self.window.add(
            {
                'tool': tool,
                'params': str(params)[:200],
                'result': str(result)[:500],
                'round': round_num,
            }
        )

    def compress_context(self, task: str, current_ctx: str = '') -> str:
        """压缩上下文，保留关键信息"""
        self._compression_count += 1

        # 策略1: 保留任务行
        task_line = f'任务: {task}'

        # 策略2: 获取重要+最近条目
        combined = self.window.get_combined(max_entries=25)

        # 策略3: 分层摘要
        if len(combined) > 15:
            # 头部：最近5条（详细）
            recent = combined[-5:]
            # 中间：10条（压缩）
            middle = combined[-15:-5]
            # 尾部：高重要性条目
            important = [e for e in combined if e.get('_importance', 1.0) > 1.5][:3]

            parts = [task_line]
            if important:
                parts.append('[关键历史]')
                for e in important:
                    parts.append(f'  {e.get("tool", "?")}: {str(e.get("result", ""))[:80]}')

            parts.append('[近期操作]')
            for e in middle:
                tool = e.get('tool', '?')
                result = str(e.get('result', ''))[:60]
                parts.append(f'  {tool}: {result}')

            parts.append('[最新]')
            for e in recent:
                tool = e.get('tool', '?')
                result = str(e.get('result', ''))[:150]
                parts.append(f'  {tool}: {result}')

            return '\n'.join(parts)
        else:
            # 少量条目，直接压缩
            return self._simple_compress(task, combined)

    def _simple_compress(self, task: str, entries: List[Dict]) -> str:
        """简单压缩：直接拼接"""
        parts = [f'任务: {task}']
        for entry in entries:
            tool = entry.get('tool', '?')
            result = str(entry.get('result', ''))[:150]
            parts.append(f'[{tool}] {result}')
        return '\n'.join(parts)

    def estimate_tokens(self, text: str) -> int:
        """估算token数（粗略）"""
        return len(text) // 2  # 中文约2字符1token

    def needs_compression(self, text: str) -> bool:
        """是否需要压缩"""
        return self.estimate_tokens(text) > self.max_tokens

    def get_stats(self) -> Dict[str, Any]:
        """获取压缩统计"""
        return {
            'compression_count': self._compression_count,
            'buffer_size': len(self.window._buffer),
            'important_entries': len(self.window._important),
        }
