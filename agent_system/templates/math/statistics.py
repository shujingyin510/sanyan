# name: 统计函数
# keywords: 统计, 均值, 中位数, 标准差, 方差, 概率, statistics, mean, median, standard deviation, variance, probability

from typing import List


def mean(data: List[float]) -> float:
    """计算均值"""
    if not data:
        raise ValueError('数据不能为空')
    return sum(data) / len(data)


def median(data: List[float]) -> float:
    """计算中位数"""
    if not data:
        raise ValueError('数据不能为空')
    sorted_data = sorted(data)
    n = len(sorted_data)
    if n % 2 == 1:
        return sorted_data[n // 2]
    else:
        return (sorted_data[n // 2 - 1] + sorted_data[n // 2]) / 2


def mode(data: List[float]) -> List[float]:
    """计算众数"""
    if not data:
        raise ValueError('数据不能为空')
    from collections import Counter

    counts = Counter(data)
    max_count = max(counts.values())
    return [k for k, v in counts.items() if v == max_count]


def variance(data: List[float], population: bool = True) -> float:
    """计算方差

    Args:
        data: 数据列表
        population: True 为总体方差，False 为样本方差
    """
    if len(data) < 2:
        raise ValueError('数据量不足')
    avg = mean(data)
    squared_diffs = [(x - avg) ** 2 for x in data]
    if population:
        return sum(squared_diffs) / len(data)
    else:
        return sum(squared_diffs) / (len(data) - 1)


def standard_deviation(data: List[float], population: bool = True) -> float:
    """计算标准差"""
    return variance(data, population) ** 0.5


def covariance(x: List[float], y: List[float]) -> float:
    """计算协方差"""
    if len(x) != len(y):
        raise ValueError('数据长度不匹配')
    if len(x) < 2:
        raise ValueError('数据量不足')
    n = len(x)
    mean_x = mean(x)
    mean_y = mean(y)
    return sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n)) / n


def correlation(x: List[float], y: List[float]) -> float:
    """计算皮尔逊相关系数"""
    cov = covariance(x, y)
    std_x = standard_deviation(x)
    std_y = standard_deviation(y)
    if std_x == 0 or std_y == 0:
        raise ValueError('标准差为 0，无法计算相关系数')
    return cov / (std_x * std_y)


def percentile(data: List[float], p: float) -> float:
    """计算百分位数

    Args:
        data: 数据列表
        p: 百分位数 (0-100)
    """
    if not data:
        raise ValueError('数据不能为空')
    if not 0 <= p <= 100:
        raise ValueError('百分位数必须在 0-100 之间')
    sorted_data = sorted(data)
    n = len(sorted_data)
    k = (n - 1) * p / 100
    f = int(k)
    c = k - f
    if f + 1 < n:
        return sorted_data[f] + c * (sorted_data[f + 1] - sorted_data[f])
    else:
        return sorted_data[f]


def quartiles(data: List[float]) -> dict:
    """计算四分位数"""
    return {
        'Q1': percentile(data, 25),
        'Q2': percentile(data, 50),
        'Q3': percentile(data, 75),
        'IQR': percentile(data, 75) - percentile(data, 25),
    }


def z_score(data: List[float]) -> List[float]:
    """计算 Z 分数"""
    avg = mean(data)
    std = standard_deviation(data)
    if std == 0:
        raise ValueError('标准差为 0，无法计算 Z 分数')
    return [(x - avg) / std for x in data]


def histogram(data: List[float], bins: int = 10) -> dict:
    """计算直方图"""
    if not data:
        raise ValueError('数据不能为空')
    min_val = min(data)
    max_val = max(data)
    if min_val == max_val:
        return {'bins': [min_val], 'counts': [len(data)]}

    bin_width = (max_val - min_val) / bins
    edges = [min_val + i * bin_width for i in range(bins + 1)]
    counts = [0] * bins

    for x in data:
        for i in range(bins):
            if edges[i] <= x < edges[i + 1] or (i == bins - 1 and x == edges[i + 1]):
                counts[i] += 1
                break

    return {
        'bins': edges,
        'counts': counts,
        'bin_width': bin_width,
    }


def linear_regression(x: List[float], y: List[float]) -> dict:
    """简单线性回归"""
    if len(x) != len(y):
        raise ValueError('数据长度不匹配')
    if len(x) < 2:
        raise ValueError('数据量不足')

    n = len(x)
    mean_x = mean(x)
    mean_y = mean(y)

    ss_xy = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))
    ss_xx = sum((x[i] - mean_x) ** 2 for i in range(n))

    if ss_xx == 0:
        raise ValueError('x 方差为 0，无法拟合')

    slope = ss_xy / ss_xx
    intercept = mean_y - slope * mean_x

    # R² 计算
    y_pred = [slope * xi + intercept for xi in x]
    ss_res = sum((y[i] - y_pred[i]) ** 2 for i in range(n))
    ss_tot = sum((y[i] - mean_y) ** 2 for i in range(n))
    r_squared = 1 - ss_res / ss_tot if ss_tot != 0 else 0

    return {
        'slope': slope,
        'intercept': intercept,
        'r_squared': r_squared,
    }
