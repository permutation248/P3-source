"""SQLAlchemy ORM model for experiments."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from anonymous_prover.models.database import Base


class Experiment(Base):
    __tablename__ = "experiments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    mode: Mapped[str] = mapped_column(String, nullable=False)
    skills_config: Mapped[str] = mapped_column(String, nullable=False)
    model: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    agent_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    tasks_dir: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    tasks_mode: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    output_dir: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    parallel: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    task_timeout_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    max_cost_usd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    notify_email: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    custom_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    total_tasks: Mapped[int] = mapped_column(Integer, default=0)
    solved_count: Mapped[int] = mapped_column(Integer, default=0)
    solved_rate: Mapped[float] = mapped_column(Float, default=0.0)
    avg_time_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    avg_cost_usd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    total_cost_usd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    avg_turns: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    summary_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    config_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(String, default="pending")

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationship
    task_results: Mapped[list["TaskResult"]] = relationship(  # noqa: F821
        "TaskResult",
        back_populates="experiment",
        cascade="all, delete-orphan",
    )

    def to_dict(self) -> dict[str, Any]:
        """Serialise this experiment to a plain dict, parsing JSON blobs."""
        from .utils import parse_json_field as _parse_json

        return {
            "id": self.id,
            "name": self.name,
            "mode": self.mode,
            "skills_config": self.skills_config,
            "model": self.model,
            "agent_type": self.agent_type,
            "tasks_dir": self.tasks_dir,
            "tasks_mode": self.tasks_mode,
            "output_dir": self.output_dir,
            "parallel": self.parallel,
            "task_timeout_seconds": self.task_timeout_seconds,
            "total_tasks": self.total_tasks,
            "solved_count": self.solved_count,
            "solved_rate": self.solved_rate,
            "avg_time_seconds": self.avg_time_seconds,
            "avg_cost_usd": self.avg_cost_usd,
            "total_cost_usd": self.total_cost_usd,
            "avg_turns": self.avg_turns,
            "summary_json": _parse_json(self.summary_json),
            "config_json": _parse_json(self.config_json),
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }
