"""网络操作：HTTP 请求（含 SSRF 防护）"""

import ipaddress
import urllib.parse

try:
    import urllib.request as _request
    import urllib.error as _error

    _HAS_NET = True
except ImportError:
    _HAS_NET = False

from values import SanyanRuntimeError
from ops.registry import register, register_alias

HTTP_TIMEOUT = 10

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


def _validate_url(url: str) -> None:
    """SSRF 防护：校验 URL 合法性，禁止访问私有/保留地址。"""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ('http', 'https'):
        raise SanyanRuntimeError(f'不允许的 URL 协议: {parsed.scheme}（仅支持 http/https）')
    hostname = parsed.hostname
    if not hostname:
        raise SanyanRuntimeError('URL 缺少主机名')
    if hostname in ('localhost', '0.0.0.0'):
        raise SanyanRuntimeError('禁止访问 localhost')
    try:
        addr = ipaddress.ip_address(hostname)
        for net in _PRIVATE_NETS:
            if addr in net:
                raise SanyanRuntimeError(f'禁止访问私有/保留地址: {hostname}')
    except ValueError:
        pass  # 非 IP 地址（域名），允许通过


def _ensure_net():
    if not _HAS_NET:
        raise SanyanRuntimeError('网络模块不可用（urllib 导入失败）')


def http_get(evaluator, args):
    """http读(url) — HTTP GET 请求，返回响应文本"""
    _ensure_net()
    if not args:
        raise SanyanRuntimeError('http读 需要一个 URL 参数')
    url = str(evaluator.eval(args[0]))
    _validate_url(url)
    try:
        resp = _request.urlopen(url, timeout=HTTP_TIMEOUT)
        return resp.read().decode('utf-8', errors='replace')
    except (_error.URLError, _error.HTTPError, ValueError, OSError) as e:
        raise SanyanRuntimeError(f'HTTP GET 失败: {e}')


def http_post(evaluator, args):
    """http写(url, 数据, headers?) — HTTP POST 请求"""
    _ensure_net()
    if len(args) < 1:
        raise SanyanRuntimeError('http写 需要 URL 参数')
    url = str(evaluator.eval(args[0]))
    _validate_url(url)
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
        resp = _request.urlopen(req, timeout=HTTP_TIMEOUT)
        return resp.read().decode('utf-8', errors='replace')
    except (_error.URLError, _error.HTTPError, ValueError, OSError) as e:
        raise SanyanRuntimeError(f'HTTP POST 失败: {e}')


register('http读', http_get)
register('http写', http_post)

register_alias('http_get', 'http读')
register_alias('http_post', 'http写')
