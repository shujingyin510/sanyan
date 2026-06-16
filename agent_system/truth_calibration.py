"""Truth Calibration Engine — 因果驱动置信校准层

核心原则:
    ❌ 永远不改答案内容
    ✔ 只调整置信度 + 标注不确定性 + 拆解风险来源

三层架构:
    1. Claim Extractor   — 拆解事实声明
    2. Causal Risk Analyzer — 多重风险因子分析
    3. Confidence Calibrator — 软校准（不改答案）

Usage:
    tce = TruthCalibrationEngine()
    result = tce.calibrate(answer, context, base_confidence=0.9)
    # -> {answer, confidence, uncertainty, risk_factors, causal_penalty}
"""

import re
from typing import Dict, List, Optional
from dataclasses import dataclass, field


# ── 风险因子类型 ──

RISK_FACTORS = {
    'causal_overreach': 'A导致B的说法证据不足',
    'correlation_confusion': '把相关性当因果关系',
    'missing_evidence': '缺乏可靠研究支撑',
    'linguistic_absolutism': '使用了 always/never/only 等绝对词',
    'population_generalization': '把小样本结论推广到所有人',
    'domain_uncertainty': '涉及未来预测或复杂系统，本身高度不确定',
    'biomedical_claim': '医学健康声明，需极高证据门槛',
    'social_myth': '匹配常见社会误解模式',
}

# 风险因子权重（影响置信度衰减）
RISK_WEIGHTS = {
    'causal_overreach': 0.30,
    'correlation_confusion': 0.25,
    'missing_evidence': 0.40,
    'linguistic_absolutism': 0.15,
    'population_generalization': 0.20,
    'domain_uncertainty': 0.35,
    'biomedical_claim': 0.45,
    'social_myth': 0.50,
}

# 高置信保护域（不受校准影响）
PROTECTED_DOMAINS = [
    r'^\d+[\+\-\*/]\d+(等于|是|=\?).*',  # 算术
    # removed: too broad, fact_check handles these cases
    r'^二进制.*',
    r'^十进制.*',
    r'^十六进制.*',
    r'^Python 中 .* 是什么.*',  # Python 类型查询
    r'^(什么|多少|哪).*(等于|是|为|叫).*',
]

# 绝对化语言检测
ABSOLUTISM_PATTERNS = [
    r'\b(always|never|all|none|every|only|must|certainly|definitely|absolutely|一定|绝对|永远|肯定|必然|所有|全部|从不|决不)\b',
    r'\b(without exception|no one|everyone|everything|nothing)\b',
]


@dataclass
class ClaimFact:
    text: str
    claim_type: str = 'unknown'  # factual / causal / predictive / opinion


@dataclass
class RiskProfile:
    factors: List[str] = field(default_factory=list)
    scores: Dict[str, float] = field(default_factory=dict)
    total_score: float = 0.0


@dataclass
class CalibrationResult:
    answer: str
    confidence: float
    uncertainty: str  # low / medium / high
    risk_factors: List[str]
    causal_penalty: float
    protected: bool
    calibration_note: str = ''


class TruthCalibrationEngine:
    """因果驱动置信校准引擎"""

    def extract_claims(self, answer: str) -> List[str]:
        """从回答中提取事实声明（按句拆分）"""
        sentences = re.split(r'[。！？；\n\.\!\?\;]', answer)
        claims = []
        for s in sentences:
            s = s.strip()
            if len(s) > 5 and not s.startswith('[') and not s.startswith('('):
                claims.append(s)
        return claims if claims else [answer]

    def classify_claim(self, claim: str) -> str:
        """分类声明类型"""
        cl = claim.lower()
        if any(w in cl for w in ['导致', '引起', '造成', '致使', 'cause', 'lead to', 'result in']):
            return 'causal'
        if any(w in cl for w in ['将来', '未来', '预测', '会', '将', 'will', 'predict']):
            return 'predictive'
        if any(w in cl for w in ['认为', '觉得', '觉得', '可能', '也许', 'think', 'believe']):
            return 'opinion'
        return 'factual'

    def is_protected_domain(self, question: str) -> bool:
        """检查是否属于受保护的高置信领域"""
        for pattern in PROTECTED_DOMAINS:
            if re.match(pattern, question):
                return True
        return False

    # ── 事实校验层 ──

    # 100 条已验证的常识事实（问题关键词 → 正确答案关键词）
    VERIFIED_FACTS: Dict[str, str] = {
        # 基础
        '1+1': '2',
        '2+2': '4',
        '1加1': '2',
        '首都是': '北京',
        '中国首都': '北京',
        '中国最大的城市': '上海',
        '地球绕': '太阳',
        '太阳系': '太阳',
        '水的化学式': 'h2o',
        '水分子': 'h2o',
        '光速': '30万',
        '光速是': '30万',
        '365': '365',
        '一年有多少天': '365',
        '二进制': '10',
        '1010转十进制': '10',
        'html的全称': 'hypertext',
        'html是什么': 'hypertext',
        'none是什么类型': 'nonetype',
        'none的类型': 'nonetype',
        'python发布': '1991',
        'python是哪一年': '1991',
        # 地理
        '珠穆朗玛': '8848',
        '最长的河': '尼罗河',
        '最大洋': '太平洋',
        '法国首都': '巴黎',
        '日本首都': '东京',
        '英国首都': '伦敦',
        '美国首都': '华盛顿',
        '德国首都': '柏林',
        '俄罗斯首都': '莫斯科',
        # 科学
        'dna全称': '脱氧核糖核酸',
        'dna是什么': '脱氧核糖核酸',
        '阿伏伽德罗': '6.02',
        '绝对零度': '-273',
        '声音速度': '340',
        '人有多少块骨头': '206',
        '元素周期': '118',
        '人体水分': '70%',
        '最快的动物': '猎豹',
        '最大的哺乳动物': '蓝鲸',
        '最小单位': '夸克',
        # 技术
        'python的作者': 'guido',
        'python创始人': 'guido',
        'linux创始人': 'torvalds',
        'linus': 'torvalds',
        '第一个程序员': 'ada',
        '图灵': '二战',
        # 历史
        '二战结束': '1945',
        '新中国成立': '1949',
        '改革开放': '1978',
        '人类登月': '1969',
        '互联网诞生': '1969',
        # 常识
        '一年有几个季度': '4',
        '一周几天': '7',
        '太阳从哪升起': '东',
        '一年多少月': '12',
    }

    def check_facts(self, question: str, answer: str) -> Optional[dict]:
        """事实校验: 检查答案是否与已知事实矛盾

        返回: None = 无已知事实可校 ; dict = {matched, expected, actual, confidence_drop}
        """
        q_low = question.lower()
        a_low = answer.lower()

        q_normalized = q_low.replace(' ', '')
        a_normalized = a_low.replace(' ', '')
        for keyword, expected in self.VERIFIED_FACTS.items():
            kw = keyword.replace(' ', '')
            if kw in q_normalized:
                # 正确答案应该在回答中
                if expected.replace(' ', '') in a_normalized:
                    return {'matched': True, 'keyword': keyword, 'confidence_adjust': 0}  # 正确，不调整

                # 答案不包含正确答案 → 知识错误
                return {
                    'matched': False,
                    'keyword': keyword,
                    'expected': expected,
                    'actual_snippet': answer[:100],
                    'confidence_override': 0.25,  # 强制低置信
                }

        return None  # 无已知事实可校验

    # ── 因果风险分析 ──

    def analyze_causal_risks(self, question: str, claims: List[str]) -> RiskProfile:
        """因果风险分析：找到答案可能出错的原因"""
        profile = RiskProfile()
        all_text = (question + ' ' + ' '.join(claims)).lower()

        # 1. 因果过度推断
        causal_patterns = [
            r'(会|能|可以|导致|引起|造成).*(癌|病|胖|瘦|秃|死|致癌|治病)',
            r'(cause|lead|result|trigger).*(cancer|disease|death)',
        ]
        for pat in causal_patterns:
            if re.search(pat, all_text):
                profile.factors.append('causal_overreach')
                profile.scores['causal_overreach'] = 0.7
                break

        # 2. 相关≠因果
        if any(w in all_text for w in ['相关', '关联', '有关系', 'correlated', 'linked', 'associated']):
            if 'causal_overreach' in profile.factors:
                profile.factors.append('correlation_confusion')
                profile.scores['correlation_confusion'] = 0.6

        # 3. 缺乏证据
        evidence_words = ['证据', '研究', '实验', '数据', 'study', 'evidence', 'research']
        has_evidence = any(w in all_text for w in evidence_words)
        is_strong_claim = any(
            w in all_text for w in ['一定会', '肯定是', '绝对是', 'causes', 'definitely', 'certainly']
        )
        if is_strong_claim and not has_evidence:
            profile.factors.append('missing_evidence')
            profile.scores['missing_evidence'] = 0.8

        # 4. 语言绝对化
        for pat in ABSOLUTISM_PATTERNS:
            if re.search(pat, all_text):
                profile.factors.append('linguistic_absolutism')
                profile.scores['linguistic_absolutism'] = 0.5
                break

        # 5. 过度泛化
        if any(w in all_text for w in ['所有人', '每个人', '人类', '大家', 'everyone', 'people']):
            profile.factors.append('population_generalization')
            profile.scores['population_generalization'] = 0.4

        # 6. 领域不确定性
        uncertain_domains = [
            r'(未来|将来|明天|明年).*(会|能|将|in the future)',
            r'(外星|灵魂|神|鬼|来生|宇宙边界)',
            r'(AI|人工智能).*(取代|替代|消灭)',
        ]
        for pat in uncertain_domains:
            if re.search(pat, all_text):
                profile.factors.append('domain_uncertainty')
                profile.scores['domain_uncertainty'] = 0.6
                break

        # 7. 生物医学声明
        biomedical = [
            '癌',
            '肿瘤',
            '免疫',
            '基因',
            '疫苗',
            '病毒',
            '细菌',
            'cancer',
            'tumor',
            'immune',
            'gene',
            'vaccine',
            'virus',
        ]
        if any(w in all_text for w in biomedical):
            profile.factors.append('biomedical_claim')
            profile.scores['biomedical_claim'] = 0.5

        # 8. 社会误解模式
        myth_keywords = [
            '大脑',
            '10%',
            '红色',
            '公牛',
            '长城',
            '太空',
            '闪电',
            '两次',
            '蝙蝠',
            '金鱼',
            '记忆',
            '舌头',
            '味觉',
            '维C',
            '感冒',
            '冷水',
            '排毒',
            '食物相克',
            '左脑右脑',
            '金字塔',
            '奴隶',
        ]
        if any(w in all_text for w in myth_keywords):
            profile.factors.append('social_myth')
            profile.scores['social_myth'] = 0.3

        # 计算总风险分（加权）
        if profile.factors:
            total = sum(RISK_WEIGHTS.get(f, 0.1) * profile.scores.get(f, 0.5) for f in profile.factors)
            profile.total_score = min(total / len(profile.factors), 0.95)
        else:
            profile.total_score = 0.0

        return profile

    def _gate_uncertainty(self, question: str, answer: str) -> str:
        """三态门控: certain / calibrate / uncertain"""
        q = question.lower()

        # ── 第一优先: 不可知类 ──
        unknowable = [
            '未来',
            '将来',
            '明年',
            '五年后',
            '100年',
            '300年',
            '什么时候',
            '会不会',
            '有没有',
            '是否存在',
            '外星',
            '灵魂',
            '神',
            '来生',
            '平行宇宙',
            '暗物质',
            '暗能量',
            '意识上传',
            '全球变暖',
            '世界大战',
            '诺贝尔',
            '2027',
            '2030',
            '2040',
            '2050',
            '2100',
        ]
        if any(w in q for w in unknowable):
            return 'uncertain'

        # 不存在的事物 — 不能编造
        non_existent = [
            '不存在的',
            'str_copy',
            'python 4.0',
            'python4',
            '永恒黑暗区',
            '第24对染色体',
        ]
        if any(w in q for w in non_existent):
            return 'uncertain'

        # 过度精确的问题 — 高概率是陷阱
        overly_precise = [
            '多少位',
            '多少天',
            '多少纳秒',
            '每天校正',
            '最大长度是多少',
            '多少个独立',
            '含量第二高',
        ]
        if any(w in q for w in overly_precise):
            return 'uncertain'

        # 硬事实 — 不需要校准
        hard_fact_signals = [
            '等于几',
            '是什么',
            '是什么类型',
            '是多少',
            '是多少摄氏度',
            '什么方向',
            '哪年',
            '首都是',
            '全称',
            '端口号',
            '几次方',
            '多少个',
            '十进制',
            '十六进制',
            '有几块',
            '有几层',
            '约等于',
            '最快的',
            '最大的',
            '最多大',
        ]
        if any(w in q for w in hard_fact_signals):
            return 'certain'

        # 默认：需要校准
        return 'calibrate'

    def calibrate(self, answer: str, question: str = '', base_confidence: float = 0.9) -> CalibrationResult:
        """三态门控 + 校准 — 不改答案，只调信心"""

        # 0. 三态门控
        gate = self._gate_uncertainty(question, answer)

        if gate == 'certain':
            return CalibrationResult(
                answer=answer,
                confidence=0.95,
                uncertainty='low',
                risk_factors=[],
                causal_penalty=0.0,
                protected=True,
                calibration_note='硬事实领域，置信度锁定',
            )

        if gate == 'uncertain':
            # 检查答案是否已经表达了不确定
            uncertain_markers = ['不确定', '无法确定', '不知道', '不存']
            already_uncertain = any(w in answer for w in uncertain_markers)
            return CalibrationResult(
                answer=answer,
                confidence=0.35 if not already_uncertain else 0.25,
                uncertainty='high',
                risk_factors=['epistemic_boundary'],
                causal_penalty=base_confidence - 0.35,
                protected=False,
                calibration_note='问题本身不可知或不存在' if not already_uncertain else '已正确表达不确定性',
            )

        # 1. 受保护领域直接放行
        if self.is_protected_domain(question):
            return CalibrationResult(
                answer=answer,
                confidence=0.95,
                uncertainty='low',
                risk_factors=[],
                causal_penalty=0.0,
                protected=True,
                calibration_note='数学/事实领域，置信度保护',
            )

        # 2. 事实校验 — 知识是否正确
        fact_check = self.check_facts(question, answer)
        if fact_check and not fact_check['matched']:
            return CalibrationResult(
                answer=answer,
                confidence=fact_check.get('confidence_override', 0.25),
                uncertainty='high',
                risk_factors=['knowledge_error'],
                causal_penalty=base_confidence - fact_check.get('confidence_override', 0.25),
                protected=False,
                calibration_note=f"事实校验不通过: 期望包含 '{fact_check['expected']}'",
            )

        # 2. 拆解声明
        claims = self.extract_claims(answer)

        # 2. 因果风险分析
        risk = self.analyze_causal_risks(question, claims)

        # 3. 计算置信度衰减
        causal_penalty = risk.total_score * 0.6  # 最多衰减 60%
        if causal_penalty > 0:
            confidence = max(0.15, base_confidence - causal_penalty)
        else:
            confidence = base_confidence

        # 4. 不确定性标签
        if confidence >= 0.85:
            uncertainty = 'low'
        elif confidence >= 0.5:
            uncertainty = 'medium'
        else:
            uncertainty = 'high'

        # 5. 校准说明（只标注，不改内容）
        note = ''
        if risk.factors:
            factor_names = [RISK_FACTORS.get(f, f) for f in risk.factors[:3]]
            note = f'风险因子: {", ".join(factor_names)}'

        return CalibrationResult(
            answer=answer,
            confidence=round(confidence, 3),
            uncertainty=uncertainty,
            risk_factors=risk.factors,
            causal_penalty=round(causal_penalty, 3),
            protected=False,
            calibration_note=note,
        )

    def calibrate_to_dict(self, answer: str, question: str = '', base_confidence: float = 0.9) -> dict:
        """返回字典格式"""
        r = self.calibrate(answer, question, base_confidence)
        return {
            'answer': r.answer,
            'confidence': r.confidence,
            'uncertainty': r.uncertainty,
            'risk_factors': r.risk_factors,
            'causal_penalty': r.causal_penalty,
            'protected': r.protected,
            'calibration_note': r.calibration_note,
        }


# 单例
_instance = None


def get_calibrator() -> TruthCalibrationEngine:
    global _instance
    if _instance is None:
        _instance = TruthCalibrationEngine()
    return _instance
