"""C 声明导入生成器（FFI 层 B 离线半，RFC docs/ffi_plan.md §4 / M3）。

把 C 头文件的**声明层**（函数签名/typedef/struct/enum）导成两件生成物：

  python -X utf8 scripts/c_bind_gen.py mylib.h --lib mylib [-I 目录]... [-D 宏]... \
      [--no-preprocess] [-o 输出目录]

  → <输出目录>/<lib>.ffi.json   manifest（ctypes/LLVM 双后端共用的唯一事实源）
  → <输出目录>/<lib>.san        三言桩模块（包装 c载入/c调 为自然函数，M4 起可运行）

设计要点（与 RFC 对齐）：
- **只导声明**：宏函数/内联函数体/位域/变参/函数指针一律不导——变参函数进 manifest
  并标 `variadic: true`（运行时拒），其余进 `skipped` 清单（fail-closed，可审）。
- **错误惯例不推断**：每函数 `err` 默认 `null`（恒判真），由人审在 manifest 里补注
  `null_ret`/`neg_ret`/`errno`——这是"生成物入库人审"的主要审点。
- **生成物入库人审后再用**（与"绝不自动合并"同一哲学：生成器出的桩是候选，人是终审）。
- 预处理默认走 `gcc -E`（gcc 缺席报错退出，与测试套件 gcc-skip 同口径）；已展开/无
  include 的头可用 `--no-preprocess` 跳过（测试走此路径，不依赖 gcc）。
- `long`/`ulong` 保留为平台宽度记号（Windows 32 位 / Linux 64 位），由 M4 的 ctypes
  侧按平台落 `c_long`——manifest 保持跨平台。

依赖：pycparser（仅本生成器需要；语言运行时保持零依赖）。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from typing import Optional

try:
    from pycparser import CParser, c_ast
except ImportError:  # pragma: no cover — CI 无 pycparser 时由调用方看到明确信息
    print('缺少 pycparser（仅生成器需要）：pip install pycparser', file=sys.stderr)
    raise

GEN_VERSION = 'c_bind_gen v1'

# C 基础类型 → manifest 类型记号（RFC §4.3；'long' 保留平台宽度语义）
_BASE_TYPES = {
    ('char',): 'int8',
    ('signed', 'char'): 'int8',
    ('unsigned', 'char'): 'uint8',
    ('short',): 'int16',
    ('short', 'int'): 'int16',
    ('unsigned', 'short'): 'uint16',
    ('unsigned', 'short', 'int'): 'uint16',
    ('int',): 'int32',
    ('signed', 'int'): 'int32',
    ('signed',): 'int32',
    ('unsigned',): 'uint32',
    ('unsigned', 'int'): 'uint32',
    ('long',): 'long',
    ('long', 'int'): 'long',
    ('unsigned', 'long'): 'ulong',
    ('unsigned', 'long', 'int'): 'ulong',
    ('long', 'long'): 'int64',
    ('long', 'long', 'int'): 'int64',
    ('unsigned', 'long', 'long'): 'uint64',
    ('unsigned', 'long', 'long', 'int'): 'uint64',
    ('float',): 'f32',
    ('double',): 'f64',
    ('void',): 'void',
    ('_Bool',): 'int8',
}


class _Unsupported(Exception):
    """类型不在阶段 1 支持面内——携带原因，调用方把所属声明记入 skipped。"""


def _names_key(names: list) -> tuple:
    # 'unsigned int' 与 'int unsigned' 等价；排序前把符号词提前保证键稳定
    order = {'signed': 0, 'unsigned': 0, 'short': 1, 'long': 1, 'char': 2, 'int': 3}
    return tuple(sorted(names, key=lambda n: (order.get(n, 2), n)))


def _map_type(node, typedefs: dict, *, depth: int = 0) -> str:
    """pycparser 类型节点 → manifest 记号。不支持的形态抛 _Unsupported。"""
    if depth > 8:
        raise _Unsupported('类型嵌套过深')
    if isinstance(node, c_ast.TypeDecl):
        return _map_type(node.type, typedefs, depth=depth + 1)
    if isinstance(node, c_ast.IdentifierType):
        key = _names_key(node.names)
        if key in _BASE_TYPES:
            return _BASE_TYPES[key]
        if len(node.names) == 1 and node.names[0] in typedefs:
            return typedefs[node.names[0]]
        raise _Unsupported(f'未知类型: {" ".join(node.names)}')
    if isinstance(node, c_ast.PtrDecl):
        inner = node.type
        if isinstance(inner, c_ast.TypeDecl) and isinstance(inner.type, c_ast.IdentifierType):
            if _names_key(inner.type.names) in (('char',), ('char', 'signed')):
                return 'cstr'  # char* 按只读串（utf-8）
        if isinstance(inner, c_ast.FuncDecl):
            raise _Unsupported('函数指针（阶段1拒：回调统一禁）')
        return 'ptr'  # 其它一切指针 → 不透明 C 句柄
    if isinstance(node, (c_ast.Struct, c_ast.Union)):
        return f'struct:{node.name or "<匿名>"}'
    if isinstance(node, c_ast.Enum):
        return 'int32'  # enum 按 int
    if isinstance(node, c_ast.ArrayDecl):
        raise _Unsupported('数组参数（阶段1拒：请以指针+长度重导）')
    if isinstance(node, c_ast.FuncDecl):
        raise _Unsupported('函数指针（阶段1拒）')
    raise _Unsupported(f'不支持的类型形态: {type(node).__name__}')


def _collect_enum(node: 'c_ast.Enum', enums: dict, skipped: list) -> None:
    if not node.values:
        return
    nxt = 0
    for e in node.values.enumerators:
        if e.value is None:
            enums[e.name] = nxt
            nxt += 1
        elif isinstance(e.value, c_ast.Constant) and e.value.type == 'int':
            nxt = int(e.value.value, 0)
            enums[e.name] = nxt
            nxt += 1
        else:
            skipped.append({'name': e.name, 'kind': 'enum', 'reason': '非常量表达式的枚举值（阶段1拒）'})


def _collect_struct(node, typedefs: dict, structs: dict, skipped: list) -> None:
    if not node.decls:  # 前向声明
        return
    name = node.name or '<匿名>'
    fields = []
    for d in node.decls:
        if getattr(d, 'bitsize', None) is not None:
            skipped.append({'name': name, 'kind': 'struct', 'reason': f'位域字段 {d.name}（阶段1拒）'})
            return
        try:
            fields.append([d.name, _map_type(d.type, typedefs)])
        except _Unsupported as ex:
            skipped.append({'name': name, 'kind': 'struct', 'reason': f'字段 {d.name}: {ex}'})
            return
    structs[name] = fields


_COMMENT_RE = re.compile(r'//[^\n]*|/\*.*?\*/', re.S)


def _strip_comments(text: str) -> str:
    """pycparser 不吃注释（正常由 cpp 剥）——--no-preprocess 路径自己剥，换行数保住行号。"""
    return _COMMENT_RE.sub(lambda m: '\n' * m.group(0).count('\n'), text)


def parse_header(text: str, filename: str = '<header>') -> dict:
    """预处理后的 C 声明文本 → manifest 骨架（不含 lib/binary，由 CLI 补）。"""
    ast = CParser().parse(_strip_comments(text), filename)
    typedefs: dict = {}
    functions: list = []
    structs: dict = {}
    enums: dict = {}
    skipped: list = []

    for ext in ast.ext:
        if isinstance(ext, c_ast.Typedef):
            try:
                typedefs[ext.name] = _map_type(ext.type, typedefs)
            except _Unsupported as ex:
                skipped.append({'name': ext.name, 'kind': 'typedef', 'reason': str(ex)})
            # typedef 里带出的 struct/enum 定义顺手收
            inner = ext.type.type if isinstance(ext.type, c_ast.TypeDecl) else None
            if isinstance(inner, (c_ast.Struct, c_ast.Union)) and inner.decls:
                _collect_struct(inner, typedefs, structs, skipped)
            if isinstance(inner, c_ast.Enum):
                _collect_enum(inner, enums, skipped)
            continue
        if not isinstance(ext, c_ast.Decl):
            continue
        if isinstance(ext.type, (c_ast.Struct, c_ast.Union)):
            _collect_struct(ext.type, typedefs, structs, skipped)
            continue
        if isinstance(ext.type, c_ast.Enum):
            _collect_enum(ext.type, enums, skipped)
            continue
        if isinstance(ext.type, c_ast.FuncDecl):
            fdecl = ext.type
            entry: dict = {'name': ext.name, 'err': None}
            variadic = False
            args: list = []
            params = fdecl.args.params if fdecl.args else []
            try:
                for p in params:
                    if isinstance(p, c_ast.EllipsisParam):
                        variadic = True
                        continue
                    t = _map_type(p.type, typedefs)
                    if t == 'void':  # f(void) 空参
                        continue
                    args.append(t)
                entry['ret'] = _map_type(fdecl.type, typedefs)
            except _Unsupported as ex:
                skipped.append({'name': ext.name, 'kind': 'function', 'reason': str(ex)})
                continue
            entry['args'] = args
            if variadic:
                entry['variadic'] = True  # 进 manifest 但运行时拒（RFC §4.2）
            functions.append(entry)

    return {'functions': functions, 'structs': structs, 'enums': enums, 'skipped': skipped}


def build_manifest(parsed: dict, lib: str) -> dict:
    return {
        'lib': lib,
        'generator': GEN_VERSION,
        'binary': {'win32': f'{lib}.dll', 'linux': f'lib{lib}.so', 'darwin': f'lib{lib}.dylib'},
        **parsed,
    }


def build_stub(manifest: dict, header_name: str) -> str:
    """manifest → 三言桩模块（sugar 语法：`定义 名 (参数) { 末表达式即返回值; }`）。

    变参函数不进桩；err 默认 null 故全部解包包装——人审把某函数补注
    null_ret/neg_ret 后，可按需把对应桩函数改成直接给出信封由调用方自判。
    """
    lib = manifest['lib']
    ts = time.strftime('%Y-%m-%d %H:%M')
    lines = [
        f'// 由 {GEN_VERSION} 生成自 {header_name}（{ts}）——人工审阅后使用',
        f'// err 惯例默认 null（恒判真）：审阅时在 {lib}.ffi.json 里按函数补注',
        '// null_ret/neg_ret/errno，并把对应桩函数改为直接给出信封（调用方自判）。',
        f'设 __库 = 解包(c载入("{lib}.ffi.json"));',
        '',
    ]
    exported = []
    for fn in manifest['functions']:
        if fn.get('variadic'):
            lines.append(f'// {fn["name"]}: 变参函数（阶段1不支持，未生成桩）')
            lines.append('')
            continue
        params = ', '.join(f'a{i + 1}' for i in range(len(fn['args'])))
        call_args = (', ' + params) if params else ''
        lines += [
            f'定义 {fn["name"]} ({params}) {{',
            f'    解包(c调(__库, "{fn["name"]}"{call_args}));',
            '}',
            '',
        ]
        exported.append(fn['name'])
    if exported:
        lines.append('导出 ' + ' '.join(exported) + ';')
    return '\n'.join(lines) + '\n'


def preprocess(header: str, include_dirs: list, defines: list) -> str:
    gcc = shutil.which('gcc') or shutil.which('cpp')
    if not gcc:
        print('未找到 gcc/cpp（预处理需要）——已展开的头可用 --no-preprocess 跳过', file=sys.stderr)
        sys.exit(2)
    cmd = [gcc, '-E', '-std=c99', header]
    for d in include_dirs:
        cmd += ['-I', d]
    for m in defines:
        cmd += ['-D', m]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=60)
    if r.returncode != 0:
        print(f'预处理失败:\n{r.stderr[:800]}', file=sys.stderr)
        sys.exit(2)
    return r.stdout


def main(argv: Optional[list] = None) -> int:
    ap = argparse.ArgumentParser(description='C 声明导入生成器：.h → manifest(.ffi.json) + 三言桩(.san)')
    ap.add_argument('header', help='C 头文件路径')
    ap.add_argument('--lib', required=True, help='库名（决定产物文件名与默认二进制名）')
    ap.add_argument('-I', dest='include_dirs', action='append', default=[], help='附加 include 目录')
    ap.add_argument('-D', dest='defines', action='append', default=[], help='预处理宏定义')
    ap.add_argument('--no-preprocess', action='store_true', help='跳过 gcc -E（头文件已展开/无 include 时）')
    ap.add_argument('-o', dest='outdir', default='', help='输出目录（默认=头文件所在目录）')
    args = ap.parse_args(argv)

    if args.no_preprocess:
        with open(args.header, encoding='utf-8', errors='replace') as f:
            text = f.read()
    else:
        text = preprocess(args.header, args.include_dirs, args.defines)

    parsed = parse_header(text, args.header)
    manifest = build_manifest(parsed, args.lib)
    outdir = args.outdir or os.path.dirname(os.path.abspath(args.header))
    os.makedirs(outdir, exist_ok=True)
    mf_path = os.path.join(outdir, f'{args.lib}.ffi.json')
    san_path = os.path.join(outdir, f'{args.lib}.san')
    with open(mf_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    with open(san_path, 'w', encoding='utf-8') as f:
        f.write(build_stub(manifest, os.path.basename(args.header)))

    print(
        f'[OK] {mf_path}: 函数 {len(manifest["functions"])} / 结构体 {len(manifest["structs"])} / 枚举常量 {len(manifest["enums"])}'
    )
    print(f'[OK] {san_path}')
    if manifest['skipped']:
        print(f'[跳过 {len(manifest["skipped"])} 项——fail-closed，人审确认]')
        for s in manifest['skipped']:
            print(f'  - {s["kind"]} {s["name"]}: {s["reason"]}')
    print('提醒：err 惯例默认 null——人审在 manifest 里补注 null_ret/neg_ret/errno（RFC §4.4）。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
