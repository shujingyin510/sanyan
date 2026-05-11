import os
import glob

def fix_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        print(f"跳过非UTF-8文件: {filepath}")
        return

    # 修正全角引号包裹的字符串：让它们成为合法的三言字符串
    # 注：词法器已统一处理，此处仅作为预防
    content = content.replace('\u3000', ' ')   # 全角空格
    # 确保文件以换行结尾
    if not content.endswith('\n'):
        content += '\n'

    with open(filepath, 'w', encoding='utf-8', newline='\n') as f:
        f.write(content)
    print(f"已清理: {filepath}")

def main():
    targets = glob.glob('tests/**/*.san', recursive=True) + glob.glob('examples/**/*.san', recursive=True)
    for fp in targets:
        fix_file(fp)
    print("完成")

if __name__ == '__main__':
    main()