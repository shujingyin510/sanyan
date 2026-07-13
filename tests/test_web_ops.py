"""三态 Web 框架测试 — 覆盖 ops/web_ops.py 的请求/响应/路由/中间件/服务器逻辑。

不起真 socket：直接驱动 TernaryServer.handle_request 走完 路由匹配→中间件→
处理器结果映射→置信度降级 全流程；_decode_wire_path 回归 v3.57.0 中文路由修复；
三态监听 只测参数错误路径（在 bind 端口之前就 raise）。
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.ternary_core import TritValue
from core.values import SanyanSyntaxError, SanyanTypeError
from ops.web_ops import (
    TernaryRequest,
    TernaryResponse,
    TernaryRouter,
    TernaryMiddleware,
    TernaryServer,
    create_app,
    _decode_wire_path,
    _request_dict,
    _ternary_web_server,
    _ternary_web_route,
    _ternary_web_listen,
)


class _E:
    """最小求值器：字面量原样返回。"""

    def eval(self, x):
        return x


class TestRequestResponse(unittest.TestCase):
    def test_request_json_valid(self):
        self.assertEqual(TernaryRequest('GET', '/', {}, '{"a": 1}').json(), {'a': 1})

    def test_request_json_empty(self):
        self.assertEqual(TernaryRequest('GET', '/', {}, '').json(), {})

    def test_request_json_invalid(self):
        self.assertEqual(TernaryRequest('GET', '/', {}, 'not json').json(), {})

    def test_request_confidence_clamped(self):
        req = TernaryRequest('GET', '/', {})
        self.assertEqual(req.set_confidence(2.0).confidence, 1.0)
        self.assertEqual(req.set_confidence(-1.0).confidence, 0.0)

    def test_response_json(self):
        r = TernaryResponse().json({'a': 1})
        self.assertEqual(r.headers['Content-Type'], 'application/json')
        self.assertEqual(json.loads(r.body), {'a': 1})

    def test_response_text_and_html(self):
        self.assertTrue(TernaryResponse().text('hi').headers['Content-Type'].startswith('text/plain'))
        self.assertTrue(TernaryResponse().html('<p>').headers['Content-Type'].startswith('text/html'))

    def test_response_status_and_header_chain(self):
        r = TernaryResponse().set_status(404).set_header('X-Test', '1')
        self.assertEqual(r.status, 404)
        self.assertEqual(r.headers['X-Test'], '1')


class TestRouter(unittest.TestCase):
    def test_verb_helpers_add_routes(self):
        r = TernaryRouter()
        r.get('/a', lambda: 1)
        r.post('/b', lambda: 1)
        r.put('/c', lambda: 1)
        r.delete('/d', lambda: 1)
        self.assertEqual(len(r.routes), 4)

    def test_match_param(self):
        r = TernaryRouter()
        r.get('/u/:id', lambda: 1)
        m = r.match('GET', '/u/9')
        self.assertIsNotNone(m)
        self.assertEqual(m[1], {'id': '9'})

    def test_match_method_mismatch(self):
        r = TernaryRouter()
        r.get('/u/:id', lambda: 1)
        self.assertIsNone(r.match('POST', '/u/9'))

    def test_match_length_mismatch(self):
        r = TernaryRouter()
        r.get('/u/:id', lambda: 1)
        self.assertIsNone(r.match('GET', '/u/9/extra'))

    def test_match_literal_mismatch(self):
        r = TernaryRouter()
        r.get('/x', lambda: 1)
        self.assertIsNone(r.match('GET', '/y'))

    def test_match_confidence_gate(self):
        r = TernaryRouter()
        r.add_route('GET', '/z', lambda: 1, min_confidence=0.8)
        self.assertIsNone(r.match('GET', '/z', confidence=0.5))
        self.assertIsNotNone(r.match('GET', '/z', confidence=0.9))


class TestMiddleware(unittest.TestCase):
    def test_cors(self):
        resp = TernaryResponse()
        TernaryMiddleware.cors_middleware(TernaryRequest('GET', '/', {}), resp)
        self.assertEqual(resp.headers['Access-Control-Allow-Origin'], '*')

    def test_confidence_threshold(self):
        mw = TernaryMiddleware.confidence_threshold(0.5)
        low = TernaryRequest('GET', '/', {})
        low.confidence = 0.3
        resp = TernaryResponse()
        self.assertFalse(mw(low, resp))
        self.assertEqual(resp.status, 403)
        high = TernaryRequest('GET', '/', {})
        high.confidence = 0.9
        self.assertTrue(mw(high, TernaryResponse()))

    def test_rate_limit(self):
        mw = TernaryMiddleware.rate_limit(2, window_seconds=60)
        req = TernaryRequest('GET', '/', {'X-Forwarded-For': '1.2.3.4'})
        self.assertTrue(mw(req, TernaryResponse()))
        self.assertTrue(mw(req, TernaryResponse()))
        blocked = TernaryResponse()
        self.assertFalse(mw(req, blocked))
        self.assertEqual(blocked.status, 429)

    def test_confidence_logger_runs(self):
        # 只验证不崩（内部 print）
        TernaryMiddleware.confidence_logger(TernaryRequest('GET', '/x', {}), TernaryResponse())


class TestServerConfidence(unittest.TestCase):
    def setUp(self):
        self.s = TernaryServer()

    def _conf(self, headers):
        return self.s._calculate_request_confidence(TernaryRequest('GET', '/', headers))

    def test_default_confidence(self):
        self.assertEqual(self._conf({}), 1.0)

    def test_authorization_capped(self):
        self.assertEqual(self._conf({'Authorization': 'Bearer x'}), 1.0)

    def test_x_confidence_header(self):
        self.assertEqual(self._conf({'X-Confidence': '0.5'}), 0.5)

    def test_x_confidence_invalid_ignored(self):
        self.assertEqual(self._conf({'X-Confidence': 'abc'}), 1.0)

    def test_degradation_unavailable(self):
        resp = self.s._apply_degradation(TernaryResponse(), 0.1)
        self.assertEqual(resp.status, 503)

    def test_degradation_partial(self):
        resp = TernaryResponse()
        resp.confidence = 1.0
        self.s._apply_degradation(resp, 0.5)
        self.assertAlmostEqual(resp.confidence, 0.8)


class TestHandleRequest(unittest.TestCase):
    def _srv(self):
        return TernaryServer()

    def test_str_result(self):
        s = self._srv()
        s.router.add_route('GET', '/s', lambda req, resp: 'hello')
        r = s.handle_request('GET', '/s')
        self.assertEqual(r.status, 200)
        self.assertEqual(r.body, 'hello')

    def test_dict_result_json(self):
        s = self._srv()
        s.router.add_route('GET', '/d', lambda req, resp: {'a': 1})
        r = s.handle_request('GET', '/d')
        self.assertEqual(r.headers['Content-Type'], 'application/json')
        self.assertEqual(json.loads(r.body), {'a': 1})

    def test_response_result_passthrough(self):
        s = self._srv()
        custom = TernaryResponse(201, 'X')
        s.router.add_route('GET', '/t', lambda req, resp: custom)
        r = s.handle_request('GET', '/t')
        self.assertEqual(r.status, 201)
        self.assertEqual(r.body, 'X')

    def test_tritvalue_numeric_result(self):
        s = self._srv()
        s.router.add_route('GET', '/n', lambda req, resp: TritValue(5))
        r = s.handle_request('GET', '/n')
        self.assertEqual(r.status, 200)
        self.assertIn('value', json.loads(r.body))

    def test_param_injected(self):
        s = self._srv()
        seen = {}

        def h(req, resp):
            seen.update(req.metadata['params'])
            return 'ok'

        s.router.add_route('GET', '/u/:id', h)
        r = s.handle_request('GET', '/u/42')
        self.assertEqual(seen, {'id': '42'})
        self.assertEqual(r.body, 'ok')

    def test_404_no_fallback(self):
        self.assertEqual(self._srv().handle_request('GET', '/nope').status, 404)

    def test_fallback(self):
        s = self._srv()
        s.router.set_fallback(lambda req, resp: resp.text('fallback'))
        self.assertEqual(s.handle_request('GET', '/nope').body, 'fallback')

    def test_handler_error_500(self):
        s = self._srv()

        def boom(req, resp):
            raise ValueError('boom')

        s.router.add_route('GET', '/e', boom)
        r = s.handle_request('GET', '/e')
        self.assertEqual(r.status, 500)
        self.assertIn('boom', r.body)

    def test_middleware_short_circuit(self):
        s = self._srv()
        s.router.use(lambda req, resp: False)
        s.router.add_route('GET', '/m', lambda req, resp: 'ran')
        r = s.handle_request('GET', '/m')
        self.assertEqual(r.body, '')  # 处理器未执行

    def test_degradation_forces_503(self):
        s = self._srv()
        s.router.add_route('GET', '/x', lambda req, resp: 'hi')
        r = s.handle_request('GET', '/x', {'X-Confidence': '0.1'})
        self.assertEqual(r.status, 503)

    def test_decorator_routes(self):
        s = self._srv()

        @s.get('/g')
        def g(req, resp):
            return 'g'

        @s.post('/p')
        def p(req, resp):
            return 'p'

        self.assertEqual(len(s.router.routes), 2)
        self.assertEqual(s.handle_request('GET', '/g').body, 'g')

    def test_serve_json_and_confidence(self):
        s = self._srv()
        self.assertEqual(json.loads(s.serve_json({'k': 'v'}).body), {'k': 'v'})
        d = json.loads(s.serve_confidence('val', 0.6).body)
        self.assertEqual(d['value'], 'val')
        self.assertEqual(d['confidence'], 0.6)


class TestModuleFuncs(unittest.TestCase):
    def test_create_app(self):
        self.assertIsInstance(create_app(), TernaryServer)

    def test_decode_wire_path_chinese_and_query(self):
        path, query = _decode_wire_path('/hello/%E4%B8%96%E7%95%8C?x=1&y=2')
        self.assertEqual(path, '/hello/世界')
        self.assertEqual(query, {'x': '1', 'y': '2'})

    def test_decode_wire_path_plain(self):
        path, query = _decode_wire_path('/plain')
        self.assertEqual(path, '/plain')
        self.assertEqual(query, {})

    def test_request_dict_keys(self):
        req = TernaryRequest('POST', '/u', {'H': 'v'}, 'body', {'q': '1'})
        req.metadata['params'] = {'id': '7'}
        d = _request_dict(req)
        self.assertEqual(d['方法'], 'POST')
        self.assertEqual(d['路径'], '/u')
        self.assertEqual(d['查询'], {'q': '1'})
        self.assertEqual(d['头'], {'H': 'v'})
        self.assertEqual(d['体'], 'body')
        self.assertEqual(d['参数'], {'id': '7'})

    def test_web_server_op_default_and_port(self):
        e = _E()
        self.assertEqual(_ternary_web_server(e, []).port, 8080)
        self.assertEqual(_ternary_web_server(e, [9000]).port, 9000)
        self.assertEqual(_ternary_web_server(e, [TritValue(7000)]).port, 7000)

    def test_web_route_op_errors(self):
        e = _E()
        with self.assertRaises(SanyanSyntaxError):
            _ternary_web_route(e, ['a', 'b', 'c'])
        with self.assertRaises(SanyanTypeError):
            _ternary_web_route(e, ['not_server', 'GET', '/x', 'h'])

    def test_web_route_op_adds_routes(self):
        e = _E()
        srv = TernaryServer()
        _ternary_web_route(e, [srv, 'GET', '/x', 'handler_name'])  # 裸名字分支
        _ternary_web_route(e, [srv, 'POST', '/y', 123])  # 表达式兜底分支
        self.assertEqual(len(srv.router.routes), 2)

    def test_web_listen_op_errors(self):
        e = _E()
        with self.assertRaises(SanyanSyntaxError):
            _ternary_web_listen(e, [])
        with self.assertRaises(SanyanTypeError):
            _ternary_web_listen(e, ['not_server'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
