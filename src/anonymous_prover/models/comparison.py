"""SQLAlchemy ORM model for experiment comparisons."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from anonymous_prover.models.database import Base


class Comparison(Base):
    __tablename__ = "comparisons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    baseline_experiment_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("experiments.id"), nullable=False
    )
    treatment_experiment_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("experiments.id"), nullable=False
    )

    common_tasks: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    baseline_solved_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    treatment_solved_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    delta: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    mcnemar_p_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    wilcoxon_time_p_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    wilcoxon_cost_p_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    comparison_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    def to_dict(self) -> dict[str, Any]:
        """Serialise this comparison to a plain dict."""
        from .utils import parse_json_field as _parse_json

        return {
            "id": self.id,
            "baseline_experiment_id": self.baseline_experiment_id,
            "treatment_experiment_id": self.treatment_experiment_id,
            "common_tasks": self.common_tasks,
            "baseline_solved_rate": self.baseline_solved_rate,
            "treatment_solved_rate": self.treatment_solved_rate,
            "delta": self.delta,
            "mcnemar_p_value": self.mcnemar_p_value,
            "wilcoxon_time_p_value": self.wilcoxon_time_p_value,
            "wilcoxon_cost_p_value": self.wilcoxon_cost_p_value,
            "comparison_json": _parse_json(self.comparison_json),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
