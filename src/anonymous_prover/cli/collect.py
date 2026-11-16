"""CLI command: collect and summarise results."""

from __future__ import annotations

import json

import click


@click.command()
@click.argument("results_dir")
@click.option("--json-output", is_flag=True, default=False, help="Output as JSON.")
@click.option("--pretty", is_flag=True, default=False, help="Pretty-print JSON output.")
def collect(results_dir: str, json_output: bool, pretty: bool) -> None:
    """Collect and summarise results from a results directory."""
    from ..collectors.factory import create_collector

    collector = create_collector()
    summary = collector.collect(results_dir)

    if json_output:
        indent = 2 if pretty else None
        click.echo(json.dumps(summary, indent=indent, default=str))
    else:
        total = summary.get("total", 0)
        solved = summary.get("solved", 0)
        rate = summary.get("solved_rate", 0.0)

        click.echo(f"Results directory: {results_dir}")
        click.echo(f"  Total tasks:  {total}")
        click.echo(f"  Solved:       {solved}")
        click.echo(f"  Solved rate:  {rate:.1f}%")

        time_stats = summary.get("time_stats", {})
        cost_stats = summary.get("cost_stats", {})
        turn_stats = summary.get("turn_stats", {})

        if time_stats.get("avg") is not None:
            click.echo(f"  Avg time:     {time_stats['avg']:.1f}s")
        if cost_stats.get("avg") is not None:
            click.echo(f"  Avg cost:     ${cost_stats['avg']:.4f}")
        if cost_stats.get("total") is not None:
            click.echo(f"  Total cost:   ${cost_stats['total']:.4f}")
        if turn_stats.get("avg") is not None:
            click.echo(f"  Avg turns:    {turn_stats['avg']:.1f}")

        per_benchmark = summary.get("per_benchmark", {})
        if per_benchmark:
            click.echo()
            click.echo("Per-benchmark breakdown:")
            for bench_name, bench_data in sorted(per_benchmark.items()):
                b_total = bench_data.get("total", 0)
                b_solved = bench_data.get("solved", 0)
                b_rate = bench_data.get("solved_rate", 0.0)
                click.echo(f"  {bench_name}: {b_solved}/{b_total} ({b_rate:.1f}%)")
