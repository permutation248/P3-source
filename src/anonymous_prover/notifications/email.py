"""Email notification via msmtp (matching main branch start.sh behaviour)."""

from __future__ import annotations

import logging
import os
import subprocess

logger = logging.getLogger(__name__)

# Defaults – override via environment variables
DEFAULT_FROM = os.environ.get("ANONYMOUS_EMAIL_FROM", "noreply@example.invalid")
DEFAULT_TO = os.environ.get("ANONYMOUS_EMAIL_TO", "recipient@example.invalid")


def send_experiment_email(
    *,
    experiment_name: str,
    status: str,
    total_tasks: int,
    solved_count: int,
    solved_rate: float,
    avg_time_seconds: float | None,
    total_cost_usd: float | None,
    avg_turns: float | None,
    started_at: str | None,
    completed_at: str | None,
    error: str | None = None,
    recipient: str | None = None,
    sender: str | None = None,
    summary: dict | None = None,
) -> bool:
    """Send an experiment completion email via msmtp.

    Returns True if the email was sent successfully.
    """
    to_addr = recipient or DEFAULT_TO
    from_addr = sender or DEFAULT_FROM

    if status == "completed":
        subject_tag = "SUCCESS"
    elif status == "failed":
        subject_tag = "FAILED"
    else:
        subject_tag = status.upper()

    subject = f"[{subject_tag}] Anonymous-Prover: {experiment_name} ({solved_count}/{total_tasks}, {solved_rate:.1f}%)"

    # Duration
    duration_str = "N/A"
    if started_at and completed_at:
        try:
            from datetime import datetime, timezone
            fmt = "%Y-%m-%dT%H:%M:%S.%f%z"
            # Handle both formats
            for f in (fmt, "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f+00:00"):
                try:
                    t0 = datetime.fromisoformat(started_at)
                    t1 = datetime.fromisoformat(completed_at)
                    delta = t1 - t0
                    total_secs = int(delta.total_seconds())
                    hours, remainder = divmod(total_secs, 3600)
                    minutes, secs = divmod(remainder, 60)
                    if hours > 0:
                        duration_str = f"{hours}h {minutes}m {secs}s"
                    else:
                        duration_str = f"{minutes}m {secs}s"
                    break
                except Exception:
                    continue
        except Exception:
            pass

    body_lines = [
        f"{'=' * 50}",
        f"  EXPERIMENT REPORT: {experiment_name}",
        f"{'=' * 50}",
        "",
        f"  Status:     {subject_tag}",
        f"  Started:    {started_at or 'N/A'}",
        f"  Finished:   {completed_at or 'N/A'}",
        f"  Duration:   {duration_str}",
        "",
        f"{'─' * 50}",
        f"  RESULTS SUMMARY",
        f"{'─' * 50}",
        "",
        f"  Total tasks:   {total_tasks}",
        f"  Solved:        {solved_count}/{total_tasks} ({solved_rate:.1f}%)",
        f"  Avg time:      {avg_time_seconds:.1f}s" if avg_time_seconds is not None else "  Avg time:      N/A",
        f"  Total cost:    ${total_cost_usd:.2f}" if total_cost_usd is not None else "  Total cost:    N/A",
        f"  Avg turns:     {avg_turns:.1f}" if avg_turns is not None else "  Avg turns:     N/A",
    ]

    # Time stats
    if summary:
        time_stats = summary.get("time_stats", {})
        cost_stats = summary.get("cost_stats", {})
        if time_stats:
            body_lines.extend([
                "",
                f"  Time stats:    median={time_stats.get('median', 0):.1f}s  "
                f"p95={time_stats.get('p95', 0):.1f}s  "
                f"min={time_stats.get('min', 0):.1f}s  "
                f"max={time_stats.get('max', 0):.1f}s",
            ])
        if cost_stats:
            body_lines.extend([
                f"  Cost stats:    median=${cost_stats.get('median', 0):.4f}  "
                f"p95=${cost_stats.get('p95', 0):.4f}  "
                f"total=${cost_stats.get('total', 0):.2f}",
            ])

    # Per-task results
    if summary and "tasks" in summary:
        tasks = summary["tasks"]
        body_lines.extend([
            "",
            f"{'─' * 50}",
            f"  PER-TASK RESULTS",
            f"{'─' * 50}",
            "",
            f"  {'Task':<35} {'Status':<10} {'Time':>8} {'Cost':>10} {'Turns':>6}",
            f"  {'─' * 35} {'─' * 10} {'─' * 8} {'─' * 10} {'─' * 6}",
        ])
        for t in sorted(tasks, key=lambda x: x.get("task_name", "")):
            name = t.get("task_name", "?")
            if t.get("solved"):
                st = "SOLVED"
            elif t.get("timeout"):
                st = "TIMEOUT"
            else:
                st = "FAILED"
            time_s = f"{t['total_time_seconds']:.1f}s" if t.get("total_time_seconds") is not None else "—"
            cost = f"${t['cost_usd']:.4f}" if t.get("cost_usd") is not None else "—"
            turns = str(t.get("total_turns", "—"))
            body_lines.append(f"  {name:<35} {st:<10} {time_s:>8} {cost:>10} {turns:>6}")

        # Summary line
        solved_names = [t["task_name"] for t in tasks if t.get("solved")]
        if solved_names:
            body_lines.extend([
                "",
                f"  Solved tasks: {', '.join(sorted(solved_names))}",
            ])

    if error:
        body_lines.extend([
            "",
            f"{'─' * 50}",
            f"  ERROR",
            f"{'─' * 50}",
            "",
            f"  {error}",
        ])

    body_lines.extend(["", f"{'=' * 50}"])
    body = "\n".join(body_lines)

    message = (
        f"From: {from_addr}\n"
        f"To: {to_addr}\n"
        f"Subject: {subject}\n"
        f"MIME-Version: 1.0\n"
        f"Content-Type: text/plain; charset=UTF-8\n"
        f"\n"
        f"{body}\n"
    )

    try:
        proc = subprocess.run(
            ["msmtp", to_addr],
            input=message,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if proc.returncode == 0:
            logger.info("Email sent to %s for experiment '%s'", to_addr, experiment_name)
            return True
        else:
            logger.warning(
                "msmtp failed (exit %d): %s", proc.returncode, proc.stderr.strip()
            )
            return False
    except FileNotFoundError:
        logger.warning("msmtp not found on PATH, skipping email notification")
        return False
    except Exception:
        logger.exception("Failed to send email for experiment '%s'", experiment_name)
        return False
