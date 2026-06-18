# name: 排序算法集合
# keywords: 排序, 冒泡, 选择, 插入, 归并, 快速, sort, bubble, selection, insertion, merge, quick


def bubble_sort(arr: list) -> list:
    """冒泡排序

    时间复杂度: O(n^2)
    空间复杂度: O(1)
    稳定排序
    """
    arr = arr.copy()
    n = len(arr)
    for i in range(n):
        for j in range(0, n - i - 1):
            if arr[j] > arr[j + 1]:
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
    return arr


def selection_sort(arr: list) -> list:
    """选择排序

    时间复杂度: O(n^2)
    空间复杂度: O(1)
    不稳定排序
    """
    arr = arr.copy()
    n = len(arr)
    for i in range(n):
        min_idx = i
        for j in range(i + 1, n):
            if arr[j] < arr[min_idx]:
                min_idx = j
        arr[i], arr[min_idx] = arr[min_idx], arr[i]
    return arr


def insertion_sort(arr: list) -> list:
    """插入排序

    时间复杂度: O(n^2)
    空间复杂度: O(1)
    稳定排序
    """
    arr = arr.copy()
    for i in range(1, len(arr)):
        key = arr[i]
        j = i - 1
        while j >= 0 and arr[j] > key:
            arr[j + 1] = arr[j]
            j -= 1
        arr[j + 1] = key
    return arr


def merge_sort(arr: list) -> list:
    """归并排序

    时间复杂度: O(n log n)
    空间复杂度: O(n)
    稳定排序
    """
    if len(arr) <= 1:
        return arr

    mid = len(arr) // 2
    left = merge_sort(arr[:mid])
    right = merge_sort(arr[mid:])

    return _merge(left, right)


def _merge(left: list, right: list) -> list:
    result = []
    i = j = 0
    while i < len(left) and j < len(right):
        if left[i] <= right[j]:
            result.append(left[i])
            i += 1
        else:
            result.append(right[j])
            j += 1
    result.extend(left[i:])
    result.extend(right[j:])
    return result


def quick_sort(arr: list) -> list:
    """快速排序

    时间复杂度: O(n log n) 平均, O(n^2) 最坏
    空间复杂度: O(log n)
    不稳定排序
    """
    if len(arr) <= 1:
        return arr

    pivot = arr[len(arr) // 2]
    left = [x for x in arr if x < pivot]
    middle = [x for x in arr if x == pivot]
    right = [x for x in arr if x > pivot]

    return quick_sort(left) + middle + quick_sort(right)


def heap_sort(arr: list) -> list:
    """堆排序

    时间复杂度: O(n log n)
    空间复杂度: O(1)
    不稳定排序
    """
    arr = arr.copy()
    n = len(arr)

    # 建堆
    for i in range(n // 2 - 1, -1, -1):
        _heapify(arr, n, i)

    # 排序
    for i in range(n - 1, 0, -1):
        arr[0], arr[i] = arr[i], arr[0]
        _heapify(arr, i, 0)

    return arr


def _heapify(arr: list, n: int, i: int):
    largest = i
    left = 2 * i + 1
    right = 2 * i + 2

    if left < n and arr[left] > arr[largest]:
        largest = left
    if right < n and arr[right] > arr[largest]:
        largest = right
    if largest != i:
        arr[i], arr[largest] = arr[largest], arr[i]
        _heapify(arr, n, largest)


def counting_sort(arr: list) -> list:
    """计数排序

    时间复杂度: O(n + k)
    空间复杂度: O(k)
    稳定排序
    适用于非负整数
    """
    if not arr:
        return arr

    max_val = max(arr)
    count = [0] * (max_val + 1)

    for num in arr:
        count[num] += 1

    result = []
    for i, c in enumerate(count):
        result.extend([i] * c)

    return result
