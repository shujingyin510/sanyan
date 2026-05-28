"""扩展 ops 模块基本冒烟测试"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import unittest
from evaluator import SanyanEvaluator


class TestCryptoOps(unittest.TestCase):
    def setUp(self):
        self.env = SanyanEvaluator()

    def test_md5(self):
        r = self.env.eval(['md5', '"hello"'])
        self.assertEqual(r, '5d41402abc4b2a76b9719d911017c592')

    def test_sha256(self):
        r = self.env.eval(['sha256', '"hello"'])
        self.assertTrue(isinstance(r, str) and len(r) == 64)

    def test_base64_encode(self):
        r = self.env.eval(['base64编码', '"hello"'])
        self.assertEqual(r, 'aGVsbG8=')

    def test_base64_decode(self):
        r = self.env.eval(['base64解码', '"aGVsbG8="'])
        self.assertEqual(r, 'hello')


class TestRegexOps(unittest.TestCase):
    def setUp(self):
        self.env = SanyanEvaluator()

    def test_re_match(self):
        r = self.env.eval(['正则匹配', '"\\\\d+"', '"123"'])
        self.assertEqual(r.to_int(), 1)

    def test_re_search(self):
        r = self.env.eval(['正则搜索', '"\\\\d+"', '"abc123"'])
        self.assertEqual(r, '123')

    def test_re_findall(self):
        r = self.env.eval(['正则查找', '"\\\\d+"', '"a1b2c3"'])
        self.assertEqual(r, ['1', '2', '3'])

    def test_re_replace(self):
        r = self.env.eval(['正则替换', '"\\\\d+"', '"X"', '"a1b2"'])
        self.assertEqual(r, 'aXbX')

    def test_re_split(self):
        r = self.env.eval(['正则分割', '"\\\\s+"', '"a b  c"'])
        self.assertEqual(r, ['a', 'b', 'c'])


class TestTimeOps(unittest.TestCase):
    def setUp(self):
        self.env = SanyanEvaluator()

    def test_timestamp(self):
        r = self.env.eval(['时间戳'])
        self.assertGreater(r.to_int(), 1_700_000_000)

    def test_sleep(self):
        import time

        t0 = time.time()
        self.env.eval(['睡眠', 50])
        dt = time.time() - t0
        self.assertGreaterEqual(dt, 0.04)


class TestUnicodeOps(unittest.TestCase):
    def setUp(self):
        self.env = SanyanEvaluator()

    def test_url_encode(self):
        r = self.env.eval(['url编码', '"hello world"'])
        self.assertEqual(r, 'hello%20world')

    def test_url_decode(self):
        r = self.env.eval(['url解码', '"hello%20world"'])
        self.assertEqual(r, 'hello world')

    def test_ord(self):
        r = self.env.eval(['字符码', '"A"'])
        self.assertEqual(r.to_int(), 65)

    def test_chr(self):
        r = self.env.eval(['字符', '65'])
        self.assertEqual(r, 'A')


class TestMathExtraOps(unittest.TestCase):
    def setUp(self):
        self.env = SanyanEvaluator()
        self.env.eval(['设', 'lst', ['列表', 1, 2, 3, 4, 5]])

    def test_mean(self):
        r = self.env.eval(['均值', 'lst'])
        self.assertEqual(r.to_int(), 3)

    def test_median(self):
        r = self.env.eval(['中位数', 'lst'])
        self.assertEqual(r.to_int(), 3)


class TestSystemOps(unittest.TestCase):
    def setUp(self):
        self.env = SanyanEvaluator()

    def test_platform(self):
        r = self.env.eval(['平台'])
        self.assertIn(r, ('win32', 'linux', 'darwin'))

    def test_pid(self):
        import os

        r = self.env.eval(['进程号'])
        self.assertEqual(r.to_int(), os.getpid())

    def test_exists(self):
        import os

        path = os.path.abspath(__file__).replace('\\', '\\\\')
        self.env.eval(['设', 'f', '"' + path + '"'])
        r = self.env.eval(['存在', 'f'])
        self.assertEqual(r.to_int(), 1)


class TestRandomOps(unittest.TestCase):
    def setUp(self):
        self.env = SanyanEvaluator()

    def test_random_float(self):
        r = self.env.eval(['随机'])
        f = r.to_float()
        self.assertGreaterEqual(f, 0.0)
        self.assertLess(f, 1.0)

    def test_randint(self):
        for _ in range(10):
            r = self.env.eval(['随机整数', 1, 10])
            self.assertIn(r.to_int(), range(1, 11))

    def test_choice(self):
        self.env.eval(['设', 'lst', ['列表', 1, 2, 3]])
        r = self.env.eval(['选取', 'lst'])
        self.assertIn(r.to_int(), [1, 2, 3])


class TestConcurrentOps(unittest.TestCase):
    def setUp(self):
        self.env = SanyanEvaluator()

    def test_delay(self):
        import time

        t0 = time.time()
        self.env.eval(['延迟', 50, ['输出', '"done"']])
        dt = time.time() - t0
        self.assertGreaterEqual(dt, 0.04)


class TestNetOps(unittest.TestCase):
    def setUp(self):
        self.env = SanyanEvaluator()

    def test_http_get(self):
        try:
            r = self.env.eval(['http读', '"https://httpbin.org/get"'])
            self.assertIn('"url"', str(r))
        except Exception:
            self.skipTest('需要网络连接')

    def test_ssrf_block_localhost(self):
        """SSRF 防护：禁止访问 localhost"""
        from values import SanyanRuntimeError
        with self.assertRaises(SanyanRuntimeError):
            self.env.eval(['http读', '"http://localhost:8080/"'])

    def test_ssrf_block_private_ip(self):
        """SSRF 防护：禁止访问私有 IP"""
        from values import SanyanRuntimeError
        with self.assertRaises(SanyanRuntimeError):
            self.env.eval(['http读', '"http://192.168.1.1/"'])

    def test_ssrf_block_loopback(self):
        """SSRF 防护：禁止访问 127.0.0.1"""
        from values import SanyanRuntimeError
        with self.assertRaises(SanyanRuntimeError):
            self.env.eval(['http读', '"http://127.0.0.1/"'])

    def test_ssrf_block_file_scheme(self):
        """SSRF 防护：禁止 file:// 协议"""
        from values import SanyanRuntimeError
        with self.assertRaises(SanyanRuntimeError):
            self.env.eval(['http读', '"file:///etc/passwd"'])

    def test_ssrf_block_10_network(self):
        """SSRF 防护：禁止访问 10.0.0.0/8"""
        from values import SanyanRuntimeError
        with self.assertRaises(SanyanRuntimeError):
            self.env.eval(['http读', '"http://10.0.0.1/"'])


class TestSandboxOps(unittest.TestCase):
    def setUp(self):
        self.env = SanyanEvaluator()

    def test_sandbox_restrict_unblock(self):
        self.env.eval(['沙箱', '输出'])
        with self.assertRaises(Exception):
            self.env.eval(['输出', '"x"'])
        self.env.eval(['沙箱开'])
        self.env.eval(['输出', '"x"'])  # should not raise


if __name__ == '__main__':
    unittest.main()
