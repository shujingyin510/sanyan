"""包管理器：安装、查询、管理三言包。"""

from __future__ import annotations
import json
import os
from ternary_core import TritValue
from values import SanyanSyntaxError, SanyanValueError, SanyanIOError, ModuleValue
from ops.registry import register

PACKAGES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'packages')
PACKAGE_INDEX_URL = 'https://raw.githubusercontent.com/shujingyin510/sanyan-packages/main/index.json'
PACKAGE_ALLOWLIST: set[str] = {
    'github.com',
    'raw.githubusercontent.com',
    'gitlab.com',
    'gitee.com',
}
"""允许的包下载域名白名单。空 set 表示不限制。"""
_installed_cache: dict[str, bool] = {}
_index_cache = None  # (timestamp, index_data)

# 超时和缓存常量
DOWNLOAD_TIMEOUT = 30
INDEX_TIMEOUT = 10
INDEX_CACHE_TTL = 300  # 5 分钟


def _resolve_package_path(name: str) -> str:
    """解析包路径：packages/name/package.san"""
    base = os.path.abspath(PACKAGES_DIR)
    safe = name.replace('.', '_').replace('/', '_')
    pkg_dir = os.path.join(base, safe)
    candidates = [
        os.path.join(pkg_dir, 'package.san'),
        os.path.join(pkg_dir, f'{safe}.san'),
        os.path.join(pkg_dir, 'main.san'),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return candidates[0]


def _get_package_info(name: str) -> dict | None:
    """读取包的元信息（从 package.json 或 index.json）。"""
    base = os.path.abspath(PACKAGES_DIR)
    safe = name.replace('.', '_').replace('/', '_')
    pkg_dir = os.path.join(base, safe)

    # 从本地 package.json 读取
    meta_path = os.path.join(pkg_dir, 'package.json')
    if os.path.exists(meta_path):
        try:
            with open(meta_path, 'r', encoding='utf-8') as f:
                result: dict = json.load(f)
                return result
        except (IOError, OSError, json.JSONDecodeError):
            pass

    # 从 index.json 读取
    local_idx = os.path.join(base, 'index.json')
    if os.path.exists(local_idx):
        try:
            with open(local_idx, 'r', encoding='utf-8') as f:
                index: dict = json.load(f)
            entry: dict | None = index.get(name)
            if entry:
                return entry
        except (IOError, OSError, json.JSONDecodeError):
            pass

    return None


class PackageOps:
    """包管理器：安装、查询、管理三言包"""

    @staticmethod
    def install(evaluator, args):
        """安装包：安装("包名") 或 安装("包名", "下载URL")

        支持两种模式：
        1. 安装("json") — 从包索引自动下载
        2. 安装("json", "http://...") — 指定 URL
        """
        if len(args) < 1:
            raise SanyanSyntaxError('安装 需要包名')
        name = evaluator.eval(args[0])
        if hasattr(name, 'to_int'):
            name = str(name.to_int())
        name = str(name)

        # 检查是否已安装
        pkg_path = _resolve_package_path(name)
        if os.path.exists(os.path.dirname(pkg_path)):
            # 已安装，直接加载
            print(f"包 '{name}' 已安装")
            return PackageOps.load(evaluator, [name])

        # 尝试从 URL 安装
        url = None
        if len(args) >= 2:
            url = evaluator.eval(args[1])
            if hasattr(url, 'to_int'):
                url = str(url.to_int())
            url = str(url)

        if url:
            if not url.startswith('https://'):
                raise SanyanValueError(f'安装包仅支持 HTTPS 地址: {url}')
            # 白名单检查
            if PACKAGE_ALLOWLIST:
                from urllib.parse import urlparse

                hostname = urlparse(url).hostname
                if hostname and not any(hostname.endswith(domain) for domain in PACKAGE_ALLOWLIST):
                    raise SanyanValueError(
                        f"域名 '{hostname}' 不在下载白名单中。允许的域名: {', '.join(sorted(PACKAGE_ALLOWLIST))}"
                    )
            PackageOps._download_and_install(name, url)
        else:
            # 尝试从索引查找
            try:
                url = PackageOps._lookup_index(name)
            except (IOError, OSError, KeyError):
                raise SanyanIOError(
                    f"包 '{name}' 未安装，且无法从索引获取。"
                    f'请先手动下载到 packages/{name}/ 目录，'
                    f'或提供 URL: 安装("{name}", "下载地址")'
                )
            if url:
                PackageOps._download_and_install(name, url)
            else:
                raise SanyanValueError(f"包 '{name}' 未找到")

        return PackageOps.load(evaluator, [name])

    @staticmethod
    def uninstall(evaluator, args):
        """卸载包：卸载("包名")"""
        import shutil

        if len(args) < 1:
            raise SanyanSyntaxError('卸载 需要包名')
        name = evaluator.eval(args[0])
        if hasattr(name, 'to_int'):
            name = str(name.to_int())
        name = str(name)

        base = os.path.abspath(PACKAGES_DIR)
        safe = name.replace('.', '_').replace('/', '_')
        pkg_dir = os.path.join(base, safe)

        if not os.path.isdir(pkg_dir):
            raise SanyanValueError(f"包 '{name}' 未安装")

        try:
            shutil.rmtree(pkg_dir)
            print(f"包 '{name}' 已卸载")
        except (IOError, OSError) as e:
            raise SanyanIOError(f'卸载包失败: {e}')

        # 清除缓存
        _installed_cache.pop(name, None)
        return TritValue(0)

    @staticmethod
    def search(evaluator, args):
        """搜索包：搜索("关键词")"""
        if len(args) < 1:
            raise SanyanSyntaxError('搜索 需要关键词')
        keyword = evaluator.eval(args[0])
        if hasattr(keyword, 'to_int'):
            keyword = str(keyword.to_int())
        keyword = str(keyword).lower()

        results = []

        # 搜索本地索引
        local_idx = os.path.join(os.path.abspath(PACKAGES_DIR), 'index.json')
        if os.path.exists(local_idx):
            try:
                with open(local_idx, 'r', encoding='utf-8') as f:
                    index = json.load(f)
                for name, info in index.items():
                    desc = info.get('description', '').lower()
                    if keyword in name.lower() or keyword in desc:
                        results.append((name, info))
            except (IOError, OSError, json.JSONDecodeError):
                pass

        # 搜索远程索引
        if not results:
            try:
                index = PackageOps._fetch_remote_index()
                if index:
                    for name, info in index.items():
                        desc = info.get('description', '').lower()
                        if keyword in name.lower() or keyword in desc:
                            results.append((name, info))
            except Exception:
                pass

        if results:
            print(f"搜索 '{keyword}' 找到 {len(results)} 个结果:")
            for name, info in results:
                desc = info.get('description', '无描述')
                ver = info.get('version', '?')
                print(f'  {name} (v{ver}) — {desc}')
        else:
            print(f"未找到与 '{keyword}' 相关的包")

        return TritValue(0)

    @staticmethod
    def info(evaluator, args):
        """查看包信息：包信息("包名")"""
        if len(args) < 1:
            raise SanyanSyntaxError('包信息 需要包名')
        name = evaluator.eval(args[0])
        if hasattr(name, 'to_int'):
            name = str(name.to_int())
        name = str(name)

        # 检查是否已安装
        base = os.path.abspath(PACKAGES_DIR)
        safe = name.replace('.', '_').replace('/', '_')
        pkg_dir = os.path.join(base, safe)
        installed = os.path.isdir(pkg_dir)

        # 获取元信息
        info = _get_package_info(name)

        print(f'包: {name}')
        print(f'  已安装: {"是" if installed else "否"}')
        if info:
            print(f'  版本: {info.get("version", "?")}')
            print(f'  描述: {info.get("description", "无")}')
            if info.get('author'):
                print(f'  作者: {info["author"]}')
            if info.get('url'):
                print(f'  地址: {info["url"]}')
        elif installed:
            # 列出包中的文件
            san_files = [f for f in os.listdir(pkg_dir) if f.endswith('.san')]
            print(f'  文件: {", ".join(san_files) if san_files else "无 .san 文件"}')
        else:
            print('  信息: 未找到包元信息')

        return TritValue(0)

    @staticmethod
    def load(evaluator, args):
        """加载已安装的包：加载包("包名")

        将包作为模块导入，返回 ModuleValue。
        """
        if len(args) < 1:
            raise SanyanSyntaxError('加载包 需要包名')
        name = evaluator.eval(args[0])
        if hasattr(name, 'to_int'):
            name = str(name.to_int())
        name = str(name)

        pkg_path = _resolve_package_path(name)
        if not os.path.exists(os.path.dirname(pkg_path)):
            raise SanyanValueError(f'包 \'{name}\' 未安装。请先执行: 安装("{name}")')

        if not os.path.exists(pkg_path):
            # 尝试查找其他 .san 文件
            pkg_dir = os.path.dirname(pkg_path)
            san_files = [f for f in os.listdir(pkg_dir) if f.endswith('.san')]
            if not san_files:
                raise SanyanValueError(f"包 '{name}' 中没有找到 .san 文件")
            pkg_path = os.path.join(pkg_dir, san_files[0])

        from evaluator import SanyanEvaluator

        module_env = SanyanEvaluator(skin_manager=evaluator.skin_manager)
        from ops.file_ops import _parse_code

        try:
            with open(pkg_path, 'r', encoding='utf-8') as f:
                code = f.read()
        except (IOError, OSError) as e:
            raise SanyanIOError(f'读取包文件失败: {e}')
        ast = _parse_code(code, module_env)

        if ast is not None:
            module_env.eval(ast)

        return ModuleValue(module_env.scope_vars, module_env.commands)

    @staticmethod
    def list_packages(evaluator, args):
        """列出已安装的包。"""
        base = os.path.abspath(PACKAGES_DIR)
        if not os.path.isdir(base):
            return TritValue(0)
        packages = []
        for name in sorted(os.listdir(base)):
            pkg_dir = os.path.join(base, name)
            if os.path.isdir(pkg_dir) and not name.startswith('.'):
                # 尝试读取版本信息
                info = _get_package_info(name)
                ver = info.get('version', '') if info else ''
                packages.append((name, ver))
        if packages:
            print('已安装的包:')
            for p, v in packages:
                ver_str = f' (v{v})' if v else ''
                print(f'  - {p}{ver_str}')
        else:
            print('没有已安装的包')
        return TritValue(0)

    @staticmethod
    def index_list(evaluator, args):
        """列出可用的包：包索引"""
        try:
            index = PackageOps._fetch_remote_index()
        except Exception:
            # 回退到本地索引
            local_idx = os.path.join(os.path.abspath(PACKAGES_DIR), 'index.json')
            if os.path.exists(local_idx):
                try:
                    with open(local_idx, 'r', encoding='utf-8') as f:
                        index = json.load(f)
                except (IOError, OSError, json.JSONDecodeError):
                    index = {}
            else:
                index = {}

        if index:
            print('可用的包:')
            for name, info in sorted(index.items()):
                desc = info.get('description', '无描述')
                ver = info.get('version', '?')
                print(f'  {name} (v{ver}) — {desc}')
        else:
            print('无法获取包索引')
        return TritValue(0)

    @staticmethod
    def _download_and_install(name: str, url: str) -> None:
        """下载并安装包。"""
        import urllib.request
        import zipfile
        import tempfile

        base = os.path.abspath(PACKAGES_DIR)
        pkg_dir = os.path.join(base, name.replace('.', '_').replace('/', '_'))

        try:
            print(f"正在下载包 '{name}'...")
            with urllib.request.urlopen(url, timeout=DOWNLOAD_TIMEOUT) as resp:
                data = resp.read()
        except (urllib.error.URLError, IOError, OSError) as e:
            raise SanyanIOError(f'下载包失败: {e}')

        # 解压（带 zip-slip 防护）
        try:
            os.makedirs(pkg_dir, exist_ok=True)
            with tempfile.TemporaryFile() as tmp:
                tmp.write(data)
                tmp.seek(0)
                pkg_dir_real = os.path.realpath(pkg_dir)
                with zipfile.ZipFile(tmp) as z:
                    for info in z.infolist():
                        safe_path = os.path.realpath(os.path.join(pkg_dir, info.filename))
                        if not safe_path.startswith(pkg_dir_real):
                            raise SanyanValueError(f'zip-slip 攻击检测: {info.filename}')
                        z.extract(info, pkg_dir)
            print(f"包 '{name}' 已安装到 {pkg_dir}")
        except (zipfile.BadZipFile, IOError, OSError) as e:
            if not os.path.exists(os.path.join(pkg_dir, 'package.san')):
                with open(os.path.join(pkg_dir, f'{name}.san'), 'wb') as f:
                    f.write(data)
            raise SanyanIOError(f'解压包失败: {e}')

    @staticmethod
    def _lookup_index(name: str) -> str | None:
        """从包索引查找下载 URL。优先查本地缓存，再查远程（每 5 分钟刷新）。"""
        global _index_cache
        import time

        # 本地索引
        local_idx = os.path.join(os.path.abspath(PACKAGES_DIR), 'index.json')
        if os.path.exists(local_idx):
            try:
                with open(local_idx, 'r', encoding='utf-8') as f:
                    index = json.load(f)
                entry = index.get(name)
                if entry:
                    return entry.get('url') or entry.get('download')  # type: ignore[no-any-return]
            except (IOError, OSError, json.JSONDecodeError):
                pass
        # 远程索引（缓存 5 分钟）
        now = time.time()
        if _index_cache is not None and now - _index_cache[0] < INDEX_CACHE_TTL:
            index = _index_cache[1]
        else:
            import urllib.request

            try:
                with urllib.request.urlopen(PACKAGE_INDEX_URL, timeout=INDEX_TIMEOUT) as resp:
                    index = json.loads(resp.read().decode('utf-8'))
                _index_cache = (now, index)
            except (urllib.error.URLError, IOError, OSError, json.JSONDecodeError):
                return None
        entry = index.get(name)
        if entry:
            return entry.get('url') or entry.get('download')  # type: ignore[no-any-return]
        return None

    @staticmethod
    def _fetch_remote_index() -> dict:
        """获取远程包索引。"""
        import urllib.request

        local_idx = os.path.join(os.path.abspath(PACKAGES_DIR), 'index.json')
        if os.path.exists(local_idx):
            try:
                with open(local_idx, 'r', encoding='utf-8') as f:
                    result: dict = json.load(f)
                    return result
            except (IOError, OSError, json.JSONDecodeError):
                pass

        try:
            with urllib.request.urlopen(PACKAGE_INDEX_URL, timeout=INDEX_TIMEOUT) as resp:
                index: dict = json.loads(resp.read().decode('utf-8'))
                return index
        except Exception:
            return {}


# 注册包管理操作
register('install', PackageOps.install)
register('安装', PackageOps.install)
register('uninstall', PackageOps.uninstall)
register('卸载', PackageOps.uninstall)
register('search', PackageOps.search)
register('搜索', PackageOps.search)
register('info', PackageOps.info)
register('包信息', PackageOps.info)
register('list_packages', PackageOps.list_packages)
register('包列表', PackageOps.list_packages)
register('index_list', PackageOps.index_list)
register('包索引', PackageOps.index_list)
register('load_package', PackageOps.load)
register('加载包', PackageOps.load)
