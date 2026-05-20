"""构建三言可视化编译器 .exe"""

import os
import sys
import subprocess


def build():
    root = os.path.dirname(__file__)
    dist_dir = os.path.join(root, 'dist')
    args = [
        sys.executable,
        '-m',
        'PyInstaller',
        '--name',
        '三言',
        '--windowed',
        '--onefile',
        '--distpath',
        dist_dir,
        '--add-data',
        f'language{os.pathsep}language',
        '--add-data',
        f'stdlib{os.pathsep}stdlib',
        '--add-data',
        f'packages{os.pathsep}packages',
        '--add-data',
        f'docs{os.pathsep}docs',
        '--hidden-import',
        'lexer',
        '--hidden-import',
        'parser',
        '--hidden-import',
        'evaluator',
        '--hidden-import',
        'preprocess',
        '--hidden-import',
        'ternary_core',
        '--hidden-import',
        'runtime',
        '--hidden-import',
        'runtime_components',
        '--hidden-import',
        'values',
        '--hidden-import',
        'skin',
        '--hidden-import',
        'ast_json',
        '--hidden-import',
        'commands',
        '--hidden-import',
        'repl',
        '--hidden-import',
        'sandbox',
        '--hidden-import',
        'sanfmt',
        '--hidden-import',
        'vm',
        '--hidden-import',
        'VERSION',
        '--hidden-import',
        'colorama',
        '--collect-all',
        'sugar',
        '--collect-all',
        'ops',
        '--collect-all',
        'lsp',
        'gui.py',
    ]
    print('>>> 开始构建三言可视化编译器...')
    print(f'>>> 输出目录: {dist_dir}')
    result = subprocess.run(args, cwd=root)
    if result.returncode == 0:
        print(f'\n✓ 构建成功! exe 位于: {os.path.join(dist_dir, "三言.exe")}')
    else:
        print(f'\n✗ 构建失败 (return code {result.returncode})')
    return result.returncode


if __name__ == '__main__':
    sys.exit(build())
