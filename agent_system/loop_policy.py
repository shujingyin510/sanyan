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
    """LLM 输出 UR 退化检测：按 10-字符 token 切分，计算 unique_ratio。
    返回 None 表示不判定（输出 < 4 条 或 tokens < 8 或过于 diverse）。
    """
    if len(outputs) < 4:
        return None

    tokens: list[str] = []
    for text in outputs:
        # 按 10 字符切分为 token
        for i in range(0, len(text), 10):
            tokens.append(text[i : i + 10])

    if len(tokens) < 8:
        return None

    unique = len(set(tokens))
    ur = unique / len(tokens)

    # 过于 diverse → 不退化
    if ur >= 0.85:
        return None

    return ur
