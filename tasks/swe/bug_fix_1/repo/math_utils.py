"""Simple math utilities."""


def calculate_average(numbers: list[float]) -> float:
    """Return the arithmetic mean of a list of numbers."""
    total = sum(numbers)
    return total / len(numbers)


def calculate_median(numbers: list[float]) -> float:
    """Return the median of a list of numbers."""
    if not numbers:
        return 0.0
    sorted_nums = sorted(numbers)
    n = len(sorted_nums)
    mid = n // 2
    if n % 2 == 0:
        return (sorted_nums[mid - 1] + sorted_nums[mid]) / 2
    return sorted_nums[mid]
