"""Persistent storage for per-task results and experiment summaries."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional


class ResultStore:
    """Read / write task results and summaries to disk (and optionally a DB session).

    Directory layout::

        results_dir/
            <task_name>.result.json
            summary.json

    Args:
        results_dir: Directory where result files are stored.
        db_session: Optional SQLAlchemy session for database persistence.
    """

    def __init__(self, results_dir: str, db_session: Optional[Any] = None) -> None:
        self.results_dir = Path(results_dir)
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.db_session = db_session

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def save_result(self, task_name: str, result: dict[str, Any]) -> None:
        """Write a single task result to ``<task_name>.result.json``."""
        path = self.results_dir / f"{task_name}.result.json"
        with open(path, "w") as fh:
            json.dump(result, fh, indent=2, default=str)

    def save_summary(self, summary: dict[str, Any]) -> None:
        """Write the experiment summary to ``summary.json``."""
        path = self.results_dir / "summary.json"
        with open(path, "w") as fh:
            json.dump(summary, fh, indent=2, default=str)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def load_result(self, task_name: str) -> dict[str, Any]:
        """Load a single task result by name."""
        path = self.results_dir / f"{task_name}.result.json"
        with open(path, "r") as fh:
            return json.load(fh)

    def load_summary(self) -> dict[str, Any]:
        """Load the experiment summary."""
        path = self.results_dir / "summary.json"
        with open(path, "r") as fh:
            return json.load(fh)

    def load_all_results(self) -> list[dict[str, Any]]:
        """Load every ``*.result.json`` file in the results directory."""
        results: list[dict[str, Any]] = []
        for path in sorted(self.results_dir.glob("*.result.json")):
            with open(path, "r") as fh:
                results.append(json.load(fh))
        return results

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def has_result(self, task_name: str) -> bool:
        """Return True if a result file exists for *task_name*."""
        return (self.results_dir / f"{task_name}.result.json").exists()
