def is_narcissistic_number(n: int) -> bool:
    """
    判断一个整数是否为水仙花数（阿姆斯特朗数）。
    水仙花数是指一个 n 位正整数，其各位数字的 n 次方之和等于该数本身。
    例如：153 = 1^3 + 5^3 + 3^3
    """
    if not isinstance(n, int) or n < 0:
        return False
    digits = [int(d) for d in str(n)]
    power = len(digits)
    return sum(d ** power for d in digits) == n


def is_prime(n: int) -> bool:
    """
    判断一个整数是否为素数。
    素数定义为大于 1 的自然数，且仅能被 1 和自身整除。
    """
    if not isinstance(n, int) or n < 2:
        return False
    if n == 2:
        return True
    if n % 2 == 0:
        return False
    # 检查奇数因子
    for i in range(3, int(n ** 0.5) + 1, 2):
        if n % i == 0:
            return False
    return True


def fibonacci(n: int) -> int:
    """
    返回第 n 个斐波那契数（从 0 开始：F(0)=0, F(1)=1）。
    """
    if not isinstance(n, int) or n < 0:
        raise ValueError("n must be a non-negative integer")
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a


def factorial(n: int) -> int:
    """
    返回 n 的阶乘 (n!)。
    """
    if not isinstance(n, int) or n < 0:
        raise ValueError("n must be a non-negative integer")
    result = 1
    for i in range(2, n + 1):
        result *= i
    return result
