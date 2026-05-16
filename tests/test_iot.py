"""IoT 模块单元测试：设备注册、传感器、执行器、随机态"""
import sys
import os
import tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
from ternary_core import TritValue
from evaluator import SanyanEvaluator
from values import SanyanNameError, SanyanSyntaxError
from ops.device_registry import DeviceRegistry, MockDevice, FileDevice


class TestDeviceRegistry(unittest.TestCase):
    def setUp(self):
        self.registry = DeviceRegistry()

    def test_register_and_get(self):
        dev = MockDevice(TritValue(1))
        self.registry.register("灯", dev)
        self.assertIs(self.registry.get("灯"), dev)

    def test_get_nonexistent(self):
        self.assertIsNone(self.registry.get("不存在"))

    def test_read_write_device(self):
        self.registry.register("风扇", MockDevice(TritValue(0)))
        self.registry.write("风扇", TritValue(1))
        self.assertEqual(self.registry.read("风扇").to_int(), 1)

    def test_read_unregistered_raises(self):
        with self.assertRaises(SanyanNameError):
            self.registry.read("未知设备")

    def test_write_unregistered_raises(self):
        with self.assertRaises(SanyanNameError):
            self.registry.write("未知设备", TritValue(1))

    def test_unregister(self):
        self.registry.register("temp", MockDevice())
        self.registry.unregister("temp")
        self.assertIsNone(self.registry.get("temp"))

    def test_list_devices(self):
        self.registry.register("a", MockDevice())
        self.registry.register("b", MockDevice())
        devices = self.registry.list_devices()
        self.assertIn("a", devices)
        self.assertIn("b", devices)


class TestMockDevice(unittest.TestCase):
    def test_initial_value(self):
        dev = MockDevice(TritValue(1))
        self.assertEqual(dev.read().to_int(), 1)

    def test_write_and_read(self):
        dev = MockDevice()
        dev.write(TritValue(-1))
        self.assertEqual(dev.read().to_int(), -1)

    def test_default_initial(self):
        dev = MockDevice()
        self.assertEqual(dev.read().to_int(), 0)


class TestFileDevice(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8')
        self.tmp.close()

    def tearDown(self):
        if os.path.exists(self.tmp.name):
            os.unlink(self.tmp.name)

    def test_write_and_read(self):
        dev = FileDevice(self.tmp.name)
        dev.write(TritValue(1))
        self.assertEqual(dev.read().to_int(), 1)

    def test_read_nonexistent_file_returns_zero(self):
        dev = FileDevice("_nonexistent_device_file_.tmp")
        self.assertEqual(dev.read().to_int(), 0)


class TestIoTEvaluatorOps(unittest.TestCase):
    def setUp(self):
        self.env = SanyanEvaluator()
        self.env.device_registry.register("测试灯", MockDevice(TritValue(0)))
        self.env.device_registry.register("测试传感器", MockDevice(TritValue(0)))

    def test_set_sensor(self):
        self.env.eval(['置', '测试灯', 1])
        self.assertEqual(self.env.device_registry.read("测试灯").to_int(), 1)

    def test_set_sensor_via_write(self):
        self.env.eval(['写入', '测试灯', -1])
        self.assertEqual(self.env.device_registry.read("测试灯").to_int(), -1)

    def test_sensor_read(self):
        self.env.device_registry.write("测试传感器", TritValue(1))
        result = self.env.eval(['读', '测试传感器'])
        self.assertEqual(result.to_int(), 1)

    def test_sensor_read_via_read(self):
        self.env.device_registry.write("测试传感器", TritValue(-1))
        result = self.env.eval(['读取', '测试传感器'])
        self.assertEqual(result.to_int(), -1)

    def test_query(self):
        self.env.device_registry.write("测试灯", TritValue(1))
        result = self.env.eval(['查', '测试灯'])
        self.assertEqual(result.to_int(), 1)

    def test_query_via_query(self):
        self.env.device_registry.write("测试灯", TritValue(-1))
        result = self.env.eval(['查询', '测试灯'])
        self.assertEqual(result.to_int(), -1)

    def test_context_op(self):
        self.env.eval(['对', '测试灯', 1])
        self.assertEqual(self.env.device_registry.read("测试灯").to_int(), 1)

    def test_register_device_mock(self):
        self.env.eval(['注册设备', '新设备', 'mock'])
        dev = self.env.device_registry.get("新设备")
        self.assertIsNotNone(dev)
        self.assertIsInstance(dev, MockDevice)

    def test_register_device_syntax_error(self):
        with self.assertRaises(SanyanSyntaxError):
            self.env.eval(['注册设备'])

    def test_read_nonexistent_sensor(self):
        with self.assertRaises(SanyanNameError):
            self.env.eval(['读', '不存在'])

    def test_query_nonexistent(self):
        with self.assertRaises(SanyanNameError):
            self.env.eval(['查', '不存在'])


class TestRandomOps(unittest.TestCase):
    def setUp(self):
        self.env = SanyanEvaluator()

    def test_random_in_range(self):
        for _ in range(20):
            result = self.env.eval(['随机数', 1, 10])
            self.assertIn(result.to_int(), range(1, 11))

    def test_random_state(self):
        for _ in range(20):
            result = self.env.eval(['随机态'])
            self.assertIn(result.to_int(), [1, 0, -1])


if __name__ == '__main__':
    unittest.main()
