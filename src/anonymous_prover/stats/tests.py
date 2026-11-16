"""Statistical tests for comparing experiment results.

Uses scipy when available, with manual fallback implementations.
"""

from __future__ import annotations

import math
from typing import Any

try:
    from scipy import stats as scipy_stats

    _HAS_SCIPY = True
except ImportError:
    _HAS_SCIPY = False


# ---------------------------------------------------------------------------
# McNemar's test
# ---------------------------------------------------------------------------


def mcnemar_test(
    baseline_outcomes: list[bool],
    treatment_outcomes: list[bool],
) -> dict[str, Any]:
    """McNemar's test for paired nominal data (solved / not-solved).

    Args:
        baseline_outcomes: Per-task boolean outcomes for the baseline.
        treatment_outcomes: Per-task boolean outcomes for the treatment.

    Returns:
        Dict with keys ``b``, ``c``, ``statistic``, ``p_value``, ``significant``.
    """
    if len(baseline_outcomes) != len(treatment_outcomes):
        raise ValueError("Outcome lists must have the same length.")

    # b = baseline solved, treatment failed
    # c = baseline failed, treatment solved
    b = sum(
        1 for bl, tr in zip(baseline_outcomes, treatment_outcomes) if bl and not tr
    )
    c = sum(
        1 for bl, tr in zip(baseline_outcomes, treatment_outcomes) if not bl and tr
    )

    if b + c == 0:
        return {
            "b": b,
            "c": c,
            "statistic": 0.0,
            "p_value": 1.0,
            "significant": False,
        }

    statistic = (abs(b - c) - 1) ** 2 / (b + c)

    if _HAS_SCIPY:
        if b + c < 25:
            # Use exact binomial test for small samples
            result = scipy_stats.binomtest(b, b + c, 0.5)
            p_value = result.pvalue
        else:
            p_value = 1.0 - scipy_stats.chi2.cdf(statistic, df=1)
    else:
        p_value = _chi2_survival(statistic, df=1)

    p_value = float(p_value)
    return {
        "b": b,
        "c": c,
        "statistic": statistic,
        "p_value": p_value,
        "significant": bool(p_value < 0.05),
    }


# ---------------------------------------------------------------------------
# Wilcoxon signed-rank test
# ---------------------------------------------------------------------------


def wilcoxon_test(
    baseline_values: list[float],
    treatment_values: list[float],
) -> dict[str, Any]:
    """Wilcoxon signed-rank test for paired continuous data.

    Args:
        baseline_values: Per-task metric values for the baseline.
        treatment_values: Per-task metric values for the treatment.

    Returns:
        Dict with keys ``n_pairs``, ``statistic``, ``p_value``.
    """
    if len(baseline_values) != len(treatment_values):
        raise ValueError("Value lists must have the same length.")

    # Remove zero differences
    diffs = [t - b for b, t in zip(baseline_values, treatment_values) if t != b]
    n_pairs = len(diffs)

    if n_pairs == 0:
        return {"n_pairs": 0, "statistic": 0.0, "p_value": 1.0}

    if _HAS_SCIPY:
        stat, p_value = scipy_stats.wilcoxon(
            baseline_values, treatment_values, zero_method="wilcox"
        )
        return {"n_pairs": n_pairs, "statistic": float(stat), "p_value": float(p_value)}

    # Manual: rank absolute differences, sum positive / negative ranks
    abs_diffs = [(abs(d), 1 if d > 0 else -1) for d in diffs]
    abs_diffs.sort(key=lambda x: x[0])

    # Assign ranks (average ties)
    ranks: list[tuple[float, int]] = []
    i = 0
    while i < len(abs_diffs):
        j = i
        while j < len(abs_diffs) and abs_diffs[j][0] == abs_diffs[i][0]:
            j += 1
        avg_rank = (i + 1 + j) / 2.0
        for k in range(i, j):
            ranks.append((avg_rank, abs_diffs[k][1]))
        i = j

    w_plus = sum(r for r, s in ranks if s > 0)
    w_minus = sum(r for r, s in ranks if s < 0)
    statistic = min(w_plus, w_minus)

    # Normal approximation for p-value
    mean = n_pairs * (n_pairs + 1) / 4.0
    std = math.sqrt(n_pairs * (n_pairs + 1) * (2 * n_pairs + 1) / 24.0)
    if std == 0:
        return {"n_pairs": n_pairs, "statistic": statistic, "p_value": 1.0}
    z = (statistic - mean) / std
    p_value = 2.0 * _normal_cdf(z)

    return {"n_pairs": n_pairs, "statistic": statistic, "p_value": p_value}


# ---------------------------------------------------------------------------
# Fisher's exact test
# ---------------------------------------------------------------------------


def fisher_exact_test(table: list[list[int]]) -> dict[str, Any]:
    """Fisher's exact test for a 2x2 contingency table.

    Args:
        table: 2x2 list ``[[a, b], [c, d]]``.

    Returns:
        Dict with keys ``odds_ratio``, ``p_value``.
    """
    if len(table) != 2 or len(table[0]) != 2 or len(table[1]) != 2:
        raise ValueError("Table must be 2x2.")

    a, b = table[0]
    c, d = table[1]

    if _HAS_SCIPY:
        odds_ratio, p_value = scipy_stats.fisher_exact(table)
        return {"odds_ratio": float(odds_ratio), "p_value": float(p_value)}

    # Manual odds ratio
    odds_ratio = (a * d) / (b * c) if (b * c) != 0 else float("inf")

    # Compute p-value via hypergeometric distribution
    n = a + b + c + d
    row1 = a + b
    col1 = a + c

    def _hypergeom_pmf(k: int) -> float:
        return (
            math.comb(row1, k)
            * math.comb(n - row1, col1 - k)
            / math.comb(n, col1)
        )

    p_obs = _hypergeom_pmf(a)
    p_value = sum(
        _hypergeom_pmf(k)
        for k in range(max(0, col1 - (n - row1)), min(row1, col1) + 1)
        if _hypergeom_pmf(k) <= p_obs + 1e-12
    )

    return {"odds_ratio": odds_ratio, "p_value": min(p_value, 1.0)}


# ---------------------------------------------------------------------------
# Significance label
# ---------------------------------------------------------------------------


def significance_label(p_value: float) -> str:
    """Return a significance label for a p-value.

    Returns:
        ``"***"`` if p < 0.001, ``"**"`` if p < 0.01,
        ``"*"`` if p < 0.05, ``"ns"`` otherwise.
    """
    if p_value < 0.001:
        return "***"
    if p_value < 0.01:
        return "**"
    if p_value < 0.05:
        return "*"
    return "ns"


# ---------------------------------------------------------------------------
# Internal helpers (fallbacks when scipy is not installed)
# ---------------------------------------------------------------------------


def _normal_cdf(z: float) -> float:
    """Approximate the standard normal CDF using the error function."""
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def _chi2_survival(x: float, df: int = 1) -> float:
    """Approximate the chi-squared survival function for df=1.

    Uses the relationship: chi2_sf(x, 1) = 2 * (1 - Phi(sqrt(x))).
    """
    if df != 1:
        raise NotImplementedError("Only df=1 is supported without scipy.")
    if x <= 0:
        return 1.0
    return 2.0 * (1.0 - _normal_cdf(math.sqrt(x)))
