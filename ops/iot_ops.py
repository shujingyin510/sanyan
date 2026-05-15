"""IoT 相关操作：置、查、读、对"""
from ternary_core import TritValue
from values import SanyanSyntaxError, SanyanNameError, SanyanValueError
from ops.device_registry import MockDevice
from ops.registry import register

class IotOps:
    @staticmethod
    def set_sensor(evaluator, args):
        if not args:
            raise SanyanSyntaxError("置 需要参数")
        target = args[0]

        def ensure_trit(val):
            if isinstance(val, TritValue):
                return val
            try:
                return TritValue.from_string(str(val))
            except Exception:
                return TritValue(0)

        def sync_device(name, state):
            """同步更新旧 dicts 和新 registry。"""
            if name in evaluator.sensors:
                evaluator.sensors[name] = state
            if name in evaluator.actuators:
                evaluator.actuators[name] = state
            if hasattr(evaluator, 'device_registry'):
                dev = evaluator.device_registry.get(name)
                if dev:
                    dev.write(state)
                else:
                    evaluator.device_registry.register(name, MockDevice(state))

        if isinstance(target, list):
            pairs = evaluator._parse_pairs(target)
            last_state = TritValue(0)
            for obj, val_str in pairs:
                try:
                    state = ensure_trit(TritValue.from_string(val_str))
                except ValueError:
                    state = ensure_trit(val_str)
                sync_device(obj, state)
                last_state = state
            return last_state

        if isinstance(target, str):
            if len(args) >= 2:
                sensor_name = target
                state = ensure_trit(evaluator.eval(args[1]))
            elif '.' in target:
                sensor_name, attr = target.split('.', 1)
                state = ensure_trit(TritValue.from_string(attr))
            elif '：' in target:
                sensor_name, attr = target.split('：', 1)
                state = ensure_trit(TritValue.from_string(attr))
            else:
                raise SanyanSyntaxError("置 的用法: (置 对象 状态) 或 (置 (对象.状态 ...))")
            sync_device(sensor_name, state)
            return state

        raise SanyanSyntaxError("置 的参数格式错误")

    @staticmethod
    def query(evaluator, args):
        target = args[0]
        if isinstance(target, list):
            results = []
            for item in target:
                result = IotOps.query(evaluator, [item])
                results.append(result)
            return results[-1] if results else TritValue(0)

        state_map = {1: "开", 0: "守", -1: "关", '+': "开", '0': "守", '-': "关"}

        def get_device_val(device_dict, key):
            val = device_dict.get(key, TritValue(0))
            if not isinstance(val, TritValue):
                try:
                    val = TritValue.from_string(str(val))
                except Exception:
                    val = TritValue(0)
                device_dict[key] = val
            return val

        def print_state(name, val):
            state_word = state_map.get(val.to_int(), val.symbol)
            print(f"  {name} 当前状态: {state_word} ({val.symbol})")
            return val

        # 优先从 registry 读取
        if hasattr(evaluator, 'device_registry'):
            dev = evaluator.device_registry.get(target)
            if dev:
                return print_state(target, dev.read())

        if target in evaluator.actuators:
            val = get_device_val(evaluator.actuators, target)
            return print_state(target, val)
        if target in evaluator.sensors:
            val = get_device_val(evaluator.sensors, target)
            return print_state(target, val)

        if isinstance(target, str) and '.' in target:
            obj, attr = target.split('.', 1)
            if hasattr(evaluator, 'device_registry'):
                dev = evaluator.device_registry.get(obj)
                if dev:
                    sensor_val = dev.read()
                    attr_val = TritValue.from_string(attr)
                    print(f"  传感器 {obj} 当前值: {sensor_val.symbol}")
                    return TritValue(1 if sensor_val.symbol == attr_val.symbol else -1)
            if obj in evaluator.actuators:
                val = get_device_val(evaluator.actuators, obj)
                return print_state(obj, val)
            if obj in evaluator.sensors:
                sensor_val = get_device_val(evaluator.sensors, obj)
                attr_val = TritValue.from_string(attr)
                print(f"  传感器 {obj} 当前值: {sensor_val.symbol}")
                return TritValue(1 if sensor_val.symbol == attr_val.symbol else -1)

        if isinstance(target, str) and '：' in target:
            obj, attr = target.split('：', 1)
            return IotOps.query(evaluator, [obj + '.' + attr])

        raise SanyanNameError(f"无法查看: {target}（执行器、传感器中均不存在）")

    @staticmethod
    def context_op(evaluator, args):
        obj = evaluator.eval(args[0])
        if isinstance(obj, TritValue):
            obj = obj.symbol
        if obj not in evaluator.actuators and obj not in evaluator.sensors:
            evaluator.actuators[obj] = TritValue(0)
            if hasattr(evaluator, 'device_registry'):
                evaluator.device_registry.register(obj, MockDevice(TritValue(0)))
        old_ctx = evaluator.context_object
        evaluator.context_object = obj
        try:
            result = None
            for action in args[1:]:
                val = evaluator.eval(action)
                if evaluator.context_object in evaluator.actuators and isinstance(val, TritValue):
                    evaluator.actuators[evaluator.context_object] = val
                    if hasattr(evaluator, 'device_registry'):
                        dev = evaluator.device_registry.get(evaluator.context_object)
                        if dev:
                            dev.write(val)
                result = val
            return result if result is not None else TritValue(0)
        finally:
            evaluator.context_object = old_ctx

    @staticmethod
    def sensor_read(evaluator, args):
        sensor_name = args[0]
        # 优先从 registry 读取
        if hasattr(evaluator, 'device_registry'):
            dev = evaluator.device_registry.get(sensor_name)
            if dev:
                return dev.read()
        if sensor_name in evaluator.sensors:
            return evaluator.sensors[sensor_name]
        raise SanyanNameError(f"未知传感器: {sensor_name}")

    @staticmethod
    def register_device_op(evaluator, args):
        """注册设备到设备注册表。"""
        if len(args) < 2:
            raise SanyanSyntaxError("注册设备 需要名称和类型")
        name = args[0]
        device_type = args[1]
        if not hasattr(evaluator, 'device_registry'):
            raise SanyanNameError("设备注册表不可用")
        from ops.device_registry import MockDevice, FileDevice
        if device_type == 'mock' or device_type == '模拟':
            device = MockDevice()
        elif device_type == 'file' or device_type == '文件':
            path = evaluator.eval(args[2]) if len(args) > 2 else f"device_{name}.txt"
            device = FileDevice(str(path))
        else:
            raise SanyanValueError(f"未知设备类型: {device_type}")
        evaluator.device_registry.register(name, device)
        return TritValue(0)

# 注册 IoT 操作及中文别名
register('write', IotOps.set_sensor)
register('query', IotOps.query)
register('context', IotOps.context_op)
register('read', IotOps.sensor_read)
register('register_device', IotOps.register_device_op)
register('置', IotOps.set_sensor)
register('查', IotOps.query)
register('读', IotOps.sensor_read)
register('读取', IotOps.sensor_read)
register('写入', IotOps.set_sensor)
register('查询', IotOps.query)
