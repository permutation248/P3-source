"""API routes for individual task details."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...models.schemas import TaskResultDetailResponse
from ...models.task_result import TaskResult
from ..deps import get_db

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.get("/{experiment_id}/{task_name}", response_model=TaskResultDetailResponse)
def get_task_detail(
    experiment_id: int,
    task_name: str,
    db: Session = Depends(get_db),
) -> dict:
    """Get the full detail of a specific task result."""
    task_result = (
        db.query(TaskResult)
        .filter(
            TaskResult.experiment_id == experiment_id,
            TaskResult.task_name == task_name,
        )
        .first()
    )
    if task_result is None:
        raise HTTPException(status_code=404, detail="Task result not found")
    return task_result.to_dict()
