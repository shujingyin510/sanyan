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
        """验证 http读 基本功能（mock 网络层）"""
        from unittest.mock import patch
        from ops.net_ops import _request, _error

        class FakeResp:
            def read(self):
                return b'{"url": "http://test"}'
            def __enter__(self): return self
            def __exit__(self, *a): pass

        with patch.object(_request, 'urlopen', return_value=FakeResp()) as mk:
            r = self.env.eval(['http读', '"http://example.com/test"'])
            self.assertIn('"url"', str(r))
            mk.assert_called_once()

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


class TestTypeOpsExtended(unittest.TestCase):
    """类型操作扩展测试"""
    def setUp(self):
        self.env = SanyanEvaluator()

    def test_is_dict_true(self):
        r = self.env.eval(['是字典', ['字典', '"a"', '1']])
        self.assertEqual(r.to_int(), 1)

    def test_is_dict_false(self):
        r = self.env.eval(['是字典', '42'])
        self.assertEqual(r.to_int(), -1)

    def test_is_list_on_dict(self):
        r = self.env.eval(['是列表', ['字典', '"a"', '1']])
        self.assertEqual(r.to_int(), -1)

    def test_str_equals_same(self):
        r = self.env.eval(['字符串相等', '"hello"', '"hello"'])
        self.assertEqual(r.to_int(), 1)

    def test_str_equals_diff(self):
        r = self.env.eval(['字符串相等', '"hello"', '"world"'])
        self.assertEqual(r.to_int(), -1)

    def test_to_number_from_string(self):
        r = self.env.eval(['to_number', '"42"'])
        self.assertEqual(r.to_int(), 42)

    def test_to_number_from_float_string(self):
        r = self.env.eval(['to_number', '"3.14"'])
        self.assertAlmostEqual(r.to_float(), 3.14, places=2)

    def test_to_number_from_negative_string(self):
        r = self.env.eval(['to_number', '"-5"'])
        self.assertEqual(r.to_int(), -5)

    def test_to_number_error(self):
        from values import SanyanTypeError
        with self.assertRaises(SanyanTypeError):
            self.env.eval(['to_number', '"abc"'])

    def test_to_string_from_number(self):
        r = self.env.eval(['字符串', '42'])
        self.assertEqual(r, '42')

    def test_to_string_from_list(self):
        r = self.env.eval(['字符串', ['列表', '1', '2', '3']])
        self.assertEqual(r, '[1, 2, 3]')

    def test_to_string_from_dict(self):
        r = self.env.eval(['字符串', ['字典', '"a"', '1']])
        self.assertIn('a', r)


class TestControlOpsExtended(unittest.TestCase):
    """控制流扩展测试"""
    def setUp(self):
        self.env = SanyanEvaluator()

    def test_if_no_else(self):
        r = self.env.eval(['若', ['等于', '1', '1'], ['输出', '"yes"']])
        # Should not raise

    def test_if_nested(self):
        r = self.env.eval(['若', ['等于', '1', '1'],
            ['若', ['等于', '2', '2'], ['加', '1', '1'], ['加', '2', '2']],
            ['减', '1', '1']])
        self.assertEqual(r.to_int(), 2)

    def test_loop_with_break(self):
        r = self.env.eval(['做',
            ['设', 'i', '0'],
            ['循环', ['小于', 'i', '10'],
                ['若', ['等于', 'i', '5'],
                    ['跳出'],
                    ['设', 'i', ['加', 'i', '1']]]],
            'i'])
        self.assertEqual(r.to_int(), 5)

    def test_do_multiple_expressions(self):
        r = self.env.eval(['做', ['设', 'x', '1'], ['设', 'y', '2'], ['加', 'x', 'y']])
        self.assertEqual(r.to_int(), 3)

    def test_for_loop(self):
        r = self.env.eval(['做',
            ['设', 'sum', '0'],
            ['设', 'i', '1'],
            ['循环', ['小于等于', 'i', '5'],
                ['做',
                    ['设', 'sum', ['加', 'sum', 'i']],
                    ['设', 'i', ['加', 'i', '1']]]],
            'sum'])
        self.assertEqual(r.to_int(), 15)


class TestMathExtraOps(unittest.TestCase):
    """数学扩展操作测试"""
    def setUp(self):
        self.env = SanyanEvaluator()

    def test_sum_list(self):
        r = self.env.eval(['求和', ['列表', '1', '2', '3', '4', '5']])
        self.assertEqual(r.to_int(), 15)

    def test_avg_list(self):
        r = self.env.eval(['均值', ['列表', '2', '4', '6']])
        self.assertEqual(r.to_int(), 4)


class TestStringOpsExtended(unittest.TestCase):
    """字符串扩展测试"""
    def setUp(self):
        self.env = SanyanEvaluator()

    def test_replace_all(self):
        r = self.env.eval(['替换', '"aabaa"', '"a"', '"X"'])
        self.assertEqual(r, 'XXbXX')

    def test_split(self):
        r = self.env.eval(['分割', '"a,b,c"', '","'])
        self.assertEqual(r, ['a', 'b', 'c'])

    def test_join(self):
        r = self.env.eval(['连接', '"a"', '"b"', '"c"'])
        self.assertEqual(r, 'abc')

    def test_trim(self):
        r = self.env.eval(['trim', '"  hello  "'])
        self.assertEqual(r, 'hello')

    def test_upper(self):
        r = self.env.eval(['大写', '"hello"'])
        self.assertEqual(r, 'HELLO')

    def test_lower(self):
        r = self.env.eval(['小写', '"HELLO"'])
        self.assertEqual(r, 'hello')

    def test_char_at(self):
        r = self.env.eval(['字符码', '"A"'])
        self.assertEqual(r.to_int(), 65)


class TestContainerOpsExtended(unittest.TestCase):
    """容器操作扩展测试"""
    def setUp(self):
        self.env = SanyanEvaluator()

    def test_dict_keys(self):
        r = self.env.eval(['字列', ['字典', '"a"', '1', '"b"', '2']])
        self.assertEqual(sorted(r), ['a', 'b'])

    def test_list_concat(self):
        r = self.env.eval(['列表合', ['列表', '1', '2'], ['列表', '3', '4']])
        self.assertEqual([x.to_int() if hasattr(x, 'to_int') else x for x in r], [1, 2, 3, 4])

    def test_list_slice(self):
        r = self.env.eval(['切片', ['列表', '1', '2', '3', '4', '5'], '1', '4'])
        self.assertEqual([x.to_int() if hasattr(x, 'to_int') else x for x in r], [2, 3, 4])

    def test_contains_list(self):
        r = self.env.eval(['包含', ['列表', '1', '2', '3'], '2'])
        self.assertEqual(r.to_int(), 1)

    def test_contains_list_missing(self):
        r = self.env.eval(['包含', ['列表', '1', '2', '3'], '5'])
        self.assertEqual(r.to_int(), -1)

    def test_get_out_of_range(self):
        result = self.env.eval(['取', ['列表', '1', '2', '3'], '10'])
        self.assertEqual(result, 0)

    def test_set_element(self):
        r = self.env.eval(['置元素', ['列表', '1', '2', '3'], '1', '99'])
        self.assertEqual([x.to_int() if hasattr(x, 'to_int') else x for x in r], [1, 99, 3])


if __name__ == '__main__':
    unittest.main()
