"""测试模板生成器 — 为模板生成对应的测试代码"""

import re
from typing import List


# 测试模板映射
TEST_TEMPLATES = {
    'is_narcissistic': """def test_is_narcissistic():
    assert is_narcissistic(153) == True
    assert is_narcissistic(370) == True
    assert is_narcissistic(371) == True
    assert is_narcissistic(407) == True
    assert is_narcissistic(1634) == True
    assert is_narcissistic(123) == False
    assert is_narcissistic(0) == True
    assert is_narcissistic(-1) == False""",
    'is_prime': """def test_is_prime():
    assert is_prime(2) == True
    assert is_prime(3) == True
    assert is_prime(5) == True
    assert is_prime(7) == True
    assert is_prime(11) == True
    assert is_prime(4) == False
    assert is_prime(1) == False
    assert is_prime(0) == False
    assert is_prime(-5) == False""",
    'fibonacci': """def test_fibonacci():
    assert fibonacci(0) == 0
    assert fibonacci(1) == 1
    assert fibonacci(2) == 1
    assert fibonacci(5) == 5
    assert fibonacci(10) == 55
    with pytest.raises(ValueError):
        fibonacci(-1)""",
    'factorial': """def test_factorial():
    assert factorial(0) == 1
    assert factorial(1) == 1
    assert factorial(5) == 120
    assert factorial(10) == 3628800
    with pytest.raises(ValueError):
        factorial(-1)""",
    'gcd': """def test_gcd():
    assert gcd(12, 8) == 4
    assert gcd(100, 75) == 25
    assert gcd(7, 13) == 1""",
    'lcm': """def test_lcm():
    assert lcm(4, 6) == 12
    assert lcm(3, 7) == 21""",
    'Stack': """def test_stack():
    s = Stack()
    assert s.is_empty() == True
    s.push(1)
    s.push(2)
    assert s.peek() == 2
    assert s.pop() == 2
    assert s.pop() == 1
    assert s.is_empty() == True""",
    'Queue': """def test_queue():
    q = Queue()
    assert q.is_empty() == True
    q.enqueue(1)
    q.enqueue(2)
    assert q.front() == 1
    assert q.dequeue() == 1
    assert q.dequeue() == 2
    assert q.is_empty() == True""",
    'bubble_sort': """def test_bubble_sort():
    assert bubble_sort([3, 1, 4, 1, 5, 9, 2, 6]) == [1, 1, 2, 3, 4, 5, 6, 9]
    assert bubble_sort([]) == []
    assert bubble_sort([1]) == [1]""",
    'quick_sort': """def test_quick_sort():
    assert quick_sort([3, 1, 4, 1, 5, 9, 2, 6]) == [1, 1, 2, 3, 4, 5, 6, 9]
    assert quick_sort([]) == []
    assert quick_sort([1]) == [1]""",
    'merge_sort': """def test_merge_sort():
    assert merge_sort([3, 1, 4, 1, 5, 9, 2, 6]) == [1, 1, 2, 3, 4, 5, 6, 9]
    assert merge_sort([]) == []
    assert merge_sort([1]) == [1]""",
    'reverse_string': '''def test_reverse_string():
    assert reverse_string("hello") == "olleh"
    assert reverse_string("") == ""
    assert reverse_string("a") == "a"''',
    'is_palindrome': """def test_is_palindrome():
    assert is_palindrome("racecar") == True
    assert is_palindrome("hello") == False
    assert is_palindrome("A man a plan a canal Panama") == True""",
    'count_chars': """def test_count_chars():
    assert count_chars("hello") == {"h": 1, "e": 1, "l": 2, "o": 1}
    assert count_chars("") == {}""",
}


def generate_test_code(module_name: str, functions: List[str]) -> str:
    """为指定函数生成测试代码"""
    lines = [
        'import pytest',
        f'from {module_name} import *',
        '',
    ]

    for func_name in functions:
        if func_name in TEST_TEMPLATES:
            lines.append(TEST_TEMPLATES[func_name])
            lines.append('')

    if len(lines) == 3:  # 没有找到模板
        lines.append('def test_basic():')
        lines.append('    # TODO: 添加测试')
        lines.append('    pass')

    return '\n'.join(lines) + '\n'


def extract_functions_from_code(code: str) -> List[str]:
    """从代码中提取函数名"""
    functions = []
    for match in re.finditer(r'def\s+(\w+)\s*\(', code):
        functions.append(match.group(1))
    for match in re.finditer(r'class\s+(\w+)\s*[:\(]', code):
        functions.append(match.group(1))
    return functions
