"""IoT 相关操作：置、查、读、对"""
from ternary_core import TritValue

class IotOps:
    @staticmethod
    def set_sensor(evaluator, args):
        if not args:
            raise SyntaxError("置 需要参数")
        target = args[0]

        def ensure_trit(val):
            if isinstance(val, TritValue):
                return val
            try:
                return TritValue.from_string(str(val))
            except:
                return TritValue(0)

        if isinstance(target, list):
            pairs = evaluator._parse_pairs(target)
            last_state = TritValue(0)
            for obj, val_str in pairs:
                state = ensure_trit(TritValue.from_string(val_str))
                if obj in evaluator.sensors:
                    evaluator.sensors[obj] = state
                elif obj in evaluator.actuators:
                    evaluator.actuators[obj] = state
                else:
                    evaluator.actuators[obj] = state
                last_state = state
            return last_state

        if isinstance(target, str):
            if len(args) >= 2:
                sensor_name = target
                state = ensure_trit(evaluator.eval(args[1]))
            elif '.' in target:
                sensor_name, attr = target.split('.')
                state = ensure_trit(TritValue.from_string(attr))
            elif '：' in target:
                sensor_name, attr = target.split('：')
                state = ensure_trit(TritValue.from_string(attr))
            else:
                raise SyntaxError("置 的用法: (置 对象 状态) 或 (置 (对象.状态 ...))")
            if sensor_name in evaluator.sensors:
                evaluator.sensors[sensor_name] = state
            elif sensor_name in evaluator.actuators:
                evaluator.actuators[sensor_name] = state
            else:
                evaluator.actuators[sensor_name] = state
            return state

        raise SyntaxError("置 的参数格式错误")

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
                except:
                    val = TritValue(0)
                device_dict[key] = val
            return val

        if target in evaluator.actuators:
            val = get_device_val(evaluator.actuators, target)
            state_word = state_map.get(val.to_int(), val.symbol)
            print(f"  {target} 当前状态: {state_word} ({val.symbol})")
            return val
        if target in evaluator.sensors:
            val = get_device_val(evaluator.sensors, target)
            state_word = state_map.get(val.to_int(), val.symbol)
            print(f"  {target} 当前状态: {state_word} ({val.symbol})")
            return val

        if isinstance(target, str) and '.' in target:
            obj, attr = target.split('.')
            if obj in evaluator.actuators:
                val = get_device_val(evaluator.actuators, obj)
                state_word = state_map.get(val.to_int(), val.symbol)
                print(f"  {obj} 当前状态: {state_word} ({val.symbol})")
                return val
            if obj in evaluator.sensors:
                sensor_val = get_device_val(evaluator.sensors, obj)
                attr_val = TritValue.from_string(attr)
                print(f"  传感器 {obj} 当前值: {sensor_val.symbol}")
                return TritValue(1 if sensor_val.symbol == attr_val.symbol else -1)

        if isinstance(target, str) and '：' in target:
            obj, attr = target.split('：')
            return IotOps.query(evaluator, [obj + '.' + attr])

        raise NameError(f"无法查看: {target}（执行器、传感器中均不存在）")

    @staticmethod
    def context_op(evaluator, args):
        obj = evaluator.eval(args[0])
        if isinstance(obj, TritValue):
            obj = obj.symbol
        if obj not in evaluator.actuators and obj not in evaluator.sensors:
            evaluator.actuators[obj] = TritValue(0)
        old_ctx = evaluator.context_object
        evaluator.context_object = obj
        try:
            result = None
            for action in args[1:]:
                val = evaluator.eval(action)
                if evaluator.context_object in evaluator.actuators and isinstance(val, TritValue):
                    evaluator.actuators[evaluator.context_object] = val
                result = val
            return result if result is not None else TritValue(0)
        finally:
            evaluator.context_object = old_ctx

    @staticmethod
    def sensor_read(evaluator, args):
        sensor_name = args[0]
        if sensor_name in evaluator.sensors:
            return evaluator.sensors[sensor_name]
        raise NameError(f"未知传感器: {sensor_name}")