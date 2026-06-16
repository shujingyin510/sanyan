"""Myth Shield — 怀疑机制层

三层防护:
    1. Common Myth Shield: 模式识别 → 置信度上限 0.6
    2. Belief Conflict Detector: 误解字典 → 冲突降权
    3. Misconception Routing: FACT→直出 / MYTH→反驳 / UNCERTAIN→弃权

Usage:
    shield = MythShield()
    route = shield.route_question("手机辐射会致癌吗？")
    # -> ("myth", 0.5, "已匹配误解: 手机辐射不致癌")
"""

import re
from typing import Tuple, Optional


# ── 50 条常见误解字典 ──

MISCONCEPTIONS = {
    # 健康类
    '手机辐射': '手机辐射不致癌，WHO将其列为2B类(可能致癌)，与咖啡同级',
    '大脑10%': '人类使用了大脑的100%，只是不同区域不同时间活跃',
    '糖多动': '糖不会导致儿童多动症，多项双盲研究已证实',
    '味觉区域': '舌头没有分区味觉，所有味蕾能感知所有味道',
    '左脑右脑': '左右脑分工是伪科学，两侧协同工作而非严格分工',
    '维C感冒': '维C不能预防感冒，仅能略微缩短病程',
    '疫苗自闭': '疫苗不会导致自闭症，始作俑者论文已被撤稿',
    '冷水感冒': '寒冷不会直接导致感冒，感冒由病毒引起',
    '食物相克': '食物相克缺乏科学依据',
    '排毒疗法': '人体自身有肝脏肾脏排毒，商业排毒产品无科学依据',
    # 科学类
    '公牛红色': '公牛是色盲，对红色无反应，激怒它的是斗篷抖动',
    '太阳颜色': '太阳是白色的，大气散射使它看起来偏黄',
    '长城太空': '肉眼从太空看不到长城，需特定条件才能分辨',
    '闪电两次': '闪电可以多次击中同一位置，摩天大楼常被反复击中',
    '蝙蝠瞎': '蝙蝠不瞎，部分种类视力甚至优于人类',
    '金鱼记忆': '金鱼记忆远超3秒，可达数月并能识别主人',
    '金字塔': '埃及金字塔主要由雇佣工人而非奴隶建造',
    '舌头地图': '味觉地图从不存在，所有舌面都能感知五味',
    '黑洞吞噬': '黑洞不会吞噬一切，在视界之外物质可以逃脱',
    '进化线性': '进化不是从低级到高级的线性过程，人类没停止进化',
    # 历史类
    '拿破仑身高': '拿破仑身高约168cm，在当时属法国平均身高',
    '中世黑暗': '中世纪并非完全黑暗时代，有大量学术和科技发展',
    '哥伦布': '哥伦布发现美洲时原住民早已居住数万年',
    '玛丽': "玛丽·安托瓦内特从未说过'让他们吃蛋糕'",
    '铁处女': '中世纪不存在铁处女刑具，是18世纪虚构',
    # 动物类
    '鸵鸟埋沙': '鸵鸟遇险不会把头埋进沙里，它会逃跑或战斗',
    '旅鼠自杀': '旅鼠不会集体自杀跳崖，该镜头是迪士尼人为制造的',
    '变色龙': '变色龙变色主要用于社交沟通而非伪装',
    '牛群': '牛并不是色盲，它们能看到黄色和蓝色',
}

# ── 神话模式正则 ──

MYTH_PATTERNS = [
    r'.*会(不会)?导致.*(癌|病|胖|瘦|秃|瞎).*[？?]?$',
    r'.*是不是.*(只|才|就|都).*[？?]?$',
    r'.*真的.*(会|能|可以).*吗[？?]?$',
    r'.*只有.*(才|才会|能|才能).*[？?]?$',
    r'.*一直.*(都会|都是).*[？?]?$',
    r'.*会不会.*[？?]?$',
    r'.*X.*导致.*Y.*[？?]?$',
    r'.*(可不可以|能不有|能不).*[？?]?$',
]

# ── 不确定模式 ──

UNCERTAIN_PATTERNS = [
    r'.*未来.*(会|能|可以|将).*[？?]?$',
    r'.*(存在|有没有|是否存在).*(外星|灵魂|神|鬼|来生).*[？?]?$',
    r'.*明年.*(会|能|将).*[？?]?$',
    r'.*(宇宙|世界).*(边界|尽头|起源).*[？?]?$',
    r'.*永远.*[？?]?$',
    r'.*所有人.*都会.*[？?]?$',
    r'.*AI.*(取代|替代|消灭).*[？?]?$',
    r'.*量子.*统一.*[？?]?$',
    r'.*最.*语言.*[？?]?$',
]


class MythShield:
    """怀疑机制 —— 问题先过盾再回答"""

    def __init__(self):
        self._myth_cache = {}

    def detect_myth_pattern(self, question: str) -> bool:
        """检测问题是否匹配神话/误解模式"""
        for pattern in MYTH_PATTERNS:
            if re.match(pattern, question):
                return True
        return False

    def detect_uncertain_pattern(self, question: str) -> bool:
        """检测问题是否属于不可知类型"""
        for pattern in UNCERTAIN_PATTERNS:
            if re.match(pattern, question):
                return True
        return False

    def find_misconception(self, question: str) -> Optional[str]:
        """查找问题是否匹配已知误解"""
        q_low = question.lower()
        for keyword, truth in MISCONCEPTIONS.items():
            if keyword.lower() in q_low:
                return truth
        return None

    def get_skepticism_level(self, question: str) -> float:
        """返回怀疑级别 0.0-1.0（越高越需要怀疑）"""
        score = 0.0

        if self.detect_myth_pattern(question):
            score += 0.4
        if self.find_misconception(question):
            score += 0.3
        if self.detect_uncertain_pattern(question):
            score += 0.2

        return min(score, 0.9)

    def route_question(self, question: str) -> Tuple[str, float, str]:
        """路由问题 → (类型, 置信度上限, 理由)

        返回类型: fact / myth / uncertain
        """
        # 1. 检查不可知
        if self.detect_uncertain_pattern(question):
            return ('uncertain', 0.3, '问题本身不可知，应弃权')

        # 2. 检查已知误解
        truth = self.find_misconception(question)
        if truth:
            return ('myth', 0.5, f'已匹配误解: {truth[:60]}')

        # 3. 检查神话模式
        if self.detect_myth_pattern(question):
            return ('myth', 0.6, '匹配神话模式，需降低置信度')

        # 4. 默认事实
        return ('fact', 0.95, '未匹配任何怀疑模式')

    def apply_shield(self, question: str, answer: str, confidence: float = 0.9) -> Tuple[str, float, str, str]:
        """对 LLM 回答施加怀疑盾

        返回: (修正后回答, 修正后置信度, 路由类型, 理由)
        """
        route_type, cap, reason = self.route_question(question)
        skepticism = self.get_skepticism_level(question)

        # 置信度修正: 原始 × (1 - 怀疑度)
        adjusted_conf = min(confidence, cap) * (1.0 - skepticism)
        adjusted_conf = max(0.1, min(0.99, adjusted_conf))

        # 神话/误解 → 追加质疑标注
        if route_type == 'myth':
            truth = self.find_misconception(question)
            if truth:
                adjusted_answer = f'{answer}  [⚠ 此话题存在常见误解: {truth}]'
            else:
                adjusted_answer = f'{answer}  [⚠ 此问题模式常见于误解，需谨慎]'
        elif route_type == 'uncertain':
            # 过度自信 → 强制收回
            uncertain_keywords = ['不确定', '无法确定', '不知道']
            if not any(w in answer for w in uncertain_keywords):
                adjusted_answer = f'不确定  [原回答已撤回: {reason}]'
            else:
                adjusted_answer = answer
        else:
            adjusted_answer = answer

        return adjusted_answer, adjusted_conf, route_type, reason

    def summary(self, results: list) -> dict:
        """统计盾牌效果"""
        total = len(results)
        routed_myth = sum(1 for r in results if r.get('route') == 'myth')
        routed_uncertain = sum(1 for r in results if r.get('route') == 'uncertain')
        routed_fact = sum(1 for r in results if r.get('route') == 'fact')
        caps_applied = sum(1 for r in results if r.get('adjusted_conf', 0.9) < 0.9)

        return {
            'total': total,
            'routed_myth': routed_myth,
            'routed_uncertain': routed_uncertain,
            'routed_fact': routed_fact,
            'confidence_capped': caps_applied,
        }


# ── 单例 ──
_shield_instance = None


def get_shield() -> MythShield:
    global _shield_instance
    if _shield_instance is None:
        _shield_instance = MythShield()
    return _shield_instance
