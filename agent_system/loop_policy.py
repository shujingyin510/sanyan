"""Agent 主循环停止条件（从 _run_legacy 抽出）"""


def results_degenerate(results: list[str]) -> bool:
    """连续三轮结果相同 → 退化。

    P2 首跑调参：原为两轮，弱模型重读一次文件（合法起手）即被判死、整轮作废；
    三轮仍足以拦真死循环（外层另有 300s 总超时与轮数上限兜底）。
    """
    if len(results) < 3:
        return False
    return results[-1] == results[-2] == results[-3]


def context_too_large(text: str, limit: int = 7000) -> bool:
    """上下文超过限制"""
    return len(text) > limit


def llm_output_ur(outputs: list[str]) -> float | None:
    """LLM 输出 UR 退化检测：按 10-字符 token 切分，计算 unique_ratio。
    返回 None 表示不判定（输出 < 4 条 或 tokens < 8 或不算退化）。

    阈值 0.5（P2 探针调参，原 0.85）：工具调用回复天生结构相似（每条都是
    `{"tool": ..., "args": ...}` JSON，共享大段前缀），健康推进的 UR 落在
    0.6~0.8，0.85 会误杀；本检测的独特价值是兜住"解析不出工具调用的重复
    胡言"（不进 history，results_degenerate 看不见）——那种 UR < 0.3。
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

    # 结构相似但仍在推进（如连续工具调用）→ 不判退化
    if ur >= 0.5:
        return None

    return ur
