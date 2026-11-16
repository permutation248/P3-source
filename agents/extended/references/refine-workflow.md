# Refine Workflow Reference

> Used by `/lean4:refine` — adjust theorem statements to make them provable or stronger.
> **This workflow is ONLY invoked via explicit `/lean4:refine` command. It is NEVER triggered automatically during `autoprove`.** `autoprove` must prove or disprove statements as-is.

## Two Modes

| Mode | Trigger | Direction | Goal |
|------|---------|-----------|------|
| **Weaken** | Statement is false (disproved via `negate_goal` or `quickcheck`) | Relax conclusion / add hypotheses | Make it provable |
| **Strengthen** | Statement is true (already proved) | Tighten conclusion / remove hypotheses | Make it maximally informative |

## Weaken Mode

When a statement has been disproved (see [negation-workflow](negation-workflow.md)):

### Workflow

1. **Identify why it's false** — examine the counterexample
2. **Select the best weakening strategy** autonomously:
   - Fix the statement (if it's a typo/off-by-one) — preferred
   - Restrict domain (add preconditions)
   - Weaken conclusion (looser bound, weaker property)
3. **Prove the weakened version** as `T_weakened` or replace the original
4. **Verify** — compile + axiom check

### Weakening Strategies

**Add precondition:**
```lean
-- Before (false)
theorem T : ∀ xs ys : Array Nat, xs.size = ys.size → xs = ys

-- After (add stronger precondition)
theorem T_weakened : ∀ xs ys : Array Nat, xs = ys → xs.size = ys.size
```

**Restrict domain:**
```lean
-- Before (false)
theorem T : ∀ n : Fin 5, n.val < 3

-- After (restrict to Fin 3)
theorem T_weakened : ∀ n : Fin 3, n.val < 3
```

**Weaken bound:**
```lean
-- Before (false)
theorem T : ∀ n : Nat, n * n < n + 1

-- After (weaken to n = 0)
theorem T_weakened : ∀ n : Nat, n = 0 → n * n < n + 1
```

## Strengthen Mode

When a statement is already proved and you want to make it stronger:

### Workflow

1. **Analyze current statement** — what hypotheses does it use? How tight is the conclusion?
2. **Select the best strengthening strategy** autonomously:
   - Remove unnecessary hypotheses
   - Tighten conclusion (sharper bound, stronger property)
   - Generalize types (e.g., `List α` → `∀ [Membership]`)
3. **Prove the strengthened version** as `T_strengthened` or replace the original
4. **Verify** — compile + axiom check

### Strengthening Strategies

**Remove hypothesis:**
```lean
-- Before
theorem T (h : n > 0) (h2 : n < 100) : n + 1 > 1

-- After (h2 was unnecessary)
theorem T_strengthened (h : n > 0) : n + 1 > 1
```

**Tighten bound:**
```lean
-- Before
theorem T : ∀ n : Nat, n ≤ n + 10

-- After
theorem T_strengthened : ∀ n : Nat, n ≤ n + 1
```

**Generalize:**
```lean
-- Before
theorem T : ∀ l : List Nat, l.length = 0 → l = []

-- After (works for any α)
theorem T_strengthened : ∀ (α : Type) (l : List α), l.length = 0 → l = []
```

## How to Discover Refinements

**For weakening (after disproof):**
- Examine the counterexample from `quickcheck` or `negate_goal`
- Ask: "What minimal precondition would exclude this counterexample?"
- Ask: "What weaker conclusion still holds?"

**For strengthening (after proof):**
- Check each hypothesis: try removing it, does the proof still compile?
- Check the conclusion: can the bound be tightened? Can `≤` become `<`?
- Use `lean_goal` to inspect what hypotheses are actually used
- Try generalizing concrete types to type variables

## Safety Rules

- Keep both original (with counterexample or proof) and refined version for traceability
- Refined statements must compile with no sorry and standard axioms only (+ `negation` if disproved)
- All decisions are autonomous — no user confirmation required
