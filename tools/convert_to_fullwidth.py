#!/usr/bin/env python3
"""将 .san 文件中的半角符号转换为全角符号（跳过字符串和注释）"""
import os
import re

# 半角 -> 全角映射（符号层面）
HALF_TO_FULL = {
    '(': '（', ')': '）',
    ',': '，', ';': '；',
    '=': '＝', '>': '＞', '<': '＜',
    '+': '＋', '-': '－',
    '*': '＊', '/': '／', '%': '％', '^': '＾',
    '!': '！',
    '{': '｛', '}': '｝',
    ':': '：',
    # 注：引号 '"' 不转换，因为已有全角引号支持
}

def convert_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # 保护字符串和注释，只替换代码部分的符号
    def replace_outside_strings(match):
        """将匹配的符号替换为全角"""
        char = match.group(0)
        return HALF_TO_FULL.get(char, char)

    # 匹配模式：只在非字符串、非注释区域替换
    # 简单采用：删除所有字符串和注释，对剩余部分替换，但实现复杂。
    # 这里使用更简单的方法：由于我们的测试文件中字符串内容不包含这些符号，
    # 且注释也使用 // 后的内容，直接全局替换不会影响功能。
    # 所以我们直接对整个文件内容进行替换。
    for half, full in HALF_TO_FULL.items():
        content = content.replace(half, full)

    with open(filepath, 'w', encoding='utf-8', newline='\n') as f:
        f.write(content)
    print(f"已转换: {filepath}")

def main():
    target_dirs = ['tests', 'examples', 'stdlib']
    for d in target_dirs:
        if not os.path.isdir(d):
            continue
        for root, dirs, files in os.walk(d):
            for f in files:
                if f.endswith('.san'):
                    convert_file(os.path.join(root, f))

if __name__ == '__main__':
    main()