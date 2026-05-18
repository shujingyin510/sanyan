"""密码学操作：哈希、编解码"""

import hashlib
import base64
from values import SanyanRuntimeError
from ops.registry import register, register_alias
from ops._util import to_str


def crypto_md5(evaluator, args):
    """md5(字符串) — 返回 MD5 十六进制哈希"""
    if not args:
        return ''
    s = to_str(evaluator.eval(args[0]) if not isinstance(args[0], str) else args[0])
    return hashlib.md5(s.encode('utf-8')).hexdigest()


def crypto_sha256(evaluator, args):
    """sha256(字符串) — 返回 SHA-256 十六进制哈希"""
    if not args:
        return ''
    s = to_str(evaluator.eval(args[0]) if not isinstance(args[0], str) else args[0])
    return hashlib.sha256(s.encode('utf-8')).hexdigest()


def crypto_base64_encode(evaluator, args):
    """base64编码(字符串) — Base64 编码"""
    if not args:
        return ''
    s = to_str(evaluator.eval(args[0]) if not isinstance(args[0], str) else args[0])
    return base64.b64encode(s.encode('utf-8')).decode('ascii')


def crypto_base64_decode(evaluator, args):
    """base64解码(base64串) — Base64 解码"""
    if not args:
        return ''
    s = to_str(evaluator.eval(args[0]) if not isinstance(args[0], str) else args[0])
    try:
        return base64.b64decode(s.encode('ascii')).decode('utf-8', errors='replace')
    except Exception as e:
        raise SanyanRuntimeError(f'Base64 解码失败: {e}')


register('md5', crypto_md5)
register('sha256', crypto_sha256)
register('base64编码', crypto_base64_encode)
register('base64解码', crypto_base64_decode)

register_alias('md5_hash', 'md5')
register_alias('sha256_hash', 'sha256')
register_alias('base64_encode', 'base64编码')
register_alias('base64_decode', 'base64解码')
