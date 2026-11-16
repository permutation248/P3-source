# Negation Workflow Reference

How to disprove a statement using `negate_goal` and `quickcheck`.

## When to Use

- Forward proof is stuck and you suspect the statement is false
- After exhausting normal tactic strategies (simp, grind, omega, aesop, etc.)
- Before giving up on a sorry

## `negate_goal` Tactic

**Import:** `import Tacs.Negate`

**What it does:**
1. `guard_goal_nums 1` — ensures exactly one goal
2. `revert_all` — reverts all hypotheses into the goal
3. `refine @negation ?_ ?_` — applies the `negation` axiom, flipping the goal to its negation
4. `push_neg` — simplifies negated quantifiers/connectives

**Usage:**
```lean
import Tacs.Negate

theorem T_counterexample : P := by
  negate_goal
  -- Goal is now ¬P (with push_neg applied)
  -- Prove the negation here
```

**Axiom:** Uses `axiom negation : ∀ {P : Prop}, ¬P → P` from `Tacs.Negate`. This is a trusted axiom in this project — proofs using `negate_goal` will show `negation` in `#print axioms`.

## `quickcheck` as Exploration Tool

**Import:** `import Quickcheck`

**Purpose:** Find counterexamples when you are NOT sure whether the statement is false. Do NOT use quickcheck when you already know a counterexample.

**IMPORTANT:** `quickcheck` is NOT a proof step. It is purely an exploration/diagnostic tool.

### Tactic mode (view output only)

```lean
import Quickcheck

example (xs ys : Array Nat) : xs.size = ys.size → xs = ys := by
  /--
  ===================
  Found a counter-example!
  xs := #[0]
  ys := #[1]
  guard: 1 = 1
  issue: #[0] = #[1] does not hold
  (0 shrinks)
  -------------------
  -/
  quickcheck
```

### Eval mode (standalone)

```lean
#eval Quickcheck.Testable.check <| ∀ (xs ys : Array Nat), xs.size = ys.size → xs = ys
```

### Limitations

- Probabilistic — may miss counterexamples
- Only works for types with `Arbitrary` / `Testable` instances
- Cannot serve as a proof term — only provides hints

## Workflow

### Case 1: Counterexample already known

Skip quickcheck. Go directly to `negate_goal` and prove the negation.

```lean
import Tacs.Negate

-- Original statement is false: xs = #[0], ys = #[1] is a counterexample
theorem T_counterexample : ∀ (xs ys : Array Nat), xs.size = ys.size → xs = ys := by
  negate_goal
  -- Now prove ¬(∀ xs ys, xs.size = ys.size → xs = ys)
  -- i.e., ∃ xs ys, xs.size = ys.size ∧ xs ≠ ys
  exact ⟨#[0], #[1], rfl, by decide⟩
```

### Case 2: Not sure if statement is false

1. Use `quickcheck` to explore
2. If counterexample found → proceed as Case 1
3. If no counterexample → statement may be true, continue forward proof attempts

## Artifacts

When a statement is disproved, create a counterexample lemma:

```lean
/-- Counterexample to `T`. -/
theorem T_counterexample : ¬ P := by
  -- direct proof of negation (without negate_goal, if possible)
  ...

-- OR, using negate_goal on the original statement:
/-- Disproof of `T` via negation. -/
theorem T_disproof : P := by
  negate_goal
  -- prove ¬P
  ...
```

Prefer direct `¬P` proofs when possible (no extra axiom). Use `negate_goal` when you need to keep the original statement shape (e.g., filling a sorry in-place).
