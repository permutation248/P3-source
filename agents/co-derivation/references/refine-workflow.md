# Refine Workflow Reference

> Used by `/lean4:refine` — adjust theorem statements to make them provable or stronger.
> **This workflow is ONLY invoked via explicit `/lean4:refine` command. It is NEVER triggered automatically during `autoprove`.** `autoprove` must prove statements as-is.

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

**For strengthening (after proof):**
- Check each hypothesis: try removing it, does the proof still compile?
- Check the conclusion: can the bound be tightened? Can `≤` become `<`?
- Use `lean_goal` to inspect what hypotheses are actually used
- Try generalizing concrete types to type variables

## Safety Rules

- Keep both original proof and refined version for traceability
- Refined statements must compile with no sorry and standard axioms only
- All decisions are autonomous — no user confirmation required
