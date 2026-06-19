import unittest

def add(a, b):
    return a + b

def subtract(a, b):
    return a - b

def multiply(a, b):
    return a * b

def divide(a, b):
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b

class TestCalculator(unittest.TestCase):
    def test_add(self):
        self.assertEqual(add(1, 2), 3)
        self.assertEqual(add(-1, 1), 0)
        self.assertEqual(add(-1, -1), -2)

    def test_subtract(self):
        self.assertEqual(subtract(5, 3), 2)
        self.assertEqual(subtract(3, 5), -2)
        self.assertEqual(subtract(0, 0), 0)

    def test_multiply(self):
        self.assertEqual(multiply(2, 3), 6)
        self.assertEqual(multiply(-2, 3), -6)
        self.assertEqual(multiply(0, 5), 0)

    def test_divide(self):
        self.assertEqual(divide(6, 3), 2)
        self.assertEqual(divide(5, 2), 2.5)
        self.assertEqual(divide(-6, 3), -2)
        with self.assertRaises(ValueError):
            divide(1, 0)

if __name__ == '__main__':
    unittest.main()