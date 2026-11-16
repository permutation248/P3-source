"""Default result comparator -- compare baseline vs. treatment."""

from __future__ import annotations

import json
import logging
import os
from collections import defaultdict

from ..stats.tests import mcnemar_test, wilcoxon_test
from .base import BaseComparator

logger = logging.getLogger(__name__)


def _safe_delta_pct(baseline_val: float, treatment_val: float) -> float | None:
    """Return percentage change, or None when baseline is zero."""
    if baseline_val == 0:
        return None
    return round((treatment_val - baseline_val) / baseline_val * 100, 2)


class DefaultComparator(BaseComparator):
    """Compare two experiment result directories."""

    def compare(self, baseline_dir: str, treatment_dir: str) -> dict:
        """Produce a comparison dict and save as ``comparison.json``."""
        baseline = self._load_task_results(baseline_dir)
        treatment = self._load_task_results(treatment_dir)
        common = self._find_common_tasks(baseline, treatment)

        if not common:
            logger.warning("No common tasks found between baseline and treatment")
            return {"error": "no common tasks"}

        # Solved rates
        b_solved = sum(1 for n in common if baseline[n].get("solved"))
        t_solved = sum(1 for n in common if treatment[n].get("solved"))
        total = len(common)
        b_rate = round(b_solved / total * 100, 2)
        t_rate = round(t_solved / total * 100, 2)

        # Metric helpers
        def _avg(results: dict[str, dict], key: str) -> float:
            vals = [results[n].get(key, 0) for n in common if key in results[n]]
            return round(sum(vals) / len(vals), 4) if vals else 0.0

        def _metric(label: str, key: str) -> dict:
            b_val = _avg(baseline, key)
            t_val = _avg(treatment, key)
            return {
                "metric": label,
                "baseline": b_val,
                "treatment": t_val,
                "delta": round(t_val - b_val, 4),
                "delta_pct": _safe_delta_pct(b_val, t_val),
            }

        metrics = [
            {
                "metric": "solved_rate",
                "baseline": b_rate,
                "treatment": t_rate,
                "delta": round(t_rate - b_rate, 2),
                "delta_pct": _safe_delta_pct(b_rate, t_rate),
            },
            _metric("avg_time", "total_time_seconds"),
            _metric("avg_cost", "cost_usd"),
            _metric("avg_turns", "total_turns"),
        ]

        # Per-benchmark comparison
        benchmarks: dict[str, list[str]] = defaultdict(list)
        for name in common:
            if "/" in name:
                prefix = name.split("/")[0]
            else:
                prefix = name.split("_")[0] if "_" in name else "other"
            benchmarks[prefix].append(name)

        per_benchmark: dict[str, dict] = {}
        for bname, tasks in sorted(benchmarks.items()):
            bt = len(tasks)
            bs = sum(1 for n in tasks if baseline[n].get("solved"))
            ts = sum(1 for n in tasks if treatment[n].get("solved"))
            per_benchmark[bname] = {
                "total": bt,
                "baseline_solved": bs,
                "treatment_solved": ts,
                "baseline_rate": round(bs / bt * 100, 2) if bt else 0.0,
                "treatment_rate": round(ts / bt * 100, 2) if bt else 0.0,
            }

        # Regressions and improvements
        regressions = [
            n for n in common
            if baseline[n].get("solved") and not treatment[n].get("solved")
        ]
        improvements = [
            n for n in common
            if not baseline[n].get("solved") and treatment[n].get("solved")
        ]

        # Statistical tests
        b_outcomes = [baseline[n].get("solved", False) for n in common]
        t_outcomes = [treatment[n].get("solved", False) for n in common]
        b_times = [baseline[n].get("total_time_seconds", 0) for n in common]
        t_times = [treatment[n].get("total_time_seconds", 0) for n in common]
        b_costs = [baseline[n].get("cost_usd", 0) for n in common]
        t_costs = [treatment[n].get("cost_usd", 0) for n in common]

        stats_tests = {
            "mcnemar_solved": mcnemar_test(b_outcomes, t_outcomes),
            "wilcoxon_time": wilcoxon_test(b_times, t_times),
            "wilcoxon_cost": wilcoxon_test(b_costs, t_costs),
        }

        comparison = {
            "common_tasks": total,
            "baseline_total": len(baseline),
            "treatment_total": len(treatment),
            "baseline_solved_rate": b_rate,
            "treatment_solved_rate": t_rate,
            "delta": round(t_rate - b_rate, 2),
            "metrics": metrics,
            "per_benchmark": per_benchmark,
            "regressions": regressions,
            "improvements": improvements,
            "statistical_tests": stats_tests,
        }

        # Save
        output_path = os.path.join(treatment_dir, "comparison.json")
        with open(output_path, "w") as f:
            json.dump(comparison, f, indent=2)
        logger.info("Saved comparison to %s", output_path)

        return comparison
