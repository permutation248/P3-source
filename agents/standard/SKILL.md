---
name: lean4-codeprover
description: "Lean 4 code generation & verification (standard variant — proves only). Use when editing .lean files with sorry placeholders, type mismatch / failed-to-synthesize errors, axiom warnings, lake build errors, or doing code verification (proving postconditions of implementations)."
---

# lean4-codeprover — Lean 4 Code Generation & Verification (Standard)

Use this skill when editing Lean 4 files that contain specifications (preconditions, postconditions) with sorry placeholders. It generates implementations, proofs, or both.

This is the **standard** variant: it only **proves** statements. Falsification via `negate_goal` and the `negation` axiom are **not allowed**.

## Core Principles

- **Never modify specifications.** Preconditions, postconditions, and theorem statements are read-only. Never change them.
- **Respect Instructions.** A `/-! Instruction: -/` docstring (placed right after the import block) or `instruction.md` in the task directory is a **hard constraint** — do not take spec-satisfying shortcuts that violate the locked algorithm or forbidden-library list.
- **Computable but Prove-friendly code.** Prefer simple, structurally recursive implementations over complex imperative ones. Use List/Array operations with known Mathlib lemmas (e.g., `List.foldl`, `Array.foldl`) rather than manual index loops.
- **Modular proofs.** Extract independent facts as `private lemma` before the main theorem.
- **Search before prove.** Many facts already exist in mathlib (100K+ theorems). Search exhaustively before writing tactics.
- **Build incrementally.** Lean's type checker is your test suite — if it compiles with no sorries and standard axioms only, the proof is sound.
- **Fully autonomous.** No user confirmation required at any step.
- **Never stop voluntarily.** You do NOT decide when to stop. The harness terminates you when budget runs out. If you can still take actions, you have budget remaining — keep working. Writing a "failure summary" while you can still act is forbidden.
- **No negation.** Never use `negate_goal`, the `negation` axiom, or `import Tacs.Negate`. If a statement appears false, try harder to prove it or report it as stuck — do not attempt to disprove it.

## Commands

| Command | Purpose |
|---------|---------|
| `/lean4-codeprover:code <file>` | Generate implementation only — fill code sorries |
| `/lean4-codeprover:proof <file>` | Generate proof only — fill proof sorries (autoprove) |
| `/lean4-codeprover:auto <file>` | Generate code + proof with auto-retry on failure |

## Sorry Classification

- **Code sorry**: sorry in a `def` body, including `decreasing_by sorry` and `termination_by sorry`. Fill top-to-bottom to respect dependencies.
- **Proof sorry**: sorry in a `theorem`/`lemma := by` block.
- **Detection**: run `sorry_analyzer.py --format=summary` to locate and classify all sorries.

## Code Mode (`/lean4-codeprover:code <file>`)

Fill code sorries only. Skip proof sorries.

1. **Read & classify** — Run `sorry_analyzer.py`, locate code sorries.
2. **Analyze spec** — Read preconditions, postconditions, function signatures. Check for a `/-! Instruction: -/` docstring (placed right after the import block) or `instruction.md` in the task directory — if present, its algorithm choice overrides any spec-satisfying shortcut (e.g. don't reduce a mandated binary search to `Array.findIdx`). Determine algorithm requirements.
3. **Generate implementation** — Fill each code sorry top-to-bottom. May add auxiliary definitions.
4. **Compile check** — `lean_diagnostic_messages(file)` after each edit. Ignore "declaration uses 'sorry'" on theorems.
5. **Fix or retry** — Compile error → fix. Still failing → try a different implementation approach.

## Proof Mode (`/lean4-codeprover:proof <file>`)

Fill proof sorries only. Skip code sorries.

1. **Plan** — Check for a `/-! Instruction: -/` docstring or `instruction.md`; if present, follow its proof strategy / helper-lemma hints before searching for Mathlib alternatives. Discover state via LSP (`lean_goal`), identify sorries. Search for needed Mathlib/stdlib facts (see [lemma-retrieval](references/lemma-retrieval.md)). Trivial goals → mark for direct closing. Complex goals → decompose into modular `private lemma` structure.
2. **Work** — Fill sorries using search + tactics. For each sorry: generate 2-3 candidates → test with `lean_multi_attempt` → apply shortest passing candidate. Compile after each edit via `lean_diagnostic_messages`. See [sorry-filling](references/sorry-filling.md) and [tactic-patterns](references/tactic-patterns.md).
3. **Checkpoint** — Stage successful work, commit if non-empty diff. See [checkpoint](references/checkpoint.md).
4. **Review** — At configured intervals, run quality check matching current scope.
5. **Replan** — Enter planner mode, produce/update action plan based on review findings. If a sorry is stuck (2-3 failed attempts), adjust the proof architecture — see [stuck-and-repair](references/stuck-and-repair.md).
6. **Continue** — Stuck means replan and try a different approach, **not stop**. The only way your session ends is: (a) all sorries filled, or (b) the harness terminates you when budget runs out. You cannot decide to stop. If you are about to write a final summary while sorries remain, that is the wrong action — replan instead.

## Auto Mode (`/lean4-codeprover:auto <file>`)

Code Mode → Proof Mode pipeline. If proof gets stuck, go back to Code Mode with a different implementation strategy. Repeat until success or the harness terminates you. Never write a summary and stop — if you can still take actions, try another approach.

### Phase 1: Read Spec + Instruction

1. Read preconditions, postconditions, and function signatures.
2. Check for an Instruction block — either `instruction.md` in the task directory or a `/-! Instruction: ... -/` docstring placed right after the import block. If present, treat its algorithm / library guidance as a **hard constraint** (locked algorithm, forbidden shortcuts, required helper lemmas).
3. If no Instruction exists, proceed by spec alone.

### Phase 2: Generate Code

Run Code Mode workflow.

### Phase 3: Generate Proof

Run Proof Mode workflow.

### Phase 4: Retry (on proof failure)

1. **Summarize failure** — Record what strategy was used and why proof failed (e.g., "recursive DP — stuck on termination proof").
2. **Rollback** — `git checkout -- <file>` to restore initial state.
3. **Choose new strategy** — Pick a different approach based on failure summary. Return to Phase 2.

### Failure State

You never trigger this yourself. The harness terminates you when budget runs out — that is the only way a session ends with sorries remaining. Until then, keep trying: rollback, pick a new algorithm, return to Phase 2. If you find yourself about to write a summary while sorries remain, that is wrong — go back to Phase 4 instead.

## Automation Tactics

Unfold definitions → try closers (`simp_all` → `grind` → `omega` → `aesop` → `decide` → `native_decide`) → structural induction → case analysis → arithmetic → last resort search (`exact?` → `apply?` → `rw?`). See [sorry-filling](references/sorry-filling.md) and [tactic-patterns](references/tactic-patterns.md).

## Compilation Error Fix

Fix errors directly during Work (type mismatch, missing import, failed to synthesize). If errors persist after 2 attempts → escalate to Repair Mode. See [compilation-errors](references/compilation-errors.md) and [stuck-and-repair](references/stuck-and-repair.md).

## Stuck

A sorry is stuck after 2-3 failed attempts with no new approach, or LSP search returns empty twice. When stuck → read [code-verification](references/code-verification.md) for advanced decomposition strategies → force review → replan. See [stuck-and-repair](references/stuck-and-repair.md).

## LSP Tools (Preferred)

Sub-second feedback via Lean LSP MCP. Always use before falling back to scripts.

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

## Core Primitives (Scripts)

Fallback when LSP is unavailable. Invoked via `${LEAN4_PYTHON_BIN:-python3} "$LEAN4_SCRIPTS/script.py"` or `bash "$LEAN4_SCRIPTS/script.sh"`.

| Script | Purpose |
|--------|---------|
| `sorry_analyzer.py` | Find sorries with context (text/json/summary) |
| `check_axioms_inline.sh` | Check for non-standard axioms |
| `smart_search.sh` | Multi-source mathlib search |
| `search_mathlib.sh` | Search mathlib by name pattern |
| `solver_cascade.py` | Automated tactic cascade |
| `parse_lean_errors.py` | Structure compiler errors |

Add `--report-only` to `sorry_analyzer.py`, `check_axioms_inline.sh` for non-blocking output.

## Quality Gate

A file is complete when all four checks pass.

### Mandatory final checks

1. **Sorry scan** — run `sorry_analyzer.py` and verify zero sorries in scope:
   ```
   ${LEAN4_PYTHON_BIN:-python3} "$LEAN4_SCRIPTS/sorry_analyzer.py" <file> --format=summary --report-only
   ```
   - `/lean4-codeprover:code`: zero code sorries (proof sorries are OK)
   - `/lean4-codeprover:proof`: zero proof sorries (code sorries are OK)
   - `/lean4-codeprover:auto`: zero sorries of any kind — including `decreasing_by sorry`, `termination_by sorry`, and auxiliary `lemma ... := sorry`
   - If any sorry remains in scope, **you are not done** — go back and fix it.

2. **Compile check** — `lean_diagnostic_messages(file)` reports no errors (warnings about sorry in out-of-scope declarations are OK for code/proof mode).

3. **Axiom check** — only standard axioms allowed:
   ```
   bash "$LEAN4_SCRIPTS/check_axioms_inline.sh" <file> --report-only
   ```
   Allowed: `propext`, `Classical.choice`, `Quot.sound`, `Lean.ofReduceBool`, `Lean.trustCompiler`.
   **NOT allowed: `negation`.**

4. **Instruction compliance** — if a `/-! Instruction: -/` docstring or `instruction.md` is present, spawn a subagent with the prompt: *"Check whether the `@start code ... @end code` region of `<file>` satisfies the Instruction's complexity/algorithm requirement. Return pass/fail with a one-line reason."* On fail: `git checkout -- <file>` and return to the Code phase with a different algorithm. Do not rebut the verdict.

## Skill-Only Behavior (no command invoked)

When editing `.lean` files without a command: **one bounded pass** — fix the immediate issue, no looping, then suggest `/lean4-codeprover:code`, `/lean4-codeprover:proof`, or `/lean4-codeprover:auto`.

## References

Read **on demand** based on what you're doing:

| When | Read |
|------|------|
| **Stuck on code verification** | [code-verification](references/code-verification.md) |
| **Searching lemmas** | [lemma-retrieval](references/lemma-retrieval.md) |
| **Running proof mode** | [cycle-engine](references/cycle-engine.md) |
| **Validation** | [build-target-policy](references/build-target-policy.md) |
| **Checkpoint phase** | [checkpoint](references/checkpoint.md) |
| **Stuck or repair needed** | [stuck-and-repair](references/stuck-and-repair.md) |
| **Filling sorries** | [sorry-filling](references/sorry-filling.md) |
| **Build error** | [compilation-errors](references/compilation-errors.md) |
| **Persistent build errors** | [compiler-guided-repair](references/compiler-guided-repair.md) |
| **Searching mathlib** | [mathlib-guide](references/mathlib-guide.md) |
| **Need a specific tactic** | [tactics-reference](references/tactics-reference.md) |
| **Choosing tactic by goal type** | [tactic-patterns](references/tactic-patterns.md) |
| **`simp` not closing** | [grind-tactic](references/grind-tactic.md) |
| **Writing `simp` lemmas** | [simp-hygiene](references/simp-hygiene.md) |
| **Calculation chain proof** | [calc-patterns](references/calc-patterns.md) |
| **Starting a proof from scratch** | [proof-templates](references/proof-templates.md) |
| **Restructuring a proof** | [proof-refactoring](references/proof-refactoring.md) |
| **Slow build or proof** | [performance-optimization](references/performance-optimization.md) |
| **LSP tools not working** | [lean-lsp-server](references/lean-lsp-server.md) |
| **Delegating sub-tasks** | [agent-workflows](references/agent-workflows.md) |
| **Scripts & fallback tools** | [scripts/README.md](scripts/README.md) |
