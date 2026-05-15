"""IoT 设备注册表与协议抽象"""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional
from ternary_core import TritValue
from values import SanyanNameError, SanyanValueError


class Device(ABC):
    """设备协议：所有设备必须实现 read 和 write。"""
    @abstractmethod
    def read(self) -> TritValue:
        pass

    @abstractmethod
    def write(self, value: TritValue) -> None:
        pass


class MockDevice(Device):
    """模拟设备：内存中的三态值。"""
    def __init__(self, initial: TritValue = TritValue(0)) -> None:
        self._value = initial

    def read(self) -> TritValue:
        return self._value

    def write(self, value: TritValue) -> None:
        self._value = value


class FileDevice(Device):
    """文件模拟设备：用文件持久化状态。"""
    def __init__(self, path: str) -> None:
        self.path = path

    def read(self) -> TritValue:
        try:
            with open(self.path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            if not content:
                return TritValue(0)
            if content in TritValue.STATE_MAP:
                return TritValue(TritValue.STATE_MAP[content])
            raise SanyanValueError(f"设备文件 '{self.path}' 内容无法识别: '{content}'")
        except (IOError, OSError):
            return TritValue(0)

    def write(self, value: TritValue) -> None:
        try:
            with open(self.path, 'w', encoding='utf-8') as f:
                f.write(value.symbol)
        except (IOError, OSError) as e:
            raise SanyanValueError(f"设备写入失败: {e}")


class DeviceRegistry:
    """设备注册表：管理所有 IoT 设备。"""
    def __init__(self) -> None:
        self._devices: dict[str, Device] = {}

    def register(self, name: str, device: Device) -> None:
        self._devices[name] = device

    def unregister(self, name: str) -> None:
        if name in self._devices:
            del self._devices[name]

    def get(self, name: str) -> Optional[Device]:
        return self._devices.get(name)

    def read(self, name: str) -> TritValue:
        device = self._devices.get(name)
        if device is None:
            raise SanyanNameError(f"未注册的设备: {name}")
        return device.read()

    def write(self, name: str, value: TritValue) -> None:
        device = self._devices.get(name)
        if device is None:
            raise SanyanNameError(f"未注册的设备: {name}")
        device.write(value)

    def list_devices(self) -> list[str]:
        return list(self._devices.keys())
