"""
日志模块
提供日志配置和获取 logger 的功能。
"""

import logging
import sys
from typing import Optional, TextIO


def configure_logging(
    level: int = logging.INFO,
    fmt: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream: Optional[TextIO] = None,
) -> None:
    """配置根日志记录器。

    Args:
        level: 日志级别，默认 INFO。
        fmt: 日志格式字符串。
        stream: 日志输出流，默认 sys.stdout。
    """
    logging.basicConfig(level=level, format=fmt, stream=stream or sys.stdout)


def get_logger(name: str) -> logging.Logger:
    """获取指定名称的 logger。

    Args:
        name: logger 名称，通常使用 __name__。

    Returns:
        logging.Logger 实例。
    """
    return logging.getLogger(name)