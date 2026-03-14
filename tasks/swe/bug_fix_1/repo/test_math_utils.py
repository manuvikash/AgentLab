"""Tests for math_utils."""

from math_utils import calculate_average, calculate_median


def test_average_basic():
    assert calculate_average([1, 2, 3]) == 2.0


def test_average_single():
    assert calculate_average([5]) == 5.0


def test_average_empty():
    assert calculate_average([]) == 0.0


def test_median_odd():
    assert calculate_median([3, 1, 2]) == 2.0


def test_median_even():
    assert calculate_median([1, 2, 3, 4]) == 2.5


def test_median_empty():
    assert calculate_median([]) == 0.0
