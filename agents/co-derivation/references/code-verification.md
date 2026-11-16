# Code Verification Reference

Program verification tasks in this project follow a fixed structure. This reference documents the task pattern, tactic strategy, and common patterns.

## Task Structure

Every verification file follows this template:

```lean
import Mathlib
set_option maxHeartbeats 0

namespace task_name

-- 1. Precondition (input constraints)
@[reducible, simp]
def func_precond (args...) : Prop := ...

-- 2. Implementation (the program to verify)
def func (args...) (h_precond : func_precond args...) : ReturnType := ...

-- 3. Postcondition (what must hold about the result)
@[reducible, simp]
def func_postcond (args...) (result : ReturnType) (h_precond : func_precond args...) : Prop := ...

-- 4. Specification theorem (the proof obligation — fill the sorry)
theorem func_postcond_satisfied (args...) (h_precond : func_precond args...) :
    func_postcond args... (func args... h_precond) h_precond := by
  sorry

end task_name
```

**Your job: replace `sorry` with a valid proof. Nothing else changes.**

## Modular Proof Structure

**Decompose the full program proof into proofs of individual program fragments.** Extract each fragment's property as a `private lemma` placed before the main theorem. The main theorem becomes short orchestration of these lemmas.

Key decomposition targets:

- **Equational lemmas** — relate each `let rec` / helper to a Mathlib/stdlib equivalent (e.g., `custom_count x l = l.count x`). Tag with `@[simp]`.
- **Loop / recursion invariants** — for each recursive helper with an accumulator, state and prove the invariant as a `private lemma` by `induction ... generalizing acc`.
- **Precondition unpacking** — when the precondition is a conjunction, extract each conjunct as a separate lemma.

```lean
-- Fragment 1: equational lemma for helper
@[simp] private lemma helper_eq (x : α) (l : List α) :
    custom_helper x l = l.filter (· == x) := by
  induction l with ...

-- Fragment 2: invariant for recursive function
private lemma findHelper_spec (nums remaining : List α)
    (h : ∃ x ∈ remaining, ...) :
    ... := by
  induction remaining with ...

-- Main theorem: short orchestration
theorem func_spec_satisfied ... := by
  simp only [func_postcond]
  exact ⟨findHelper_spec ..., ...⟩
```

## Hard Rules

- **NEVER modify** precondition, postcondition, or implementation definitions
- **NEVER use `sorry`** in the final proof
- **NEVER add custom axioms**
- **`native_decide` is allowed** — it introduces `Lean.ofReduceBool` and `Lean.trustCompiler` axioms, which are accepted in this project

## Lemma Retrieval (Before Proving)

**Before writing any tactics**, search for the lemmas you will need. Unfold key definitions to see the goal shape, then search using LSP tools (`lean_loogle`, `lean_leansearch`, `lean_local_search`) or `exact?` / `apply?` / `rw?`. Having the right lemmas in hand makes automation (`simp [found_lemmas...]`) far more effective than blind `simp_all`. See [lemma-retrieval](lemma-retrieval.md) for the full workflow.

## Tactic Strategy (Priority Order)

For code verification, the strategy differs from mathematical theorem proving. **Unfold and reduce first, then induct.**

### Step 1: Unfold Definitions

Since precond/postcond are `@[reducible, simp]`, start by unfolding everything:

```lean
simp only [func, func_postcond, func_precond]
-- or
unfold func func_postcond func_precond
```

### Step 2: Try Automation

After unfolding, try closers in this order:

```
simp_all → omega → grind → aesop → decide → native_decide
```

If the goal closes, done. Otherwise continue.

### Step 3: Structural Induction

Most verification proofs require induction on the primary data structure:

```lean
induction xs with
| nil => simp_all
| cons x xs ih => simp_all; ...
```

### Step 4: Case Analysis

For if-then-else or match expressions:

```lean
split           -- split on if/match
cases h : expr  -- case split with name
by_cases h : P  -- classical case split on decidable prop
```

### Step 5: Arithmetic and Logic

```lean
omega           -- linear arithmetic over Nat/Int
linarith        -- linear arithmetic (more general)
nlinarith       -- nonlinear arithmetic
ring            -- ring equalities
norm_num        -- numeric normalization
```

### Step 6: Rewriting

```lean
rw [lemma]          -- rewrite with lemma
simp [lemma1, ...]  -- simplify with specific lemmas
conv => ...         -- targeted rewriting
```

## Common Verification Patterns

### Pattern 1: List Recursion

Most algorithms process lists recursively. The proof mirrors the recursion:

```lean
-- Function uses match on list
def process : List α → Result
  | [] => base
  | x :: xs => step x (process xs)

-- Proof uses induction on list
theorem spec : ... := by
  induction xs with
  | nil => simp [process, postcond]
  | cons x xs ih =>
    simp [process]
    split  -- for if-then-else in step
    · ...  -- case 1
    · ...  -- case 2
```

### Pattern 2: Accumulator / Helper with Invariant

Many functions use a helper with an accumulator:

```lean
def func (input) :=
  let rec helper (remaining) (acc) := ...
  helper input init_acc
```

Strategy: extract a **private lemma** about the helper's behavior, then the main theorem is short:

```lean
-- Extracted as private lemma (not inline have)
private lemma helper_invariant (remaining acc) (h_inv : invariant acc) :
    postcond (helper remaining acc) := by
  induction remaining generalizing acc with ...

-- Main spec is short
theorem spec : ... := by
  simp only [func_postcond, func]
  exact helper_invariant input init_acc init_invariant_proof
```

Key: use `induction xs generalizing acc` to keep the accumulator general in the IH.

### Pattern 3: Array with Index Bounds

Array verification often involves index bounds:

```lean
-- Common lemmas
Array.getD_eq_get   -- getD with valid index = get
Array.size_push     -- (a.push x).size = a.size + 1
Array.get_push_lt   -- (a.push x)[i] = a[i] when i < a.size
```

Use `omega` heavily for index arithmetic.

### Pattern 4: Boolean Postcondition

Some postconditions use `decide` or boolean evaluation:

```lean
def postcondB (...) : Bool := ...
def postcond (...) : Prop := postcondB ... = true
```

Strategy: unfold to the boolean level, then use `simp` or `decide`:

```lean
simp only [postcond, postcondB]
-- now working with Bool = true goals
```

### Pattern 5: Recursive Function with Termination

Functions with `termination_by` / `decreasing_by` need careful handling:

```lean
-- Use the function's unfolding equation
simp only [func]
-- Or unfold step by step
unfold func
split  -- on the termination condition
```

### Pattern 6: Imperative Code (`Id.run do` → `List.foldl`)

Many implementations use `Id.run do` with `for` loops and `let mut` variables. These cannot be reasoned about directly — you must bridge them to pure `List.foldl` form first.

#### Three-Layer Bridge Architecture

```
Id.run do (for x in xs do ...)     -- imperative
        ↓  Bridge 1: simp lemma chain
List.foldl (fun acc x => ...) init xs   -- pure functional
        ↓  Bridge 2: loop invariant induction
Recursive spec / postcond               -- specification
```

#### Bridge 1: `Id.run do` → `List.foldl`

**Step 1**: Extract the loop body as a named function:

```lean
private def loopBody (x : α) (acc : β) : β :=
  if ... then ... else ...
```

**Step 2**: Prove the bridge lemma using this simp chain:

```lean
set_option linter.deprecated false in
private lemma impl_eq_foldl (args...) :
    (Id.run do
      let mut acc := init
      for x in xs do
        acc := loopBody x acc
      return acc) =
    xs.foldl (fun acc x => loopBody x acc) init := by
  simp only [Id.run, Id.pure_eq, Id.bind_eq, Id.map_eq, bind_pure_comp]
  simp only [List.forIn_yield_eq_foldl]
```

**Key simp lemmas** (apply in this order):

| Lemma | Purpose |
|-------|---------|
| `Id.run` | Unwrap `Id.run` |
| `Id.pure_eq`, `Id.bind_eq`, `Id.map_eq` | Eliminate Id monad wrappers |
| `bind_pure_comp` | Simplify monadic composition |
| `List.forIn_yield_eq_foldl` | Convert `forIn` to `List.foldl` |
| `← apply_ite ForInStep.yield` | Merge `if c then yield a else yield b` into `yield (if c then a else b)` — **required before the second `forIn_yield_eq_foldl` in nested loops** |
| `Std.Range.forIn_eq_forIn_range'` | Convert `[start:stop]` range to `List.range'` |

**Nested `for` loops**: Apply the simp chain twice — once for the inner loop, once for the outer. Before the second application, use `← apply_ite ForInStep.yield` to merge any `if-then-else` inside the inner loop body into a single `ForInStep.yield`.

```lean
-- Nested loops: inner first, then merge if-then-else, then outer
private lemma dp_eq_foldl ... :=
    ... = outerFold ... := by
  simp only [Id.run, Id.pure_eq, Id.bind_eq, Id.map_eq, bind_pure_comp]
  simp only [List.forIn_yield_eq_foldl]           -- inner loop
  simp only [← apply_ite ForInStep.yield]          -- merge if branches
  simp only [List.forIn_yield_eq_foldl]           -- outer loop
```

**`set_option linter.deprecated false`**: Some Id lemmas are deprecated; add this annotation to suppress warnings.

### Pattern 7: While Loop (Fuel Recursion)

`while` loops cannot be directly formalized in Lean 4. Replace them with a recursive function that takes an explicit `fuel : Nat` parameter.

#### Step 1: Define fuel-based recursion

```lean
def whileBody (state : σ) (fuel : Nat) : σ :=
  match fuel with
  | 0 => state
  | fuel + 1 =>
    if cond state then
      whileBody (step state) fuel
    else state
```

#### Step 2: Choose fuel

The fuel must be large enough that the loop terminates before it runs out. Typically use the container's `.size` or `xs.length`.

#### Step 3: Prove the bridge

Show that `Id.run do ... while cond do ... = whileBody initState fuel`:

```lean
private lemma while_eq_fuel ... :
    (Id.run do
      let mut s := init
      while cond s do
        s := step s
      return s) =
    whileBody init container.size := by
  ...
```

#### Step 4: Prove properties by induction on fuel

```lean
private lemma whileBody_spec (s : σ) (fuel : Nat) (h_fuel : sufficient fuel s) :
    postcond (whileBody s fuel) := by
  induction fuel generalizing s with
  | zero => simp [whileBody] at h_fuel; ...
  | succ n ih =>
    simp only [whileBody]
    split
    · exact ih (step s) ...   -- cond holds: recurse
    · ...                      -- cond fails: base case
```

### Pattern 8: Nested-Loop DP (Loop Invariant)

For DP algorithms with nested loops that fill an array, use this structured approach.

#### Step 1: Extract loop body as `dpCell`

```lean
private def dpCell (i j : Nat) (dp : Array (Array Int)) : Array (Array Int) :=
  -- exactly mirrors one iteration of the inner loop
  if ... then dp.set! i (dp[i]!.set! j value1)
  else dp.set! i (dp[i]!.set! j value2)
```

#### Step 2: Prove `dpCell` properties

These are the building blocks for the invariant proof:

```lean
-- Size preservation
private lemma dpCell_size : (dpCell i j dp).size = dp.size

-- Same-index read (the cell that was written)
private lemma dpCell_val (h : i < dp.size) (h2 : j < (dp[i]!).size) :
    ((dpCell i j dp)[i]!)[j]! = expectedValue i j

-- Different-row read (other rows unchanged)
private lemma dpCell_other_row (h : i' ≠ i) :
    ((dpCell i j dp)[i']!)[j']! = (dp[i']!)[j']!

-- Different-col read (same row, other columns unchanged)
private lemma dpCell_other_col (h : j' ≠ j) :
    ((dpCell i j dp)[i]!)[j']! = (dp[i]!)[j']!
```

#### Step 3: Define folds

```lean
private def innerFold (i : Nat) (dp : Array (Array Int)) : Array (Array Int) :=
  (List.range cols).foldl (fun dp j => dpCell i j dp) dp

private def outerFold (dp : Array (Array Int)) : Array (Array Int) :=
  (List.range rows).foldl (fun dp i => innerFold i dp) dp
```

#### Step 4: Prove loop invariant by induction on `List.range k`

**Inner loop invariant** (induction on columns processed):

```lean
private lemma inner_inv (i k : Nat) (dp₀ : Array (Array Int))
    (hk : k ≤ cols) (h_pre : preconds dp₀) :
    let dp := (List.range k).foldl (fun dp j => dpCell i j dp) dp₀
    dp.size = dp₀.size
    ∧ (∀ j, j < k → ((dp[i]!)[j]!) = specValue i j)    -- filled cells correct
    ∧ (∀ j, j ≥ k → ((dp[i]!)[j]!) = (dp₀[i]!)[j]!)   -- unfilled cells unchanged
    ∧ (∀ i', i' ≠ i → (dp[i']!) = (dp₀[i']!))          -- other rows unchanged
    := by
  induction k with
  | zero => simp [List.range, List.foldl]; exact ⟨rfl, fun j hj => absurd hj (by omega), ...⟩
  | succ k ihk =>
    have step : (List.range (k + 1)).foldl f init =
        f ((List.range k).foldl f init) k := by
      rw [List.range_succ, List.foldl_append, List.foldl_cons, List.foldl_nil]
    rw [step]
    obtain ⟨sz_k, fill_k, zero_k, other_k⟩ := ihk (by omega)
    ...
```

**Outer loop invariant** (induction on rows processed): same structure, wrapping `innerFold`.

**Key induction step technique** — unwrap `List.range (k+1)`:

```lean
have step : (List.range (k + 1)).foldl f init =
    f ((List.range k).foldl f init) k := by
  rw [List.range_succ, List.foldl_append, List.foldl_cons, List.foldl_nil]
rw [step]
-- Now goal is about f (prev_result) k
-- Apply IH to prev_result, then dpCell properties to the outermost f
```

**Naming intermediate results** to prevent simp from over-rewriting:

```lean
set dp_k := (List.range k).foldl f init with h_dp_k
-- Use h_dp_k to rewrite IH hypotheses
simp only [← h_dp_k] at sz_k fill_k zero_k other_k
```

### Pattern 9: Array `set!`/`getElem!` Helpers

Array verification frequently needs get-after-set lemmas. Define these once:

```lean
private lemma gs_same (ar : Array α) (i : Nat) (v : α) (h : i < ar.size) :
    (ar.set! i v)[i]! = v := by
  simp [Array.getElem!_pos, Array.set!, Array.size_set,
        Array.getElem_set, h]

private lemma gs_diff (ar : Array α) (i j : Nat) (v : α)
    (hij : i ≠ j) (hj : j < ar.size) :
    (ar.set! i v)[j]! = ar[j]! := by
  simp [Array.getElem!_pos, Array.set!, Array.size_set,
        Array.getElem_set, hij, hj]
```

**Handling `match dp with | #[] => ... | _ => ...`**: Define a named function to avoid equation-generation issues:

```lean
private def applyResult (dp : Array Int) : Int :=
  match dp with | #[] => 0 | _ => dp.foldl max 0

-- Bridge via congrArg
have : func args h = applyResult (computedArray args) :=
  congrArg applyResult bridge_lemma
```

## Common Useful Lemmas

### List
```
List.length_nil, List.length_cons
List.mem_cons, List.mem_nil_iff
List.map_cons, List.map_nil
List.filter_cons, List.filter_nil
List.append_nil, List.append_cons
List.count_cons, List.count_nil
List.all_cons, List.all_nil
List.zip_cons_cons, List.zip_nil_left
List.take_cons, List.take_zero
List.get_cons_zero, List.get_cons_succ
```

### Nat / Int
```
Nat.zero_le, Nat.succ_le_succ
Nat.lt_of_lt_of_le, Nat.le_of_lt_succ
Int.ofNat_le, Int.ofNat_lt
max_comm, max_assoc, le_max_left, le_max_right
```

### List (foldl / forIn)
```
List.foldl_cons, List.foldl_nil
List.foldl_append                      -- foldl f init (xs ++ ys) = foldl f (foldl f init xs) ys
List.range_succ                        -- range (n+1) = range n ++ [n]
List.forIn_cons, List.forIn_nil
List.forIn_yield_eq_foldl              -- key bridge: forIn → foldl
```

### Array (indexing & mutation)
```
-- Size
Array.size_push, Array.size_empty, Array.size_set, Array.size_mkArray

-- Safe indexing (getElem with proof)
Array.getElem_push_lt                  -- (a.push x)[i] = a[i]  when i < a.size
Array.getElem_push_eq                  -- (a.push x)[a.size] = x
Array.getElem_set_eq                   -- (a.set i v)[i] = v
Array.getElem_set_ne                   -- (a.set i v)[j] = a[j]  when i ≠ j
Array.getElem_mkArray                  -- (mkArray n v)[i] = v

-- Unsafe indexing (getElem! / get! — uses Inhabited default on OOB)
Array.getElem!_pos                     -- a[i]! = a[i]  when i < a.size  (bridge ! to safe)

-- Conversion
Array.toList_eq, Array.data_push, Array.data_set
Array.toList_length                    -- a.toList.length = a.size
```

### Array (set! bridge — define these as private lemmas)
```
-- get-after-set same index:   (a.set! i v)[i]! = v        (when i < a.size)
-- get-after-set diff index:   (a.set! i v)[j]! = a[j]!    (when i ≠ j, j < a.size)
-- See Pattern 9 for template implementations
```

### Std.HashSet
```
Std.HashSet.contains_insert            -- (s.insert x).contains y ↔ (x == y) || s.contains y
Std.HashSet.contains_empty             -- Std.HashSet.empty.contains x = false
Std.HashSet.mem_insert                 -- y ∈ s.insert x ↔ y = x ∨ y ∈ s
Std.HashSet.size_insert                -- bound on size after insert
```

### Id Monad (for imperative code bridge)
```
Id.run                                 -- unwrap Id.run
Id.pure_eq                             -- Id.pure x = x  (may be deprecated)
Id.bind_eq                             -- Id.bind x f = f x  (may be deprecated)
Id.map_eq                              -- Id.map f x = f x  (may be deprecated)
bind_pure_comp                         -- simplify monadic composition
```

### Std.Range (for `[start:stop]` syntax)
```
Std.Range.forIn_eq_forIn_range'        -- [a:b] range → List.range'
```

### General
```
Bool.and_eq_true, Bool.or_eq_true
decide_eq_true_eq
ite_true, ite_false
apply_ite                              -- f (if c then a else b) = if c then f a else f b
← apply_ite ForInStep.yield            -- merge if-then-else inside forIn body
max_comm, max_assoc, le_max_left, le_max_right
min_comm, min_assoc, min_le_left, min_le_right
```

## Debugging Tips

1. **Goal inspection**: Use `lean_goal(file, line)` via LSP to see the exact goal state
2. **Type check**: When `simp` doesn't close, check what's left with LSP hover
3. **Heartbeat timeout**: Already set to `maxHeartbeats 0`, but if a tactic is slow, try more specific `simp only [...]` instead of `simp_all`
4. **Unfold order matters**: Unfold user defs first, then try automation, then unfold stdlib defs if needed
5. **`generalizing` keyword**: When doing induction with accumulators, use `induction xs generalizing acc` to keep the accumulator general in the IH

