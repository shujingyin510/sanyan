"""皮肤管理器：加载并切换语言皮肤，保护三态词根"""
import json
import os

class SkinManager:
    # 根三态词表（中文，永远可用）
    ROOT_TERNARY = {
        '真': 1, '亮': 1, '有': 1, '是': 1,
        '假': -1, '灭': -1, '无': -1, '否': -1,
        '可能': 0, '守': 0, '待': 0, '未知': 0
    }

    def __init__(self, lang='zh'):
        self.lang = lang
        self.skin_data = {}
        self.ternary_map = dict(self.ROOT_TERNARY)  # 初始化为根表
        self._load_skin(lang)

    def _load_skin(self, lang):
        """加载皮肤 JSON 文件，合并三态词表"""
        path = os.path.join('language', f'{lang}.json')
        if not os.path.exists(path):
            raise FileNotFoundError(f"皮肤文件不存在: {path}")
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        self.skin_data = data
        self.lang = lang

        # 合并三态词：保留根表，追加皮肤定义的同义词
        self.ternary_map = dict(self.ROOT_TERNARY)
        states = data.get('ternary_states', {})
        for word in states.get('true', []):
            self.ternary_map[word] = 1
        for word in states.get('false', []):
            self.ternary_map[word] = -1
        for word in states.get('maybe', []):
            self.ternary_map[word] = 0

    def get_keyword(self, internal):
        """内部标识 → 当前语言关键字"""
        return self.skin_data.get('keywords', {}).get(internal, internal)

    def get_op(self, internal):
        """内部标识 → 当前语言操作符"""
        return self.skin_data.get('operators', {}).get(internal, internal)

    def get_internal_keyword(self, word):
        """当前语言关键字 → 内部标识（反向查找）"""
        for intern, name in self.skin_data.get('keywords', {}).items():
            if name == word:
                return intern
        return None

    def get_internal_op(self, word):
        """当前语言操作符或符号 → 内部标识（反向查找）"""
        for intern, name in self.skin_data.get('operators', {}).items():
            if name == word:
                return intern
        return None

    def is_ternary_word(self, word):
        """判断是否为三态词，返回对应整数值 1/0/-1，否则返回 None"""
        return self.ternary_map.get(word)

    def switch_skin(self, lang):
        self._load_skin(lang)