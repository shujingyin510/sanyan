import os
import glob

SAFE_MAP = {
    '(': '（', ')': '）',
    ',': '，', ';': '；',
    '=': '＝', '>': '＞', '<': '＜',
    '+': '＋', '-': '－',
    '*': '＊', '/': '／', '%': '％', '^': '＾',
    '{': '｛', '}': '｝',
    ':': '：',
    # 不包含: // 注释符号 ' " 字符串符号
}

def convert_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    for half, full in SAFE_MAP.items():
        content = content.replace(half, full)
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(content)
    print(f"已转换: {path}")

def main():
    for root, dirs, files in os.walk('tests'):
        for f in files:
            if f.endswith('.san'):
                convert_file(os.path.join(root, f))
    for root, dirs, files in os.walk('examples'):
        for f in files:
            if f.endswith('.san'):
                convert_file(os.path.join(root, f))
    for root, dirs, files in os.walk('stdlib'):
        for f in files:
            if f.endswith('.san'):
                convert_file(os.path.join(root, f))

if __name__ == '__main__':
    main()