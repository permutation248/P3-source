"""Pydantic schemas for API request / response bodies."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, field_validator


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class ExperimentCreate(BaseModel):
    """Schema for creating a new experiment."""
    name: str
    mode: str = "auto"
    skills_config: str = "none"
    tasks_dir: str = ""
    tasks_mode: str = "file"
    model: str = "sonnet-4-6"
    agent_type: str = "claude-code"
    parallel: int = 4
    task_timeout_seconds: int = 1800
    max_cost_usd: Optional[float] = None
    notify_email: Optional[str] = None
    custom_prompt: Optional[str] = None

    @field_validator("tasks_mode")
    @classmethod
    def _tasks_mode_valid(cls, v: str) -> str:
        if v not in {"file", "project"}:
            raise ValueError("tasks_mode must be one of: file, project")
        return v


class ComparisonCreate(BaseModel):
    """Schema for creating a new comparison between two experiments."""
    baseline_experiment_id: int
    treatment_experiment_id: int


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class ExperimentResponse(BaseModel):
    """Full experiment response."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    mode: str
    skills_config: str
    model: Optional[str] = None
    agent_type: Optional[str] = None
    tasks_dir: Optional[str] = None
    tasks_mode: Optional[str] = None
    output_dir: Optional[str] = None
    parallel: Optional[int] = None
    task_timeout_seconds: Optional[int] = None
    total_tasks: int = 0
    solved_count: int = 0
    solved_rate: float = 0.0
    avg_time_seconds: Optional[float] = None
    avg_cost_usd: Optional[float] = None
    total_cost_usd: Optional[float] = None
    avg_turns: Optional[float] = None
    summary_json: Optional[Any] = None
    config_json: Optional[Any] = None
    status: str = "pending"
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class TaskResultResponse(BaseModel):
    """Compact task result for list views."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_name: str
    solved: bool = False
    sorry_count: int = 0
    total_time_seconds: Optional[float] = None
    cost_usd: Optional[float] = None
    cost_source: Optional[str] = None
    total_turns: Optional[int] = None
    mode: Optional[str] = None


class TaskResultDetailResponse(BaseModel):
    """Full task result including the raw JSON blob."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    experiment_id: int
    task_name: str
    solved: bool = False
    sorry_count: int = 0
    error_count: int = 0
    compilation_error: bool = False
    timeout: bool = False
    total_time_seconds: Optional[float] = None
    total_tokens: Optional[int] = None
    cost_usd: Optional[float] = None
    cost_source: Optional[str] = None
    total_turns: Optional[int] = None
    mode: Optional[str] = None
    result_json: Optional[Any] = None
    created_at: Optional[datetime] = None


class ComparisonResponse(BaseModel):
    """Full comparison response."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    baseline_experiment_id: int
    treatment_experiment_id: int
    common_tasks: Optional[int] = None
    baseline_solved_rate: Optional[float] = None
    treatment_solved_rate: Optional[float] = None
    delta: Optional[float] = None
    mcnemar_p_value: Optional[float] = None
    wilcoxon_time_p_value: Optional[float] = None
    wilcoxon_cost_p_value: Optional[float] = None
    comparison_json: Optional[Any] = None
    created_at: Optional[datetime] = None


class SummaryResponse(BaseModel):
    """Aggregated experiment summary."""
    total_tasks: int = 0
    solved_count: int = 0
    solved_rate: float = 0.0
    avg_time: Optional[float] = None
    avg_cost: Optional[float] = None
    total_cost: Optional[float] = None
    avg_turns: Optional[float] = None
    per_benchmark: dict[str, Any] = {}


class PaginatedResponse(BaseModel):
    """Generic paginated response wrapper."""
    items: list[Any]
    total: int
    page: int
    page_size: int
