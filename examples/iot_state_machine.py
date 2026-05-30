"""
iot_state_machine.py — 二值逻辑IoT设备状态机（对比实现）
功能与 iot_state_machine.san 相同，展示二值逻辑需要多少额外代码
"""

import random
from enum import Enum
from typing import Optional


class TriState(Enum):
    TRUE = 'true'
    FALSE = 'false'
    MAYBE = 'maybe'


class DeviceState(Enum):
    ONLINE = 'online'
    OFFLINE = 'offline'
    DEGRADED = 'degraded'


def check_network() -> TriState:
    r = random.randint(1, 100)
    if r <= 70:
        return TriState.TRUE
    if r <= 85:
        return TriState.MAYBE
    return TriState.FALSE


def check_battery() -> TriState:
    r = random.randint(1, 100)
    if r <= 60:
        return TriState.TRUE
    if r <= 80:
        return TriState.MAYBE
    return TriState.FALSE


def check_lock() -> TriState:
    r = random.randint(1, 100)
    if r <= 85:
        return TriState.TRUE
    if r <= 95:
        return TriState.MAYBE
    return TriState.FALSE


def check_fingerprint() -> TriState:
    r = random.randint(1, 100)
    if r <= 75:
        return TriState.TRUE
    if r <= 90:
        return TriState.MAYBE
    return TriState.FALSE


def tri_and(a: TriState, b: TriState) -> TriState:
    """三值 AND — Python 需要手写，三言内置"""
    if a == TriState.FALSE or b == TriState.FALSE:
        return TriState.FALSE
    if a == TriState.TRUE and b == TriState.TRUE:
        return TriState.TRUE
    return TriState.MAYBE


def tri_or(a: TriState, b: TriState) -> TriState:
    """三值 OR — Python 需要手写"""
    if a == TriState.TRUE or b == TriState.TRUE:
        return TriState.TRUE
    if a == TriState.FALSE and b == TriState.FALSE:
        return TriState.FALSE
    return TriState.MAYBE


def device_state(network, battery, lock, fingerprint) -> TriState:
    if lock == TriState.FALSE:
        return TriState.FALSE
    aux = tri_and(network, fingerprint)
    if battery == TriState.FALSE:
        return TriState.FALSE
    return tri_and(tri_and(lock, battery), aux)


def device_action(state: TriState, network, battery) -> str:
    if state == TriState.FALSE:
        print('  🔴 设备故障，进入安全锁定模式')
        return '安全锁定'
    elif state == TriState.MAYBE:
        print('  🟡 设备状态不确定，进入降级模式')
        if battery == TriState.MAYBE:
            print('    → 电池状态不明，降低功耗')
            return '低功耗模式'
        if network == TriState.MAYBE:
            print('    → 网络状态不明，缓存本地日志')
            return '离线模式'
        return '降级运行'
    else:
        print('  🟢 设备正常，全功能运行')
        return '全功能'


def should_restart(current: TriState, battery, network) -> TriState:
    if current == TriState.FALSE and battery == TriState.TRUE:
        return TriState.TRUE
    if current == TriState.MAYBE and network == TriState.MAYBE:
        return TriState.MAYBE
    return TriState.FALSE


def main():
    print('═' * 43)
    print('  二值逻辑IoT设备状态机 v1.0 (Python)')
    print('═' * 43)
    print()

    count_full = count_degraded = count_locked = count_restart = 0

    for t in range(1, 16):
        print(f'═══ 时刻 #{t} ═══')
        net = check_network()
        bat = check_battery()
        lock = check_lock()
        fp = check_fingerprint()
        print(f'  子系统: 网络={net.value} 电池={bat.value} 锁芯={lock.value} 指纹={fp.value}')

        state = device_state(net, bat, lock, fp)
        print(f'  设备状态: {state.value}')

        action = device_action(state, net, bat)

        restart = should_restart(state, bat, net)
        if restart == TriState.TRUE:
            print('  ⟳ 执行设备重启...')
            count_restart += 1
        elif restart == TriState.MAYBE:
            print('  ⟳ 等待中（可能需要重启）...')
        print()

        if action == '全功能':
            count_full += 1
        elif action in ('低功耗模式', '离线模式', '降级运行'):
            count_degraded += 1
        elif action == '安全锁定':
            count_locked += 1

    print('═' * 43)
    print('  设备运行统计')
    print('═' * 43)
    print(f'  全功能运行: {count_full} 个时刻')
    print(f'  降级运行:   {count_degraded} 个时刻')
    print(f'  安全锁定:   {count_locked} 个时刻')
    print(f'  执行重启:   {count_restart} 次')
    print()
    print('二值逻辑需要：手写 tri_and/tri_or 函数，Enum 类定义')
    print('三值逻辑只需：内置 且/或/非 运算符')


if __name__ == '__main__':
    main()
