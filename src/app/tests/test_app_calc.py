from django.test import SimpleTestCase

from app.calc import add, divide, multiply, power, square_root, subtract


class CalcTestCase(SimpleTestCase):
    """Test cases for calculator functions."""

    def test_add(self):
        """Test addition."""
        self.assertEqual(add(2, 3), 5)
        self.assertEqual(add(-1, 1), 0)
        self.assertEqual(add(0, 0), 0)

    def test_subtract(self):
        """Test subtraction."""
        self.assertEqual(subtract(5, 3), 2)
        self.assertEqual(subtract(1, 1), 0)
        self.assertEqual(subtract(-5, -3), -2)

    def test_multiply(self):
        """Test multiplication."""
        self.assertEqual(multiply(3, 4), 12)
        self.assertEqual(multiply(-2, 3), -6)
        self.assertEqual(multiply(0, 100), 0)

    def test_divide(self):
        """Test division."""
        self.assertEqual(divide(10, 2), 5.0)
        self.assertEqual(divide(7, 2), 3.5)
        self.assertEqual(divide(-10, 2), -5.0)

    def test_divide_by_zero(self):
        """Test division by zero raises error."""
        with self.assertRaises(ValueError):
            divide(10, 0)

    def test_power(self):
        """Test power function."""
        self.assertEqual(power(2, 3), 8.0)
        self.assertEqual(power(5, 2), 25.0)
        self.assertEqual(power(10, 0), 1.0)

    def test_square_root(self):
        """Test square root function."""
        self.assertEqual(square_root(16), 4.0)
        self.assertEqual(square_root(25), 5.0)
        self.assertEqual(square_root(0), 0.0)

    def test_square_root_negative(self):
        """Test square root of negative number raises error."""
        with self.assertRaises(ValueError):
            square_root(-1)
