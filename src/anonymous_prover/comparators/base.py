"""Base comparator with shared loading helpers."""

from __future__ import annotations

import glob
import json
import logging
import os

logger = logging.getLogger(__name__)


class BaseComparator:
    """Shared utilities for result comparators."""

    @staticmethod
    def _load_task_results(results_dir: str) -> dict[str, dict]:
        """Load all ``*.result.json`` in *results_dir*, keyed by task_name."""
        pattern = os.path.join(results_dir, "*.result.json")
        mapping: dict[str, dict] = {}
        for path in sorted(glob.glob(pattern)):
            try:
                with open(path, "r") as f:
                    data = json.load(f)
                name = data.get("task_name", os.path.splitext(os.path.basename(path))[0])
                mapping[name] = data
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Failed to load %s: %s", path, exc)
        return mapping

    @staticmethod
    def _find_common_tasks(
        baseline: dict[str, dict], treatment: dict[str, dict]
    ) -> list[str]:
        """Return sorted list of task names present in both result sets."""
        return sorted(set(baseline.keys()) & set(treatment.keys()))
