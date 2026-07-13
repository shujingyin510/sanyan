"""网络操作：HTTP 请求（SSRF 防护 + SANYAN_NET 门控 + 三态信封）

门控（对齐 FFI 惯例，docs/ffi_plan.md §3.6）：
  - `SANYAN_NET=0` 全局禁网——旧算子（http读/http写）抛可读错误，
    信封算子（http请求）信封报假，绝不裸 traceback。
    与 SANYAN_FFI 默认关不同：http 算子是先于门控机制发布的既有能力
    （agent LLM 通道、LLVM 原生路径都在用），故默认开、显式关。
  - `SANYAN_NET_ALLOW_LOCAL=1` 显式豁免 SSRF 对 localhost/私网的封锁——
    供本机服务（三态Web服务器、本地推理端点）自测成环；默认仍封。

三态信封（http请求）：{'判','值','错','源','状态码','响应头'}，与 FFI 信封
同构（信封判 可直接消费）。判=真(2xx/3xx) / 假(4xx/5xx、传输失败、被禁)
/ 可能(超时——超时 ≠ 宕机，见 examples/health_check.san 的论证)。

后端矩阵：解释器路径全量；http读/http写 另有 LLVM 原生路径（WinHTTP，
llvmgen/runtime.c）；字节码/种子 VM 无网络运行时——编译期显式报错
（compiler/compile_bytecode.py，repl 捕获后回退求值器）。
"""

import ipaddress
import os
import urllib.parse

try:
    import urllib.request as _request
    import urllib.error as _error

    _HAS_NET = True
except ImportError:
    _HAS_NET = False

from core.ternary_core import TritValue
from core.values import SanyanRuntimeError
from ops.capability import can, register_self_guarded
from ops.registry import register, register_alias

HTTP_TIMEOUT = 60

# SSRF 防护：禁止访问的私有/保留 IP 范围
_PRIVATE_NETS = [
    ipaddress.ip_network('127.0.0.0/8'),
    ipaddress.ip_network('10.0.0.0/8'),
    ipaddress.ip_network('172.16.0.0/12'),
    ipaddress.ip_network('192.168.0.0/16'),
    ipaddress.ip_network('169.254.0.0/16'),
    ipaddress.ip_network('::1/128'),
    ipaddress.ip_network('fc00::/7'),
    ipaddress.ip_network('fe80::/10'),
]


def _net_enabled() -> bool:
    return os.environ.get('SANYAN_NET', '1') != '0'


def _allow_local() -> bool:
    return os.environ.get('SANYAN_NET_ALLOW_LOCAL') == '1'


def _validate_url(url: str) -> None:
    """SSRF 防护：校验 URL 合法性；SANYAN_NET_ALLOW_LOCAL=1 时豁免本机/私网。"""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ('http', 'https'):
        raise SanyanRuntimeError(f'不允许的 URL 协议: {parsed.scheme}（仅支持 http/https）')
    hostname = parsed.hostname
    if not hostname:
        raise SanyanRuntimeError('URL 缺少主机名')
    if _allow_local():
        return
    if hostname in ('localhost', '0.0.0.0'):
        raise SanyanRuntimeError('禁止访问 localhost（本机自测设 SANYAN_NET_ALLOW_LOCAL=1 豁免）')
    try:
        addr = ipaddress.ip_address(hostname)
        for net in _PRIVATE_NETS:
            if addr in net:
                raise SanyanRuntimeError(f'禁止访问私有/保留地址: {hostname}（SANYAN_NET_ALLOW_LOCAL=1 可豁免）')
    except ValueError:
        pass  # 非 IP 地址（域名），允许通过


def _ensure_net():
    if not _HAS_NET:
        raise SanyanRuntimeError('网络模块不可用（urllib 导入失败）')
    if not _net_enabled():
        raise SanyanRuntimeError('网络已禁用（SANYAN_NET=0）')


_URI_SAFE = "/%!$&'()*+,;=:@~-._"  # RFC3986 保留+非保留；'%' 在内→已编码序列不二次编码


def _iri_to_uri(url: str) -> str:
    """IRI → URI：中文路径/查询百分号编码、中文域名 IDNA——urllib 只吃 ASCII。

    中文优先的语言里 `http读("…/问候/世界")` 是常态用法，不能让 'ascii' codec
    报错裸穿透（v3.57.0 册子冒烟现形）。已编码的 %XX 原样保留。
    """
    if url.isascii():
        return url
    p = urllib.parse.urlsplit(url)
    host = p.hostname or ''
    if not host.isascii():
        host = host.encode('idna').decode('ascii')
    netloc = host
    if p.port:
        netloc = f'{netloc}:{p.port}'
    if p.username:
        userinfo = urllib.parse.quote(p.username, safe='')
        if p.password:
            userinfo += ':' + urllib.parse.quote(p.password, safe='')
        netloc = f'{userinfo}@{netloc}'
    return urllib.parse.urlunsplit(
        (
            p.scheme,
            netloc,
            urllib.parse.quote(p.path, safe=_URI_SAFE),
            urllib.parse.quote(p.query, safe=_URI_SAFE + '?'),
            urllib.parse.quote(p.fragment, safe=_URI_SAFE + '?'),
        )
    )


def _timeout_of(evaluator) -> int:
    """优先读作用域变量 超时秒数，否则用默认值。

    .san 里 `设 超时秒数 = 5` 存的是 TritValue——必须走 to_int()，
    裸 int() 会炸并被静默吞掉回落 60s（旧 http写 的此机制自上线即未生效，
    v3.57.0 册子冒烟现形后修复）。
    """
    try:
        if evaluator.has_var('超时秒数'):
            v = evaluator.get_var('超时秒数')
            n = int(v.to_int() if hasattr(v, 'to_int') else v)
            if n > 0:
                return n
    except Exception:
        pass
    return HTTP_TIMEOUT


def http_get(evaluator, args):
    """http读(url) — HTTP GET，返回响应文本（失败抛错；要状态码/三态判用 http请求）"""
    _ensure_net()
    if not args:
        raise SanyanRuntimeError('http读 需要一个 URL 参数')
    url = str(evaluator.eval(args[0]))
    _validate_url(url)
    url = _iri_to_uri(url)
    try:
        resp = _request.urlopen(url, timeout=_timeout_of(evaluator))
        return resp.read().decode('utf-8', errors='replace')
    except (_error.URLError, _error.HTTPError, ValueError, OSError) as e:
        raise SanyanRuntimeError(f'HTTP GET 失败: {e}')


def http_post(evaluator, args):
    """http写(url, 数据, headers?) — HTTP POST，返回响应文本（失败抛错）"""
    _ensure_net()
    if len(args) < 1:
        raise SanyanRuntimeError('http写 需要 URL 参数')
    url = str(evaluator.eval(args[0]))
    _validate_url(url)
    url = _iri_to_uri(url)
    data = ''
    if len(args) > 1:
        data_arg = evaluator.eval(args[1])
        data = str(data_arg) if not isinstance(data_arg, str) else data_arg
    headers = {}
    if len(args) > 2:
        headers_arg = evaluator.eval(args[2])
        if isinstance(headers_arg, dict):
            headers = {str(k): str(v) for k, v in headers_arg.items()}
    try:
        body = data.encode('utf-8')
        req = _request.Request(url, data=body, method='POST', headers=headers)
        resp = _request.urlopen(req, timeout=_timeout_of(evaluator))
        return resp.read().decode('utf-8', errors='replace')
    except (_error.URLError, _error.HTTPError, ValueError, OSError) as e:
        raise SanyanRuntimeError(f'HTTP POST 失败: {e}')


# ── 三态信封版（能力面惯例：永不 raise，一律信封）──


def _envelope(trit: int, *, value='', err='', code=0, headers=None, conf=1.0, reason='') -> dict:
    """三态信封。`因`（reason）封闭枚举：约束|门控|超时|远端|传输（成功为空）——
    给程序看（`错` 给人看）。`因` 活在 dict、零核心成本；裸 TritValue 的元通道另议
    （与 allow_unknown 合并一次演化，见 约束-方向研究 §D1/§D4）。"""
    return {
        '判': TritValue(trit, confidence=conf),
        '值': value,
        '错': err[:200],
        '源': 'http',
        '因': reason,
        '状态码': code,
        '响应头': headers or {},
    }


def http_request(evaluator, args):
    """http请求(方法, url, 体?, 头?) — 三态信封版 HTTP。

    判=真(2xx/3xx) / 假(4xx/5xx、传输失败、被禁) / 可能(超时)；
    状态码/响应头 随信封返回；永不 raise（对齐 FFI 能力面惯例）。
    """
    if not _HAS_NET:
        return _envelope(-1, err='网络模块不可用（urllib 导入失败）', reason='门控')
    if not _net_enabled():
        return _envelope(-1, err='网络未启用：SANYAN_NET=0（移除该环境变量以恢复）', reason='门控')
    if not can(evaluator, '网'):  # 能力约束：块内未 `许 网` → 判假·因=约束（不抛，走信封契约）
        return _envelope(-1, err='约束禁止: 网(http请求)', reason='约束')
    if len(args) < 2:
        return _envelope(-1, err='http请求 需要 方法 与 URL 两个参数')
    method = str(evaluator.eval(args[0])).upper()
    url = str(evaluator.eval(args[1]))
    try:
        _validate_url(url)
    except SanyanRuntimeError as e:
        return _envelope(-1, err=str(e), reason='约束')  # SSRF 是内建约束
    url = _iri_to_uri(url)
    body = None
    if len(args) > 2:
        data_arg = evaluator.eval(args[2])
        text = data_arg if isinstance(data_arg, str) else str(data_arg)
        if text:
            body = text.encode('utf-8')
    headers = {}
    if len(args) > 3:
        headers_arg = evaluator.eval(args[3])
        if isinstance(headers_arg, dict):
            headers = {str(k): str(v) for k, v in headers_arg.items()}
    timeout = _timeout_of(evaluator)
    try:
        req = _request.Request(url, data=body, method=method, headers=headers)
        resp = _request.urlopen(req, timeout=timeout)
        text = resp.read().decode('utf-8', errors='replace')
        code = getattr(resp, 'status', None) or resp.getcode() or 0
        return _envelope(1, value=text, code=int(code), headers=dict(resp.headers))
    except _error.HTTPError as e:  # 4xx/5xx：有响应——判假，但信封携带全部信息
        try:
            text = e.read().decode('utf-8', errors='replace')
        except Exception:
            text = ''
        return _envelope(
            -1, value=text, err=f'HTTP {e.code}', code=int(e.code), headers=dict(e.headers or {}), reason='远端'
        )
    except TimeoutError as e:  # 超时 ≠ 宕机：第三值的用武之地
        return _envelope(0, err=f'超时（{timeout}s）: {e}', conf=0.5, reason='超时')
    except _error.URLError as e:
        if isinstance(getattr(e, 'reason', None), TimeoutError):
            return _envelope(0, err=f'超时（{timeout}s）: {e.reason}', conf=0.5, reason='超时')
        return _envelope(-1, err=f'传输失败: {e}', reason='传输')
    except (ValueError, OSError) as e:
        return _envelope(-1, err=f'传输失败: {e}', reason='传输')


register('http读', http_get)
register('http写', http_post)
register('http请求', http_request)

register_alias('http_get', 'http读')
register_alias('http_post', 'http写')
register_alias('http_request', 'http请求')

# http请求 是信封式：块内被禁时自返判假·因=约束（分派处不抛）。别名一并覆盖。
register_self_guarded('http请求')
