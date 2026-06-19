import pytest
from string_utils import *

def test_reverse_string():
    assert reverse_string("hello") == "olleh"
    assert reverse_string("") == ""
    assert reverse_string("a") == "a"

def test_is_palindrome():
    assert is_palindrome("racecar") == True
    assert is_palindrome("hello") == False
    assert is_palindrome("A man a plan a canal Panama") == True

def test_count_chars():
    assert count_chars("hello") == {"h": 1, "e": 1, "l": 2, "o": 1}
    assert count_chars("") == {}

