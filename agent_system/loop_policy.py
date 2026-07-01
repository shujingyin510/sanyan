"""Agent 主循环停止条件（从 _run_legacy 抽出）"""


def results_degenerate(results: list[str]) -> bool:
    """连续两轮结果相同 → 退化"""
    if len(results) < 2:
        return False
    return results[-1] == results[-2]


def context_too_large(text: str, limit: int = 7000) -> bool:
    """上下文超过限制"""
    return len(text) > limit


def llm_output_ur(outputs: list[str]) -> float | None:
    """LLM 输出 UR 退化检测：< 4 条不判定，否则返回 UR 得分"""
    if len(outputs) < 4:
        return None
    unique = len(set(outputs))
    return 1.0 - (unique / len(outputs))
