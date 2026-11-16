#!/usr/bin/env python3
"""Profile a Claude Code session log for efficiency bottlenecks.

Usage:
    python3 scripts/profile_session.py <session_log.json>
    python3 scripts/profile_session.py *.json          # multiple files
    python3 scripts/profile_session.py log.json --json  # machine-readable output
"""

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

# ── Pricing (Opus) ──────────────────────────────────────────────────
PRICE_INPUT = 15 / 1e6
PRICE_CACHE_CREATE = 18.75 / 1e6
PRICE_CACHE_READ = 1.5 / 1e6
PRICE_OUTPUT = 75 / 1e6


def parse_session(path: str) -> list[dict]:
    """Parse session JSON into a list of API calls with metadata."""
    with open(path) as f:
        lines = f.readlines()

    events = [json.loads(l) for l in lines]

    calls = []
    current = None

    for e in events:
        etype = e.get("type")

        if etype == "stream_event":
            ev = e.get("event", {})
            evtype = ev.get("type")

            if evtype == "message_start":
                usage = ev.get("message", {}).get("usage", {})
                current = {
                    "input": usage.get("input_tokens", 0),
                    "cache_create": usage.get("cache_creation_input_tokens", 0),
                    "cache_read": usage.get("cache_read_input_tokens", 0),
                    "output": 0,
                    "tools": [],
                    "tool_inputs": {},
                }

            elif evtype == "message_delta" and current is not None:
                current["output"] = ev.get("usage", {}).get("output_tokens", 0)
                calls.append(current)
                current = None

            elif evtype == "content_block_start" and current is not None:
                cb = ev.get("content_block", {})
                if cb.get("type") == "tool_use":
                    current["tools"].append(cb.get("name", ""))

        elif etype == "assistant" and current is not None:
            msg = e.get("message", {})
            for c in msg.get("content", []):
                if c.get("type") == "tool_use":
                    name = c.get("name", "")
                    inp = c.get("input", {})
                    if name == "Edit":
                        current["tool_inputs"][name] = {
                            "old_len": len(inp.get("old_string", "")),
                            "new_len": len(inp.get("new_string", "")),
                        }
                    elif name == "Write":
                        current["tool_inputs"][name] = {
                            "content_len": len(inp.get("content", "")),
                        }

    return calls


def categorize(tools: list[str]) -> str:
    """Categorize an API call by its primary tool."""
    for t in tools:
        if "ToolSearch" in t:
            return "ToolSearch"
        if "diagnostic" in t:
            return "diagnostic"
        if t == "Write":
            return "Write"
        if t == "Edit":
            return "Edit"
        if any(s in t for s in ["loogle", "leansearch", "leanfinder", "local_search", "state_search", "hammer_premise"]):
            return "lemma_search"
        if "multi_attempt" in t:
            return "multi_attempt"
        if "goal" in t and "lean" in t:
            return "lean_goal"
        if "verify" in t:
            return "verify"
        if t == "Read":
            return "Read"
        if "TodoWrite" in t:
            return "TodoWrite"
        if t in ("Bash", "Grep", "Glob"):
            return "Bash/Grep"
        if "build" in t:
            return "lean_build"
    if not tools:
        return "thinking"
    return "other"


CATEGORY_LABELS = {
    "Edit": "Edit (写/改代码)",
    "Write": "Write (全文写入)",
    "lemma_search": "Lemma搜索 (loogle等)",
    "ToolSearch": "ToolSearch (加载schema)",
    "diagnostic": "diagnostic (类型检查)",
    "multi_attempt": "multi_attempt (批量测试)",
    "lean_goal": "lean_goal (查看目标)",
    "Read": "Read (读文件)",
    "TodoWrite": "TodoWrite",
    "verify": "verify (公理检查)",
    "Bash/Grep": "Bash/Grep",
    "lean_build": "lean_build",
    "thinking": "thinking (纯文本)",
    "other": "other",
}


def detect_antipatterns(calls: list[dict]) -> list[dict]:
    """Detect efficiency anti-patterns in the call sequence."""
    patterns = []
    cats = [categorize(c["tools"]) for c in calls]

    # 1. Edit→diagnostic cycle count
    edit_diag_cycles = 0
    error_rounds = 0
    for i in range(len(cats) - 1):
        if cats[i] in ("Edit", "Write") and cats[i + 1] == "diagnostic":
            edit_diag_cycles += 1
            # If diagnostic is followed by more Edit/Write, it found errors
            if i + 2 < len(cats) and cats[i + 2] in ("Edit", "Write", "lemma_search"):
                error_rounds += 1

    if edit_diag_cycles > 0:
        patterns.append({
            "name": "edit_diagnostic_cycles",
            "severity": "high" if error_rounds > 5 else "medium" if error_rounds > 2 else "low",
            "message": f"Edit→diagnostic 循环 {edit_diag_cycles} 次，其中 {error_rounds} 次有错需继续修",
            "suggestion": "减少修复轮次：确保 lemma 全部预搜确认后再写代码",
            "cycles": edit_diag_cycles,
            "error_rounds": error_rounds,
        })

    # 2. Search after Write/Edit (lemma gate violation)
    first_write_idx = None
    for i, cat in enumerate(cats):
        if cat in ("Edit", "Write") and first_write_idx is None:
            first_write_idx = i
            break

    search_after_write = 0
    if first_write_idx is not None:
        for i in range(first_write_idx, len(cats)):
            if cats[i] == "lemma_search":
                search_after_write += 1

    if search_after_write > 0:
        patterns.append({
            "name": "search_after_write",
            "severity": "high" if search_after_write > 3 else "medium",
            "message": f"写代码之后又搜了 {search_after_write} 次 lemma（违反 lemma gate）",
            "suggestion": "所有 lemma 搜索应在第一次 Edit/Write 之前完成",
            "count": search_after_write,
        })

    # 3. Write (full file rewrite) count
    write_count = sum(1 for cat in cats if cat == "Write")
    if write_count > 1:
        total_write_chars = sum(
            c.get("tool_inputs", {}).get("Write", {}).get("content_len", 0)
            for c in calls if categorize(c["tools"]) == "Write"
        )
        patterns.append({
            "name": "multiple_writes",
            "severity": "high" if write_count > 3 else "medium",
            "message": f"全文 Write {write_count} 次（共 {total_write_chars:,} chars）",
            "suggestion": "首次 Write 后应改用 Edit 增量修改",
            "count": write_count,
            "total_chars": total_write_chars,
        })

    # 4. ToolSearch overhead
    ts_output = sum(c["output"] for c in calls if categorize(c["tools"]) == "ToolSearch")
    total_output = sum(c["output"] for c in calls)
    if ts_output > 0 and total_output > 0:
        pct = ts_output * 100 / total_output
        patterns.append({
            "name": "toolsearch_overhead",
            "severity": "medium" if pct > 15 else "low",
            "message": f"ToolSearch 消耗 {ts_output:,} 输出 tokens（{pct:.0f}%），纯框架开销",
            "suggestion": "不可避免，但注意占比",
            "output_tokens": ts_output,
            "pct": round(pct, 1),
        })

    # 5. Large single Edit (>3000 chars new_string)
    large_edits = []
    for i, c in enumerate(calls):
        if categorize(c["tools"]) == "Edit":
            new_len = c.get("tool_inputs", {}).get("Edit", {}).get("new_len", 0)
            if new_len > 3000:
                large_edits.append((i + 1, new_len))

    if large_edits:
        patterns.append({
            "name": "large_edits",
            "severity": "medium" if len(large_edits) > 2 else "low",
            "message": f"大块 Edit {len(large_edits)} 次: " + ", ".join(f"#{n}({sz}ch)" for n, sz in large_edits),
            "suggestion": "大块 Edit 容易出错，考虑拆成更小的增量修改",
            "edits": large_edits,
        })

    # 6. Repeated loogle with similar queries (redundant search)
    loogle_queries = []
    for e_raw_line in open(sys.argv[1]):
        e = json.loads(e_raw_line)
        if e.get("type") == "assistant":
            for c in e.get("message", {}).get("content", []):
                if c.get("type") == "tool_use" and "loogle" in c.get("name", ""):
                    loogle_queries.append(c.get("input", {}).get("query", ""))

    if len(loogle_queries) > 5:
        patterns.append({
            "name": "many_loogle",
            "severity": "medium",
            "message": f"Loogle 搜索 {len(loogle_queries)} 次",
            "suggestion": "优先用关键词搜索（lean_local_search）而非类型模式搜索",
            "count": len(loogle_queries),
            "queries": loogle_queries,
        })

    return patterns


def profile(path: str, json_output: bool = False) -> dict:
    """Run full profile on a session log."""
    calls = parse_session(path)

    if not calls:
        return {"error": "No API calls found"}

    # ── Token totals ──
    total_input = sum(c["input"] for c in calls)
    total_cache_create = sum(c["cache_create"] for c in calls)
    total_cache_read = sum(c["cache_read"] for c in calls)
    total_output = sum(c["output"] for c in calls)

    cost_input = total_input * PRICE_INPUT
    cost_cache_create = total_cache_create * PRICE_CACHE_CREATE
    cost_cache_read = total_cache_read * PRICE_CACHE_READ
    cost_output = total_output * PRICE_OUTPUT
    total_cost = cost_input + cost_cache_create + cost_cache_read + cost_output

    # ── Per-category breakdown ──
    by_cat = defaultdict(lambda: {"count": 0, "output": 0, "cache_read": 0})
    for c in calls:
        cat = categorize(c["tools"])
        by_cat[cat]["count"] += 1
        by_cat[cat]["output"] += c["output"]
        by_cat[cat]["cache_read"] += c["cache_read"]

    # ── Anti-patterns ──
    antipatterns = detect_antipatterns(calls)

    # ── Top expensive calls ──
    top_calls = sorted(enumerate(calls), key=lambda x: -x[1]["output"])[:5]

    result = {
        "file": str(path),
        "api_calls": len(calls),
        "tokens": {
            "input": total_input,
            "cache_create": total_cache_create,
            "cache_read": total_cache_read,
            "output": total_output,
        },
        "cost": {
            "input": round(cost_input, 3),
            "cache_create": round(cost_cache_create, 3),
            "cache_read": round(cost_cache_read, 3),
            "output": round(cost_output, 3),
            "total": round(total_cost, 3),
        },
        "by_category": {
            cat: data for cat, data in sorted(by_cat.items(), key=lambda x: -x[1]["output"])
        },
        "antipatterns": antipatterns,
        "top_expensive_calls": [
            {"call_num": i + 1, "output_tokens": c["output"], "tools": c["tools"]}
            for i, c in top_calls
        ],
    }

    if not json_output:
        print_report(result)

    return result


def severity_marker(s: str) -> str:
    if s == "high":
        return "[!!!]"
    elif s == "medium":
        return "[!! ]"
    return "[!  ]"


def print_report(r: dict):
    """Print human-readable profile report."""
    print(f"\n{'=' * 70}")
    print(f"  Session Profile: {Path(r['file']).name}")
    print(f"{'=' * 70}")

    # Overview
    t = r["tokens"]
    c = r["cost"]
    print(f"\n  API 调用: {r['api_calls']}")
    print(f"  输出 tokens: {t['output']:,}  |  Cache 读取: {t['cache_read']:,}")
    print(f"  总成本: ${c['total']:.2f}  (输出=${c['output']:.2f} + cache读=${c['cache_read']:.2f} + cache写=${c['cache_create']:.2f})")

    # Category breakdown
    print(f"\n  {'类别':<30} {'次数':>4} {'输出tokens':>10} {'占比':>6}")
    print(f"  {'-' * 55}")
    total_out = t["output"] or 1
    for cat, data in r["by_category"].items():
        label = CATEGORY_LABELS.get(cat, cat)
        pct = data["output"] * 100 / total_out
        print(f"  {label:<30} {data['count']:>4} {data['output']:>10,} {pct:>5.1f}%")

    # Anti-patterns
    if r["antipatterns"]:
        print(f"\n  Anti-patterns:")
        for ap in sorted(r["antipatterns"], key=lambda x: {"high": 0, "medium": 1, "low": 2}[x["severity"]]):
            marker = severity_marker(ap["severity"])
            print(f"    {marker} {ap['message']}")
            print(f"           → {ap['suggestion']}")
    else:
        print(f"\n  Anti-patterns: none detected")

    # Top expensive calls
    print(f"\n  Top 5 最贵 API 调用:")
    for item in r["top_expensive_calls"]:
        tools = [t.replace("mcp__lean-lsp__", "") for t in item["tools"]]
        print(f"    #{item['call_num']:>2}: {item['output_tokens']:>6} tokens  {', '.join(tools)}")

    print(f"\n{'=' * 70}\n")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    json_output = "--json" in sys.argv
    files = [f for f in sys.argv[1:] if f != "--json"]

    all_results = []
    for f in files:
        if not Path(f).exists():
            print(f"File not found: {f}", file=sys.stderr)
            continue
        result = profile(f, json_output)
        all_results.append(result)

    if json_output:
        print(json.dumps(all_results if len(all_results) > 1 else all_results[0], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
