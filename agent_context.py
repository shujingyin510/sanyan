"""上下文压缩：摘要替换 + 证据链精简 + 假设合并
避免 token 爆炸，长对话自动压缩
"""


class ContextCompressor:
    """上下文压缩器"""

    def __init__(self, hard_limit: int = 7000, soft_limit: int = 5000):
        self.hard_limit = hard_limit
        self.soft_limit = soft_limit

    def should_compress(self, ctx: str) -> bool:
        """是否需要压缩"""
        return len(ctx) > self.soft_limit

    def compress(self, ctx: str, llm_fn=None) -> str:
        """压缩上下文"""
        if len(ctx) <= self.soft_limit:
            return ctx
        parts = ctx.split('\n')
        # 策略1：保留任务行和最近内容
        head = []
        tail_start = max(len(parts) - 20, 0)
        for p in parts[:5]:
            if '任务:' in p or 'Plan' in p or '任务' in p:
                head.append(p)
        tail = parts[tail_start:]
        # 策略2：中间部分用LLM摘要
        middle = '\n'.join(parts[5:tail_start])
        if middle and llm_fn:
            summary = llm_fn(f'用一句话总结以下内容:\n{middle[:1500]}')
            if summary and 'error' not in summary.lower():
                head.append(f'[摘要] {summary[:200]}')
        elif middle:
            # 无LLM时截断
            head.append(f'[已省略{len(middle)}字符]')
        return '\n'.join(head + ['[最新]'] + tail)

    def compress_hypotheses(self, hypotheses: list, keep_top: int = 2) -> str:
        """压缩假设历史：只保留Top-N的关键证据"""
        if not hypotheses:
            return ''
        sorted_hyps = sorted(hypotheses, key=lambda h: h.confidence, reverse=True)
        parts = []
        for h in sorted_hyps[:keep_top]:
            evidence_summary = '; '.join(
                f'{e["tool"]}→{["假", "可能", "真"][e["trit"] + 1]}({e["conf"]:.2f})' for e in h.evidence[-3:]
            )
            parts.append(f'H{h.id}: {h.description[:30]} [{evidence_summary}]')
        return '\n'.join(parts)

    def compress_evidence_chain(self, evidence: list, max_items: int = 5) -> str:
        """压缩证据链：只保留关键证据"""
        if not evidence:
            return ''
        # 保留：第一步、最后一步、失败步、最高置信度步
        key_evidence = []
        if evidence:
            key_evidence.append(evidence[0])
        # 失败步
        for e in evidence:
            if e['trit'] == -1 and e not in key_evidence:
                key_evidence.append(e)
        # 最高置信度步
        if evidence:
            best = max(evidence, key=lambda e: e['conf'])
            if best not in key_evidence:
                key_evidence.append(best)
        # 最后一步
        if evidence and evidence[-1] not in key_evidence:
            key_evidence.append(evidence[-1])
        # 限制数量
        key_evidence = key_evidence[:max_items]
        return '; '.join(f'{e["tool"]}→{["假", "可能", "真"][e["trit"] + 1]}({e["conf"]:.2f})' for e in key_evidence)


class TokenBudget:
    """Token 预算管理"""

    def __init__(self, hard_limit: int = 7000, soft_limit: int = 5000):
        self.hard_limit = hard_limit
        self.soft_limit = soft_limit
        self.compressor = ContextCompressor(hard_limit, soft_limit)

    def check(self, ctx: str) -> str:
        """检查并压缩上下文"""
        if len(ctx) <= self.soft_limit:
            return ctx
        if len(ctx) <= self.hard_limit:
            # 软超限：轻量压缩
            return self.compressor.compress(ctx)
        # 硬超限：强制压缩
        return self.compressor.compress(ctx)
