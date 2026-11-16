#!/usr/bin/env python3
"""Split a JSONL trace into N parallel lane files.

Usage:
    python3 scripts/split_parallel_trace.py claude_traces/2026-03-25/trace_174759.jsonl
    python3 scripts/split_parallel_trace.py trace.jsonl --lanes 4 --mode worker
    python3 scripts/split_parallel_trace.py trace.jsonl --mode by-turn-index
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


def nested_get(obj: dict[str, Any], dotted_path: str) -> Any:
    cur: Any = obj
    for part in dotted_path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Split JSONL trace by parallel lanes."
    )
    parser.add_argument("input", type=Path, help="Input JSONL file path")
    parser.add_argument(
        "--lanes",
        type=int,
        default=4,
        help="Number of parallel lanes (default: 4)",
    )
    parser.add_argument(
        "--mode",
        choices=["worker", "by-turn-index"],
        default="worker",
        help=(
            "worker: keep same worker key in same lane; "
            "by-turn-index: group by order within each turn"
        ),
    )
    parser.add_argument(
        "--worker-key",
        default="request.headers.Host",
        help=(
            "Dotted key path used in worker mode "
            "(default: request.headers.Host)"
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory (default: <input_stem>_split)",
    )
    return parser.parse_args()


def split_worker_mode(
    records: list[tuple[str, dict[str, Any]]],
    lanes: int,
    worker_key: str,
) -> tuple[list[list[str]], dict[int, int], dict[str, int]]:
    lane_lines: list[list[str]] = [[] for _ in range(lanes)]
    lane_counts: dict[int, int] = defaultdict(int)
    worker_to_lane: dict[str, int] = {}

    for raw_line, obj in records:
        key_val = nested_get(obj, worker_key)
        if key_val is None:
            # Fallback to turn-index identity when worker key missing.
            key_val = f"turn:{obj.get('turn')}#req:{obj.get('request_id')}"
        key = str(key_val)

        if key not in worker_to_lane:
            if len(worker_to_lane) < lanes:
                worker_to_lane[key] = len(worker_to_lane)
            else:
                # If more keys than lanes, keep deterministic sharding.
                worker_to_lane[key] = hash(key) % lanes

        lane_idx = worker_to_lane[key]
        lane_lines[lane_idx].append(raw_line)
        lane_counts[lane_idx] += 1

    return lane_lines, lane_counts, worker_to_lane


def split_turn_index_mode(
    records: list[tuple[str, dict[str, Any]]],
    lanes: int,
) -> tuple[list[list[str]], dict[int, int], dict[str, int]]:
    lane_lines: list[list[str]] = [[] for _ in range(lanes)]
    lane_counts: dict[int, int] = defaultdict(int)
    worker_map: dict[str, int] = {}

    turn_rows: dict[Any, list[tuple[str, dict[str, Any]]]] = defaultdict(list)
    for row in records:
        turn_rows[row[1].get("turn")].append(row)

    for turn in sorted(turn_rows, key=lambda x: (x is None, x)):
        rows = turn_rows[turn]
        rows.sort(
            key=lambda r: (
                r[1].get("timestamp", ""),
                str(r[1].get("request_id", "")),
            )
        )
        for idx, (raw_line, obj) in enumerate(rows):
            lane_idx = idx % lanes
            lane_lines[lane_idx].append(raw_line)
            lane_counts[lane_idx] += 1
            rid = str(obj.get("request_id", ""))
            if rid:
                worker_map[rid] = lane_idx

    return lane_lines, lane_counts, worker_map


def main() -> None:
    args = parse_args()

    if not args.input.exists():
        raise SystemExit(f"Input not found: {args.input}")
    if args.lanes <= 0:
        raise SystemExit("--lanes must be > 0")

    out_dir = args.output_dir or args.input.with_name(f"{args.input.stem}_split")
    out_dir.mkdir(parents=True, exist_ok=True)

    records: list[tuple[str, dict[str, Any]]] = []
    bad_lines: list[str] = []

    with args.input.open("r", encoding="utf-8") as f:
        for line in f:
            raw_line = line.rstrip("\n")
            if not raw_line.strip():
                continue
            try:
                obj = json.loads(raw_line)
            except json.JSONDecodeError:
                bad_lines.append(raw_line)
                continue
            records.append((raw_line, obj))

    if args.mode == "worker":
        lane_lines, lane_counts, worker_map = split_worker_mode(
            records, args.lanes, args.worker_key
        )
    else:
        lane_lines, lane_counts, worker_map = split_turn_index_mode(
            records, args.lanes
        )

    for i in range(args.lanes):
        lane_path = out_dir / f"lane_{i + 1}.jsonl"
        with lane_path.open("w", encoding="utf-8") as wf:
            for line in lane_lines[i]:
                wf.write(line + "\n")

    if bad_lines:
        bad_path = out_dir / "unparsed_lines.log"
        with bad_path.open("w", encoding="utf-8") as wf:
            for line in bad_lines:
                wf.write(line + "\n")

    summary_path = out_dir / "summary.txt"
    with summary_path.open("w", encoding="utf-8") as sf:
        sf.write(f"input={args.input}\n")
        sf.write(f"mode={args.mode}\n")
        sf.write(f"lanes={args.lanes}\n")
        sf.write(f"worker_key={args.worker_key}\n")
        sf.write(f"parsed_records={len(records)}\n")
        sf.write(f"bad_lines={len(bad_lines)}\n")
        for i in range(args.lanes):
            sf.write(f"lane_{i + 1}={lane_counts.get(i, 0)}\n")
        sf.write(f"unique_worker_keys={len(worker_map)}\n")

    print(f"Done. Output dir: {out_dir}")
    for i in range(args.lanes):
        print(f"  lane_{i + 1}.jsonl: {lane_counts.get(i, 0)} lines")
    if bad_lines:
        print(f"  unparsed_lines.log: {len(bad_lines)} lines")
    print(f"  summary.txt")


if __name__ == "__main__":
    main()
