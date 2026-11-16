# Stuck Detection and Repair

## Stuck Definition

A sorry or repair target is **stuck** when any of these hold:

1. Same sorry failed 2-3 times with no new approach
2. Same build error repeats after 2 repair attempts
3. No sorry count decrease for 10+ minutes
4. LSP search returns empty twice for same goal

**Same blocker** is computed as `(file, line, primary_error_code_or_text_hash)`. Two consecutive iterations producing the same blocker signature = same blocker.

**When stuck detected:**

| Step | Action |
|------|--------|
| 1. Review | `/lean4:review <file> --scope=sorry --line=N --mode=stuck` |
| 2. Replan | Enter planner mode, produce fresh plan (3-6 steps) |
| 3. Approval | Auto-approve, next cycle executes plan |

**Stuck handoff evidence:** When declaring a sorry stuck, include:
- LSP queries attempted (tool name + query text)
- Top candidate lemmas returned (if any)
- `lean_multi_attempt` outcomes (snippets tested, pass/fail for each)

**Important:** Stuck-triggered replan is mandatory even if `--planning=off`. It is a safety mechanism, not optional planning.

## When Stuck on a Proof

When stuck, try these strategies in order:

1. **Decompose** — Break the goal into smaller sub-goals with `have` statements
2. **Generalize** — Try proving a stronger intermediate lemma that implies the goal
3. **Change approach** — Switch between induction, case analysis, and direct proof
4. **Search harder** — Use `lean_leanfinder`, `lean_leansearch`, `lean_loogle` with different queries
5. **Restructure code** — If the implementation makes the proof hard, rollback and try a different implementation

**CRITICAL: Never modify theorem statements or any definitions they depend on during `autoprove`.** The task is to prove the given statement exactly as written. Do NOT "fix" or "refine" the statement to make it provable.

## Repair Mode

Compiler-guided repair is an **escalation-only** workflow — not the default response to a first failure. Invoke only when compiler errors are the active blocker and LSP-first tactics cannot resolve them.

**Trigger conditions** (any one sufficient):
- Same blocker signature repeats 2 consecutive iterations
- Same build error repeats after 2 repair attempts
- 3 or more distinct compiler errors active in scope simultaneously

**Direct-fix-first rule:** For straightforward single errors (missing import, obvious coercion, local instance, simple typo), apply the fix directly. Escalate to the repair agent only if the direct fix fails or the error recurs.

**Budgets:**

| Parameter | prove | autoprove |
|-----------|-------|-----------|
| Max repair attempts per error signature per cycle | 2 | 2 |
| Max total repair attempts per cycle | 6 | 8 |

**Improvement definition:** Error count in scope decreases OR the current blocker signature disappears. A repair attempt that changes errors without reducing count is neutral (counts toward budget but does not reset it).

**No-improvement rule:** If 2 consecutive repair attempts on the same signature produce no improvement → target is **stuck**. Force review + replan (see [Stuck Definition](#stuck-definition)).

| Behavior | Action |
|----------|--------|
| Repair prompts | Autonomous: auto-select next strategy |
| On stuck after repair | Auto-replan, next cycle executes |

**Error quick-reference:**

| Error | Typical Fix |
|-------|-------------|
| `type mismatch` | Add coercion, `convert`, fix argument |
| `unknown identifier` | Search mathlib, add import |
| `failed to synthesize` | Add `haveI`/`letI` |
| `timeout` | Narrow `simp`, add explicit types |

For detailed fixes, see [compilation-errors.md](compilation-errors.md).
