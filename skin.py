"""皮肤管理器：加载并切换语言皮肤，保护三态词根"""

import json
import os
from ternary_core import TritValue


class SkinManager:
    def __init__(self, lang='chinese'):
        self.lang = lang
        self.skin_data = {}
        self.ternary_map = dict(TritValue.STATE_MAP)  # 以 TritValue.STATE_MAP 为统一来源
        self._load_skin(lang)

    def _load_skin(self, lang):
        """加载皮肤 JSON 文件，合并三态词表"""
        path = os.path.join('language', f'{lang}.json')
        if not os.path.exists(path):
            raise FileNotFoundError(f'皮肤文件不存在: {path}')
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        self.skin_data = data
        self.lang = lang

        # 合并三态词：保留根表，追加皮肤定义的同义词
        self.ternary_map = dict(TritValue.STATE_MAP)
        states = data.get('ternary_states', {})
        for word in states.get('true', []):
            self.ternary_map[word] = 1
        for word in states.get('false', []):
            self.ternary_map[word] = -1
        for word in states.get('maybe', []):
            self.ternary_map[word] = 0

        # 构建反向查找缓存（支持列表多别名和单字符串两种格式）
        self._keyword_cache = {}
        for intern, name_or_names in data.get('keywords', {}).items():
            if isinstance(name_or_names, list):
                for name in name_or_names:
                    self._keyword_cache[name] = intern
            else:
                self._keyword_cache[name_or_names] = intern
        self._op_cache = {}
        for intern, name_or_names in data.get('operators', {}).items():
            if isinstance(name_or_names, list):
                for name in name_or_names:
                    self._op_cache[name] = intern
            else:
                self._op_cache[name_or_names] = intern

    def get_keyword(self, internal):
        """内部标识 → 当前语言关键字（列表时取首个）"""
        val = self.skin_data.get('keywords', {}).get(internal, internal)
        if isinstance(val, list):
            return val[0] if val else internal
        return val

    def get_op(self, internal):
        """内部标识 → 当前语言操作符（列表时取首个）"""
        val = self.skin_data.get('operators', {}).get(internal, internal)
        if isinstance(val, list):
            return val[0] if val else internal
        return val

    def get_internal_keyword(self, word):
        """当前语言关键字 → 内部标识（反向查找）"""
        return self._keyword_cache.get(word)

    def get_internal_op(self, word):
        """当前语言操作符或符号 → 内部标识（反向查找）"""
        return self._op_cache.get(word)

    def is_ternary_word(self, word):
        """判断是否为三态词，返回对应整数值 1/0/-1，否则返回 None"""
        return self.ternary_map.get(word)

    def switch_skin(self, lang):
        lang_map = {'中文': 'chinese', '英文': 'english'}
        lang = lang_map.get(lang, lang)
        self._load_skin(lang)
