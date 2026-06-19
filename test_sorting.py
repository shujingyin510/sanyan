import pytest
from None import *

def test_bubble_sort():
    assert bubble_sort([3, 1, 4, 1, 5, 9, 2, 6]) == [1, 1, 2, 3, 4, 5, 6, 9]
    assert bubble_sort([]) == []
    assert bubble_sort([1]) == [1]

def test_merge_sort():
    assert merge_sort([3, 1, 4, 1, 5, 9, 2, 6]) == [1, 1, 2, 3, 4, 5, 6, 9]
    assert merge_sort([]) == []
    assert merge_sort([1]) == [1]

def test_quick_sort():
    assert quick_sort([3, 1, 4, 1, 5, 9, 2, 6]) == [1, 1, 2, 3, 4, 5, 6, 9]
    assert quick_sort([]) == []
    assert quick_sort([1]) == [1]

