# Lean 4 Tactics Reference

This reference provides comprehensive guidance on essential Lean 4 tactics, when to use them, and common patterns.

**For tactic lookup:** grep `^### TacticName` in this file to jump to a specific tactic.

## Decision Tree

```
What's my goal?
├─ Close with exact term → exact / assumption
├─ Apply lemma to reduce goal → apply / refine
├─ Prove equality
│   ├─ By definition → rfl
│   ├─ By rewriting → rw [lemma]
│   ├─ By calculation → calc / ring / field_simp
│   └─ By extensionality → ext / funext
├─ Split goal
│   ├─ And/Iff → constructor
│   ├─ Or → left / right
│   └─ Exists → use witness
├─ Goal has if/match → split
├─ Split hypothesis → cases / rcases / obtain
├─ Induction on structure → induction xs (+ generalizing acc if accumulator)
├─ Closed decidable prop → decide / native_decide
├─ Simplify → simp / norm_num / ring
├─ Mixed logic/equality → aesop (then grind if aesop fails)
└─ Don't know → exact? / apply? / simp?
```

---

## Quick Reference

| Want to... | Use... |
|------------|--------|
| Close with exact term | `exact` |
| Apply lemma | `apply` |
| Rewrite once | `rw [lemma]` |
| Normalize expression | `simp`, `ring`, `norm_num` |
| Split if/match in goal | `split` |
| Split cases | `by_cases`, `cases`, `rcases` |
| Induction with accumulator | `induction xs generalizing acc` |
| Prove exists | `use witness` |
| Prove and/iff | `constructor` |
| Prove function equality | `ext` / `funext` |
| Close decidable prop | `decide` / `native_decide` |
| Automated reasoning | `aesop` (logic), `grind` (SMT-style) |
| Explore options | `exact?`, `apply?`, `simp?` |
| Automate domain-specific | `ring`, `linarith`, `continuity`, `measurability` |

The most important tactic is the one you understand!

## Essential Tactics

### Simplification Tactics

#### `simp` - The Workhorse Simplifier

**What it does:** Recursively applies `@[simp]` lemmas to rewrite expressions to normal form.

**Basic usage:**
```lean
example : x + 0 = x := by simp           -- Uses simp lemmas
example : f (g x) = h x := by simp [f_g] -- Explicitly simp with f_g
example : P → Q := by simpa using h      -- simp then exact h
```

**Variants:**
```lean
simp                    -- Use all simp lemmas
simp only [lem1, lem2]  -- Use only specified lemmas (preferred)
simp [*]                -- Include all hypotheses
simp at h               -- Simplify hypothesis h
simp at *               -- Simplify all hypotheses and goal
simpa using h           -- simp then exact h
simp?                   -- Show which lemmas it uses (exploration)
```

**When to use `simp`:**
- Obvious algebraic simplifications (`x + 0`, `x * 1`, etc.)
- Normalizing expressions to canonical form
- Cleaning up after other tactics

**When to use `simp only`:**
- You know which lemmas you need (preferred for clarity)
- Want explicit, reviewable proof
- Avoiding surprising simp behavior

**When NOT to use `simp`:**
- Simple rewrites (use `rw` instead)
- Unclear what it's doing (use `simp?` first, then convert to `simp only`)

#### Deep Dive: The `simp` Tactic

**How simp works internally:**
1. Collects all `@[simp]` lemmas in scope
2. Tries to match lemma left-hand sides against expression
3. Rewrites using right-hand side
4. Recursively simplifies subexpressions
5. Continues until no more lemmas apply

**What makes a good @[simp] lemma:**
```lean
-- ✅ Good: Makes expression simpler
@[simp] lemma add_zero (x : ℕ) : x + 0 = x

@[simp] lemma map_nil : List.map f [] = []

@[simp] lemma indicator_apply (x : X) :
    Set.indicator s f x = if x ∈ s then f x else 0

-- ❌ Bad: Doesn't simplify (creates loop)
@[simp] lemma bad : f (g x) = g (f x)  -- Rewrites back and forth!

-- ❌ Bad: Makes more complex
@[simp] lemma worse : x = x + 0 - 0  -- Right side more complex
```

**Decision tree for adding @[simp]:**
```
Is the right side simpler than the left?
├─ Yes → Good @[simp] candidate
│  └─ Does it create loops with other simp lemmas?
│     ├─ No → Add @[simp]
│     └─ Yes → Don't add @[simp], use manually
└─ No → Don't add @[simp]
```

**Using simp effectively:**
```lean
-- 1. Exploration phase: Use simp? to see what happens
example : x + 0 + y * 1 = x + y := by simp?
-- Output: Try this: simp only [add_zero, mul_one]

-- 2. Production: Convert to explicit
example : x + 0 + y * 1 = x + y := by simp only [add_zero, mul_one]
```

**Common simp patterns:**
```lean
-- Simplify specific terms
simp only [my_def]  -- Unfold my_def

-- Simplify with additional lemmas
simp only [add_zero, mul_one, my_lemma]

-- Simplify and close
simpa [my_lemma] using h

-- Simplify at hypothesis
simp only [my_lemma] at h

-- Normalize then continue
simp only [my_def]
apply other_lemma
```

**simp with calc chains:**

When using `simp` before a `calc` chain, the `calc` must start with the **already simplified form**, not the original expression:

```lean
-- ❌ WRONG: calc starts with pre-simp form
simp only [my_def]
calc original_form    -- simp already transformed this!
    _ = ... := by ...

-- ✅ CORRECT: calc starts with post-simp form
simp only [my_def]
calc simplified_form  -- Start with what simp produced
    _ = ... := by ...
```

### Case Analysis Tactics

#### `by_cases` - Boolean/Decidable Split

```lean
by_cases h : p  -- Creates two goals: one with h : p, one with h : ¬p

example (n : ℕ) : ... := by
  by_cases h : n = 0
  · -- Case h : n = 0
    sorry
  · -- Case h : n ≠ 0
    sorry
```

#### `rcases` - Destructure Hypotheses

```lean
-- Exists
rcases h with ⟨x, hx⟩        -- h : ∃ x, P x
                              -- Gives: x and hx : P x

-- And
rcases h with ⟨h1, h2⟩       -- h : P ∧ Q
                              -- Gives: h1 : P and h2 : Q

-- Or
rcases h with h1 | h2        -- h : P ∨ Q
                              -- Creates two goals

-- Nested
rcases h with ⟨x, y, ⟨hx, hy⟩⟩  -- h : ∃ x y, P x ∧ Q y
```

#### `obtain` - Rcases with Proof

```lean
-- Like rcases but shows intent
obtain ⟨C, hC⟩ := h_bound    -- h_bound : ∃ C, ∀ x, ‖f x‖ ≤ C
-- Now have: C and hC : ∀ x, ‖f x‖ ≤ C
```

#### `cases` - Inductive Type Split

```lean
cases l with                 -- l : List α
| nil => sorry              -- l = []
| cons head tail => sorry   -- l = head :: tail

cases n with                 -- n : ℕ
| zero => sorry             -- n = 0
| succ k => sorry           -- n = k + 1
```

#### `split` - Split on `if`/`match`/`decide`

**What it does:** Splits the goal on the first `if-then-else`, `match`, or `Decidable` condition it finds.

**Basic usage:**
```lean
-- Split an if-then-else in the goal
example (n : Nat) : (if n = 0 then 1 else n) > 0 := by
  split
  · -- Case: n = 0, goal: 1 > 0
    omega
  · -- Case: n ≠ 0, goal: n > 0
    omega

-- Split a match expression
example (o : Option Nat) : (match o with | none => 0 | some n => n + 1) ≥ 0 := by
  split
  · omega   -- none branch
  · omega   -- some branch
```

**Named variant:**
```lean
split
next h =>   -- h names the condition/pattern in each branch
  ...
```

**Splitting in a hypothesis:**
```lean
split at h   -- split the first if/match in hypothesis h
```

**When to use:**
- After `unfold`/`simp` reveals `if-then-else` or `match` in the goal
- Code verification: virtually every branching implementation needs `split`
- Recursive functions with `match` on the primary argument

**Common pattern in code verification:**
```lean
theorem spec ... := by
  simp only [func, postcond]
  induction xs with
  | nil => simp
  | cons x xs ih =>
    simp only [helper]
    split                    -- split on the if/match inside helper
    · simp_all; omega       -- branch 1
    · simp_all; omega       -- branch 2
```

**`split` vs `by_cases`:**
- `split`: splits on an existing `if`/`match` already in the goal — no need to name the condition
- `by_cases h : P`: introduces a new case split on arbitrary `Decidable` prop `P` — you choose what to split on

#### `induction` - Structural Induction

**Basic usage:**
```lean
induction xs with
| nil => ...
| cons x xs ih => ...
```

**With `generalizing` (critical for accumulator patterns):**

When the function uses a helper with an accumulator, the induction hypothesis must be general over the accumulator. Use `generalizing` to achieve this:

```lean
-- Function with accumulator
def sumHelper : List Nat → Nat → Nat
  | [], acc => acc
  | x :: xs, acc => sumHelper xs (acc + x)

-- WITHOUT generalizing: IH is stuck with a specific acc value
-- WITH generalizing: IH works for ALL acc values
private lemma sumHelper_eq (xs : List Nat) (acc : Nat) :
    sumHelper xs acc = acc + xs.foldl (· + ·) 0 := by
  induction xs generalizing acc with    -- ← generalizing acc is essential
  | nil => simp [sumHelper]
  | cons x xs ih =>
    simp only [sumHelper, List.foldl_cons]
    rw [ih]    -- IH: ∀ acc', sumHelper xs acc' = acc' + xs.foldl ...
    omega
```

**When to use `generalizing`:**
- The function pattern-matches on one argument but also takes an accumulator/state
- The accumulator changes across recursive calls (e.g., `acc + x`, `acc.push x`)
- Without it, the IH is too weak to apply in the inductive step

**Multiple generalizing variables:**
```lean
induction xs generalizing acc1 acc2 with ...
```

**Strong induction (on `Nat`):**
```lean
induction n using Nat.strong_rec_on with
| _ n ih => ...
-- ih : ∀ m, m < n → P m
```

### Rewriting Tactics

#### `rw` - Rewrite with Equality

```lean
rw [lemma]       -- Left-to-right rewrite
rw [← lemma]     -- Right-to-left rewrite (note ←)
rw [lem1, lem2]  -- Multiple rewrites in sequence
rw [lemma] at h  -- Rewrite in hypothesis
```

**Example:**
```lean
example (h : x = y) : x + 1 = y + 1 := by
  rw [h]  -- Rewrites x to y in goal
```

#### `simp_rw` - Simplifying Rewrites

**When to use:** Multiple sequential rewrites or rewrite chains

```lean
-- Sequential rewrites (less efficient)
rw [h₁]
rw [h₂]
rw [h₃]

-- Better: chain with simp_rw
simp_rw [h₁, h₂, h₃]
```

**Advantages over `rw`:**
- Applies rewrites left-to-right repeatedly
- More powerful for chains: can use intermediate results
- Single tactic call = clearer proof structure

**When to prefer `simp_rw`:**
- Multiple related rewrites in sequence
- Rewrite chains where later steps use earlier results

#### `rfl` - Reflexivity of Equality

```lean
-- Proves goals of form a = a (definitionally)
example : 2 + 2 = 4 := by rfl
```

### Application Tactics

#### `exact` - Provide Exact Proof

```lean
exact proof_term  -- Closes goal if term has exactly the right type
```

#### `apply` - Apply Lemma, Leave Subgoals

```lean
apply my_lemma     -- Applies lemma, creates goals for premises
```

**Difference:**
```lean
-- exact: Type must match exactly
example : P := by
  exact h  -- h must have type P

-- apply: Unifies, creates subgoals
example : Q := by
  apply my_lemma  -- my_lemma : P → Q
  -- Creates goal: P
```

#### `refine` - Apply with Placeholders

```lean
refine { field1 := value1, field2 := ?_, field3 := value3 }
-- Creates goal for field2
```

### Construction Tactics

#### `constructor` - Build Inductive

```lean
-- For P ∧ Q
constructor
-- Creates two goals: P and Q

-- For P ↔ Q
constructor
-- Creates: P → Q and Q → P

-- For structures
constructor
-- Creates goals for each field
```

#### `use` - Provide Witness for Exists

```lean
use value   -- For ∃ x, P x, provide the x
            -- Creates goal: P value
```

**Example:**
```lean
example : ∃ n : ℕ, n > 5 := by
  use 10
  -- Goal: 10 > 5
  norm_num
```

### Extension & Congruence

#### `ext` / `funext` - Function Extensionality

```lean
ext x       -- To prove f = g, prove f x = g x for all x
funext x    -- Same, alternative syntax
```

#### `congr` - Congruence

```lean
congr  -- Breaks f a = f b into a = b (when f is the same)
```

### Specialized Tactics

#### Domain-Specific Automation

**Algebra:**
```lean
ring         -- Solve ring equations
field_simp   -- Simplify field expressions
group        -- Solve group equations
```

**Arithmetic:**
```lean
omega        -- Linear arithmetic over Nat/Int
             -- Example: have : n + 1 < n + 5 := by omega
linarith     -- Linear arithmetic (works on Nat, Int, and ordered types)
             -- Example: have : x ≤ y := by linarith
nlinarith    -- Non-linear arithmetic
             -- Example: have : x * x ≥ 0 := by nlinarith
norm_num     -- Normalize concrete numerical expressions
             -- Example: have : 2 + 3 = 5 := by norm_num
ring         -- Ring equalities (polynomials)
             -- Example: have : (a + b) * (a - b) = a^2 - b^2 := by ring
```

**When to use which arithmetic tactic:**
```lean
-- omega: Nat/Int linear inequalities (fastest, most common in code verification)
lemma nat_ineq (n m : ℕ) (h1 : n < m) (h2 : m < n + 5) : n + 1 < n + 5 := by omega

-- linarith: linear inequalities with hypotheses (more general than omega)
lemma lin_ineq (x y : Int) (h1 : x ≤ y) (h2 : y < x + 1) : x < x + 1 := by linarith

-- nlinarith: nonlinear (multiplications, squares)
lemma sq_nonneg (x : Int) : x * x ≥ 0 := by nlinarith

-- norm_num: concrete number evaluation
example : 17 % 3 = 2 := by norm_num
```

#### `decide` / `native_decide` - Decision Procedures

**What they do:** Close goals that are decidable propositions by evaluating them to `true`.

**`decide`:**
```lean
-- Works on small, finite goals
example : 2 + 3 = 5 := by decide
example : ¬(3 < 2) := by decide
example : (true && false) = false := by decide
example : [1, 2, 3].length = 3 := by decide
```

**`native_decide`:**
```lean
-- Uses compiled native code — much faster for large computations
-- Introduces Lean.ofReduceBool and Lean.trustCompiler axioms (accepted in this project)
example : (List.range 1000).length = 1000 := by native_decide
```

**When to use `decide`:**
- Goal is a closed (no free variables) decidable proposition
- Small instances: Bool operations, small Nat/Int comparisons, finite type enumerations
- Bridging `Bool` and `Prop`: `(expr == expr') = true`

**When to use `native_decide`:**
- Same as `decide` but the kernel reduction is too slow
- Large numeric computations, string operations, list operations on concrete data

**When NOT to use:**
- Goal contains free variables (universally quantified) — use `intro` first or `simp`/`omega`
- Goal requires structural reasoning, not just evaluation
- Goal involves infinite types without decidable instances

**Common code verification pattern:**
```lean
-- Postcondition uses a Bool function
def postcond (result : Nat) : Prop := checkResult result = true

-- After unfolding, goal becomes: checkResult (func input) = true
-- If input is concrete:
theorem spec : postcond (func concreteInput) := by native_decide

-- If input has free variables, decide won't work — use simp/induction instead
```

**`Decidable` instance errors:**
```
failed to synthesize Decidable (P x)
```
Fix: Provide a `Decidable` instance or switch to `simp`/`omega`/`induction`.

#### `aesop` - Automated Reasoning

**What it does:** Combines `simp`, `apply`, `cases`, `constructor`, `exact`, and other tactics in a best-first search to close the goal. More powerful than `simp` but slower.

**Basic usage:**
```lean
-- Close goals that need a mix of intro/apply/cases/simp
example (h : P ∧ Q) : Q ∧ P := by aesop

-- With additional lemmas
example : ... := by aesop (add norm simp [my_lemma])
```

**Variants:**
```lean
aesop                              -- default rule set
aesop?                             -- show what it did (for converting to explicit proof)
aesop (add norm simp [lem1, lem2]) -- add simp lemmas
aesop (add safe apply [my_thm])   -- add safe apply rules
aesop (add unsafe 50% apply [h])  -- add unsafe rule with priority
```

**When to use:**
- After `simp_all` fails but the goal seems "obviously" closeable
- Goals that need a combination of `intro`, `constructor`, `cases`, `exact`
- As a closer in induction branches: `induction xs with | nil => aesop | cons ...`
- Membership/subset proofs, simple logic

**When NOT to use:**
- Pure arithmetic — use `omega`/`linarith` instead
- Pure rewriting — use `simp` instead
- Goals with many hypotheses — `aesop` search can blow up

**Making lemmas available to `aesop`:**
```lean
@[aesop safe apply] lemma my_safe_lemma : ...    -- always applied
@[aesop unsafe 70% apply] lemma my_hint : ...     -- tried with priority
@[aesop norm simp] lemma my_simp_rule : ...        -- used in normalization
```

**Common code verification pattern:**
```lean
-- As a closer after unfolding + induction
theorem spec ... := by
  unfold postcond func
  induction xs with
  | nil => aesop
  | cons x xs ih =>
    simp only [helper]
    split <;> aesop
```

#### `grind` - SMT-Style Automation

**What it does:** Combines congruence closure, E-matching, case splitting, and arithmetic/algebraic solvers to close mixed-constraint goals.

**When to reach for it:**
- `simp` normalizes but does not close
- Goal mixes equalities + inequalities + algebraic facts
- Finite-domain reasoning (`Fin`, `Bool`, small enums)

**Baseline usage:**
```lean
example (h1 : a = b) (h2 : b = c) : a = c := by grind
example [CommRing R] [NoZeroDivisors R] (h : x * y = 0) (hx : x ≠ 0) : y = 0 := by grind
example : (5 : Fin 3) = 2 := by grind

-- Typical sequence:
simp only [normalize_defs]
grind
```

**High-value controls (official docs):**
```lean
grind?                       -- suggest a grind call (lemmas/options)
grind [key_lemma1, key_lemma2]      -- add lemmas
grind only [key_lemma1, key_lemma2] -- restrict lemma set
grind [-some_lemma]                  -- exclude one lemma
grind (splits := 0)                  -- disable case splitting
grind (splits := 8)                  -- bound case splitting
grind -splitIte -splitMatch +splitImp
grind -ring                           -- disable ring solver
grind -funCC +revert -reducible       -- newer search/reduction controls
```

**When NOT to use `grind`:**
- Pure rewrites -> `simp`
- Integer-only arithmetic -> `omega`
- Nonlinear arithmetic -> `nlinarith`
- Combinatorial/bit-blasting search -> `bv_decide`

**Notes:**
- Local hypotheses are already in scope for `grind`; avoid passing them redundantly.
- If search explodes, reduce splitting (`splits := 0`) before adding more lemmas.
- For custom automation, register lemmas with `@[grind]` / `@[grind =]` / `@[grind ->]` and use `@[grind_pattern]` only when matching needs manual shaping.

**For full details:** [grind-tactic.md](grind-tactic.md)

## Tactic Combinations

### Common Patterns

**Pattern 1: Simplify then apply**
```lean
by
  simp only [my_defs]
  apply main_lemma
```

**Pattern 2: Cases then simplify each**
```lean
by
  by_cases h : p
  · simp [h]  -- Use h in simplification
  · simp [h]
```

**Pattern 3: Induction with automation**
```lean
by
  induction n with
  | zero => simp
  | succ k ih => simp [ih]; ring
```

**Pattern 4: Destructure and combine**
```lean
by
  obtain ⟨x, hx⟩ := exists_proof
  obtain ⟨y, hy⟩ := another_exists
  exact combined_lemma hx hy
```

**Pattern 5: Work with what you have (avoid rearrangement)**

When a lemma gives `a + b + c = d` but you need `b = d - a - c`, extract directly with `linarith` instead of fighting commutativity:
```lean
have sum_eq : a + b + c = d := some_lemma ...
have : b = d - a - c := by linarith [sum_eq]
```

**Pattern 6: by_contra + le_antisymm (squeeze to equality)**

Prove `x = 0` from `0 ≤ x` and a contradiction assumption `x ≤ 0`:
```lean
by_contra h_ne
push_neg at h_ne
have : x = 0 := le_antisymm h_le_zero h_ge_zero
contradiction
```

## Interactive Exploration Commands

Not tactics but essential for development:

```lean
#check expr                    -- Show type
#check @theorem                -- Show with all implicit arguments
#print theorem                 -- Show definition/proof
#print axioms theorem          -- List axioms used
#eval expr                     -- Evaluate (computable only)

-- In tactic mode
trace "Current goal: {·}"

-- Debug instance synthesis
set_option trace.Meta.synthInstance true in
theorem my_theorem : Goal := by apply_instance
```

## Tactic Selection Decision Tree

```
What am I trying to do?

├─ Close goal with term I have
│  └─ exact term

├─ Apply lemma but need to prove premises
│  └─ apply lemma

├─ Prove equality
│  ├─ Definitionally equal? → rfl
│  ├─ Need rewrites? → rw [lemmas]
│  ├─ Need normalization? → simp / ring / norm_num
│  └─ Functions equal pointwise? → ext / funext

├─ Split into cases
│  ├─ On decidable prop? → by_cases
│  ├─ On inductive type? → cases / induction
│  └─ Destruct exists/and/or? → rcases / obtain

├─ Prove exists
│  └─ use witness

├─ Prove and
│  └─ constructor (or ⟨proof1, proof2⟩)

└─ Unsure / Complex
   └─ simp? / exact? / apply?  (exploration tactics)
```

## Advanced Patterns

### Calc Mode (Transitive Reasoning)

```lean
calc
  a = b := by proof1
  _ = c := by proof2
  _ = d := by proof3
-- Chains equalities/inequalities
```

### Conv Mode (Rewrite Specific Subterms)

```lean
conv => {
  lhs           -- Focus on left-hand side
  arg 2         -- Focus on 2nd argument
  rw [lemma]    -- Rewrite there
}
```

### Tactic Sequences

```lean
-- Sequential (each line is one tactic)
by
  line1
  line2
  line3

-- Chained with semicolon (all get same tactic)
by constructor <;> simp  -- Apply simp to both goals

-- Focused with bullets
by
  constructor
  · -- First goal
    sorry
  · -- Second goal
    sorry
```
