"""包管理器测试"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import os


import unittest
from evaluator import SanyanEvaluator
from ops.package_ops import _resolve_package_path


class TestPackageManager(unittest.TestCase):
    def setUp(self):
        self.env = SanyanEvaluator()

    def test_list_packages(self):
        # 包列表不崩溃即可
        result = self.env.eval(['list_packages'])
        self.assertIsNotNone(result)

    def test_load_nonexistent(self):
        from values import SanyanValueError

        with self.assertRaises(SanyanValueError):
            self.env.eval(['load_package', '"nonexistent_pkg_xyz"'])

    def test_install_no_url(self):
        from values import SanyanValueError

        with self.assertRaises(SanyanValueError):
            self.env.eval(['install', '"nonexistent_pkg_xyz"'])

    def test_install_rejects_http(self):
        from values import SanyanValueError

        with self.assertRaises(SanyanValueError):
            self.env.eval(['install', '"test_pkg"', '"http://example.com/pkg.zip"'])

    def test_install_rejects_ftp(self):
        from values import SanyanValueError

        with self.assertRaises(SanyanValueError):
            self.env.eval(['install', '"test_pkg"', '"ftp://example.com/pkg.zip"'])

    def test_resolve_package_path(self):
        path = _resolve_package_path('test')
        self.assertIn('packages', path)
        self.assertTrue(path.endswith('.san') or os.path.isdir(os.path.dirname(path)))


if __name__ == '__main__':
    unittest.main()
