"""三态Web框架：基于置信度的HTTP服务、路由、中间件"""

import json
import time
from typing import Any, Callable, Dict, List, Optional, Tuple
from ternary_core import TritValue
from values import SanyanSyntaxError, SanyanTypeError
from ops.registry import register, register_alias


class TernaryRequest:
    """三态请求：HTTP请求对象，带置信度信息"""

    def __init__(
        self, method: str, path: str, headers: Dict[str, str], body: str = '', query: Optional[Dict[str, str]] = None
    ):
        self.method = method
        self.path = path
        self.headers = headers
        self.body = body
        self.query = query or {}
        self.confidence = 1.0  # 请求置信度
        self.metadata: Dict[str, Any] = {}

    def json(self) -> Any:
        """解析JSON请求体"""
        try:
            return json.loads(self.body) if self.body else {}
        except json.JSONDecodeError:
            return {}

    def set_confidence(self, conf: float):
        """设置请求置信度"""
        self.confidence = max(0.0, min(1.0, conf))
        return self


class TernaryResponse:
    """三态响应：HTTP响应对象，带置信度信息"""

    def __init__(self, status: int = 200, body: str = '', headers: Optional[Dict[str, str]] = None):
        self.status = status
        self.body = body
        self.headers = headers or {}
        self.confidence = 1.0  # 响应置信度

    def json(self, data: Any, confidence: float = 1.0):
        """设置JSON响应"""
        self.headers['Content-Type'] = 'application/json'
        self.body = json.dumps(data, ensure_ascii=False)
        self.confidence = confidence
        return self

    def text(self, text: str, confidence: float = 1.0):
        """设置文本响应"""
        self.headers['Content-Type'] = 'text/plain; charset=utf-8'
        self.body = text
        self.confidence = confidence
        return self

    def html(self, html: str, confidence: float = 1.0):
        """设置HTML响应"""
        self.headers['Content-Type'] = 'text/html; charset=utf-8'
        self.body = html
        self.confidence = confidence
        return self

    def set_status(self, status: int):
        """设置状态码"""
        self.status = status
        return self

    def set_header(self, key: str, value: str):
        """设置响应头"""
        self.headers[key] = value
        return self


class TernaryRouter:
    """三态路由：基于置信度的路由匹配"""

    def __init__(self):
        self.routes: List[Tuple[str, str, Callable, float]] = []  # (方法, 路径, 处理器, 最低置信度)
        self.middlewares: List[Callable] = []
        self.fallback: Optional[Callable] = None

    def add_route(self, method: str, path: str, handler: Callable, min_confidence: float = 0.0):
        """添加路由"""
        self.routes.append((method.upper(), path, handler, min_confidence))
        return self

    def get(self, path: str, handler: Callable, min_confidence: float = 0.0):
        """GET路由"""
        return self.add_route('GET', path, handler, min_confidence)

    def post(self, path: str, handler: Callable, min_confidence: float = 0.0):
        """POST路由"""
        return self.add_route('POST', path, handler, min_confidence)

    def put(self, path: str, handler: Callable, min_confidence: float = 0.0):
        """PUT路由"""
        return self.add_route('PUT', path, handler, min_confidence)

    def delete(self, path: str, handler: Callable, min_confidence: float = 0.0):
        """DELETE路由"""
        return self.add_route('DELETE', path, handler, min_confidence)

    def use(self, middleware: Callable):
        """添加中间件"""
        self.middlewares.append(middleware)
        return self

    def set_fallback(self, handler: Callable):
        """设置默认处理器"""
        self.fallback = handler
        return self

    def match(self, method: str, path: str, confidence: float = 1.0) -> Optional[Tuple[Callable, Dict]]:
        """匹配路由，返回 (处理器, 参数) 或 None"""
        for route_method, route_path, handler, min_conf in self.routes:
            if route_method != method.upper():
                continue

            # 简单路径匹配（支持 :param 格式）
            route_parts = route_path.strip('/').split('/')
            path_parts = path.strip('/').split('/')

            if len(route_parts) != len(path_parts):
                continue

            params = {}
            match = True
            for rp, pp in zip(route_parts, path_parts):
                if rp.startswith(':'):
                    params[rp[1:]] = pp
                elif rp != pp:
                    match = False
                    break

            if match:
                # 检查置信度阈值
                if confidence < min_conf:
                    continue
                return handler, params

        return None


class TernaryMiddleware:
    """三态中间件：置信度感知的请求处理"""

    @staticmethod
    def confidence_logger(request: TernaryRequest, response: TernaryResponse):
        """置信度日志中间件"""
        print(
            f'[{time.strftime("%H:%M:%S")}] {request.method} {request.path} '
            f'置信度={request.confidence:.2f} → {response.status} '
            f'(响应置信度={response.confidence:.2f})'
        )

    @staticmethod
    def cors_middleware(request: TernaryRequest, response: TernaryResponse):
        """CORS中间件"""
        response.set_header('Access-Control-Allow-Origin', '*')
        response.set_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        response.set_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')

    @staticmethod
    def confidence_threshold(threshold: float):
        """置信度阈值中间件：低于阈值的请求返回403"""

        def middleware(request: TernaryRequest, response: TernaryResponse):
            if request.confidence < threshold:
                response.set_status(403)
                response.text(f'请求置信度 {request.confidence:.2f} 低于阈值 {threshold}')
                return False  # 中断处理
            return True

        return middleware

    @staticmethod
    def rate_limit(max_requests: int, window_seconds: int = 60):
        """速率限制中间件"""
        requests: Dict[str, List[float]] = {}

        def middleware(request: TernaryRequest, response: TernaryResponse):
            client_ip = request.headers.get('X-Forwarded-For', '127.0.0.1')
            now = time.time()

            # 清理过期记录
            requests[client_ip] = [t for t in requests.get(client_ip, []) if now - t < window_seconds]

            if len(requests.get(client_ip, [])) >= max_requests:
                response.set_status(429)
                response.text('请求过于频繁')
                return False

            requests.setdefault(client_ip, []).append(now)
            return True

        return middleware


class TernaryServer:
    """三态服务器：基于置信度的HTTP服务"""

    def __init__(self, host: str = '127.0.0.1', port: int = 8080):
        self.host = host
        self.port = port
        self.router = TernaryRouter()
        self.confidence_config = {
            'default': 1.0,
            'min_threshold': 0.3,
            'degradation_factor': 0.8,
        }

    def route(self, path: str, method: str = 'GET', min_confidence: float = 0.0):
        """路由装饰器"""

        def decorator(handler):
            self.router.add_route(method, path, handler, min_confidence)
            return handler

        return decorator

    def get(self, path: str, min_confidence: float = 0.0):
        """GET路由装饰器"""
        return self.route(path, 'GET', min_confidence)

    def post(self, path: str, min_confidence: float = 0.0):
        """POST路由装饰器"""
        return self.route(path, 'POST', min_confidence)

    def use(self, middleware: Callable):
        """添加中间件"""
        self.router.use(middleware)
        return self

    def _calculate_request_confidence(self, request: TernaryRequest) -> float:
        """计算请求置信度"""
        conf = self.confidence_config['default']

        # 基于请求头调整置信度
        if 'Authorization' in request.headers:
            conf *= 1.2  # 有认证信息提高置信度

        if request.headers.get('X-Confidence'):
            try:
                header_conf = float(request.headers['X-Confidence'])
                conf *= header_conf
            except ValueError:
                pass

        return min(1.0, max(0.0, conf))

    def _apply_degradation(self, response: TernaryResponse, request_confidence: float) -> TernaryResponse:
        """应用置信度降级"""
        if request_confidence < self.confidence_config['min_threshold']:
            response.set_status(503)
            response.text('服务不可用：置信度不足')
            response.confidence = 0.0
        elif request_confidence < 0.7:
            # 降级响应
            response.confidence *= self.confidence_config['degradation_factor']

        return response

    def handle_request(
        self,
        method: str,
        path: str,
        headers: Optional[Dict[str, str]] = None,
        body: str = '',
        query: Optional[Dict[str, str]] = None,
    ) -> TernaryResponse:
        """处理HTTP请求"""
        request = TernaryRequest(method, path, headers or {}, body, query)
        response = TernaryResponse()

        # 计算请求置信度
        request.confidence = self._calculate_request_confidence(request)

        # 执行中间件
        for middleware in self.router.middlewares:
            result = middleware(request, response)
            if result is False:
                return self._apply_degradation(response, request.confidence)

        # 匹配路由
        match = self.router.match(method, path, request.confidence)
        if match is None:
            if self.router.fallback:
                return self.router.fallback(request, response)
            response.set_status(404)
            response.text('未找到路由')
            return response

        handler, params = match
        request.metadata['params'] = params

        try:
            result = handler(request, response)
            if isinstance(result, TernaryResponse):
                response = result
            elif isinstance(result, str):
                response.text(result)
            elif isinstance(result, dict):
                response.json(result)
            elif isinstance(result, TritValue):
                if result.is_string():
                    response.text(result.to_payload(), result.confidence)
                else:
                    response.json({'value': result.to_int(), 'confidence': result.confidence}, result.confidence)
        except Exception as e:
            response.set_status(500)
            response.text(f'服务器错误: {str(e)}')
            response.confidence = 0.0

        return self._apply_degradation(response, request.confidence)

    def serve_json(self, data: Any, confidence: float = 1.0):
        """快速返回JSON响应"""
        response = TernaryResponse()
        response.json(data, confidence)
        return response

    def serve_confidence(self, value: Any, confidence: float):
        """返回带置信度的三态响应"""
        return self.serve_json({'value': value, 'confidence': confidence, 'timestamp': time.time()}, confidence)


def create_app(host: str = '127.0.0.1', port: int = 8080) -> TernaryServer:
    """创建三态Web应用"""
    return TernaryServer(host, port)


# ── 三言操作接口 ──


def _ternary_web_server(evaluator, args):
    """三态Web服务器(端口) — 创建Web服务器"""
    port = 8080
    if args:
        port_val = evaluator.eval(args[0])
        port = port_val.to_int() if isinstance(port_val, TritValue) else int(port_val)
    return TernaryServer('127.0.0.1', port)


def _ternary_web_route(evaluator, args):
    """三态路由(server, 方法, 路径, 处理器) — 添加路由"""
    if len(args) < 4:
        raise SanyanSyntaxError('三态路由 需要服务器、方法、路径和处理器')
    server = evaluator.eval(args[0])
    if not isinstance(server, TernaryServer):
        raise SanyanTypeError('第一个参数必须是三态Web服务器')
    method = evaluator.eval(args[1])
    if isinstance(method, TritValue) and method.is_string():
        method = method.to_payload()
    path = evaluator.eval(args[2])
    if isinstance(path, TritValue) and path.is_string():
        path = path.to_payload()
    handler = args[3]  # 不求值，作为函数节点
    server.router.add_route(str(method), str(path), lambda req, resp: evaluator.eval(handler))
    return server


def _ternary_web_listen(evaluator, args):
    """三态监听(server) — 启动服务器（简单HTTP模式）"""
    if not args:
        raise SanyanSyntaxError('三态监听 需要服务器参数')
    server = evaluator.eval(args[0])
    if not isinstance(server, TernaryServer):
        raise SanyanTypeError('参数必须是三态Web服务器')

    # 简单HTTP服务器实现
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self._handle('GET')

        def do_POST(self):
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8') if content_length > 0 else ''
            self._handle('POST', body)

        def _handle(self, method, body=''):
            response = server.handle_request(method, self.path, dict(self.headers), body)
            self.send_response(response.status)
            for key, value in response.headers.items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(response.body.encode('utf-8'))

        def log_message(self, format, *args):
            pass  # 静默日志

    print(f'三态Web服务器启动: http://{server.host}:{server.port}')
    httpd = HTTPServer((server.host, server.port), Handler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print('服务器关闭')
    return TritValue(0)


register('三态Web服务器', _ternary_web_server)
register('三态路由', _ternary_web_route)
register('三态监听', _ternary_web_listen)

register_alias('ternary_web_server', '三态Web服务器')
register_alias('ternary_web_route', '三态路由')
register_alias('ternary_web_listen', '三态监听')
