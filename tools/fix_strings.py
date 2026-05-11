import os
import re

def fix_strings(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 修复规则：将 输出(中文内容) 或 输出（中文内容）转成 输出("中文内容")
    # 匹配模式：输出( 开头，后面跟非引号的中文字符序列，直到闭合的 )
    # 简单处理：如果 输出( 后第一个字符是中文，且没有引号，则添加引号
    lines = content.splitlines(keepends=True)
    new_lines = []
    for line in lines:
        # 查找 输出( ... ) 或 输出（ ... ）
        # 忽略已经有引号包裹的情况
        line = re.sub(r'输出\(\s*(?!["\u201c\u2018])([\u4e00-\u9fff\w\s]+)\s*\)', r'输出("\1")', line)
        line = re.sub(r'输出（\s*(?![“\u201c\u2018])([\u4e00-\u9fff\w\s]+)\s*）', r'输出（"\1"）', line)
        new_lines.append(line)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    print(f"已清理: {filepath}")

def main():
    for root, dirs, files in os.walk('tests'):
        for f in files:
            if f.endswith('.san'):
                fix_strings(os.path.join(root, f))
    for root, dirs, files in os.walk('examples'):
        for f in files:
            if f.endswith('.san'):
                fix_strings(os.path.join(root, f))
    print("完成")

if __name__ == '__main__':
    main()