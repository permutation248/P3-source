"""Default result collector -- aggregates individual task results."""

from __future__ import annotations

import json
import logging
import os
from collections import defaultdict

from .base import BaseCollector

logger = logging.getLogger(__name__)


class DefaultCollector(BaseCollector):
    """Collect all ``*.result.json`` files and produce an experiment summary."""

    def collect(self, results_dir: str) -> dict:
        """Aggregate results and save ``summary.json``."""
        results = self._load_results(results_dir)

        total = len(results)
        solved = sum(1 for r in results if r.get("solved"))
        failed = sum(1 for r in results if not r.get("solved") and not r.get("timeout"))
        timeouts = sum(1 for r in results if r.get("timeout"))
        solved_rate = (solved / total * 100) if total else 0.0

        times = [r["total_time_seconds"] for r in results if "total_time_seconds" in r]
        costs = [r["cost_usd"] for r in results if "cost_usd" in r]
        turns = [float(r["total_turns"]) for r in results if "total_turns" in r]

        # Per-benchmark breakdown
        benchmarks: dict[str, list[dict]] = defaultdict(list)
        for r in results:
            name = r.get("task_name", "")
            # Try directory-based prefix first (e.g. "algoveribench/foo" -> "algoveribench")
            if "/" in name:
                prefix = name.split("/")[0]
            else:
                # Fallback: first component separated by underscore
                prefix = name.split("_")[0] if "_" in name else "other"
            benchmarks[prefix].append(r)

        per_benchmark: dict[str, dict] = {}
        for bname, b_results in sorted(benchmarks.items()):
            b_total = len(b_results)
            b_solved = sum(1 for r in b_results if r.get("solved"))
            per_benchmark[bname] = {
                "total": b_total,
                "solved": b_solved,
                "solved_rate": round(b_solved / b_total * 100, 2) if b_total else 0.0,
                "time_stats": self._compute_stats(
                    [r["total_time_seconds"] for r in b_results if "total_time_seconds" in r]
                ),
                "cost_stats": self._compute_stats(
                    [r["cost_usd"] for r in b_results if "cost_usd" in r]
                ),
            }

        cost_stats = self._compute_stats(costs)
        cost_stats["total"] = round(sum(costs), 4) if costs else 0.0

        summary = {
            "total": total,
            "solved": solved,
            "failed": failed,
            "timeouts": timeouts,
            "solved_rate": round(solved_rate, 2),
            "time_stats": self._compute_stats(times),
            "cost_stats": cost_stats,
            "turn_stats": self._compute_stats(turns),
            "per_benchmark": per_benchmark,
            "tasks": [
                {
                    "task_name": r.get("task_name"),
                    "solved": r.get("solved"),
                    "sorry_count": r.get("sorry_count"),
                    "timeout": r.get("timeout"),
                    "total_time_seconds": r.get("total_time_seconds"),
                    "cost_usd": r.get("cost_usd"),
                    "total_turns": r.get("total_turns"),
                }
                for r in results
            ],
        }

        # Persist
        summary_path = os.path.join(results_dir, "summary.json")
        with open(summary_path, "w") as f:
            json.dump(summary, f, indent=2)
        logger.info("Saved summary to %s", summary_path)

        return summary
