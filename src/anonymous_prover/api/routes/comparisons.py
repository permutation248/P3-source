"""API routes for experiment comparisons."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...models.comparison import Comparison
from ...models.experiment import Experiment
from ...models.schemas import ComparisonCreate, ComparisonResponse
from ...models.task_result import TaskResult
from ...stats.tests import mcnemar_test, significance_label, wilcoxon_test
from ..deps import get_db

router = APIRouter(prefix="/api/comparisons", tags=["comparisons"])


@router.post("", response_model=ComparisonResponse, status_code=201)
def create_comparison(
    data: ComparisonCreate,
    db: Session = Depends(get_db),
) -> Comparison:
    """Create a statistical comparison between two experiments."""
    baseline = (
        db.query(Experiment)
        .filter(Experiment.id == data.baseline_experiment_id)
        .first()
    )
    if baseline is None:
        raise HTTPException(status_code=404, detail="Baseline experiment not found")

    treatment = (
        db.query(Experiment)
        .filter(Experiment.id == data.treatment_experiment_id)
        .first()
    )
    if treatment is None:
        raise HTTPException(status_code=404, detail="Treatment experiment not found")

    # Load task results
    baseline_results = (
        db.query(TaskResult)
        .filter(TaskResult.experiment_id == data.baseline_experiment_id)
        .all()
    )
    treatment_results = (
        db.query(TaskResult)
        .filter(TaskResult.experiment_id == data.treatment_experiment_id)
        .all()
    )

    baseline_by_name = {tr.task_name: tr for tr in baseline_results}
    treatment_by_name = {tr.task_name: tr for tr in treatment_results}

    # Find common tasks
    common_tasks = sorted(set(baseline_by_name.keys()) & set(treatment_by_name.keys()))

    if not common_tasks:
        raise HTTPException(status_code=400, detail="No common tasks between experiments")

    # Compute solved rates
    baseline_solved = sum(1 for t in common_tasks if baseline_by_name[t].solved)
    treatment_solved = sum(1 for t in common_tasks if treatment_by_name[t].solved)
    n_common = len(common_tasks)
    baseline_solved_rate = baseline_solved / n_common * 100.0
    treatment_solved_rate = treatment_solved / n_common * 100.0
    delta = treatment_solved_rate - baseline_solved_rate

    # McNemar test
    baseline_outcomes = [baseline_by_name[t].solved for t in common_tasks]
    treatment_outcomes = [treatment_by_name[t].solved for t in common_tasks]
    mcnemar = mcnemar_test(baseline_outcomes, treatment_outcomes)

    # Wilcoxon tests for time and cost
    baseline_times = []
    treatment_times = []
    baseline_costs = []
    treatment_costs = []
    for t in common_tasks:
        bt = baseline_by_name[t]
        tt = treatment_by_name[t]
        if bt.total_time_seconds is not None and tt.total_time_seconds is not None:
            baseline_times.append(bt.total_time_seconds)
            treatment_times.append(tt.total_time_seconds)
        if bt.cost_usd is not None and tt.cost_usd is not None:
            baseline_costs.append(bt.cost_usd)
            treatment_costs.append(tt.cost_usd)

    wilcoxon_time = (
        wilcoxon_test(baseline_times, treatment_times) if len(baseline_times) >= 2 else None
    )
    wilcoxon_cost = (
        wilcoxon_test(baseline_costs, treatment_costs) if len(baseline_costs) >= 2 else None
    )

    # Build detailed comparison JSON
    comparison_detail = {
        "common_tasks": common_tasks,
        "baseline_name": baseline.name,
        "treatment_name": treatment.name,
        "mcnemar": mcnemar,
        "wilcoxon_time": wilcoxon_time,
        "wilcoxon_cost": wilcoxon_cost,
        "mcnemar_significance": significance_label(mcnemar["p_value"]),
    }

    comparison = Comparison(
        baseline_experiment_id=data.baseline_experiment_id,
        treatment_experiment_id=data.treatment_experiment_id,
        common_tasks=n_common,
        baseline_solved_rate=baseline_solved_rate,
        treatment_solved_rate=treatment_solved_rate,
        delta=delta,
        mcnemar_p_value=mcnemar["p_value"],
        wilcoxon_time_p_value=wilcoxon_time["p_value"] if wilcoxon_time else None,
        wilcoxon_cost_p_value=wilcoxon_cost["p_value"] if wilcoxon_cost else None,
        comparison_json=json.dumps(comparison_detail),
    )
    db.add(comparison)
    db.commit()
    db.refresh(comparison)

    return comparison


@router.get("/{comparison_id}", response_model=ComparisonResponse)
def get_comparison(
    comparison_id: int,
    db: Session = Depends(get_db),
) -> dict:
    """Get a comparison by ID with parsed comparison_json."""
    comparison = db.query(Comparison).filter(Comparison.id == comparison_id).first()
    if comparison is None:
        raise HTTPException(status_code=404, detail="Comparison not found")
    return comparison.to_dict()
