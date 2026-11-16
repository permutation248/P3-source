"""CLI command: compare two experiment result directories."""

from __future__ import annotations

import json

import click


@click.command()
@click.argument("baseline_dir")
@click.argument("treatment_dir")
@click.option("--json-output", is_flag=True, default=False, help="Output as JSON.")
@click.option("--pretty", is_flag=True, default=False, help="Pretty-print JSON output.")
def compare(baseline_dir: str, treatment_dir: str, json_output: bool, pretty: bool) -> None:
    """Compare results from two experiment directories."""
    from ..comparators.factory import create_comparator

    comparator = create_comparator()
    result = comparator.compare(baseline_dir, treatment_dir)

    if json_output:
        indent = 2 if pretty else None
        click.echo(json.dumps(result, indent=indent, default=str))
    else:
        click.echo(f"Baseline:  {baseline_dir}")
        click.echo(f"Treatment: {treatment_dir}")
        click.echo()

        common = result.get("common_tasks", 0)
        click.echo(f"Common tasks: {common}")
        click.echo()

        baseline_rate = result.get("baseline_solved_rate", 0.0)
        treatment_rate = result.get("treatment_solved_rate", 0.0)
        delta = result.get("delta", 0.0)

        click.echo(f"Baseline solved rate:  {baseline_rate:.1f}%")
        click.echo(f"Treatment solved rate: {treatment_rate:.1f}%")
        click.echo(f"Delta:                 {delta:+.1f}%")
        click.echo()

        # Statistical tests
        from ..stats.tests import significance_label

        stats_tests = result.get("statistical_tests", {})

        mcnemar = stats_tests.get("mcnemar_solved", {})
        if mcnemar:
            p = mcnemar.get("p_value", 1.0)
            if p is not None:
                label = significance_label(p)
                click.echo(f"McNemar test:  p={p:.4f} {label}")

        wilcoxon_time = stats_tests.get("wilcoxon_time", {})
        if wilcoxon_time:
            p = wilcoxon_time.get("p_value")
            if p is not None:
                label = significance_label(p)
                click.echo(f"Wilcoxon (time): p={p:.4f} {label}")

        wilcoxon_cost = stats_tests.get("wilcoxon_cost", {})
        if wilcoxon_cost:
            p = wilcoxon_cost.get("p_value")
            if p is not None:
                label = significance_label(p)
                click.echo(f"Wilcoxon (cost): p={p:.4f} {label}")
