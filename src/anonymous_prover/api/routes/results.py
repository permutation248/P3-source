"""API routes for experiment results and summaries."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from ...models.experiment import Experiment
from ...models.schemas import PaginatedResponse, SummaryResponse, TaskResultResponse
from ...models.task_result import TaskResult
from ..deps import get_db

router = APIRouter(prefix="/api/results", tags=["results"])


def _latest_task_results_query(db: Session, experiment_id: int):
    """Return a query containing only the latest row per task_name."""
    latest_ids_subq = (
        db.query(
            TaskResult.task_name.label("task_name"),
            func.max(TaskResult.id).label("latest_id"),
        )
        .filter(TaskResult.experiment_id == experiment_id)
        .group_by(TaskResult.task_name)
        .subquery()
    )

    return (
        db.query(TaskResult)
        .join(latest_ids_subq, TaskResult.id == latest_ids_subq.c.latest_id)
        .filter(TaskResult.experiment_id == experiment_id)
    )


@router.get("/{experiment_id}/summary", response_model=SummaryResponse)
def get_summary(
    experiment_id: int,
    db: Session = Depends(get_db),
) -> dict:
    """Return the summary for an experiment."""
    experiment = db.query(Experiment).filter(Experiment.id == experiment_id).first()
    if experiment is None:
        raise HTTPException(status_code=404, detail="Experiment not found")

    # Try to use stored summary_json first
    if experiment.summary_json:
        try:
            return json.loads(experiment.summary_json)
        except (json.JSONDecodeError, TypeError):
            pass

    # Fall back to computing from task results
    task_results = _latest_task_results_query(db, experiment_id).all()
    total = len(task_results)
    solved = sum(1 for tr in task_results if tr.solved)
    times = [tr.total_time_seconds for tr in task_results if tr.total_time_seconds is not None]
    costs = [tr.cost_usd for tr in task_results if tr.cost_usd is not None]
    turns = [tr.total_turns for tr in task_results if tr.total_turns is not None]

    return {
        "total_tasks": total,
        "solved_count": solved,
        "solved_rate": (solved / total * 100.0) if total > 0 else 0.0,
        "avg_time": sum(times) / len(times) if times else None,
        "avg_cost": sum(costs) / len(costs) if costs else None,
        "total_cost": sum(costs) if costs else None,
        "avg_turns": sum(turns) / len(turns) if turns else None,
        "per_benchmark": {},
    }


@router.get("/{experiment_id}/tasks", response_model=PaginatedResponse)
def list_task_results(
    experiment_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    solved: bool | None = None,
    sort_by: str = "task_name",
    sort_order: str = "asc",
    db: Session = Depends(get_db),
) -> dict:
    """List task results with pagination, optional filtering, and sorting."""
    experiment = db.query(Experiment).filter(Experiment.id == experiment_id).first()
    if experiment is None:
        raise HTTPException(status_code=404, detail="Experiment not found")

    query = _latest_task_results_query(db, experiment_id)

    if solved is not None:
        query = query.filter(TaskResult.solved == solved)

    # Determine sort column
    sort_column_map = {
        "task_name": TaskResult.task_name,
        "solved": TaskResult.solved,
        "total_time_seconds": TaskResult.total_time_seconds,
        "cost_usd": TaskResult.cost_usd,
        "total_turns": TaskResult.total_turns,
        "created_at": TaskResult.created_at,
    }
    sort_col = sort_column_map.get(sort_by, TaskResult.task_name)
    if sort_order == "desc":
        sort_col = sort_col.desc()
    else:
        sort_col = sort_col.asc()
    query = query.order_by(sort_col)

    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()

    return {
        "items": [TaskResultResponse.model_validate(tr).model_dump() for tr in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }
