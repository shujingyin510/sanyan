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

    喂入契约（0707 第十轮回敲）：**只喂解析失败（tool=None）的输出**。
    原先每轮 raw 全喂——模板化 JSON 工具调用只有参数在变，累积重复 token
    使 UR 单调衰减，第 4 条必然跌破 0.5，把参数各异的正常探索在 r3-r8 误杀
    （首个全零超时窗口 4/4 尝试全灭于 UR≈0.47）。真工具调用的打转由
    results_degenerate（3 连同结果）+ 同工具限额守着；本检测的独特价值是
    兜住"解析不出工具调用的重复胡言"（不进 history，results_degenerate
    看不见）——那种 UR < 0.3；多样化散文（各说各话）UR ≥ 0.5 不误伤，由
    轮数上限/预算兜底。阈值 0.5 为 P2 探针调参（原 0.85 连工具调用都误杀）。
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
