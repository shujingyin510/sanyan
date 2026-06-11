"""三态数据管线：ETL清洗、聚合、脏数据处理"""

import time
from typing import Any, Callable, Dict, List, Tuple
from ternary_core import TritValue
from values import SanyanSyntaxError, SanyanTypeError, SanyanValueError
from ops.registry import register, register_alias


class TernaryData:
    """三态数据单元：带置信度的数据值"""

    def __init__(self, value: Any, confidence: float = 1.0, source: str = '', timestamp: float = None):
        self.value = value
        self.confidence = max(0.0, min(1.0, confidence))
        self.source = source
        self.timestamp = timestamp or time.time()
        self.metadata: Dict[str, Any] = {}

    def is_valid(self, threshold: float = 0.5) -> bool:
        """数据是否有效（置信度 >= 阈值）"""
        return self.confidence >= threshold

    def to_trit(self) -> TritValue:
        """转为三态值"""
        if isinstance(self.value, (int, float)):
            int_val = 1 if self.value != 0 else 0
        elif isinstance(self.value, str):
            int_val = 1 if self.value else 0
        elif isinstance(self.value, (list, dict)):
            int_val = 1 if self.value else 0
        else:
            int_val = 1 if self.value is not None else 0
        return TritValue(int_val, confidence=self.confidence)

    def __str__(self):
        return str(self.value)

    def __repr__(self):
        return f'三态数据({self.value}, 置信度={self.confidence:.2f}, 来源={self.source})'


class TernaryPipeline:
    """三态数据管线：ETL处理流程"""

    def __init__(self, name: str = '默认管线'):
        self.name = name
        self.stages: List[Tuple[str, Callable]] = []
        self.stats = {
            'total': 0,
            'valid': 0,
            'invalid': 0,
            'avg_confidence': 0.0,
        }
        self._confidence_sum = 0.0

    def add_stage(self, name: str, processor: Callable):
        """添加处理阶段"""
        self.stages.append((name, processor))
        return self

    def extract(self, data: Any, source: str = '') -> TernaryData:
        """提取数据"""
        if isinstance(data, TernaryData):
            return data

        # 根据数据类型自动推断置信度
        confidence = 1.0
        if data is None:
            confidence = 0.0
        elif isinstance(data, str) and not data:
            confidence = 0.3
        elif isinstance(data, (list, dict)) and not data:
            confidence = 0.5

        return TernaryData(data, confidence, source)

    def process(self, data: TernaryData) -> TernaryData:
        """处理数据（依次执行所有阶段）"""
        self.stats['total'] += 1
        current = data

        for stage_name, processor in self.stages:
            try:
                result = processor(current)
                if isinstance(result, TernaryData):
                    current = result
                else:
                    # 包装为三态数据
                    current = TernaryData(result, current.confidence, current.source, current.timestamp)
            except Exception as e:
                # 处理失败，降低置信度
                current = TernaryData(current.value, current.confidence * 0.5, current.source, current.timestamp)
                current.metadata['error'] = str(e)
                current.metadata['failed_stage'] = stage_name

        # 更新统计
        if current.is_valid():
            self.stats['valid'] += 1
        else:
            self.stats['invalid'] += 1

        self._confidence_sum += current.confidence
        self.stats['avg_confidence'] = self._confidence_sum / self.stats['total']

        return current

    def process_batch(self, data_list: List[Any], source: str = '') -> List[TernaryData]:
        """批量处理数据"""
        results = []
        for item in data_list:
            extracted = self.extract(item, source)
            processed = self.process(extracted)
            results.append(processed)
        return results

    def get_stats(self) -> Dict[str, Any]:
        """获取处理统计"""
        return self.stats.copy()

    def reset_stats(self):
        """重置统计"""
        self.stats = {
            'total': 0,
            'valid': 0,
            'invalid': 0,
            'avg_confidence': 0.0,
        }
        self._confidence_sum = 0.0


class TernaryCleaner:
    """三态数据清洗器"""

    @staticmethod
    def remove_null(data: TernaryData) -> TernaryData:
        """移除空值"""
        if data.value is None:
            return TernaryData(None, 0.0, data.source, data.timestamp)
        return data

    @staticmethod
    def fill_default(data: TernaryData, default: Any) -> TernaryData:
        """填充默认值"""
        if data.value is None or (isinstance(data.value, str) and not data.value):
            return TernaryData(default, data.confidence * 0.8, data.source, data.timestamp)
        return data

    @staticmethod
    def normalize_confidence(data: TernaryData, min_conf: float = 0.0, max_conf: float = 1.0) -> TernaryData:
        """归一化置信度"""
        normalized = min_conf + (max_conf - min_conf) * data.confidence
        return TernaryData(data.value, normalized, data.source, data.timestamp)

    @staticmethod
    def deduplicate(data_list: List[TernaryData], key: Callable = None) -> List[TernaryData]:
        """去重（保留置信度最高的）"""
        if key is None:

            def key(x):
                return str(x.value)

        seen = {}
        for item in data_list:
            k = key(item)
            if k not in seen or item.confidence > seen[k].confidence:
                seen[k] = item

        return list(seen.values())

    @staticmethod
    def validate_range(data: TernaryData, min_val: Any = None, max_val: Any = None) -> TernaryData:
        """验证值范围"""
        if min_val is not None and data.value < min_val:
            return TernaryData(data.value, data.confidence * 0.5, data.source, data.timestamp)
        if max_val is not None and data.value > max_val:
            return TernaryData(data.value, data.confidence * 0.5, data.source, data.timestamp)
        return data


class TernaryAggregator:
    """三态数据聚合器"""

    @staticmethod
    def average(data_list: List[TernaryData]) -> TernaryData:
        """平均值（置信度加权）"""
        if not data_list:
            return TernaryData(0, 0.0)

        total_weight = 0.0
        weighted_sum = 0.0

        for item in data_list:
            val = item.value
            if isinstance(val, TritValue):
                val = val.to_int() if val.is_numeric() else 0
            if isinstance(val, (int, float)):
                weighted_sum += val * item.confidence
                total_weight += item.confidence

        if total_weight == 0:
            return TernaryData(0, 0.0)

        avg = weighted_sum / total_weight
        avg_conf = total_weight / len(data_list)

        return TernaryData(avg, avg_conf)

    @staticmethod
    def sum(data_list: List[TernaryData]) -> TernaryData:
        """求和"""
        total = 0.0
        min_conf = 1.0

        for item in data_list:
            val = item.value
            if isinstance(val, TritValue):
                val = val.to_int() if val.is_numeric() else 0
            if isinstance(val, (int, float)):
                total += val
                min_conf = min(min_conf, item.confidence)

        return TernaryData(total, min_conf)

    @staticmethod
    def count(data_list: List[TernaryData], threshold: float = 0.5) -> TernaryData:
        """计数（只统计有效数据）"""
        valid_count = sum(1 for item in data_list if item.is_valid(threshold))
        total = len(data_list)
        conf = valid_count / total if total > 0 else 0.0

        return TernaryData(valid_count, conf)

    @staticmethod
    def group_by(data_list: List[TernaryData], key_func: Callable) -> Dict[str, List[TernaryData]]:
        """分组"""
        groups = {}
        for item in data_list:
            k = str(key_func(item))
            groups.setdefault(k, []).append(item)
        return groups

    @staticmethod
    def merge_confidence(data_list: List[TernaryData]) -> TernaryData:
        """融合置信度（取最小值）"""
        if not data_list:
            return TernaryData(None, 0.0)

        min_conf = min(item.confidence for item in data_list)
        values = [item.value for item in data_list]

        # 返回融合后的数据
        if all(isinstance(v, (int, float)) for v in values):
            avg = sum(values) / len(values)
            return TernaryData(avg, min_conf)

        return TernaryData(values, min_conf)


class TernaryValidator:
    """三态数据验证器"""

    @staticmethod
    def schema(data: Any, schema: Dict[str, Any]) -> TernaryData:
        """模式验证"""
        errors = []

        for field, rules in schema.items():
            if field not in data:
                if rules.get('required', False):
                    errors.append(f'缺少必填字段: {field}')
                continue

            value = data[field]

            # 类型检查
            expected_type = rules.get('type')
            if expected_type:
                if expected_type == 'int' and not isinstance(value, int):
                    errors.append(f'{field} 类型错误: 期望int，得到{type(value).__name__}')
                elif expected_type == 'str' and not isinstance(value, str):
                    errors.append(f'{field} 类型错误: 期望str，得到{type(value).__name__}')
                elif expected_type == 'float' and not isinstance(value, (int, float)):
                    errors.append(f'{field} 类型错误: 期望float，得到{type(value).__name__}')

            # 范围检查
            min_val = rules.get('min')
            max_val = rules.get('max')
            if min_val is not None and value < min_val:
                errors.append(f'{field} 小于最小值 {min_val}')
            if max_val is not None and value > max_val:
                errors.append(f'{field} 大于最大值 {max_val}')

        if errors:
            return TernaryData({'errors': errors}, 0.0)

        return TernaryData(data, 1.0)

    @staticmethod
    def confidence_check(data: TernaryData, threshold: float = 0.5) -> TernaryData:
        """置信度检查"""
        if data.confidence < threshold:
            return TernaryData(
                data.value,
                data.confidence,
                data.source,
                data.timestamp,
            )
        return data


# ── 三言操作接口 ──


def _ternary_pipeline_new(evaluator, args):
    """三态管线(名称) — 创建数据管线"""
    name = '默认管线'
    if args:
        name_val = evaluator.eval(args[0])
        name = name_val.to_payload() if isinstance(name_val, TritValue) and name_val.is_string() else str(name_val)
    return TernaryPipeline(name)


def _ternary_pipeline_add_stage(evaluator, args):
    """三态管线加阶段(管线, 名称, 处理器)"""
    if len(args) < 3:
        raise SanyanSyntaxError('三态管线加阶段 需要管线、名称和处理器')
    pipe = evaluator.eval(args[0])
    if not isinstance(pipe, TernaryPipeline):
        raise SanyanTypeError('第一个参数必须是三态管线')
    name = evaluator.eval(args[1])
    if isinstance(name, TritValue) and name.is_string():
        name = name.to_payload()
    handler = args[2]  # 不求值，作为函数节点
    pipe.add_stage(str(name), lambda data: evaluator.eval([handler, data]))
    return pipe


def _ternary_pipeline_process(evaluator, args):
    """三态管线处理(管线, 数据)"""
    if len(args) < 2:
        raise SanyanSyntaxError('三态管线处理 需要管线和数据')
    pipe = evaluator.eval(args[0])
    if not isinstance(pipe, TernaryPipeline):
        raise SanyanTypeError('第一个参数必须是三态管线')
    data = evaluator.eval(args[1])
    if not isinstance(data, TernaryData):
        data = TernaryData(data)
    return pipe.process(data)


def _ternary_pipeline_stats(evaluator, args):
    """三态管线统计(管线)"""
    if not args:
        raise SanyanSyntaxError('三态管线统计 需要管线参数')
    pipe = evaluator.eval(args[0])
    if not isinstance(pipe, TernaryPipeline):
        raise SanyanTypeError('参数必须是三态管线')
    return pipe.get_stats()


def _ternary_data_new(evaluator, args):
    """三态数据(值 [, 置信度 [, 来源]])"""
    if not args:
        raise SanyanSyntaxError('三态数据 需要至少一个参数')
    value = evaluator.eval(args[0])
    conf = 1.0
    source = ''
    if len(args) >= 2:
        conf_val = evaluator.eval(args[1])
        conf = conf_val.to_float() if isinstance(conf_val, TritValue) else float(conf_val)
    if len(args) >= 3:
        source_val = evaluator.eval(args[2])
        source = (
            source_val.to_payload() if isinstance(source_val, TritValue) and source_val.is_string() else str(source_val)
        )
    return TernaryData(value, conf, source)


def _ternary_clean(evaluator, args):
    """三态清洗(数据, 规则)"""
    if len(args) < 2:
        raise SanyanSyntaxError('三态清洗 需要数据和规则')
    data = evaluator.eval(args[0])
    if not isinstance(data, TernaryData):
        data = TernaryData(data)
    rule = evaluator.eval(args[1])

    if isinstance(rule, str) and rule in ('去空', 'remove_null'):
        return TernaryCleaner.remove_null(data)
    elif isinstance(rule, str) and rule in ('归一化', 'normalize'):
        return TernaryCleaner.normalize_confidence(data)

    return data


def _ternary_aggregate(evaluator, args):
    """三态聚合(数据列表, 方式)"""
    if len(args) < 2:
        raise SanyanSyntaxError('三态聚合 需要数据列表和方式')
    data_list = evaluator.eval(args[0])
    if not isinstance(data_list, list):
        raise SanyanTypeError('第一个参数必须是列表')
    method = evaluator.eval(args[1])
    if isinstance(method, TritValue) and method.is_string():
        method = method.to_payload()

    # 转换为 TernaryData 列表
    ternary_list = []
    for item in data_list:
        if isinstance(item, TernaryData):
            ternary_list.append(item)
        else:
            ternary_list.append(TernaryData(item))

    if method in ('平均', 'average'):
        return TernaryAggregator.average(ternary_list)
    elif method in ('求和', 'sum'):
        return TernaryAggregator.sum(ternary_list)
    elif method in ('计数', 'count'):
        return TernaryAggregator.count(ternary_list)
    elif method in ('融合', 'merge'):
        return TernaryAggregator.merge_confidence(ternary_list)

    raise SanyanValueError(f'未知聚合方式: {method}')


def _ternary_validate(evaluator, args):
    """三态验证(数据, 规则)"""
    if len(args) < 2:
        raise SanyanSyntaxError('三态验证 需要数据和规则')
    data = evaluator.eval(args[0])
    rule = evaluator.eval(args[1])

    if isinstance(rule, dict):
        return TernaryValidator.schema(data, rule)

    return TernaryData(data, 1.0)


register('三态管线', _ternary_pipeline_new)
register('三态管线加阶段', _ternary_pipeline_add_stage)
register('三态管线处理', _ternary_pipeline_process)
register('三态管线统计', _ternary_pipeline_stats)
register('三态数据', _ternary_data_new)
register('三态清洗', _ternary_clean)
register('三态聚合', _ternary_aggregate)
register('三态验证', _ternary_validate)

register_alias('ternary_pipeline', '三态管线')
register_alias('ternary_pipeline_add_stage', '三态管线加阶段')
register_alias('ternary_pipeline_process', '三态管线处理')
register_alias('ternary_pipeline_stats', '三态管线统计')
register_alias('ternary_data', '三态数据')
register_alias('ternary_clean', '三态清洗')
register_alias('ternary_aggregate', '三态聚合')
register_alias('ternary_validate', '三态验证')
