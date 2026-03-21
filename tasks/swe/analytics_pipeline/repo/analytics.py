"""In-memory data analytics helpers.

Each public method operates on a list-of-dicts dataset supplied at
construction time.  Missing values for a requested column are silently
skipped so that sparse datasets are handled gracefully.
"""

from __future__ import annotations

from collections import Counter


class DataAnalytics:
    """Perform basic analytics over a list-of-dicts dataset."""

    def __init__(self, data: list[dict]) -> None:
        self._data = data

    # ------------------------------------------------------------------
    # Descriptive statistics
    # ------------------------------------------------------------------

    def mean(self, column: str) -> float:
        """Return the arithmetic mean of *column* (0.0 if no values)."""
        values = [row[column] for row in self._data if column in row]
        if not values:
            return 0.0
        return sum(values) / len(values)

    def variance(self, column: str) -> float:
        """Return the *sample* (Bessel-corrected) variance of *column*.

        Uses the n-1 denominator so that the result is an unbiased estimator
        of the population variance.  Returns 0.0 when fewer than 2 values are
        present.
        """
        values = [row[column] for row in self._data if column in row]
        if len(values) < 2:
            return 0.0
        m = self.mean(column)
        # BUG 1: divides by len(values) — that is the *population* variance.
        #        Sample variance requires dividing by len(values) - 1.
        return sum((x - m) ** 2 for x in values) / len(values)

    def mode(self, column: str):
        """Return the most frequently occurring value in *column*.

        When multiple values share the highest frequency the one that appears
        first in ``Counter.most_common`` is returned.  Returns ``None`` if the
        column is empty.
        """
        values = [row[column] for row in self._data if column in row]
        if not values:
            return None
        counts = Counter(values)
        # BUG 2: most_common(1) returns [(value, count)].
        #        [0][1] is the *count*; the correct index for the value is [0][0].
        return counts.most_common(1)[0][1]

    # ------------------------------------------------------------------
    # Filtering and grouping
    # ------------------------------------------------------------------

    def filter_rows(self, column: str, min_value: float) -> list[dict]:
        """Return all rows where *column* >= *min_value*.

        Rows that do not contain *column* are excluded from the result.
        """
        # BUG 3: strict '>' excludes rows where column value equals min_value.
        #        The docstring and tests require '>=' (inclusive lower bound).
        return [
            row for row in self._data
            if column in row and row[column] > min_value
        ]

    def group_sum(self, group_col: str, value_col: str) -> dict:
        """Return ``{group_value: sum_of_value_col}`` for each unique group.

        Rows missing either column are skipped.
        """
        result: dict = {}
        for row in self._data:
            key = row.get(group_col)
            val = row.get(value_col, 0)
            if key is None or value_col not in row:
                continue
            # BUG 4: assignment overwrites the running total on every iteration.
            #        Should be: result[key] = result.get(key, 0) + val
            result[key] = val
        return result
