"""SQLAlchemy ORM model for individual task results."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from anonymous_prover.models.database import Base


class TaskResult(Base):
    __tablename__ = "task_results"
    __table_args__ = (
        Index("ix_task_results_experiment_task", "experiment_id", "task_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    experiment_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("experiments.id"), nullable=False
    )
    task_name: Mapped[str] = mapped_column(String, nullable=False)

    solved: Mapped[bool] = mapped_column(Boolean, default=False)
    sorry_count: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    compilation_error: Mapped[bool] = mapped_column(Boolean, default=False)
    timeout: Mapped[bool] = mapped_column(Boolean, default=False)

    total_time_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    total_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    input_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # "reported" (CLI) | "estimated" (computed locally, e.g. miromind) | "none"
    cost_source: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    total_turns: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    mode: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    result_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    # Relationship
    experiment: Mapped["Experiment"] = relationship(  # noqa: F821
        "Experiment", back_populates="task_results"
    )

    def to_dict(self) -> dict[str, Any]:
        """Serialise this task result to a plain dict."""
        from .utils import parse_json_field as _parse_json

        return {
            "id": self.id,
            "experiment_id": self.experiment_id,
            "task_name": self.task_name,
            "solved": self.solved,
            "sorry_count": self.sorry_count,
            "error_count": self.error_count,
            "compilation_error": self.compilation_error,
            "timeout": self.timeout,
            "total_time_seconds": self.total_time_seconds,
            "total_tokens": self.total_tokens,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_usd": self.cost_usd,
            "cost_source": self.cost_source,
            "total_turns": self.total_turns,
            "mode": self.mode,
            "result_json": _parse_json(self.result_json),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
