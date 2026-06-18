# name: 文件工具函数
# keywords: 文件, 读写, 目录, 路径, file, read, write, directory, path, IO

import os
import json
import csv
from typing import Any, Dict, List


def read_text(filepath: str, encoding: str = 'utf-8') -> str:
    """读取文本文件"""
    with open(filepath, 'r', encoding=encoding) as f:
        return f.read()


def write_text(filepath: str, content: str, encoding: str = 'utf-8'):
    """写入文本文件"""
    os.makedirs(os.path.dirname(filepath) or '.', exist_ok=True)
    with open(filepath, 'w', encoding=encoding) as f:
        f.write(content)


def append_text(filepath: str, content: str, encoding: str = 'utf-8'):
    """追加文本到文件"""
    with open(filepath, 'a', encoding=encoding) as f:
        f.write(content)


def read_lines(filepath: str, encoding: str = 'utf-8') -> List[str]:
    """读取文件行"""
    with open(filepath, 'r', encoding=encoding) as f:
        return [line.rstrip('\n') for line in f]


def write_lines(filepath: str, lines: List[str], encoding: str = 'utf-8'):
    """写入文件行"""
    with open(filepath, 'w', encoding=encoding) as f:
        for line in lines:
            f.write(line + '\n')


def read_json(filepath: str, encoding: str = 'utf-8') -> Any:
    """读取 JSON 文件"""
    with open(filepath, 'r', encoding=encoding) as f:
        return json.load(f)


def write_json(filepath: str, data: Any, encoding: str = 'utf-8', indent: int = 2):
    """写入 JSON 文件"""
    os.makedirs(os.path.dirname(filepath) or '.', exist_ok=True)
    with open(filepath, 'w', encoding=encoding) as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)


def read_csv(filepath: str, encoding: str = 'utf-8') -> List[Dict[str, str]]:
    """读取 CSV 文件"""
    with open(filepath, 'r', encoding=encoding) as f:
        reader = csv.DictReader(f)
        return list(reader)


def write_csv(filepath: str, data: List[Dict[str, str]], encoding: str = 'utf-8'):
    """写入 CSV 文件"""
    if not data:
        return
    os.makedirs(os.path.dirname(filepath) or '.', exist_ok=True)
    with open(filepath, 'w', encoding=encoding, newline='') as f:
        writer = csv.DictWriter(f, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)


def list_files(directory: str, pattern: str = '*', recursive: bool = False) -> List[str]:
    """列出目录下的文件"""
    import glob

    if recursive:
        pattern = os.path.join(directory, '**', pattern)
        return glob.glob(pattern, recursive=True)
    else:
        pattern = os.path.join(directory, pattern)
        return glob.glob(pattern)


def list_directories(directory: str) -> List[str]:
    """列出目录下的子目录"""
    return [d for d in os.listdir(directory) if os.path.isdir(os.path.join(directory, d))]


def file_exists(filepath: str) -> bool:
    """检查文件是否存在"""
    return os.path.isfile(filepath)


def directory_exists(dirpath: str) -> bool:
    """检查目录是否存在"""
    return os.path.isdir(dirpath)


def create_directory(dirpath: str):
    """创建目录"""
    os.makedirs(dirpath, exist_ok=True)


def delete_file(filepath: str):
    """删除文件"""
    if os.path.exists(filepath):
        os.remove(filepath)


def delete_directory(dirpath: str, recursive: bool = False):
    """删除目录"""
    import shutil

    if recursive:
        shutil.rmtree(dirpath)
    else:
        os.rmdir(dirpath)


def copy_file(src: str, dst: str):
    """复制文件"""
    import shutil

    os.makedirs(os.path.dirname(dst) or '.', exist_ok=True)
    shutil.copy2(src, dst)


def move_file(src: str, dst: str):
    """移动文件"""
    import shutil

    os.makedirs(os.path.dirname(dst) or '.', exist_ok=True)
    shutil.move(src, dst)


def get_file_size(filepath: str) -> int:
    """获取文件大小（字节）"""
    return os.path.getsize(filepath)


def get_file_extension(filepath: str) -> str:
    """获取文件扩展名"""
    return os.path.splitext(filepath)[1]


def get_filename_without_extension(filepath: str) -> str:
    """获取文件名（不含扩展名）"""
    return os.path.splitext(os.path.basename(filepath))[0]


def join_paths(*args: str) -> str:
    """连接路径"""
    return os.path.join(*args)


def get_absolute_path(filepath: str) -> str:
    """获取绝对路径"""
    return os.path.abspath(filepath)


def get_parent_directory(filepath: str) -> str:
    """获取父目录"""
    return os.path.dirname(filepath)


def walk_directory(directory: str):
    """遍历目录"""
    for root, dirs, files in os.walk(directory):
        yield root, dirs, files


def count_lines(filepath: str) -> int:
    """统计文件行数"""
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        return sum(1 for _ in f)


def search_in_file(filepath: str, pattern: str) -> List[tuple]:
    """在文件中搜索"""
    import re

    results = []
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        for line_num, line in enumerate(f, 1):
            if re.search(pattern, line):
                results.append((line_num, line.rstrip()))
    return results


def replace_in_file(filepath: str, old: str, new: str) -> int:
    """在文件中替换"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    count = content.count(old)
    if count > 0:
        content = content.replace(old, new)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
    return count
