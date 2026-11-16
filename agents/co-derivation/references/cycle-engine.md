# Cycle Engine Reference

> Shared logic for `/lean4:prove` and `/lean4:autoprove`.

Both commands share a six-phase cycle engine. This reference documents the shared mechanics; command-specific behavior is noted inline.

## Six-Phase Cycle

```
Plan → Work → Checkpoint → Review → Replan → Continue/Stop
```

1. **Plan** — Discover state via LSP, identify sorries, search for needed lemmas, decompose into modular `private lemma` structure
2. **Work** — Fill sorries using search + tactics (see [sorry-filling.md](sorry-filling.md))
3. **Checkpoint** — Stage and commit progress (see [checkpoint.md](checkpoint.md))
4. **Review** — Quality check at configured intervals
5. **Replan** — Enter planner mode, produce/update action plan
6. **Continue/Stop** — auto-continue or stop (fully autonomous, no user prompts)

## LSP-First Protocol

LSP tools are the normative first-pass for all discovery, search, and validation. Script fallback is permitted only when LSP is unavailable or its budget is exhausted.

**Plan phase (per target sorry):**
1. `lean_goal(file, line)` — understand goal before ordering
2. Up to 3 LSP search tools (time-boxed ~30s total): `lean_local_search`, one of `lean_leanfinder`/`lean_leansearch`/`lean_hammer_premise`, and `lean_loogle`
3. Record top candidate lemmas and intended next attempts in the plan
4. **Trivial-goal shortcut:** If the goal is obviously solvable (`rfl`, `simp`, `exact` with a known lemma), skip extended search — proceed directly to work phase
5. **Complex-goal decompose:** Based on search results, design modular `private lemma` structure — equational lemmas for helpers, loop/recursion invariants, precondition unpacking. Record decomposition plan.

**Work phase (per sorry):**
1. Refresh `lean_goal(file, line)` at start
2. Run up to 2 LSP search tools before any script fallback (skip if trivial goal or prior planning search was conclusive)
3. Generate 2-3 candidate proof snippets from search results. When `lean_hammer_premise` returns premises, generate `simp only [p1, p2]` and `grind [p1, p2]` candidates.
4. Test with `lean_multi_attempt(file, line, snippets=[...])`
5. Prefer shortest passing candidate; only then edit/commit

**Fallback gate:** Script fallback (`$LEAN4_SCRIPTS/smart_search.sh`, `$LEAN4_SCRIPTS/search_mathlib.sh`) and repair agents are permitted when:
- LSP search budget is exhausted (at least 2 searches returning empty/inconclusive), OR
- LSP server is confirmed unavailable, timing out, or rate-limited

For sorry discovery fallback, prefer one-pass structured output:
`${LEAN4_PYTHON_BIN:-python3} "$LEAN4_SCRIPTS/sorry_analyzer.py" <target> --format=json --report-only`.
Use default `text` for quick human review and `summary` only for counts.
Do not suppress script stderr via `/dev/null`; surfaced errors are part of the fallback signal.

## Review Phase

At configured intervals (`--review-every`), run review matching current scope:
- Working on single sorry → `--scope=sorry --line=N`
- Working on file → `--scope=file`
- Never trigger `--scope=project` automatically

Reviews act as gates: review → replan → auto-continue. No user approval is required at any step.

## Replan Phase

After review → enter planner mode → produce/update action plan. Work phase follows that plan next cycle.

## Safety

Blocked git commands (both prove and autoprove):
- `git push` (review first)
- `git commit --amend` (preserve history)
- `gh pr create` (review first)
- `git checkout --`/`git restore`/`git reset --hard`/`git clean` (use `git stash push -u` or revert commit)

## See Also

- [sorry-filling.md](sorry-filling.md) — Sorry elimination tactics
- [build-target-policy.md](build-target-policy.md) — Three-tier verification ladder
- [checkpoint.md](checkpoint.md) — Checkpoint logic
- [stuck-and-repair.md](stuck-and-repair.md) — Stuck detection, falsification, repair mode
- [deep-mode.md](deep-mode.md) — Deep mode for stubborn sorries
- [compilation-errors.md](compilation-errors.md) — Error-by-error repair guidance
- [command-examples.md](command-examples.md) — Usage examples
