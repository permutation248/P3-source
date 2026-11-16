# Deep Mode

Bounded subroutine for stubborn sorries. Allows multi-file refactoring, helper extraction, and statement generalization.

## Budget Enforcement

- `--deep-sorry-budget` — max sorries per deep invocation
- `--deep-time-budget` — max time per deep invocation
- `--max-deep-per-cycle` — max deep invocations per cycle (default: 1)

If deep budget is exhausted with no progress → stuck.

| Feature | prove | autoprove |
|---------|-------|-----------|
| `--deep=ask` | Prompt before each deep invocation | Not supported (coerced to `stuck`) |
| `--deep=stuck` | Auto-escalate when stuck | Auto-escalate when stuck (default) |
| `--deep=always` | Auto-escalate on any failure | Auto-escalate on any failure |
| `--deep=never` | No deep (default) | No deep |
| `--deep-sorry-budget` | 1 (default) | 2 (default) |
| `--deep-time-budget` | 10m (default) | 20m (default) |
| `--max-deep-per-cycle` | 1 | 1 |
| `--max-consecutive-deep-cycles` | N/A | 2 (autoprove-only) |
| `--deep-snapshot` | `stash` | `stash` | Pre-deep recovery (V1: `stash` only) |
| `--deep-rollback` | `on-regression` | `on-regression` | When to revert: `on-regression` / `on-no-improvement` / `always` / `never` |
| `--deep-scope` | `target` | `target` | Scope fence: `target` (sorry's file only) / `cross-file` |
| `--deep-max-files` | 1 | 2 | Max files deep may edit per invocation |
| `--deep-max-lines` | 120 | 200 | Max added+deleted lines per deep invocation |
| `--deep-regression-gate` | `strict` | `strict` | `strict`: auto-abort on regression; `off`: log only |
| Statement changes | Interactive approval prompt | Logged but auto-skipped |
| `--commit=ask` | Per-commit prompt (yes/yes-all/no/never) | Coerced to `auto` at startup |

## Safety Definitions

- **Regression**: sorry count increases, new diagnostic errors appear, or new blocker signatures introduced compared to pre-deep snapshot
- **No improvement**: sorry count unchanged AND no diagnostic improvement after deep completes
- **Rollback**: restore working tree to pre-deep snapshot via saved snapshot id/ref; mark sorry as stuck with reason (e.g., `"deep: regression — sorry count increased from 3 to 5"`)

## Snapshot and Rollback

Before entering deep mode, the engine captures a **path-scoped** snapshot of all files in the deep scope (target file when `--deep-scope=target`; declared files when `--deep-scope=cross-file`). Only deep-managed paths are snapshotted — unrelated working-tree edits are not swept in.

The snapshot mechanism is implementation-defined; the contract is that rollback restores the snapshotted files to their exact pre-deep state without affecting other files.

**Rollback triggers** (per `--deep-rollback`):

| `--deep-rollback` | Trigger |
|---|---|
| `on-regression` (default) | Regression detected |
| `on-no-improvement` | Regression OR no improvement |
| `always` | After every deep invocation (test-only) |
| `never` | Never rollback (prove only — coerced in autoprove) |

**On rollback:** restore snapshotted files to pre-deep state, mark sorry as stuck with reason `"deep: <trigger> — <detail>"`. If rollback itself fails (e.g., conflict), stop the current cycle immediately, mark sorry as stuck with `"deep: rollback failed"`, and skip checkpoint for this cycle. Stuck handoff must include the abort reason.

## Scope Fence

`--deep-scope` controls which files deep may touch:

| `--deep-scope` | Behavior |
|---|---|
| `target` (default) | Only the file containing the target sorry |
| `cross-file` | Multi-file refactoring, helper extraction |

If deep edits exceed `--deep-max-files` or `--deep-max-lines`, the engine triggers immediate rollback and marks stuck with reason `"deep: scope exceeded — N files / M lines"`.

## Regression Gate

When `--deep-regression-gate=strict` (default): after each deep phase, the engine compares diagnostics against the pre-deep baseline.

**File set (identical for baseline and comparison):** the target file when `--deep-scope=target`; all files declared in the deep plan when `--deep-scope=cross-file`. This is the same set used for the path-scoped snapshot.

**Baseline:** `lean_diagnostic_messages` output for all files in the set, captured immediately before the first deep edit.

**Comparison:** re-run `lean_diagnostic_messages` on the same file set and compare:

1. Sorry count increased → rollback + stuck (`"deep: regression — sorry count +N"`)
2. New diagnostic errors appeared (error not present in baseline) → rollback + stuck (`"deep: regression — new errors"`)
3. New blocker signatures introduced (see [stuck-and-repair](stuck-and-repair.md)) → rollback + stuck (`"deep: regression — new blockers"`)

When `off`: regressions are logged but do not trigger rollback. Only available in prove (coerced to `strict` in autoprove).

## Safety Coercions (autoprove)

| Flag | Coerced from | Coerced to | Warning |
|---|---|---|---|
| `--deep-rollback` | `never` | `on-regression` | "deep-rollback=never disables safety rollback. Using on-regression for unattended operation." |
| `--deep-regression-gate` | `off` | `strict` | "deep-regression-gate=off allows regressions. Using strict for unattended operation." |
