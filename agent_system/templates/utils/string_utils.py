# name: 字符串工具函数
# keywords: 字符串, 反转, 回文, 计数, 统计, string, reverse, palindrome, count


def reverse_string(s: str) -> str:
    """反转字符串"""
    return s[::-1]


def is_palindrome(s: str) -> bool:
    """判断是否为回文字符串

    忽略大小写和非字母数字字符
    """
    s = ''.join(c.lower() for c in s if c.isalnum())
    return s == s[::-1]


def count_chars(s: str) -> dict:
    """统计字符出现次数"""
    result = {}
    for c in s:
        result[c] = result.get(c, 0) + 1
    return result


def count_words(s: str) -> dict:
    """统计单词出现次数"""
    words = s.lower().split()
    result = {}
    for w in words:
        result[w] = result.get(w, 0) + 1
    return result


def caesar_cipher(s: str, shift: int) -> str:
    """凯撒密码加密"""
    result = []
    for c in s:
        if c.isalpha():
            base = ord('A') if c.isupper() else ord('a')
            result.append(chr((ord(c) - base + shift) % 26 + base))
        else:
            result.append(c)
    return ''.join(result)


def is_anagram(s1: str, s2: str) -> bool:
    """判断两个字符串是否为变位词"""
    return sorted(s1.lower()) == sorted(s2.lower())


def longest_common_prefix(strs: list) -> str:
    """最长公共前缀"""
    if not strs:
        return ''
    prefix = strs[0]
    for s in strs[1:]:
        while not s.startswith(prefix):
            prefix = prefix[:-1]
            if not prefix:
                return ''
    return prefix


def levenshtein_distance(s1: str, s2: str) -> int:
    """编辑距离（Levenshtein距离）"""
    m, n = len(s1), len(s2)
    dp = [[0] * (n + 1) for _ in range(m + 1)]

    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if s1[i - 1] == s2[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
            else:
                dp[i][j] = 1 + min(dp[i - 1][j], dp[i][j - 1], dp[i - 1][j - 1])

    return dp[m][n]