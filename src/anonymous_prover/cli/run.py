"""CLI command: run an experiment."""

from __future__ import annotations

import sys

import click


@click.command()
@click.option("--config", "config_path", type=click.Path(exists=True), help="YAML config file.")
@click.option("--name", type=str, help="Experiment name.")
@click.option(
    "--mode",
    type=click.Choice(["code", "proof", "auto"]),
    help="Experiment mode.",
)
@click.option(
    "--skills-config",
    type=click.Choice(["none", "standard", "extended", "co_derivation", "docs_only", "tools_only"]),
    default=None,
    help="Skills configuration.",
)
@click.option("--tasks-dir", type=str, help="Directory containing task .lean files.")
@click.option(
    "--tasks-mode",
    type=click.Choice(["file", "project"]),
    default=None,
    help="Task discovery mode.",
)
@click.option("--model", type=str, default=None, help="Agent model name.")
@click.option("--parallel", type=int, default=None, help="Number of parallel workers.")
@click.option("--timeout", "task_timeout", type=int, default=None, help="Task timeout in seconds.")
@click.option("--force", is_flag=True, default=False, help="Re-run even if results exist.")
def run(
    config_path: str | None,
    name: str | None,
    mode: str | None,
    skills_config: str | None,
    tasks_dir: str | None,
    tasks_mode: str | None,
    model: str | None,
    parallel: int | None,
    task_timeout: int | None,
    force: bool,
) -> None:
    """Run a Lean 4 experiment."""
    import os

    from ..core.config import ExperimentConfig
    from ..core.enums import AgentType
    from ..runner.experiment_runner import ExperimentRunner

    def _resolve_agent_type(model_name: str | None) -> AgentType:
        m = (model_name or "").strip().lower()
        if m.startswith("gpt-") or "codex" in m:
            return AgentType.codex
        return AgentType.claude_code

    if config_path:
        config = ExperimentConfig.from_yaml(config_path)
        # Override with any CLI args that were explicitly provided
        overrides: dict = {}
        if name is not None:
            overrides["name"] = name
        if mode is not None:
            overrides["mode"] = mode
        if skills_config is not None:
            overrides["skills_config"] = skills_config
        if tasks_dir is not None:
            overrides["tasks_dir"] = tasks_dir
        if tasks_mode is not None:
            overrides["tasks_mode"] = tasks_mode
        if parallel is not None:
            overrides["parallel"] = parallel
        if task_timeout is not None:
            overrides["task_timeout_seconds"] = task_timeout
        if force:
            overrides["force"] = True
        if model is not None:
            # Need to override nested agent config
            agent_data = config.agent.model_dump()
            agent_data["model"] = model
            agent_data["type"] = _resolve_agent_type(model)
            overrides["agent"] = agent_data
        if overrides:
            config = config.model_copy(update=overrides)
    else:
        if not name or not mode or not tasks_dir:
            click.echo(
                "Error: --name, --mode, and --tasks-dir are required when --config is not provided.",
                err=True,
            )
            sys.exit(1)
        config = ExperimentConfig(
            name=name,
            mode=mode,
            skills_config=skills_config or "none",
            tasks_dir=tasks_dir,
            tasks_mode=tasks_mode or "file",
            parallel=parallel or 4,
            task_timeout_seconds=task_timeout or 1800,
            force=force,
        )
        if model is not None:
            from ..core.config import AgentConfig
            config = config.model_copy(
                update={"agent": AgentConfig(type=_resolve_agent_type(model), model=model)}
            )

    project_root = os.getcwd()
    runner = ExperimentRunner(config, project_root)

    click.echo(f"Running experiment: {config.name}")
    click.echo(f"  Mode: {config.mode}")
    click.echo(f"  Tasks: {config.tasks_dir}")
    click.echo(f"  Model: {config.agent.model}")
    click.echo(f"  Parallel: {config.parallel}")
    click.echo()

    def progress_callback(completed: int, total: int, task_name: str, result: dict | None) -> None:
        status = "done" if result and result.get("solved") else "fail"
        click.echo(f"  [{completed}/{total}] {task_name}: {status}")

    summary = runner.run(progress_callback=progress_callback)

    click.echo()
    total = summary.get("total", 0)
    solved = summary.get("solved", 0)
    rate = summary.get("solved_rate", 0.0)
    avg_time = summary.get("avg_time")
    avg_cost = summary.get("avg_cost")

    click.echo(f"Results: {solved}/{total} solved ({rate:.1f}%)")
    if avg_time is not None:
        click.echo(f"  Avg time: {avg_time:.1f}s")
    if avg_cost is not None:
        click.echo(f"  Avg cost: ${avg_cost:.4f}")
