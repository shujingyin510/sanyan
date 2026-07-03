"""loop_policy：从 _run_legacy 抽出的停止条件纯函数 —— 验证与原内联逐位一致 + 边界。"""

from agent_system.loop_policy import context_too_large, llm_output_ur, results_degenerate


def test_results_degenerate():
    # P2 调参：两轮相同不再判死（弱模型重读一次文件是合法起手），三轮才算退化
    assert results_degenerate(['a', 'a']) is False  # 两轮相同 → 给一次恢复机会
    assert results_degenerate(['a', 'a', 'a']) is True  # 三轮相同 → 退化
    assert results_degenerate(['b', 'a', 'a']) is False
    assert results_degenerate(['a', 'b']) is False  # 不同
    assert results_degenerate(['a']) is False
    assert results_degenerate([]) is False
    assert results_degenerate(['x', 'a', 'a', 'a']) is True  # 窗口尾部三连同


def test_context_too_large_boundary():
    assert context_too_large('x' * 7001) is True
    assert context_too_large('x' * 7000) is False  # 边界：> 7000 而非 >=
    assert context_too_large('x' * 6999) is False
    assert context_too_large('x' * 10, limit=5) is True


def test_llm_output_ur_needs_four_outputs():
    assert llm_output_ur(['a', 'b', 'c']) is None  # < 4 条 → 不判定
    assert llm_output_ur([]) is None


def test_llm_output_ur_degenerate():
    same = ['同' * 120] * 4  # 每条 120 字符全同 → token 全同 → UR 极低
    ur = llm_output_ur(same)
    assert ur is not None and ur < 0.30


def test_llm_output_ur_diverse_returns_none():
    # 40 个互不相同的 10 字符 token → UR=1.0 → None（不退化）
    diverse, k = [], 0
    for _ in range(4):
        s = ''
        for _ in range(10):
            s += f'{k:010d}'
            k += 1
        diverse.append(s)
    assert llm_output_ur(diverse) is None


def test_llm_output_ur_structured_tool_calls_not_degenerate():
    # P2 探针#6 误杀回归守护：工具调用 JSON 共享大段前缀、尾部各异（UR≈0.625），
    # 是健康推进而非退化，不得判死
    prefix = '{"tool": "read_file", "args": {"path": "ops/control_ops.py"'  # 共享前缀
    outs, k = [], 0
    for _ in range(4):
        tail = ''
        for _ in range(10):
            tail += f'{k:010d}'
            k += 1
        outs.append((prefix + '0' * (100 - len(prefix)))[:100] + tail[:100])
    ur_val = llm_output_ur(outs)
    assert ur_val is None  # 0.5 ≤ UR < 0.85 区间：旧阈值会误杀，新阈值放行


def test_llm_output_ur_too_few_tokens_none():
    # 输出太短 → tokens < 8 → None（与原内联 len(tokens)>=8 门一致）
    assert llm_output_ur(['ab', 'cd', 'ef', 'gh']) is None
