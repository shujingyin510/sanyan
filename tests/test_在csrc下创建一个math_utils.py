import pytest
from 在csrc下创建一个math_utils import *

def test_is_narcissistic():
    assert is_narcissistic(153) == True
    assert is_narcissistic(370) == True
    assert is_narcissistic(371) == True
    assert is_narcissistic(407) == True
    assert is_narcissistic(1634) == True
    assert is_narcissistic(123) == False
    assert is_narcissistic(0) == True
    assert is_narcissistic(-1) == False

def test_is_prime():
    assert is_prime(2) == True
    assert is_prime(3) == True
    assert is_prime(5) == True
    assert is_prime(7) == True
    assert is_prime(11) == True
    assert is_prime(4) == False
    assert is_prime(1) == False
    assert is_prime(0) == False
    assert is_prime(-5) == False

def test_fibonacci():
    assert fibonacci(0) == 0
    assert fibonacci(1) == 1
    assert fibonacci(2) == 1
    assert fibonacci(5) == 5
    assert fibonacci(10) == 55
    with pytest.raises(ValueError):
        fibonacci(-1)

def test_factorial():
    assert factorial(0) == 1
    assert factorial(1) == 1
    assert factorial(5) == 120
    assert factorial(10) == 3628800
    with pytest.raises(ValueError):
        factorial(-1)

def test_gcd():
    assert gcd(12, 8) == 4
    assert gcd(100, 75) == 25
    assert gcd(7, 13) == 1

def test_lcm():
    assert lcm(4, 6) == 12
    assert lcm(3, 7) == 21

