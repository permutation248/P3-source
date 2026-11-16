# Calc Chain Patterns

## Overview

Calc chains are powerful for chaining equalities and inequalities, but they interact with simplification in non-obvious ways.

## Key Principles

1. **After simp, check the actual goal state FIRST** — simp may or may not simplify depending on context
2. **Start calc from whatever the goal actually is** — not what you expect it to be
3. **Use canonical forms** — be consistent within a calc chain
4. **Don't fight simp** — work with its transformations, not against them
5. **One simplification pass** — let simp do all transformations, then reason

## Critical Pattern: simp Before calc

After `simp` (or `simp only [...]`), the goal may have changed. The `calc` chain must start with **whatever form the goal is actually in** after simp runs.

```lean
-- ❌ WRONG: calc starts with pre-simp form
simp only [my_def]
calc original_form       -- simp already transformed this!
    _ = ... := by ...

-- ✅ CORRECT: check goal after simp, start from the actual state
simp only [my_def]
calc simplified_form     -- matches what simp produced
    _ = ... := by ...
```

**Debugging checklist when calc fails:**
- Did I use simp before calc?
- Did I check the actual goal state after simp? (Use LSP `lean_goal` or insert `sorry`)
- Am I starting calc from the ACTUAL goal, not the expected form?

## Common Calc Patterns

### Equality Chain

```lean
calc a
    _ = b := by rw [lemma1]
  _ = c := by ring
  _ = d := by simp [lemma2]
```

### Inequality Chain

```lean
calc a
    _ ≤ b := by omega
  _ ≤ c := by linarith [h1]
  _ ≤ d := by exact h2
```

### Mixed Chain

```lean
calc a
    _ = b := by simp [def1]
  _ ≤ c := by omega
  _ < d := by linarith
```

### Triangle Inequality

```lean
calc |f x - h x|
    _ = |f x - g x + (g x - h x)| := by ring_nf
  _ ≤ |f x - g x| + |g x - h x| := abs_add _ _
  _ ≤ bound1 + bound2 := by linarith [hf, hg]
```

## Anti-Patterns

### Redundant Steps After simp

```lean
-- ❌ BAD: manually performing what simp already did
simp only [my_def]
calc original_expr
    _ = simplified_expr := by rw [...]  -- simp already did this!
  _ ≤ ...

-- ✅ GOOD: skip straight to the reasoning
simp only [my_def]
calc simplified_expr
  _ ≤ ...
```

### Inconsistent Notation

```lean
-- ❌ BAD: mixing different representations
calc (a : Int)
    _ ≤ a.toNat := ...    -- inconsistent types

-- ✅ GOOD: consistent throughout
calc (a : Int)
    _ ≤ (b : Int) := ...
  _ ≤ (c : Int) := ...
```
