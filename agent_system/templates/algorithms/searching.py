# name: 搜索算法
# keywords: 搜索, 二分, 线性, 广度优先, 深度优先, search, binary search, linear search, BFS, DFS

from typing import List


def linear_search(arr: List, target) -> int:
    """线性搜索

    时间复杂度: O(n)
    空间复杂度: O(1)
    """
    for i, val in enumerate(arr):
        if val == target:
            return i
    return -1


def binary_search(arr: List, target) -> int:
    """二分搜索（要求数组已排序）

    时间复杂度: O(log n)
    空间复杂度: O(1)
    """
    left, right = 0, len(arr) - 1
    while left <= right:
        mid = (left + right) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            left = mid + 1
        else:
            right = mid - 1
    return -1


def binary_search_left(arr: List, target) -> int:
    """二分搜索（查找最左位置）"""
    left, right = 0, len(arr)
    while left < right:
        mid = (left + right) // 2
        if arr[mid] < target:
            left = mid + 1
        else:
            right = mid
    return left


def binary_search_right(arr: List, target) -> int:
    """二分搜索（查找最右位置）"""
    left, right = 0, len(arr)
    while left < right:
        mid = (left + right) // 2
        if arr[mid] <= target:
            left = mid + 1
        else:
            right = mid
    return left


def jump_search(arr: List, target) -> int:
    """跳跃搜索

    时间复杂度: O(√n)
    空间复杂度: O(1)
    """
    import math

    n = len(arr)
    step = int(math.sqrt(n))
    prev = 0

    while arr[min(step, n) - 1] < target:
        prev = step
        step += int(math.sqrt(n))
        if prev >= n:
            return -1

    for i in range(prev, min(step, n)):
        if arr[i] == target:
            return i

    return -1


def interpolation_search(arr: List, target) -> int:
    """插值搜索

    时间复杂度: O(log log n) 平均, O(n) 最坏
    空间复杂度: O(1)
    适用于均匀分布的数据
    """
    left, right = 0, len(arr) - 1

    while left <= right and arr[left] <= target <= arr[right]:
        if arr[left] == arr[right]:
            if arr[left] == target:
                return left
            break

        pos = left + ((target - arr[left]) * (right - left)) // (arr[right] - arr[left])

        if arr[pos] == target:
            return pos
        elif arr[pos] < target:
            left = pos + 1
        else:
            right = pos - 1

    return -1


def exponential_search(arr: List, target) -> int:
    """指数搜索

    时间复杂度: O(log n)
    空间复杂度: O(1)
    """
    if not arr:
        return -1

    if arr[0] == target:
        return 0

    n = len(arr)
    i = 1
    while i < n and arr[i] <= target:
        i *= 2

    return binary_search(arr[: min(i, n)], target)


def fibonacci_search(arr: List, target) -> int:
    """斐波那契搜索

    时间复杂度: O(log n)
    空间复杂度: O(1)
    """
    n = len(arr)
    fib_m2 = 0  # (m-2)th Fibonacci
    fib_m1 = 1  # (m-1)th Fibonacci
    fib_m = fib_m2 + fib_m1  # mth Fibonacci

    while fib_m < n:
        fib_m2 = fib_m1
        fib_m1 = fib_m
        fib_m = fib_m2 + fib_m1

    offset = -1

    while fib_m > 1:
        i = min(offset + fib_m2, n - 1)

        if arr[i] < target:
            fib_m = fib_m1
            fib_m1 = fib_m2
            fib_m2 = fib_m - fib_m1
            offset = i
        elif arr[i] > target:
            fib_m = fib_m2
            fib_m1 = fib_m1 - fib_m2
            fib_m2 = fib_m - fib_m1
        else:
            return i

    if fib_m1 and offset + 1 < n and arr[offset + 1] == target:
        return offset + 1

    return -1


def ternary_search(arr: List, target) -> int:
    """三元搜索

    时间复杂度: O(log n)
    空间复杂度: O(1)
    """
    left, right = 0, len(arr) - 1

    while left <= right:
        mid1 = left + (right - left) // 3
        mid2 = right - (right - left) // 3

        if arr[mid1] == target:
            return mid1
        if arr[mid2] == target:
            return mid2

        if target < arr[mid1]:
            right = mid1 - 1
        elif target > arr[mid2]:
            left = mid2 + 1
        else:
            left = mid1 + 1
            right = mid2 - 1

    return -1
