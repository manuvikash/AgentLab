"""Tests for DataAnalytics.

Dataset used by most tests
--------------------------
region  | sales | units
--------|-------|------
north   |  100  |  3
south   |  200  |  7
north   |  150  |  5
east    |   50  |  2
north   |   50  |  1
"""

import pytest

from analytics import DataAnalytics

SALES = [
    {"region": "north", "sales": 100, "units": 3},
    {"region": "south", "sales": 200, "units": 7},
    {"region": "north", "sales": 150, "units": 5},
    {"region": "east",  "sales":  50, "units": 2},
    {"region": "north", "sales":  50, "units": 1},
]


# ---------------------------------------------------------------------------
# mean
# ---------------------------------------------------------------------------

def test_mean_basic():
    da = DataAnalytics(SALES)
    # (100 + 200 + 150 + 50 + 50) / 5 = 110.0
    assert da.mean("sales") == pytest.approx(110.0)


def test_mean_missing_column():
    da = DataAnalytics(SALES)
    assert da.mean("revenue") == 0.0


def test_mean_empty_dataset():
    assert DataAnalytics([]).mean("sales") == 0.0


# ---------------------------------------------------------------------------
# variance  (BUG 1: population ÷ N  vs  sample ÷ N-1)
# ---------------------------------------------------------------------------

def test_variance_sample():
    da = DataAnalytics(SALES)
    # values  : [100, 200, 150, 50, 50]
    # mean    : 110
    # sq_devs : [100, 8100, 1600, 3600, 3600]  → sum = 17000
    # sample  : 17000 / 4 = 4250.0
    assert da.variance("sales") == pytest.approx(4250.0)


def test_variance_population_is_wrong():
    """Guard: population variance (÷N) must NOT be returned."""
    da = DataAnalytics(SALES)
    assert da.variance("sales") != pytest.approx(3400.0)


def test_variance_single_value():
    da = DataAnalytics([{"x": 99}])
    assert da.variance("x") == 0.0


def test_variance_two_values():
    da = DataAnalytics([{"x": 2}, {"x": 4}])
    # mean = 3, sq_devs = [1, 1], sum = 2, sample = 2/1 = 2.0
    assert da.variance("x") == pytest.approx(2.0)


# ---------------------------------------------------------------------------
# mode  (BUG 2: returns count instead of value)
# ---------------------------------------------------------------------------

def test_mode_returns_value_not_count():
    da = DataAnalytics(SALES)
    # "north" appears 3 times — should return the *string* "north", not 3
    result = da.mode("region")
    assert result == "north", f"Expected 'north', got {result!r}"


def test_mode_numeric():
    da = DataAnalytics([{"v": 1}, {"v": 2}, {"v": 2}, {"v": 3}])
    assert da.mode("v") == 2


def test_mode_empty():
    assert DataAnalytics([]).mode("x") is None


# ---------------------------------------------------------------------------
# filter_rows  (BUG 3: > instead of >=)
# ---------------------------------------------------------------------------

def test_filter_rows_inclusive_boundary():
    da = DataAnalytics(SALES)
    # sales >= 100 → rows with 100, 150, 200 → 3 rows
    result = da.filter_rows("sales", 100)
    assert len(result) == 3, (
        f"Expected 3 rows (sales >= 100), got {len(result)}: "
        f"{[r['sales'] for r in result]}"
    )


def test_filter_rows_boundary_value_included():
    """The row exactly at the boundary must be present."""
    da = DataAnalytics(SALES)
    sales_values = {r["sales"] for r in da.filter_rows("sales", 100)}
    assert 100 in sales_values, "Row with sales == 100 should be included"


def test_filter_rows_all():
    da = DataAnalytics(SALES)
    assert len(da.filter_rows("sales", 0)) == 5


def test_filter_rows_none():
    da = DataAnalytics(SALES)
    assert da.filter_rows("sales", 9999) == []


def test_filter_rows_missing_column_excluded():
    data = [{"sales": 50}, {"other": 10}]
    da = DataAnalytics(data)
    assert len(da.filter_rows("sales", 0)) == 1


# ---------------------------------------------------------------------------
# group_sum  (BUG 4: assignment instead of accumulation)
# ---------------------------------------------------------------------------

def test_group_sum_accumulates_sales():
    da = DataAnalytics(SALES)
    result = da.group_sum("region", "sales")
    # north: 100 + 150 + 50 = 300
    assert result["north"] == 300, f"north should be 300, got {result['north']}"
    # south: 200
    assert result["south"] == 200
    # east: 50
    assert result["east"] == 50


def test_group_sum_accumulates_units():
    da = DataAnalytics(SALES)
    result = da.group_sum("region", "units")
    # north: 3 + 5 + 1 = 9
    assert result["north"] == 9
    # south: 7
    assert result["south"] == 7


def test_group_sum_single_member_groups():
    """Groups with only one row should still work correctly."""
    da = DataAnalytics(SALES)
    result = da.group_sum("region", "sales")
    assert result["east"] == 50


def test_group_sum_missing_value_col_skipped():
    data = [
        {"cat": "a", "val": 10},
        {"cat": "a"},               # missing value_col → skip
        {"cat": "b", "val": 5},
    ]
    da = DataAnalytics(data)
    result = da.group_sum("cat", "val")
    assert result["a"] == 10
    assert result["b"] == 5
