---
name: lean4-codeprover
description: "Lean 4 code generation & verification with a co-derivation discipline — code and proof sketch are derived together from a single shared reasoning trace. Use when editing .lean files with sorry placeholders."
---

# lean4-codeprover — Lean 4 Code & Proof Co-Derivation

Use this skill when editing Lean 4 files that contain specifications with sorry placeholders.

**Central discipline**: co-derive code and proof from one shared informal plan. The plan's recursion scheme dictates the code's case split *and* the proof's induction shape. Forward flow (Phases 4 → 5) only fills tactic details; the plan itself is revised only under *When stuck*. Structural drift between code and proof is the failure mode this skill exists to prevent.

## Hard constraints (non-negotiable)

- **Never modify specifications.** Preconditions, postconditions, and theorem statements are read-only.
- **Respect Instructions.** A `/-! Instruction: -/` docstring (immediately after the import block) or `instruction.md` in the task directory is a hard constraint — do not take spec-satisfying shortcuts that violate the stated algorithm or complexity.
- **Standard axioms only.** `propext`, `Classical.choice`, `Quot.sound`, `Lean.ofReduceBool`, `Lean.trustCompiler`. Nothing else.
- **Never stop voluntarily.** Only the harness terminates you. While you can still take actions, keep working.

## Commands

| Command | Phases | Scope |
|---------|--------|-------|
| `/lean4-codeprover code <file>` | 1 → 2 → 3 → 4 → 6 | Fill code sorries; emit proof sketch only |
| `/lean4-codeprover proof <file>` | 1 → (2) → (3) → 5 → 6 | Fill proof sorries only; parenthesised phases run only if no plan file exists — reverse-engineer one from the code first |
| `/lean4-codeprover auto <file>` | 1 → 2 → 3 → 4 → 5 → 6 | Full co-derivation |

Phase 6 always runs last.

## Workflow

Each phase has a **produces** (artifact) and an **exit check** (must pass before advancing). Don't leave a phase until its exit check holds.

| # | Phase | Produces | Exit check |
|---|-------|----------|------------|
| 1 | **Understand** | Classified sorry inventory (code vs proof), restated spec + instruction in your head. | `${LEAN4_PYTHON_BIN:-python3} "$LEAN4_SCRIPTS/sorry_analyzer.py" <file> --format=summary` lists every sorry; Instruction source (docstring or `instruction.md`) located or confirmed absent. |
| 2 | **Co-derive plan** | `<file>.plan.md` — prose plan whose required sections are defined in [plan-schema](references/plan-schema.md). Read it before emitting the plan. | All required sections present; a locked-algorithm instruction is restated verbatim in `## Restated contract`. |
| 3 | **Plan review** | Reviewer verdict on (a) complexity meets instruction, (b) invariant base + step + termination implies postcondition. | Verdict obtained from a **fresh subagent** given the plan path and both questions — self-review defeats the gate. On fail, revise the named plan field and re-review; do not advance with a failing verdict. |
| 4 | **Emit code sketch + proof sketch** | **Sketches only — no proof bodies.** Formal `def` bodies from the recursion scheme, but leaving `decreasing_by sorry` (or omitting `decreasing_by` entirely if Lean can auto-derive). Plus proof-sketch stubs (main theorem + auxiliary lemmas) whose bodies are `sorry`. Split into two parallel subagents (one code, one sketch) only when the work is genuinely independent — typically ≥ 2 auxiliary lemmas or ≥ 50 lines of new code. For a single recursive def with one spec lemma, write both in one edit. | `lean_diagnostic_messages(file)`: no errors; expected `sorry` warnings only (on tactic bodies and, if written, `decreasing_by`); code signatures elaborate so the sketch parses. |
| 5 | **Fill tactic details** | All tactic-level sorries closed — this includes proof sorries **and** `decreasing_by sorry` in recursive defs (they are tactic blocks even though they sit inside `def`). Dispatch one subagent per sorry (or per tightly-coupled group) in parallel when practical. | `lean_diagnostic_messages(file)`: no errors and no in-scope sorries remaining. |
| 6 | **Quality gate (final)** | Go/no-go on delivery. | All four must hold — see *Phase 6 commands* below. |

You choose tactics, search tools, editing granularity, and commit cadence within each phase. This skill prescribes *what* each phase produces and *when* it is allowed to exit, not *how* you get there.

## Phase 6 commands

All four checks must hold. Use `--report-only` for non-blocking output while iterating.

1. **Sorry scan** — zero in-scope sorries:
   ```bash
   ${LEAN4_PYTHON_BIN:-python3} "$LEAN4_SCRIPTS/sorry_analyzer.py" <file> --format=summary --report-only
   ```
2. **Compile check** — `lean_diagnostic_messages(<file>)` reports no errors.
3. **Axiom check** — only standard axioms:
   ```bash
   bash "$LEAN4_SCRIPTS/check_axioms_inline.sh" <file> --report-only
   ```
4. **Instruction compliance** — if a `/-! Instruction: -/` docstring or `instruction.md` is present, spawn a subagent: *"Check whether the `@start code … @end code` region of `<file>` satisfies the Instruction's complexity/algorithm requirement. Return pass/fail with a one-line reason."* On fail, revert with `git checkout -- <file>`, revise `## Algorithmic idea` in the plan, then re-enter from Phase 3. Do not rebut the verdict.

## LSP tools (preferred)

Sub-second feedback via Lean LSP MCP. Prefer these over scripts.

```
lean_goal(file, line)                           # See exact goal
lean_hover_info(file, line, col)                # Understand types
lean_local_search("keyword")                    # Fast local + mathlib (unlimited)
lean_leanfinder("goal or query")                # Semantic search (10/30s)
lean_leansearch("natural language")             # Natural language (3/30s)
lean_loogle("?a → ?b → _")                      # Type-pattern search
lean_hammer_premise(file, line, col)            # Premise suggestions (3/30s)
lean_state_search(file, line, col)              # Goal-conditioned search (3/30s)
lean_multi_attempt(file, line, snippets=[...])  # Test multiple tactics
lean_diagnostic_messages(file)                  # Check errors
```

## Scripts (fallback)

Invoke Python scripts via `${LEAN4_PYTHON_BIN:-python3}` and shell scripts via `bash`, with `$LEAN4_SCRIPTS` pointing at the scripts directory. Add `--report-only` to `sorry_analyzer.py` / `check_axioms_inline.sh` for non-blocking output.

| Script | Purpose |
|--------|---------|
| `sorry_analyzer.py` | Find sorries with context (formats: `text` / `json` / `summary`) |
| `check_axioms_inline.sh` | Check for non-standard axioms |
| `smart_search.sh` | Multi-source mathlib search |
| `search_mathlib.sh` | Search mathlib by name pattern |
| `solver_cascade.py` | Automated tactic cascade fallback |
| `parse_lean_errors.py` | Structure compiler errors |

## When stuck

Revise the plan upward through layers: **tactic → invariant → recursion scheme → contract**. Most failures resolve at the invariant layer. Contract edits are rare and usually mean you misread the spec in Phase 1.

## References (on-demand)

| Need | Read |
|------|------|
| Design philosophy | [co-derivation](references/co-derivation.md), [invariant-first](references/invariant-first.md) |
| Plan file format | [plan-schema](references/plan-schema.md) |
| Subagent dispatch | [agent-workflows](references/agent-workflows.md) |
| Filling sorries / tactic patterns | [sorry-filling](references/sorry-filling.md), [tactic-patterns](references/tactic-patterns.md) |
| Searching for lemmas | [lemma-retrieval](references/lemma-retrieval.md), [mathlib-guide](references/mathlib-guide.md) |
| Stuck or repair | [stuck-and-repair](references/stuck-and-repair.md), [code-verification](references/code-verification.md) |
| Compile errors | [compilation-errors](references/compilation-errors.md), [compiler-guided-repair](references/compiler-guided-repair.md) |
| Slow proofs | [performance-optimization](references/performance-optimization.md) |
| LSP tools | [lean-lsp-server](references/lean-lsp-server.md) |
| Scripts | [scripts/README.md](scripts/README.md) |

