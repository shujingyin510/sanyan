import os

def clean_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    # 替换全角空格为半角空格
    content = content.replace('\u3000', ' ')
    # 移除 BOM
    if content.startswith('\ufeff'):
        content = content[1:]
    # 确保使用 LF 换行
    content = content.replace('\r\n', '\n').replace('\r', '\n')
    # 去除尾部多余空白，保留一个换行
    content = content.rstrip() + '\n'
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(content)
    print(f"{path} 已清理")

clean_file('examples/greenhouse.san')
print("完成。")