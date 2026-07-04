"""TernaryEngine: 三态认知计算框架
面向不确定性决策 — Kleene传播 × 贝叶斯置信度 × 保护门控
用法: Agent/IoT/Village 共用
"""
# ====== TernaryEngine: 三态决策核心 ======


class TernaryEngine:
    """三态决策引擎：移植自 decision.san

    每步工具调用 → cog分类 → 三态映射(-1/0/1) → Kleene传播 → 置信度衰减 → 保护门控
    """

    COG_MAP = {'AFFIRM': 1, 'NEGATE': -1, 'CONFLICTED': -1}
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
        'replace_lines': 0.60,
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
        """工具执行后分类认知态 — 五态（非简单二值）"""
        result_str = str(result).lower()
        r = str(result)

        # ── 读类工具：返回值是内容负载（代码/搜索结果天然含 error/失败 字样），
        #    失败判定只看工具自身错误信封（前缀区），绝不嗅探负载正文。
        #    P2 探针#8 实测：read_file 读回 ternary_match 函数体被全文嗅探判成
        #    高置信 NEGATE(0.77)，门控当场断轮 —— string sniff 假阳性在读操作还魂。 ──
        if tool in ('read_file', 'search_code', 'analyze', 'find_symbol', 'list_files', 'git_diff', 'git_status'):
            head = r[:80]
            if '错误' in head or '未找到' in head or 'No such file' in head or head.startswith('(空:'):
                return 'UNCERT'  # 工具错误信封：可恢复（路径/范围问题，非逻辑错误）
            if not r.strip():
                return 'UNCERT'  # 空负载：无信息量
            return 'AFFIRM'

        # ── NEGATE: 明确失败 ──
        if 'error' in result_str and 'No such file' not in r:
            return 'NEGATE'
        if 'fail' in result_str or 'traceback' in result_str:
            return 'NEGATE'
        if '不支持' in r or 'denied' in result_str or 'forbidden' in result_str:
            return 'NEGATE'
        if tool == 'run_shell' and ('rc=1' in r or 'rc=2' in r):
            return 'NEGATE'
        if tool == 'run_test' and ('FAIL' in r or 'fail' in r or '失败' in r):
            return 'NEGATE'

        # ── UNCERT: 模糊/部分成功 ──
        if 'No such file' in r or '找不到' in r:
            return 'UNCERT'  # 可能是路径问题，非逻辑错误
        if tool == 'write_file' and '已写入' in r:
            return 'AFFIRM'
        if tool in ('replace_in_file', 'replace_lines', 'replace_all'):
            if '未找到' in r or '语法错误' in r or '行区间无效' in r:
                return 'UNCERT'  # 目标文本不精确/写坏被守卫还原——可恢复，非逻辑错误
            if '已' in r or '共' in r:
                return 'AFFIRM'
        if tool == 'done':
            return 'AFFIRM'

        # ── AFFIRM: 明确成功 ──
        if '通过' in r or 'ok' in r or 'success' in result_str:
            return 'AFFIRM'
        if '⚠' in r and len(r) > 50:
            return 'AFFIRM'  # 分析结果（有内容）

        # ── CONFLICTED: 矛盾信号 ──
        if 'error' in result_str and 'ok' in result_str:
            return 'CONFLICTED'

        # ── 默认：不确定 ──
        return 'UNCERT'

    def map_trit(self, cog):
        return self.COG_MAP.get(cog, 0)

    def propagate(self, upstream_trit, current_trit):
        return self.KLEENE.get((upstream_trit, current_trit), current_trit)

    def confidence(self, cog, tool=''):
        base = {'AFFIRM': 0.9, 'NEGATE': 0.85, 'UNCERT': 0.4}.get(cog, 0.5)
        tool_conf = self.TOOL_CONFIDENCE.get(tool, 0.7)
        return min(0.99, max(0.01, base * tool_conf))

    def propagate_confidence(self, upstream_conf, current_conf, current_trit=0):
        # ⑦ 置信度回血：本步成功(AFFIRM, trit=1)用几何均值向当前步收敛——健康长链稳在
        # 高位，不再被"跑得久"乘性稀释到 0.01（旧行为让 NEGATE 门失灵：晚到的失败因低
        # 置信落进"可重试"而非"停止"，长成功链还会撞上"信息增益不足"误判人工介入）。
        # 失败/不确定(默认)仍乘性衰减，疑虑逐步累积——偶发成功不一笔勾销既有失败信号。
        if current_trit == 1:
            blended = (max(upstream_conf, 0.01) * max(current_conf, 0.01)) ** 0.5
            return min(0.99, max(0.01, blended))
        return min(0.99, max(0.01, upstream_conf * current_conf))

    def protect(self, risk, trit, confidence, history):
        """三态门控：基于认知态决定执行策略"""
        # 高风险 + 非肯定 → 拒绝
        if risk == '高' and trit <= 0:
            return {'action': 'block', 'reason': '高风险+不确定=拒绝', 'conf': confidence}

        # NEGATE + 高置信 → 停止
        if trit == -1 and confidence > 0.6:
            return {'action': 'block', 'reason': f'高置信拒绝({confidence:.2f})', 'conf': confidence}

        # NEGATE + 低置信 → 可重试（可能是临时错误）
        if trit == -1 and confidence < 0.4:
            return {'action': 'retry', 'reason': f'低置信拒绝({confidence:.2f})，可重试', 'conf': confidence}

        # UNCERT 积累 → 犹豫计数
        if trit == 0:
            if self.hesitation >= self.max_hesitation:
                vote = self._majority(history)
                return {
                    'action': 'block',
                    'reason': f'犹豫{self.hesitation}次，多数判定={vote}',
                    'vote': vote,
                    'conf': confidence,
                }
            return {'action': 'continue', 'reason': f'不确定({confidence:.2f})，继续观察', 'conf': confidence}

        # CONFLICTED → 降级为 UNCERT 处理
        if trit == 0 and self.hesitation > 0:  # CONFLICTED maps to trit=0
            return {'action': 'continue', 'reason': '信号矛盾，继续收集信息', 'conf': confidence}

        # 置信度衰减检测
        if history:
            hist_avg = sum(c for _, c in history[-5:]) / min(len(history), 5)
            gain = abs(confidence - hist_avg)
            # ⑦ 仅"低置信 + 无增益"才判停滞：高置信稳态是健康收敛（回血后长成功链常驻
            # 高位），不该逼人工介入；真正卡死的是低置信还原地打转。
            if gain < self.min_gain and len(history) >= 4 and confidence < 0.6:
                return {'action': 'block', 'reason': '信息增益不足，建议人工介入', 'conf': confidence}

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
        propagated_conf = self.propagate_confidence(upstream_conf, conf, trit)

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
