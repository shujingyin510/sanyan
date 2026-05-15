"""JSON 解析与生成支持"""
import json
from ternary_core import TritValue
from values import SanyanValueError, SanyanTypeError
from ops.registry import register

class JsonOps:
    @staticmethod
    def to_json(evaluator, args):
        if len(args) != 1:
            raise SanyanValueError("转JSON 需要一个参数")
        val = evaluator.eval(args[0])

        def convert(obj):
            if isinstance(obj, TritValue):
                return obj.to_float() if obj.is_float() else obj.to_int()
            if isinstance(obj, list):
                return [convert(i) for i in obj]
            if isinstance(obj, dict):
                return {str(k): convert(v) for k, v in obj.items()}
            return obj

        try:
            return json.dumps(convert(val), ensure_ascii=False)
        except Exception as e:
            raise SanyanTypeError(f"无法转换为 JSON: {e}")

    @staticmethod
    def from_json(evaluator, args):
        if len(args) != 1:
            raise SanyanValueError("解析JSON 需要一个参数")
        s = evaluator.eval(args[0])
        if not isinstance(s, str):
            raise SanyanTypeError("解析JSON 需要字符串参数")

        def convert(obj):
            if isinstance(obj, bool):
                return TritValue(1 if obj else -1)
            if isinstance(obj, (int, float)):
                return TritValue(obj)
            if isinstance(obj, list):
                return [convert(i) for i in obj]
            if isinstance(obj, dict):
                return {k: convert(v) for k, v in obj.items()}
            return obj

        try:
            data = json.loads(s)
            return convert(data)
        except Exception as e:
            raise SanyanValueError(f"JSON 解析失败: {e}")

# 注册 JSON 操作
register('to_json', JsonOps.to_json)
register('from_json', JsonOps.from_json)
