# Compiler-Guided Proof Repair - Quick Reference

## Table of Contents

- [Philosophy](#philosophy)
- [Quick Start](#quick-start)
- [API Discovery Workflow](#api-discovery-workflow)
- [Core Workflow](#core-workflow)
- [Repair Strategies by Error Type](#repair-strategies-by-error-type)
- [Common Pitfalls](#common-pitfalls)
- [Error Pattern Recognition](#error-pattern-recognition)
- [Key Success Factors](#key-success-factors)
- [Expected Outcomes](#expected-outcomes)
- [Tools Reference](#tools-reference)
- [Common Patterns](#common-patterns)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)

---

**Core insight:** Use Lean's compiler feedback to drive iterative repair with small, budgeted LLM calls instead of blind best-of-N sampling.

**Key principle:** Generate → Compile → Diagnose → Fix → Verify (tight loop, K=1)

**Inspired by:** APOLLO (https://arxiv.org/abs/2505.05758)

---

## Philosophy

**Traditional Approach (Blind Sampling):**
```
Generate 100 proof attempts → Test all → Pick best
❌ Wasteful: Most attempts fail identically
❌ No learning: Same error repeated many times
❌ Expensive: Large model × high K
```

**Compiler-Guided Approach:**
```
Generate attempt → Lean error → Route to specific fix → Retry (max 24 attempts)
✅ Efficient: Error-driven action selection
✅ Adaptive: Different fix strategies per error type
✅ Economical: Small K (often K=1), fast model first, escalate only when needed
✅ Learning: Log attempts, avoid repeating dead ends
```

**Key wins:**
- **Low sampling budgets** (K=1 or K=3) with compiler guidance beat high-K blind sampling
- **Multi-stage approach** (fast model → escalate to strong model) optimizes cost/quality
- **Solver cascade** (try automation before resampling) handles many cases mechanically
- **Early stopping** (bail after 3 identical errors) prevents runaway costs

---

## Quick Start

Repair is integrated into `/lean4:prove` and `/lean4:autoprove`:

```
/lean4:prove --repair-only         # Fix build errors only (guided)
/lean4:prove                       # Full workflow (includes repair when needed)
```

Repair is **escalation-only**: it triggers when compiler errors are the active blocker and LSP-first tactics cannot resolve them (same blocker 2x, same build error 2x, or 3+ errors). Not the default on first failure. See [stuck-and-repair.md](stuck-and-repair.md#repair-mode) for the full invocation policy.

---

## API Discovery Workflow

**Core principle:** Search before guessing. LeanFinder + LSP tools prevent 80% of API-related errors.

### The "LeanFinder First" Rule

Before writing ANY Lean API call:

1. **Search with natural language** (`lean_leanfinder`):
   ```python
   lean_leanfinder(query="list filter by predicate")
   ```

2. **Confirm locally** (`lean_local_search`):
   ```python
   lean_local_search("List.filter", limit=5)
   ```

3. **Check signature** (`lean_hover_info`):
   ```python
   lean_hover_info(file, line, col)
   ```

4. **THEN write the code**

**Why this matters:**
- API names may differ from what you expect
- Type signatures have subtle requirements
- Field vs function matters (`x.foo` vs `Foo.bar x`)

---

## Core Workflow

### 1. Compile → Extract Error
```bash
lake env lean FILE.lean 2> errors.txt   # run from project root
python3 $LEAN4_SCRIPTS/parse_lean_errors.py errors.txt > context.json
```

Extracts: error type, location, goal state, local context, code snippet

### 2. Try Solver Cascade (many simple cases, free!)
```bash
python3 $LEAN4_SCRIPTS/solver_cascade.py context.json FILE.lean
```

Tries in order: `rfl → simp → ring → linarith → nlinarith → omega → exact? → apply? → grind → aesop`

If any succeeds → apply diff, recompile

### 3. Agent Repair (if cascade fails)

**Stage 1 (Haiku, fast):** First 6 attempts
- Model: `haiku`, thinking OFF
- Temperature: 0.2, K=1
- Budget: ~2s per attempt
- Strategy: Quick, obvious fixes

**Stage 2 (Opus, precise):** After Stage 1 exhausted or complex errors
- Model: `opus`, thinking ON
- Temperature: 0.1, K=1
- Budget: ~10s per attempt
- Strategy: Strategic thinking, global context

**Escalation triggers:**
- Same error 3 times in Stage 1
- Error types: `synth_instance`, `recursion_depth`, `timeout`
- Stage 1 attempts exhausted

### 4. Apply Patch → Recompile

```bash
git apply patch.diff
lake env lean FILE.lean   # run from project root
```

If success → done! If fail → next iteration (max 24 attempts)

**Cycle-level budget:** The 24-attempt internal limit is the agent ceiling. Within prove/autoprove, tighter cycle budgets apply: max 2 per error signature, max 6 (prove) or 8 (autoprove) per cycle. No improvement after 2 consecutive attempts on same signature → stuck.

---

## Repair Strategies by Error Type

### type_mismatch

**Strategies:**
1. `convert _ using N` (N = unification depth 1-3)
2. Explicit type annotation: `(expr : TargetType)`
3. `refine` with placeholders
4. `rw` to align types
5. Intermediate `have` with correct type

**Example:**
```diff
-  exact h
+  convert continuous_of_measurable h using 2
+  simp
```

### unsolved_goals

**Strategies:**
1. Try automation: `simp?`, `apply?`, `exact?`, `grind`, `aesop`
2. By goal shape:
   - Equality → `rfl`, `ring`, `linarith`
   - ∀ → `intro`
   - ∃ → `use` or `refine ⟨_, _⟩`
   - → → `intro` then conclusion
3. Search mathlib for lemma
4. Break down: `constructor`, `cases`, `induction`

**Example:**
```diff
-  sorry
+  intro x
+  apply lemma_from_mathlib
+  exact h
```

### unknown_ident

**Strategies:**
1. **Use LeanFinder FIRST:** `lean_leanfinder(query="natural language description of what you want")`
2. Check for ASCII vs Unicode naming (ℒp → MemLp, not Memℒp)
3. Search locally: `lean_local_search("ident", limit=10)`
4. Add namespace: `open Foo` or `open scoped Bar`
5. Add import: `import Mathlib.Foo.Bar`
6. Check for typo

**Example:**
```diff
+import Mathlib.Topology.Instances.Real
 ...
-  continuous_real
+  Real.continuous
```

**Why LeanFinder first:**
- Mathematical notation ≠ API names (use natural language instead)
- Finds correct spelling and namespace immediately
- Much faster than trial-and-error with imports

### synth_implicit / synth_instance

**Strategies:**
1. Provide instance: `haveI : Instance := ...`
2. Local instance: `letI : Instance := ...`
3. Open scope: `open scoped Topology`
4. Reorder arguments (instances before regular params)

**Example:**
```diff
+  haveI : MeasurableSpace β := inferInstance
   apply theorem_needing_instance
```

### sorry_present

**Strategies:**
1. Search mathlib (many already exist)
2. Automated solvers (cascade handles this)
3. Compositional proof from mathlib lemmas
4. Break into subgoals

### timeout / recursion_depth

**Strategies:**
1. Narrow `simp`: `simp only [lem1, lem2]` not `simp [*]`
2. Clear unused: `clear h1 h2`
3. Replace `decide` with `native_decide`
4. Provide instances explicitly
5. Revert then re-intro in better order

**Example:**
```diff
-  simp [*]
+  simp only [foo_lemma, bar_lemma]
```

---

## Common Pitfalls

### Pitfall 1: Field Access vs Function Call

**The trap:** `x.foo` and `Foo.bar x` are different in Lean.

**❌ What fails:**
```lean
have := hf.someMethod  -- ❌ Invalid field 'someMethod'
```

**✅ What works:**
```lean
have := SomeType.someMethod hf arg  -- ✓ Function call, not field access
```

**How to catch this:**
1. Error message: "Invalid field 'X'" → It's a function, not a field
2. Use `lean_hover_info` to check if it's a field or function
3. Use `lean_local_search` to find the correct namespace

**Rule of thumb:**
- Fields: Data stored in a structure (e.g., `point.x`, `arr.size`)
- Functions: Operations on types (e.g., `List.filter`, `Array.push`)

### Pitfall 2: Symmetry Direction for Equivalences

**The trap:** Many relations have directionality. Lemmas expect specific order.

**❌ What fails:**
```lean
-- h : a = b, but lemma expects b = a
exact some_lemma h  -- ❌ Type mismatch
```

**✅ What works:**
```lean
exact some_lemma h.symm  -- ✓ Reverse with .symm
```

**General pattern:** Use `.symm` for:
- `=` (equality)
- `↔` (iff)
- `≈` (equivalence)
- Any symmetric relation

---

## Error Pattern Recognition

**Quick diagnosis guide:** Match error message to likely cause and fix strategy.

### "Invalid field 'X'"
**Likely cause:** Using dot notation for a function, not a field.

**Fix strategy:**
1. Use `lean_hover_info` to check if it's a function
2. Change `x.foo` to `Foo.bar x`
3. Use `lean_local_search` to find correct namespace

### "Unknown identifier 'X'"
**Likely cause:** Missing import, wrong namespace, or typo.

**Fix strategy:**
1. **Try LeanFinder FIRST:** `lean_leanfinder(query="natural language description")`
2. Search locally: `lean_local_search("X")`
3. Add import if found externally
4. Check for typo

### "Failed to synthesize instance"
**Likely cause:** Missing type class instance in context.

**Fix strategy:**
1. Add instance: `haveI : Instance := inferInstance`
2. Or: `letI : Instance := ...`
3. Check import: may need additional imports
4. Reorder parameters (instances before regular params)

---

## Key Success Factors

### Low Sampling Budgets
- K=1 per attempt (not K=100)
- Strong compiler feedback guides next attempt
- Efficient iteration to success

### Solver-First Strategy
- Many errors solved by automation
- Zero LLM cost for simple cases
- Only escalate to agent when needed

### Multi-Stage Escalation
- Fast model (Haiku) for most cases
- Strong model (Sonnet) only when needed
- Cost-effective repair process

### Early Stopping
- Bail after 3 identical errors
- Prevents runaway costs
- Max 24 attempts total

### Structured Logging
- Every attempt logged to `.repair/attempts.ndjson`
- Track: error hash, stage, solver success, elapsed time
- Learn successful patterns over time

---

## Expected Outcomes

Success improves over time as structured logging enables learning from repair attempts.

**Efficiency benefits:**
- Solver cascade handles many simple cases mechanically (zero LLM cost)
- Multi-stage escalation: fast model first, strong model only when needed
- Early stopping prevents runaway attempts on intractable errors
- Low sampling budget (K=1) with strong compiler feedback

**Cost optimization:**
- Solver cascade: Free (automated tactics)
- Stage 1 (Haiku): Low cost, handles most common cases
- Stage 2 (Sonnet): Higher cost, reserved for complex cases
- Much more cost-effective than blind best-of-N sampling

---

## Tools Reference

**Error parsing:**
```bash
python3 $LEAN4_SCRIPTS/parse_lean_errors.py errors.txt
```

**Solver cascade:**
```bash
python3 $LEAN4_SCRIPTS/solver_cascade.py context.json FILE.lean
```

**Via prove/autoprove:**
```
/lean4:prove --repair-only         # Repair mode (guided)
/lean4:prove                       # Full workflow with repair
```

**Search (LSP preferred):**
```
lean_leansearch("description")     # Natural language
lean_loogle("type pattern")        # Type-based
```

**Fallback scripts:**
```bash
bash $LEAN4_SCRIPTS/smart_search.sh "query" --source=all
```

---

## Common Patterns

### Pattern 1: Type Mismatch with convert

**Before:**
```lean
theorem foo (h : SomeProp f) : RelatedProp f := by
  exact h  -- ❌ type mismatch
```

**After:**
```lean
theorem foo (h : SomeProp f) : RelatedProp f := by
  convert related_of_some h using 2
  simp
```

### Pattern 2: Missing Instance with haveI

**Before:**
```lean
theorem bar : Property := by
  apply lemma  -- ❌ failed to synthesize instance
```

**After:**
```lean
theorem bar : Property := by
  haveI : RequiredClass α := inferInstance
  apply lemma
```

### Pattern 3: Unknown Identifier → Import

**Before:**
```lean
theorem baz : Result := by
  exact Continuous.comp  -- ❌ unknown identifier
```

**After:**
```lean
import Mathlib.Topology.Basic

theorem baz : Result := by
  exact Continuous.comp
```

### Pattern 4: Unsolved Goal → Automation

**Before:**
```lean
theorem qux : a + b = b + a := by
  sorry  -- ❌
```

**After:**
```lean
theorem qux : a + b = b + a := by
  ring  -- ✓ (found by solver cascade)
```

---

## Best Practices

### 1. Build After Every Fix (Most Important!)

**Rule:** Build after EVERY 1-2 fixes, not after "a batch of fixes."

**Why:**
- One error at a time is faster than five errors at once
- Immediate feedback prevents cascading errors
- Errors compound—fixing one may introduce another
- Fast iteration loop beats careful batch processing

**Anti-pattern:**
```bash
# ❌ BAD: Make many changes, then build
fix error 1
fix error 2
fix error 3
lake build  # Now you have errors from all three fixes mixing together!
```

**Better pattern:**
```bash
# ✅ GOOD: Verify after each fix
# Per-edit: lean_diagnostic_messages(file) for immediate feedback
# File gate: lake env lean FILE.lean after each fix (run from project root)
# Milestone: lake build only at checkpoint
fix error 1  # → lean_diagnostic_messages(file) → lake env lean FILE.lean
fix error 2  # → lean_diagnostic_messages(file) → lake env lean FILE.lean
fix error 3  # → lean_diagnostic_messages(file) → lake env lean FILE.lean
```

**With LSP (even better):**
```python
# After each edit, immediate verification:
lean_diagnostic_messages(file_path)
lean_goal(file_path, line)
```

### 2. LeanFinder First, Always

Before writing ANY API call:
1. `lean_leanfinder(query="natural language")`
2. `lean_local_search("result")`
3. `lean_hover_info` to check signature
4. THEN write code

**Prevents:** Wrong API names, wrong type signatures, wrong argument order.

### 3. Start with Solver Cascade

Always try automated solvers before LLM. Many cases succeed with zero cost.

### 4. Search Mathlib First

Many proofs already exist. Use search tools before generating novel proofs.

### 5. Minimal Diffs

Change only 1-5 lines. Preserve existing proof structure and style.

### 6. Trust the Loop

Don't overthink individual attempts. The loop will iterate. Fast attempts beat perfect attempts.

### 7. Learn from Logs

Review `.repair/attempts.ndjson` to see what strategies worked. Build intuition over time.

---

## Troubleshooting

**Repair loop stuck on same error:**
- Check if error is truly at fault line
- Run `/lean4:prove` with "every change" review cadence to see attempts
- May need manual intervention

**Agent generates wrong fixes:**
- Fast approaches optimize for speed → may miss context
- Use `/lean4:prove` with conservative approach for better understanding
- Or fix manually and continue

**Solver cascade too aggressive:**
- Some proofs need structure, not automation
- Fix manually and continue with `/lean4:prove`

**Cost concerns:**
- Solver cascade is free (use it!)
- Stage 1 (Haiku) very low cost
- Early stopping prevents runaway costs
- Much more cost-effective than blind sampling

---

## False Statement Handling

**When repair loop fails repeatedly:**
- Consider the statement may be false
- Try explicit counterexample search on small domains
- If found, create counterexample lemma instead of continuing repair
- See prove/autoprove stuck → salvage workflow

---

*Compiler-guided repair inspired by APOLLO (https://arxiv.org/abs/2505.05758)*
*Word count: ~1100*
