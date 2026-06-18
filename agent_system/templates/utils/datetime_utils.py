# name: 日期时间工具函数
# keywords: 日期, 时间, 时间戳, 格式化, 计算, datetime, date, time, timestamp, format, parse

from datetime import datetime, timedelta, date
from typing import Optional, Union


def now() -> datetime:
    """获取当前时间"""
    return datetime.now()


def today() -> date:
    """获取今天的日期"""
    return date.today()


def format_datetime(dt: Union[datetime, date], fmt: str = '%Y-%m-%d %H:%M:%S') -> str:
    """格式化日期时间"""
    return dt.strftime(fmt)


def parse_datetime(s: str, fmt: str = '%Y-%m-%d %H:%M:%S') -> datetime:
    """解析日期时间字符串"""
    return datetime.strptime(s, fmt)


def format_date(d: Union[date, datetime], fmt: str = '%Y-%m-%d') -> str:
    """格式化日期"""
    return d.strftime(fmt)


def parse_date(s: str, fmt: str = '%Y-%m-%d') -> date:
    """解析日期字符串"""
    return datetime.strptime(s, fmt).date()


def format_time(t: Union[datetime, timedelta], fmt: str = '%H:%M:%S') -> str:
    """格式化时间"""
    if isinstance(t, timedelta):
        hours = t.seconds // 3600
        minutes = (t.seconds % 3600) // 60
        seconds = t.seconds % 60
        return f'{hours:02d}:{minutes:02d}:{seconds:02d}'
    return t.strftime(fmt)


def timestamp() -> float:
    """获取当前时间戳"""
    return datetime.now().timestamp()


def from_timestamp(ts: float) -> datetime:
    """从时间戳创建日期时间"""
    return datetime.fromtimestamp(ts)


def add_days(dt: Union[datetime, date], days: int) -> Union[datetime, date]:
    """添加天数"""
    return dt + timedelta(days=days)


def add_hours(dt: datetime, hours: int) -> datetime:
    """添加小时"""
    return dt + timedelta(hours=hours)


def add_minutes(dt: datetime, minutes: int) -> datetime:
    """添加分钟"""
    return dt + timedelta(minutes=minutes)


def add_seconds(dt: datetime, seconds: int) -> datetime:
    """添加秒"""
    return dt + timedelta(seconds=seconds)


def diff_days(dt1: Union[datetime, date], dt2: Union[datetime, date]) -> int:
    """计算两个日期之间的天数差"""
    if isinstance(dt1, datetime):
        dt1 = dt1.date()
    if isinstance(dt2, datetime):
        dt2 = dt2.date()
    return (dt1 - dt2).days


def diff_seconds(dt1: datetime, dt2: datetime) -> float:
    """计算两个时间之间的秒数差"""
    return (dt1 - dt2).total_seconds()


def is_leap_year(year: int) -> bool:
    """判断是否为闰年"""
    return (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)


def days_in_month(year: int, month: int) -> int:
    """获取某月的天数"""
    if month == 2:
        return 29 if is_leap_year(year) else 28
    elif month in [4, 6, 9, 11]:
        return 30
    else:
        return 31


def day_of_week(dt: Union[datetime, date]) -> str:
    """获取星期几"""
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    return days[dt.weekday()]


def day_of_week_cn(dt: Union[datetime, date]) -> str:
    """获取星期几（中文）"""
    days = ['星期一', '星期二', '星期三', '星期四', '星期五', '星期六', '星期日']
    return days[dt.weekday()]


def week_number(dt: Union[datetime, date]) -> int:
    """获取周数"""
    return dt.isocalendar()[1]


def month_name(month: int) -> str:
    """获取月份名称"""
    names = [
        'January',
        'February',
        'March',
        'April',
        'May',
        'June',
        'July',
        'August',
        'September',
        'October',
        'November',
        'December',
    ]
    return names[month - 1]


def month_name_cn(month: int) -> str:
    """获取月份名称（中文）"""
    names = ['一月', '二月', '三月', '四月', '五月', '六月', '七月', '八月', '九月', '十月', '十一月', '十二月']
    return names[month - 1]


def quarter(dt: Union[datetime, date]) -> int:
    """获取季度"""
    return (dt.month - 1) // 3 + 1


def start_of_day(dt: datetime) -> datetime:
    """获取当天开始时间"""
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


def end_of_day(dt: datetime) -> datetime:
    """获取当天结束时间"""
    return dt.replace(hour=23, minute=59, second=59, microsecond=999999)


def start_of_week(dt: Union[datetime, date]) -> date:
    """获取本周开始日期（周一）"""
    if isinstance(dt, datetime):
        dt = dt.date()
    return dt - timedelta(days=dt.weekday())


def end_of_week(dt: Union[datetime, date]) -> date:
    """获取本周结束日期（周日）"""
    if isinstance(dt, datetime):
        dt = dt.date()
    return dt + timedelta(days=6 - dt.weekday())


def start_of_month(dt: Union[datetime, date]) -> date:
    """获取本月开始日期"""
    if isinstance(dt, datetime):
        dt = dt.date()
    return dt.replace(day=1)


def end_of_month(dt: Union[datetime, date]) -> date:
    """获取本月结束日期"""
    if isinstance(dt, datetime):
        dt = dt.date()
    return dt.replace(day=days_in_month(dt.year, dt.month))


def age(birth_date: date, reference_date: Optional[date] = None) -> int:
    """计算年龄"""
    if reference_date is None:
        reference_date = date.today()
    age = reference_date.year - birth_date.year
    if (reference_date.month, reference_date.day) < (birth_date.month, birth_date.day):
        age -= 1
    return age


def countdown(target: Union[datetime, date]) -> dict:
    """倒计时"""
    now = datetime.now()
    if isinstance(target, date) and not isinstance(target, datetime):
        target = datetime.combine(target, datetime.min.time())

    diff = target - now
    if diff.total_seconds() < 0:
        return {'expired': True, 'days': 0, 'hours': 0, 'minutes': 0, 'seconds': 0}

    days = diff.days
    hours = diff.seconds // 3600
    minutes = (diff.seconds % 3600) // 60
    seconds = diff.seconds % 60

    return {
        'expired': False,
        'days': days,
        'hours': hours,
        'minutes': minutes,
        'seconds': seconds,
        'total_seconds': int(diff.total_seconds()),
    }
