# Co-Derivation: Shared Informal Reasoning → Code + Proof Sketch

This skill follows a **Dijkstra-inspired** discipline: from a single informal reasoning trace, *simultaneously* derive the code's recursion structure and the proof's induction structure. They are not generated independently and then reconciled — they are **two views of one plan**.

## Why this matters

Conventional LLM pipelines for verified code do:

```
Spec → (Informal Reasoning₁) → Code
       → (Informal Reasoning₂) → Proof → Verify → on fail, loop
```

Two independent reasoning passes produce two artifacts that drift apart. Verification fails because the code's control flow does not match the invariants the proof needs. Iteration then re-does the reasoning from scratch.

We want instead:

```
Spec → Informal Reasoning (once) →  {Code structure,  Proof sketch}
                                     ─ structurally consistent by construction ─
       → Fill in code body + tactic details → Verify
```

What this buys you: verification failures, if they happen, are about **tactic details or missing auxiliary lemmas** — not about structural mismatches between code and proof. Iteration is cheaper and rarer.

## What "shared informal reasoning" contains

Before writing any Lean code, lock down:

1. **Algorithmic idea** — what transformation is happening (fold, map, divide-and-conquer, …).
2. **Recursion scheme** — what the input decomposes into (`[]` vs `x :: xs`, `n = 0` vs `n+1`, tree leaves vs nodes).
3. **Loop / structural invariant** — the property preserved across the recursion. Derived from the postcondition — see [invariant-first](invariant-first.md).
4. **Proof strategy** — the induction/case split that mirrors the recursion, plus the auxiliary lemmas likely needed.

All four are decided *together*, because they constrain each other. A cleverer invariant often forces a different recursion scheme, which in turn forces a different code structure. Resolving this at the reasoning stage is much cheaper than reconciling it after both artifacts exist.

## Honest scope: "sketch", not "full proof"

We do **not** claim to emit `code + fully discharged proof` in one shot. Creative steps — novel auxiliary lemmas, subtle tactic choices, quantifier instantiations — cannot in general be mechanically derived.

What we *do* co-produce:

- **Code** (full definition, compiles)
- **Proof sketch**: theorem statements of auxiliary lemmas, the induction skeleton of the main proof, each case stubbed as `sorry` or with a first-pass tactic attempt

The tactic-level filling is then a bounded, local search problem — at a granularity where current LLMs + Lean LSP tooling are strong.

## The functional dividend (Lean 4 specific)

For **structural recursion on inductive types**, Lean's equation compiler automatically generates an induction principle whose case split mirrors the function's pattern match **one-for-one**. This means structural consistency between code and proof is not something we have to *enforce* — it is delivered by the compiler.

Concrete illustration:

```lean
def append : List α → List α → List α
  | [], ys      => ys
  | x :: xs, ys => x :: append xs ys
```

Lean automatically generates:

- `append.eq_1 : append [] ys = ys`
- `append.eq_2 : append (x :: xs) ys = x :: append xs ys`
- `append.induct` — induction principle with cases `[]` and `x :: xs`

Proving associativity then follows the function's shape mechanically:

```lean
theorem append_assoc (xs ys zs : List α) :
    (xs ++ ys) ++ zs = xs ++ (ys ++ zs) := by
  induction xs with
  | nil          => rfl              -- matches append's [] case
  | cons x xs ih => simp [ih]        -- matches append's x :: xs case
```

The proof's case split mirrors the function's pattern match 1:1 — **not coincidence, but a direct consequence of the Curry-Howard-style correspondence between recursion schemes and induction principles**.

One informal reasoning decision — "structural induction on the list, base `[]`, step `x :: xs`" — simultaneously fixes:

- The code's `match` arms
- The proof's `induction … with` arms
- The shape of the induction hypothesis `ih` (given by Lean)

No reconciliation needed.

## Boundaries of the dividend

The 1:1 free correspondence is cleanest for **structural recursion**. It weakens for:

1. **Well-founded recursion** (e.g., merge sort on `length`) — the induction principle exists (`WellFoundedRecursion.induct`), but its shape is no longer a direct pattern match. Sketch must explicitly name the measure.
2. **Mutual recursion** — induction principle is a mutual one; sketches need to handle multiple goals simultaneously.
3. **Proofs needing a generalized IH** — Lean's default IH may be too weak; the sketch must say `induction … generalizing …`.

For Verina / AlgoVeri-scale tasks, the dividend holds for the majority of problems.

## How this interacts with the rest of the skill

- Phase 2 of Auto Mode (**"Derive Invariant"**) is the moment where shared reasoning is captured. Do not shortcut it.
- [invariant-first](invariant-first.md) gives the mechanics of going postcondition → invariant → recursion scheme → proof skeleton.
- When a proof sorry gets stuck (see [stuck-and-repair](stuck-and-repair.md)), the right move is usually **to revise the shared reasoning** (change the invariant, switch the recursion scheme), not to try more tactics on the current skeleton. Tactic-level stuckness is a signal that the sketch itself is wrong.
- Auxiliary lemmas discovered during proof-writing should be treated as **additions to the shared reasoning**, not afterthoughts. Extract them as `private lemma` before the main theorem — they are part of the plan.

## Checklist before writing any Lean

Before the first `def` or `theorem`, you should be able to answer:

- [ ] What is the postcondition? (Read verbatim.)
- [ ] What invariant, maintained across the recursion, implies it at termination?
- [ ] What does the input decompose into? (Base case / inductive case.)
- [ ] What is the accumulator / carried state?
- [ ] Does the invariant use Mathlib-friendly concepts? (`List.sum`, `List.length`, `Perm`, …)
- [ ] What auxiliary lemmas will the proof need? List their statements.
- [ ] Which `induction … [generalizing …]` will the main theorem use?

If any of these is unclear, the reasoning is not yet shared/complete. Do not start coding.
