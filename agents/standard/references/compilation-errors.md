# Common Compilation Errors in Lean 4

This reference provides detailed explanations and fixes for the most common compilation errors encountered in Lean 4 theorem proving.

## Quick Reference Table

| Error | Cause | Fix |
|-------|-------|-----|
| **"failed to synthesize instance"** | Missing type class | Add `haveI : MyClass α := inferInstance` |
| **"maximum recursion depth"** | Type class loop/complex search | Provide manually: `letI := instance` or increase: `set_option synthInstance.maxHeartbeats 40000` |
| **WHNF/isDefEq timeout** (500k+ heartbeats) | Complex function in polymorphic goal | **[performance-optimization.md](performance-optimization.md)** - use `@[irreducible]` wrapper |
| **"type mismatch"** | Wrong type | Use coercion `↑x`, type annotation `(x : T)`, or restructure |
| **"tactic 'exact' failed"** | Goal/term type mismatch | Use `apply` for unification or restructure: `⟨h.2, h.1⟩` |
| **"unknown identifier"** | Missing import OR unqualified name | Import module OR use fully qualified name |
| **"unexpected token/identifier"** | Section comment in proof | Replace `/-! -/` with `--` in tactic mode |
| **"no goals to be solved"** | Tactic already finished | Remove redundant tactics after `simp` |
| **"equation compiler failed"** | Can't prove termination | Add `termination_by my_rec n => n` clause |
| **"synthesized: m, inferred: inst✝"** | Instance pollution (multiple typeclasses) | Pin ambient instance with `haveI`/`letI`, use `@` for explicit instance |
| **"binder x doesn't match goal's binder y"** | Alpha/beta-equivalence issue | Use `set F := <expr> with hF`, apply to `F`, unfold with `simpa [hF]` |
| **Error at line N** | Actual error before line N | Check 5-10 lines before reported location |

### Code Verification Quick Reference

| Error | Cause | Fix |
|-------|-------|-----|
| **`Id.run do` won't unfold** | Monadic `do` blocks need special simp | `simp only [Id.run, Id.pure_eq, Id.bind_eq, ...]` (see CV-1) |
| **`getElem!` vs `getElem` mismatch** | `a[i]!` ≠ `a[i]` | Bridge with `Array.getElem!_pos` (see CV-2) |
| **Can't unfold `match #[] => ...`** | Equation lemma not generated | Define named wrapper + `congrArg` (see CV-3) |
| **`let rec` helper inaccessible** | Local function not referenceable | Lift to top-level `def` + prove equivalence (see CV-4) |
| **`subst` renames wrong variable** | Variable shadowing | Use `rw [h'] at *` instead (see CV-5) |
| **`while` loop in implementation** | Can't reason about `while` directly | Replace with fuel-based recursion (see CV-6) |
| **`Decidable` not found for `decide`** | Free variables in proposition | Use `simp`/`omega`/`induction` instead (see CV-7) |

---

## Code Verification Errors

These errors are specific to code verification tasks (proving postconditions of implementations). They are distinct from mathematical theorem proving errors.

### CV-1. `Id.run` / `forIn` Won't Unfold

**Symptom:** After `simp only [func]` or `unfold func`, the goal still contains `Id.run do ...` or `forIn ...`.

**Why:** `simp` doesn't know how to simplify monadic `do` blocks by default.

**Solution:** Use the imperative bridge simp chain (see Pattern 6 in code-verification.md):
```lean
simp only [Id.run, Id.pure_eq, Id.bind_eq, Id.map_eq, bind_pure_comp,
           List.forIn_yield_eq_foldl]
```

**If `Id.pure_eq` is deprecated:**
```lean
set_option linter.deprecated false in
private lemma impl_eq_foldl ... := by
  simp only [Id.run, Id.pure_eq, Id.bind_eq, Id.map_eq, ...]
```

### CV-2. `getElem!` vs `getElem` Type Mismatch

**Symptom:**
```
type mismatch: has type @getElem! ... but expected @getElem ...
```

**Why:** `a[i]!` (with `!`) returns a value using `Inhabited` default on out-of-bounds, while `a[i]` (without `!`) requires an in-bounds proof `i < a.size`.

**Solution:** Bridge with `Array.getElem!_pos`:
```lean
have h_bound : i < a.size := by omega
rw [Array.getElem!_pos a i h_bound]
-- Now a[i]! is replaced with a[i]'h_bound
```

### CV-3. `match` Equation Generation Failure

**Symptom:** Can't unfold or `simp` a top-level `match` on an Array/structure.

**Why:** Lean sometimes fails to generate equation lemmas for complex `match` expressions, especially `match arr with | #[] => ... | _ => ...`.

**Solution:** Define a named wrapper function:
```lean
private def applyResult (dp : Array Int) : Int :=
  match dp with | #[] => 0 | _ => dp.foldl max 0

-- Bridge via congrArg
have : func args h = applyResult (computedArray args) :=
  congrArg applyResult bridge_lemma
```

### CV-4. `let rec` Inner Function Inaccessible

**Symptom:** Can't reference or unfold a `let rec` helper defined inside the implementation.

**Why:** `let rec` functions are local and may not have accessible equation lemmas.

**Solution:** Lift to a top-level `def` and prove equivalence:
```lean
def myHelper ... := ...   -- copy the let rec body

private lemma myHelper_eq : myHelper ... = func.innerHelper ... := by
  induction ... with
  | nil => rfl
  | cons _ _ ih => simp only [myHelper, func.innerHelper]; split <;> [rfl; exact ih _]

-- Optionally prove function-level equality for lambda rewriting
private lemma fn_eq : @func.innerHelper = @myHelper := by funext; exact (myHelper_eq ..).symm
```

### CV-5. `subst` Variable Shadowing

**Symptom:** After `subst h` where `h : a = b`, a variable gets renamed unexpectedly and subsequent tactics fail.

**Why:** `subst` eliminates one variable and renames occurrences, which can shadow other variables with the same name.

**Solution:** Control substitution direction:
```lean
-- Instead of: subst h  (which may eliminate the wrong variable)
-- Use:
have h' : a = b := h
rw [h'] at *     -- or: rw [h'] at specific_hyp
-- Or explicitly name variables differently to avoid collision
```

### CV-6. `while` Loop in Implementation

**Symptom:** Implementation uses `while cond do body` which cannot be directly reasoned about.

**Why:** `while` in Lean 4 is syntax sugar for a fixed-point computation that's hard to unfold.

**Solution:** Replace with fuel-based recursion (see Pattern 7 in code-verification.md). This is a modeling change — define a recursive function that takes `fuel : Nat` and prove it equivalent to the `while` behavior when fuel is sufficient.

### CV-7. `Decidable` Instance Not Found for `decide`

**Symptom:**
```
failed to synthesize instance
  Decidable (∀ x ∈ xs, P x)
```

**Why:** `decide` and `native_decide` require `Decidable` instances for the proposition. Universal quantifiers over unbounded types don't have `Decidable` instances.

**Solution:**
- If the type is finite/bounded: provide or derive a `DecidableEq` or `Fintype` instance
- If the proposition has free variables: don't use `decide` — use `simp`, `omega`, or `induction` instead
- If the data is concrete: try `native_decide` (faster kernel evaluation)

---

## Multiple Typeclass Instances?

If you have multiple instances of the same typeclass in scope (e.g., multiple orderings, metrics, or algebraic structures), pin the ambient instance with `haveI`/`letI` and use `@` for explicit instance passing to prevent subtle bugs and timeout errors.

---

## Detailed Error Explanations

### 1. Failed to Synthesize Instance

**Full error message:**
```
failed to synthesize instance
  SomeClass α
```

**What it means:** Lean cannot automatically infer the required type class instance.

**Common scenarios:**
- Missing `DecidableEq`, `BEq`, or `Hashable` instances for data types
- Custom types without derived instances
- Nested type class dependencies not resolvable

**Solutions:**

**Pattern 1: Explicit instance declaration**
```lean
haveI : DecidableEq α := inferInstance
haveI : BEq α := inferInstance
```

**Pattern 2: Using Fact for constraints**
```lean
have h_le : m ≤ n := ...
haveI : Fact (m ≤ n) := ⟨h_le⟩
```

**Pattern 3: Explicit instance passing with `@`**
```lean
@myLemma α inst1 inst2 arg1 arg2
```

**Pattern 4: Exclude unwanted section variables**
```lean
omit [SomeClass α] in
lemma my_lemma : Statement := by
  proof
```
- **Must appear before the docstring** (not after)
- Can omit multiple: `omit [inst1] [inst2] in`

**For typeclass conflict patterns:** pin ambient instance with `haveI`/`letI`, use `@` for explicit instance passing.

**Debug with:**
```lean
set_option trace.Meta.synthInstance true in
theorem my_theorem : Goal := by
  apply_instance
```

### 2. Maximum Recursion Depth

**Full error message:**
```
(deterministic) timeout at 'typeclass', maximum number of heartbeats (20000) has been reached
```

**What it means:** Type class synthesis is stuck in a loop or the search is too complex.

**Common causes:**
- Circular instance dependencies
- Very deep instance search trees
- Ambiguous instances competing

**Solutions:**

**Solution 1: Provide instance manually**
```lean
letI : SomeClass α := myInstance  -- Freeze the instance
-- Now Lean won't search
```

**Solution 2: Increase search limit**
```lean
set_option synthInstance.maxHeartbeats 40000 in
theorem my_theorem : Goal := ...
```

**Solution 3: Check for instance loops**
```lean
-- ❌ BAD: Creates loop
instance [Foo A] : Bar A := ...
instance [Bar A] : Foo A := ...

-- ✅ GOOD: One-directional
instance [Foo A] : Bar A := ...
```

### 3. Type Mismatch

**Full error message:**
```
type mismatch
  x
has type
  Nat
but is expected to have type
  Int
```

**What it means:** The term's type doesn't match what's expected.

**Common scenarios:**
- `Nat` used where `Int` expected (or vice versa)
- `Bool` used where `Prop` expected
- Different numeric types mixed

**Solutions:**

**Pattern 1: Explicit coercion**
```lean
(n : Int)   -- Preferred: type ascription
↑n          -- Alternative: up-coercion
```

**Pattern 2: Check actual types**
```lean
#check x        -- See current type
#check (x : Int)  -- Verify coercion works
```

**Pattern 3: Function application with coercion**
```lean
-- If f : Int → Int and n : Nat
f ↑n       -- Apply after coercion
f (n : Int)  -- Explicit
```

### 4. Tactic 'exact' Failed

**Full error message:**
```
tactic 'exact' failed, type mismatch
  term
has type
  A → B
but is expected to have type
  ∀ x, A x → B x
```

**What it means:** The term's type is close but not exactly the goal type.

**Solutions:**

**Solution 1: Use apply instead**
```lean
-- exact doesn't work but apply might
apply my_lemma
-- Leaves subgoals to fill
```

**Solution 2: Restructure term**
```lean
-- Wrong order
exact ⟨h.1, h.2⟩  -- Type mismatch

-- Correct order
exact ⟨h.2, h.1⟩  -- Works
```

**Solution 3: Add intermediate steps**
```lean
-- Instead of: exact complex_term
have h1 := part1
have h2 := part2
exact ⟨h1, h2⟩
```

### 5. Unknown Identifier (Missing Tactic or Qualification)

**Full error message:**
```
unknown identifier 'ring'
unknown identifier 'Tendsto'
```

**What it means:** Tactic not imported OR identifier needs qualification.

**Cause 1: Missing tactic import**

**Common missing imports:**
```lean
import Mathlib.Tactic.Ring          -- ring, ring_nf
import Mathlib.Tactic.Linarith      -- linarith, nlinarith
import Mathlib.Tactic.FieldSimp     -- field_simp
import Mathlib.Tactic.Continuity    -- continuity
import Mathlib.Tactic.Measurability -- measurability
import Mathlib.Tactic.Positivity    -- positivity
```

**Quick fix:**
1. See error for tactic name
2. Add `import Mathlib.Tactic.TacticName`
3. Rebuild

**Cause 2: Bare identifier needs qualification**

Lean 4 often requires fully qualified names:

```lean
-- ❌ WRONG: Bare identifier
have h : SomeType := ...

-- ✅ CORRECT: Qualified name
have h : Namespace.SomeType := ...
-- Or open the namespace:
open Namespace in
have h : SomeType := ...
```

### 6. Equation Compiler Failed (Termination)

**Full error message:**
```
fail to show termination for
  my_recursive_function
with errors
  ...
```

**What it means:** Lean can't automatically prove the function terminates.

**Solutions:**

**Pattern 1: Add termination_by clause**
```lean
def my_rec (n : ℕ) : ℕ :=
  if n = 0 then 0
  else my_rec (n - 1)
termination_by n  -- Decreasing argument
```

**Pattern 2: Well-founded recursion**
```lean
def my_rec (l : List α) : Result :=
  match l with
  | [] => base_case
  | h :: t => combine h (my_rec t)
termination_by l.length
```

**Pattern 3: Use sorry for termination proof**
```lean
def my_rec (x : X) : Y := ...
termination_by measure_func x
decreasing_by sorry  -- TODO: Prove later
```

### 7. Unsolved Goals (Nat.pos_of_ne_zero and Arithmetic)

**Full error message:**
```
unsolved goals
h : m ≠ 0
h2 : (4 : ℝ) / ε ≤ ↑m
⊢ False
```

**What it means:** After introducing a contradiction hypothesis, the goal is `False` but the tactic can't derive the contradiction.

**Common scenario:** Proving `m > 0` from `m ≠ 0` and some bound, but `norm_num` fails because the expressions are symbolic (not concrete numbers).

**Why norm_num fails:**
- `norm_num` works on **concrete numerical expressions** (like `2 + 2 = 4`)
- When you have symbolic variables like `4/ε`, `norm_num` can't evaluate them
- After `rw [h]` where `h : m = 0`, you get `4/ε ≤ 0`, but `norm_num` can't derive `False` from this

**Solution: Use simp to eliminate variables, then linarith**

```lean
-- ❌ WRONG: norm_num can't solve symbolic arithmetic
have hm_pos' : m > 0 := Nat.pos_of_ne_zero (by
  intro h
  rw [h] at h2  -- Now h2 : 4/ε ≤ 0
  norm_num at h2  -- FAILS: can't derive False because 4/ε is symbolic
  )
-- Error: unsolved goals ⊢ False

-- ✅ CORRECT: simp eliminates the variable, then linarith
have hm_pos' : m > 0 := Nat.pos_of_ne_zero (by
  intro h
  simp [h] at h2  -- Now h2 : 4/ε ≤ 0 AND we eliminated m entirely
  have : (4 : ℝ) / ε > 0 := by positivity  -- Explicit positivity proof
  linarith)  -- Can now derive contradiction: 0 < 4/ε ≤ 0
```

**Key insight:**
- `norm_num` = numerical normalization (concrete numbers)
- `simp` = simplification (eliminates variables, unfolds definitions)
- `linarith` = linear arithmetic solver (works with inequalities and symbolic expressions)

**General pattern for contradiction proofs:**
1. `simp [hypothesis]` to eliminate the contradictory assumption
2. Establish any needed positivity facts with `positivity`
3. `linarith` to derive the contradiction from inequalities

**When to use each tactic:**
- `norm_num`: Concrete arithmetic (`2 + 2 = 4`, `7 < 10`)
- `simp`: Simplify using hypotheses and definitions
- `linarith`: Linear inequalities with variables (`a + b ≤ c`, `x > 0 → x + 1 > 0`)
- `omega`: Integer linear arithmetic (Lean 4.13+, works on `ℕ` and `ℤ`)

### 8. Unexpected Token/Identifier in Proof (Section Doc Comments)

**Full error message:**
```
unexpected identifier; expected command
unexpected token 'have'; expected command
```

**What it means:** Section doc comments `/-! ... -/` in tactic mode can terminate proof parsing.

**CRITICAL:** Section doc comments terminate proof context, causing everything after to be interpreted as top-level declarations.

```lean
-- ❌ WRONG: Section comments break proof
lemma my_proof := by
  classical
  set mW := ... with hmW

  /-! ### Step 0: documentation -/

  set φp := ... with hφp  -- ERROR: unexpected identifier
  have h := ...           -- ERROR: unexpected token 'have'

-- ✅ CORRECT: Use regular comments
lemma my_proof := by
  classical
  set mW := ... with hmW
  -- Step 0: documentation
  set φp := ... with hφp  -- ✓ Works
  have h := ...           -- ✓ Works
```

**Best practice:** Use `--` for in-proof comments, reserve `/-! -/` for top-level documentation only.

### 9. Variable Shadowing in Lambda

**What it means:** Lambda variable shadows outer variable, causing type confusion.

```lean
-- ❌ WRONG: 'x' in lambda shadows outer 'x'
have h : ∀ x, P x := by
  intro x
  have := some_lemma (fun x => f x)  -- 'x' shadows!
    ... x  -- ERROR: which 'x'?

-- ✅ CORRECT: Rename lambda variable
have h : ∀ x, P x := by
  intro x
  have := some_lemma (fun y => f y)
    ... x  -- ✓ Clear: outer 'x'
```

**Prevention:** Use different variable names in nested lambdas or add explicit type annotations.

### 10. No Goals After Tactic

**Full error message:**
```
no goals to be solved
```

**What it means:** Previous tactic already completed the proof, but another tactic remains.

```lean
-- ❌ WRONG: simp already solved goal
have hφp_nn : ∀ a, 0 ≤ φp a := by
  intro a
  simp [φp]
  exact le_max_right _ _  -- ERROR: no goals left

-- ✅ CORRECT: Remove redundant tactic
have hφp_nn : ∀ a, 0 ≤ φp a := by
  intro a
  simp [φp]  -- ✓ simp completes proof
```

**Debug:** Check goal state after each tactic. If "no goals" appears, proof is done.

## Quick Debug Workflow

When encountering any error:

1. **Read error location carefully** - Often points to exact issue
2. **Use #check** - Verify types of all terms involved
3. **Simplify** - Try to create minimal example that fails
4. **Search mathlib** - Error might be documented in lemma comments
5. **Ask Zulip** - Lean community is very helpful

### Quick Checklist for "Unexpected" Errors in Proofs

When facing "unexpected identifier/token" in long proofs:

1. ☐ Search for `/-! ... -/` section comments → replace with `--`
2. ☐ Check for bare identifiers → add namespace qualification
3. ☐ Look for lambda shadowing → rename variables or add type annotations
4. ☐ Check for "no goals" after `simp` → remove redundant tactics
5. ☐ For section variables + explicit params → rely on section, use `(by infer_instance)`

---

## Additional Common Errors

### 11. Error Location Can Be Misleading

**Problem:** Lean reports errors where elaboration fails, not always where the mistake is.

**Example:**
```
error: type mismatch at line 4238
```
But the actual mistake is at line 4231.

**Why:** Elaborator processes code sequentially and reports failure at the point where it can't continue, which may be several lines after the actual error.

**Strategy:**

**When investigating an error:**
1. Read 5-10 lines **before** the reported location
2. Look for recent changes (especially new `let` bindings, `have` statements, or tactic calls)
3. Check for missing hypotheses or incorrect variable names
4. Verify that all previous lines actually compile in isolation

**Example workflow:**
```lean
-- Error reported at line 50
-- Start reading from line 40-45

-- Line 43: Wrong variable name here
let result := compute xs  -- Should be ys not xs

-- Lines 44-49: These all assumed result was correct
-- Line 50: Where elaboration finally failed
```

**Pattern:** The mistake is often in:
- Most recent `let` or `have` before error (wrong RHS)
- Most recent tactic (applied wrong lemma)
- Missing hypothesis from 2-5 lines before

**Don't:** Assume the error line is where you need to fix.
**Do:** Trace backwards from error to find the root cause.

### 12. Alpha/Beta-Equivalence Issues (Binder Mismatches)

**Problem:** Lean fails to match expressions because binder names differ or beta-redexes aren't reduced.

**Error message:**
```
tactic 'simp' failed
  binder x doesn't match goal's binder y
```

**Why it fails:** Lean doesn't always recognize that `fun x => F x` and `fun y => F y` are the same.

**Solution: Use `set ... with` pattern to name expression once**

```lean
-- Name the complex expression once
set F := fun x => someComplexExpr x with hF

-- Apply lemma to named function F
have h := some_lemma (f := F)

-- Unfold F when needed
simpa [hF] using h
```

**Pattern:**
1. `set F := <complex expr> with hF`
2. Apply lemma to the named `F`
3. Unfold with `simpa [hF]` or `rw [hF]`

---

## Type Class Debugging Commands

```lean
-- See synthesis trace
set_option trace.Meta.synthInstance true in
theorem test : Goal := by apply_instance

-- Check all implicit arguments
#check @my_lemma
```

## Common Patterns to Avoid

### ❌ Fighting the Type Checker

```lean
-- Repeatedly trying variations until something compiles
exact h
exact h.1
exact ⟨h⟩
exact (h : _)  -- Guessing
```

### ✅ Understanding Then Fixing

```lean
#check h  -- See what h actually is
#check goal  -- See what's needed
-- Now fix systematically
```

### ❌ Ignoring Error Messages

```lean
-- "It says type mismatch, let me try random things"
```

### ✅ Reading Carefully

```lean
-- Error says "has type A but expected B"
-- Solution: Convert A to B or restructure
```

---

## Build Log Capture

For debugging persistent build errors, capture the full log for inspection:

### Basic Capture

```bash
LOG=$(mktemp -t lean4_build_XXXXXX.log)
lake build 2>&1 | tee "$LOG"

# Quick scans
tail -n 120 "$LOG"
rg -n "error|warning|failed" "$LOG"
```

### With Git Hash (Conflict-Safe)

```bash
HASH=$(git rev-parse --short HEAD 2>/dev/null || date +%s)
LOG="/tmp/lean4_build_${HASH}_$RANDOM.log"
lake build 2>&1 | tee "$LOG"
```

**Benefits:**
- Preserves logs across rebuilds for comparison
- Avoids filename clashes between runs
- Enables grep without rebuilding
- Links log to specific commit state

**See also:** [Repair Mode](stuck-and-repair.md#repair-mode) for escalation-only repair policy.
