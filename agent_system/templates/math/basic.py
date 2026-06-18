# name: 数学函数集合
# keywords: 水仙花数, 素数, 斐波那契, 阶乘, 数学, math, narcissistic, prime, fibonacci, factorial


def is_narcissistic(n: int) -> bool:
    """判断是否为水仙花数（阿姆斯特朗数）

    水仙花数是指一个 n 位数，它的每个位上的数字的 n 次幂之和等于它本身。
    例如：153 = 1^3 + 5^3 + 3^3
    """
    if n < 0:
        return False
    digits = [int(d) for d in str(n)]
    power = len(digits)
    return sum(d**power for d in digits) == n


def is_prime(n: int) -> bool:
    """判断是否为素数（质数）

    素数是指在大于 1 的自然数中，除了 1 和它本身以外不再有其他因数的自然数。
    """
    if n < 2:
        return False
    if n == 2:
        return True
    if n % 2 == 0:
        return False
    i = 3
    while i * i <= n:
        if n % i == 0:
            return False
        i += 2
    return True


def fibonacci(n: int) -> int:
    """返回第 n 项斐波那契数（从 0 开始：F(0)=0, F(1)=1）

    斐波那契数列：0, 1, 1, 2, 3, 5, 8, 13, 21, ...
    """
    if n < 0:
        raise ValueError('n must be non-negative')
    if n == 0:
        return 0
    if n == 1:
        return 1
    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b


def factorial(n: int) -> int:
    """返回 n 的阶乘 (n!)

    阶乘：n! = n × (n-1) × ... × 2 × 1
    0! = 1
    """
    if n < 0:
        raise ValueError('n must be non-negative')
    result = 1
    for i in range(2, n + 1):
        result *= i
    return result


def gcd(a: int, b: int) -> int:
    """求最大公约数（欧几里得算法）"""
    while b:
        a, b = b, a % b
    return a


def lcm(a: int, b: int) -> int:
    """求最小公倍数"""
    return a * b // gcd(a, b)


def is_perfect_number(n: int) -> bool:
    """判断是否为完全数

    完数是指一个数等于它的因子之和（不包括自身）。
    例如：6 = 1 + 2 + 3
    """
    if n < 2:
        return False
    divisors_sum = 1
    for i in range(2, int(n**0.5) + 1):
        if n % i == 0:
            divisors_sum += i
            if i != n // i:
                divisors_sum += n // i
    return divisors_sum == n


def collatz_length(n: int) -> int:
    """返回考拉兹序列长度

    考拉兹猜想：对于正整数 n，
    - 如果 n 是偶数，n = n / 2
    - 如果 n 是奇数，n = 3n + 1
    最终都会到达 1。
    """
    if n < 1:
        raise ValueError('n must be positive')
    length = 1
    while n != 1:
        n = n // 2 if n % 2 == 0 else 3 * n + 1
        length += 1
    return length
