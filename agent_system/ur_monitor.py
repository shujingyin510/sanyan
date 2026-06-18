"""UR 退化检测器 — 检测 LLM 是否在重复自己

原理：
  unique_ratio = 窗口内不同 token 数 / 窗口内总 token 数
  UR < 0.30 → LLM 在退化（重复输出）
  UR ≥ 0.30 → LLM 正常生成

应用：
  1. Agent 调 LLM 后检查返回内容的 UR
  2. UR < 0.30 → 标记为退化，停止或换策略
  3. 连续多次退化 → 强制退出

来源：docs/research/ternary_gating_report.md
"""

import re
from typing import List, Tuple


def simple_tokenize(text: str) -> List[str]:
    """简易分词：英文按空格，中文按字"""
    # 英文单词
    en_tokens = re.findall(r'[a-zA-Z_]\w+', text.lower())
    # 中文字符
    cn_tokens = re.findall(r'[\u4e00-\u9fff]', text)
    # 标点
    punct = re.findall(r'[^\w\s]', text)
    return en_tokens + cn_tokens + punct


def calc_ur(tokens: List[str], window: int = 32) -> float:
    """计算 unique_ratio

    Args:
        tokens: token 列表
        window: 滑动窗口大小

    Returns:
        UR 值 (0.0 ~ 1.0)
    """
    if len(tokens) < 8:
        return 1.0  # 太短不算退化

    # 取最后 window 个 token
    recent = tokens[-window:]
    if len(recent) < 8:
        return 1.0

    return len(set(recent)) / len(recent)


def check_degeneration(text: str, window: int = 32, threshold: float = 0.30) -> Tuple[bool, float]:
    """检查文本是否退化

    Args:
        text: LLM 返回的文本
        window: 滑动窗口大小
        threshold: 退化阈值

    Returns:
        (is_degenerate, ur_value)
    """
    tokens = simple_tokenize(text)
    ur = calc_ur(tokens, window)
    return ur < threshold, ur


class URMonitor:
    """UR 监控器：跟踪 LLM 调用的退化情况"""

    def __init__(self, window: int = 32, threshold: float = 0.30, max_degen: int = 3):
        self.window = window
        self.threshold = threshold
        self.max_degen = max_degen  # 连续退化次数上限
        self.history: List[Tuple[str, float, bool]] = []  # (text, ur, is_degenerate)
        self.consecutive_degen = 0

    def check(self, text: str) -> Tuple[bool, float, str]:
        """检查一次 LLM 输出

        Returns:
            (should_stop, ur, reason)
        """
        is_degen, ur = check_degeneration(text, self.window, self.threshold)

        # 记录历史
        self.history.append((text[:100], ur, is_degen))

        if is_degen:
            self.consecutive_degen += 1
            if self.consecutive_degen >= self.max_degen:
                return True, ur, f'连续{self.consecutive_degen}次退化 (UR={ur:.3f})，强制停止'
            return False, ur, f'退化检测 (UR={ur:.3f} < {self.threshold})'
        else:
            self.consecutive_degen = 0
            return False, ur, ''

    def get_stats(self) -> dict:
        """获取统计信息"""
        if not self.history:
            return {'total': 0, 'degen_count': 0, 'avg_ur': 1.0}

        degen_count = sum(1 for _, _, d in self.history if d)
        avg_ur = sum(ur for _, ur, _ in self.history) / len(self.history)

        return {
            'total': len(self.history),
            'degen_count': degen_count,
            'degen_rate': degen_count / len(self.history),
            'avg_ur': avg_ur,
            'consecutive_degen': self.consecutive_degen,
        }

    def reset(self):
        """重置监控器"""
        self.history.clear()
        self.consecutive_degen = 0
