"""网络操作：HTTP 请求"""
try:
    import urllib.request as _request
    _HAS_NET = True
except ImportError:
    _HAS_NET = False

from values import SanyanRuntimeError
from ops.registry import register, register_alias


def _ensure_net():
    if not _HAS_NET:
        raise SanyanRuntimeError('网络模块不可用（urllib 导入失败）')


def http_get(evaluator, args):
    """http读(url) — HTTP GET 请求，返回响应文本"""
    _ensure_net()
    if not args:
        raise SanyanRuntimeError('http读 需要一个 URL 参数')
    url = args[0] if isinstance(args[0], str) else str(evaluator.eval(args[0]))
    try:
        resp = _request.urlopen(url, timeout=10)
        return resp.read().decode('utf-8', errors='replace')
    except Exception as e:
        raise SanyanRuntimeError(f'HTTP GET 失败: {e}')


def http_post(evaluator, args):
    """http写(url, 数据) — HTTP POST 请求"""
    _ensure_net()
    if len(args) < 1:
        raise SanyanRuntimeError('http写 需要 URL 参数')
    url = args[0] if isinstance(args[0], str) else str(evaluator.eval(args[0]))
    data = ''
    if len(args) > 1:
        data_arg = evaluator.eval(args[1])
        data = str(data_arg) if not isinstance(data_arg, str) else data_arg
    try:
        body = data.encode('utf-8')
        req = _request.Request(url, data=body, method='POST')
        resp = _request.urlopen(req, timeout=10)
        return resp.read().decode('utf-8', errors='replace')
    except Exception as e:
        raise SanyanRuntimeError(f'HTTP POST 失败: {e}')


register('http读', http_get)
register('http写', http_post)

register_alias('http_get', 'http读')
register_alias('http_post', 'http写')
