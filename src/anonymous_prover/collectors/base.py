"""Base collector with shared statistics helpers."""

from __future__ import annotations

import glob
import json
import logging
import os
import statistics

logger = logging.getLogger(__name__)


class BaseCollector:
    """Shared utilities for result collectors."""

    @staticmethod
    def _compute_stats(values: list[float]) -> dict:
        """Return descriptive statistics for a list of numeric values."""
        if not values:
            return {"avg": 0.0, "median": 0.0, "p95": 0.0, "min": 0.0, "max": 0.0}

        sorted_vals = sorted(values)
        n = len(sorted_vals)
        p95_idx = min(int(n * 0.95), n - 1)

        return {
            "avg": round(statistics.mean(sorted_vals), 4),
            "median": round(statistics.median(sorted_vals), 4),
            "p95": round(sorted_vals[p95_idx], 4),
            "min": round(sorted_vals[0], 4),
            "max": round(sorted_vals[-1], 4),
        }

    @staticmethod
    def _load_results(results_dir: str) -> list[dict]:
        """Glob for ``*.result.json`` in *results_dir* and load each."""
        pattern = os.path.join(results_dir, "*.result.json")
        paths = sorted(glob.glob(pattern))
        results: list[dict] = []
        for p in paths:
            try:
                with open(p, "r") as f:
                    results.append(json.load(f))
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Failed to load %s: %s", p, exc)
        return results
