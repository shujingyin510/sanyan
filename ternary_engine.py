"""TernaryEngine: 三态认知计算框架
面向不确定性决策 — Kleene传播 × 贝叶斯置信度 × 保护门控
用法: Agent/IoT/Village 共用
"""
# ====== TernaryEngine: 三态决策核心 ======


class TernaryEngine:
    """三态决策引擎：移植自 decision.san

    每步工具调用 → cog分类 → 三态映射(-1/0/1) → Kleene传播 → 置信度衰减 → 保护门控
    """

    COG_MAP = {'AFFIRM': 1, 'NEGATE': -1}
    COG_NAMES = {'AFFIRM': '确信', 'NEGATE': '拒绝', 'UNCERT': '不确定', 'CONFLICTED': '矛盾', 'PENDING': '待定'}
    TRIT_NAMES = {1: '真', -1: '假', 0: '可能'}
    KLEENE = {
        (-1, -1): -1,
        (-1, 0): -1,
        (-1, 1): -1,
        (0, -1): -1,
        (0, 0): 0,
        (0, 1): 0,
        (1, -1): -1,
        (1, 0): 0,
        (1, 1): 1,
    }
    TOOL_CONFIDENCE = {
        'analyze': 0.90,
        'find_symbol': 0.85,
        'read_file': 0.90,
        'search_code': 0.85,
        'replace_in_file': 0.60,
        'replace_all': 0.50,
        'write_file': 0.50,
        'run_test': 0.80,
        'git_diff': 0.90,
        'git_status': 0.90,
        'done': 1.0,
    }

    def __init__(self, max_hesitation=3, min_gain=0.05):
        self.history = []  # [(trit, confidence)]
        self.hesitation = 0
        self.max_hesitation = max_hesitation
        self.min_gain = min_gain

    def classify(self, tool, result, scene_risk='低'):
        """工具执行后分类认知态"""
        result_str = str(result).lower()
        if '未找到' in result_str or 'error' in result_str:
            return 'NEGATE'
        if '⚠' in str(result) or '通过' in str(result) or 'ok' in str(result):
            return 'AFFIRM'
        if 'fail' in result_str or '失败' in result_str or '错误' in result_str:
            return 'NEGATE'
        # 修改类工具成功 → AFFIRM
        if tool in ('replace_in_file', 'replace_all', 'write_file'):
            return 'AFFIRM' if '已' in str(result) or '共' in str(result) else 'UNCERT'
        return 'AFFIRM'

    def map_trit(self, cog):
        return self.COG_MAP.get(cog, 0)

    def propagate(self, upstream_trit, current_trit):
        return self.KLEENE.get((upstream_trit, current_trit), current_trit)

    def confidence(self, cog, tool=''):
        base = {'AFFIRM': 0.9, 'NEGATE': 0.85, 'UNCERT': 0.4}.get(cog, 0.5)
        tool_conf = self.TOOL_CONFIDENCE.get(tool, 0.7)
        return min(0.99, max(0.01, base * tool_conf))

    def propagate_confidence(self, upstream_conf, current_conf):
        return min(0.99, max(0.01, upstream_conf * current_conf))

    def protect(self, risk, trit, confidence, history):
        if risk == '高' and trit <= 0:
            return {'action': 'block', 'reason': '高风险+不确定=拒绝', 'conf': confidence}
        if self.hesitation >= self.max_hesitation:
            vote = self._majority(history)
            return {'action': 'block', 'reason': f'犹豫{self.hesitation}次', 'vote': vote, 'conf': confidence}
        # 增益计算
        if history:
            hist_avg = sum(c for _, c in history[-5:]) / min(len(history), 5)
            gain = abs(confidence - hist_avg)
            if gain < self.min_gain:
                return {'action': 'continue', 'reason': '信息增益不足', 'conf': confidence}
        return {'action': 'continue', 'reason': '', 'conf': confidence}

    def step(self, tool, result, risk='低'):
        """执行一步三态决策，返回 (trit, conf, gate_action)"""
        cog = self.classify(tool, result, risk)
        trit = self.map_trit(cog)
        conf = self.confidence(cog, tool)

        upstream_trit = 1
        upstream_conf = 1.0
        if self.history:
            upstream_trit, upstream_conf = self.history[-1]

        propagated = self.propagate(upstream_trit, trit)
        propagated_conf = self.propagate_confidence(upstream_conf, conf)

        if trit == 0:
            self.hesitation += 1

        gate = self.protect(risk, propagated, propagated_conf, self.history)
        self.history.append((propagated, propagated_conf))

        return propagated, propagated_conf, gate, cog

    def _majority(self, hist):
        true_count = sum(1 for t, _ in hist if t == 1)
        false_count = sum(1 for t, _ in hist if t == -1)
        if true_count > false_count:
            return 1
        if false_count > true_count:
            return -1
        return 0

    def summary(self):
        if not self.history:
            return '无记录'
        last_trit, last_conf = self.history[-1]
        name = self.TRIT_NAMES.get(last_trit, '?')
        return f'{name}({last_conf:.2f})'

    def trit_display(self, trit, conf):
        bars = {-1: '○○○', 0: '◐◐◐', 1: '●●●'}
        return f'{self.TRIT_NAMES.get(trit, "?")} {bars.get(trit, "???")} [{conf:.2f}]'

