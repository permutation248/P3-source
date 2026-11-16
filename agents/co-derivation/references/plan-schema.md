# Plan Schema

The Phase 2 output of the co-derivation workflow is a **purely informal** reasoning document. It describes the algorithmic idea, the invariant, and the proof strategy **in prose** — never in Lean syntax. The plan is the single source of truth for Phase 4 subagents, who **interpret** the prose into formal Lean code (definitions) and formal Lean statements (proof sketch).

The clean separation:

- **Plan (`.plan.md`)** — informal reasoning artifact. Prose only. The *intent*.
- **Code (`.lean`)** — formal Lean definitions. The *implementation*.
- **Proof sketch (`.lean`)** — formal Lean lemma statements with `:= by sorry`. The *theorem scaffolding*.

The plan must be **precise enough** that two subagents reading it produce structurally identical Lean artifacts, but it must **never contain Lean syntax** — that is the subagent's job.

## File conventions

- **Location**: same directory as the target Lean file.
- **Name**: if target is `Foo.lean`, plan is `Foo.plan.md`.
- **Scope**: one plan per target Lean file. Multiple related declarations go under one plan's `## Target`.
- **Mutability**: revised in place during `When stuck`. Prior versions live in git — commit after each stable revision.
- **Format**: Markdown with the required sections below. **No ```lean fences, no type signatures in Lean syntax, no tactic snippets.** Writing `acc + remaining.sum` is prose notation (acceptable as disambiguation); writing `acc + remaining.sum : Int` or wrapping it in a ```lean block is not.

## What counts as "prose" vs "Lean syntax"

Borderline cases come up — here is the rule:

- **OK (prose notation)**: using identifier names like `acc`, `xs`, `remaining` to be precise; describing values with mathematical notation like `0`, `acc + head`, `the sum of remaining elements`.
- **OK (names of Lean artifacts)**: naming the target function or theorem that already exists in the `.lean` file (e.g., "the function `sumList`"). You are *referring* to a formal artifact, not authoring new Lean.
- **Not OK**: Lean type annotations (`: List Int`, `→`), ```lean fences, multi-line tactic script, pattern syntax (`x :: xs` in a code context), lemma type signatures.
- **Single carve-out — `expected closer`**: the per-case one-line tactic hint in `## Proof strategy` is *allowed* Lean tactic syntax (`omega`, `simp [<def>]; split_ifs`, `exact <lemma>`, `linarith [<hyp>]`, etc.). Keep it to one line. If your expected closer grows to a multi-line script, move that content back into prose and leave only the first-try tactic.

If you find yourself wanting to write Lean syntax outside the expected-closer carve-out, rewrite the same content as prose. "The invariant is `acc + remaining.sum = xs.sum`" should be "the accumulator plus the sum of the remaining list equals the total sum of the original input."

## Required sections (in order)

### `## Target`

The declarations this plan covers. Name them (they already exist in the `.lean` file as `sorry` stubs) with short natural-language descriptions:

```
- Definition `sumList` — takes a list of integers and returns their sum.
- Theorem `sumList_correct` — states that `sumList xs` equals the mathematical sum of the elements of `xs`.
```

### `## Restated contract`

Concise prose restatement of the spec — the anchor that every downstream layer must still satisfy. Include:

- **Inputs** and their types (in prose).
- **Preconditions**, split into individual conjuncts if compound.
- **Postconditions**, split into individual conjuncts if compound.
- **Locked algorithm**, if Phase 1 found instruction in one of the two authoritative sources (`instruction.md` in the task directory, or a file-top comment tagged `Instruction:`). If neither source was present, write `Locked algorithm: none` — **the task name is not instruction**, so a declaration called `binary_search_lower_bound` does not by itself lock the algorithm to binary search.
- **Complexity bound**, if the instruction specifies one (e.g., `Complexity: must be O(n)`). Copy it verbatim. Treat it as part of the contract — `## Algorithmic idea` picks an algorithm that meets it, and downstream phases implement and prove that algorithm.

This section is the Contract layer's entire content (together with `## Algorithmic idea`). If a later layer's revision seems to require editing this section, treat it as a Phase 1 misread: re-read the spec before editing.

```
- Inputs: a list of integers `xs`.
- Precondition: none (total function).
- Postcondition: the result equals the mathematical sum of the elements of `xs`.
- Locked algorithm: none (no instruction.md, no Instruction: comment).
```

### `## Library support`

Best-guess list of Mathlib (or local) fragments you expect to use, from prior knowledge — **not** the result of a search probe. Authored in Phase 2 without running search tools; search happens on-demand in Phase 5 for gaps this field didn't anticipate, and findings can be back-filled here so sibling sorries don't re-search.

Each entry: fully-qualified name plus a one-phrase description of where it helps. An explicit (even rough) list is preferable to empty — list fragments you *expect* to need even if you're unsure of the exact name.

```
- `List.max` — maximum element of a non-empty list; directly computes the output.
- `List.max_mem` — the max is in the list; discharges the `result ∈ lst` conjunct.
- `List.le_max_of_mem` — every element is ≤ the max; discharges the universal bound.
- `List.length_pos_iff_ne_nil` — turns the `length > 0` precondition into the `≠ []` that `List.max` expects.
```

Or, when no single library call covers the full task:

```
- `List.sum_cons` — unfolds `(x :: xs).sum` for the inductive step (algebraic rewriting).
- `Nat.add_comm`, `Nat.add_assoc` — expected arithmetic closers under `omega`/`linarith`.
- No direct silver-bullet library call; a recursion with accumulator invariant is needed.
```

Empty is acceptable only if prior knowledge genuinely offers nothing plausible (rare). This section feeds `## Algorithmic idea` (reduce-vs-derive decision) and `## Auxiliary lemmas` (tagging entries `[library]` vs `[derived]`).

### `## Algorithmic idea`

One to three sentences. What transformation is happening at a high level. Prose only.

**If `## Library support` covers the core transformation**, the first sentence must be of the form *"Reduce to `<library name>`; <one-sentence why the reduction works>."* Do not describe a roll-your-own recursion when a library covers the case — the downstream phases will produce a one-liner.

**Otherwise**, describe the fresh derivation as prose (see below).

**If the Restated contract records a complexity bound**, pick an algorithm that meets it and state its complexity explicitly at the end of this section (one phrase: *"This is `O(n)` — one `foldl` pass."*). The complexity phrase is a commitment — `## Recursion scheme` and later phases implement and prove this same algorithm. When the most obvious implementation is too expensive, recall the canonical technique for the problem shape (XOR for "single occurrence among pairs", Boyer-Moore for majority, tabular DP for LIS, etc.) and plan its proof here — a harder correctness proof on the compliant algorithm is the expected trade.

> *(Library-reduction example)* Reduce to `List.max`; the precondition provides non-emptiness, and the postcondition is exactly the conjunction `List.max_mem ∧ List.le_max_of_mem`.

> *(Derivation example)* Fold the input list left-to-right with a running accumulator that tracks the partial sum. A tail-recursive shape keeps the correctness proof clean because the induction step corresponds to consuming one element.

### `## Recursion scheme`

Describe, in prose, exactly how the recursion proceeds. Must be precise enough that two independent readers produce the same `match` structure in code and the same `induction` cases in proof.

- What the function recurses on (name the parameter).
- What decrease is used to ensure termination (structural on an inductive type, a measure like length, etc.).
- The base case — which structural shape is the stopping condition.
- The inductive case — which structural shape triggers a recursive call, and how the arguments of that recursive call relate to the current arguments.
- If there is an accumulator: its name, its initial value, and its role.

> Recurses on the input list. Termination is by structural recursion on that list.
> The base case is an empty list; in that case the function returns the current accumulator.
> The inductive case is a nonempty list — we split into a head element and a tail.
> There is one accumulator, named `acc`, initialized to zero. It holds the running partial sum of all elements already consumed.

### `## Invariant`

A precise prose description of the property preserved across recursion. Use symbolic notation for precision (this is prose, not Lean), but never wrap in ```lean fences or annotate types.

> **Invariant**: the accumulator plus the sum of the remaining list equals the total sum of the original input list.
>
> In symbols (prose): `acc + remaining.sum = original.sum`

Follow immediately with three justifications:

- **Base holds**: explain in prose why the invariant is true at the initial call (before any recursion).
  > At the first call, `acc = 0` and `remaining` is the original list. So `0 + original.sum = original.sum`, which is trivially true.
- **Preserved**: explain in prose why each recursive step preserves it. Include the algebraic identity that makes it work.
  > When we consume the head `x`, we update `acc` to `acc + x` and `remaining` to the tail. The new invariant requires `(acc + x) + tail.sum = original.sum`. By associativity of addition and the definition of list sum, `(acc + x) + tail.sum = acc + (x + tail.sum) = acc + remaining.sum`, which equals `original.sum` by the old invariant.
- **Implies postcondition at termination**: explain in prose why invariant combined with the base case reaching implies the postcondition.
  > At termination, `remaining` is empty, so `remaining.sum = 0`, and the invariant gives `acc = original.sum`. Since we return `acc`, the result equals `original.sum`, which matches the postcondition.

### `## Proof strategy`

Prose hints for the proof — NOT tactic script. For each case include **both** the prose intent and a one-line **expected closer** (the tactic you would try first). The expected closer is a hypothesis for Phase 5, not a commitment — if it doesn't close, that's a signal to escalate per the Phase 5 stuck-recovery layers.

- Name the main induction target (which parameter you induct on, and whether you need to generalize other parameters).
- Indicate that cases correspond one-to-one with the `## Recursion scheme` case split.
- For each case: one-sentence tactic intent + expected closer. Tactic categories to draw from: `omega` / `linarith` / `simp [<defs>]` / `simp_all` / `grind` / `aesop` / `exact <lemma>` / `induction` / `rw [<lemma>]`.

> **Main induction**: on the input list, generalizing the accumulator (because the accumulator varies across recursive calls and the induction hypothesis must range over all starting accumulator values).
>
> **Cases**:
>
> - Base (empty list): reduce the function to its base case and close by direct computation plus the invariant at the base point. *Expected closer*: `simp [sumList]`.
> - Inductive (head + tail): reduce by one step, apply IH with updated accumulator, close residual by algebraic rewriting of the preservation identity. *Expected closer*: `simp [sumList, List.sum_cons]; linarith [ih (acc + x)]`.

### `## Auxiliary lemmas`

Each entry describes a helper the proof will need, in prose. Do NOT write Lean type signatures. **Tag every entry**:

- `[library]` — a lemma already in `## Library support`. Used directly in the proof; no `private lemma` wrapper, no proof obligation. List these explicitly so Phase 5 subagents know which sorries close by `exact <name>`.
- `[derived]` — must be stated and proved as a local `private lemma` before the main theorem. Requires a proof idea.

For each entry:

- Natural-language statement of what the lemma says.
- Where in the proof it is used.
- For `[derived]` only: proof idea in prose.

> **`[library]` List.max_mem** — the maximum of a non-empty list is in the list.
>
> - *Used by*: the left conjunct of the main theorem's postcondition.

> **`[derived]` sumList_invariant_generalized** — for any starting accumulator and any remaining-list suffix, the function applied to them produces the accumulator plus the sum of the remaining list.
>
> - *Needed because*: the main theorem's induction cannot range over different accumulator values unless the invariant is stated generically.
> - *Proof idea*: induction on the remaining list, generalizing over the accumulator; both cases reduce by unfolding and algebraic rewriting.

If no auxiliary lemmas are needed, write `- None.` Do not omit the section.

### `## Revision anchors`

Meta-field: what this plan is uncertain about, tagged by the section that might need editing if Phase 5 gets stuck. This is what the `When stuck` flow targets.

Anchors track genuine proof-side uncertainty — a lemma name you expect but aren't sure of, an invariant phrasing that may need strengthening, a rewrite that may unfold awkwardly. If you notice the `## Algorithmic idea` itself doesn't meet a known-in-advance constraint (like a complexity bound from `## Restated contract`), that belongs in `## Algorithmic idea` as an edit now, not in anchors as a future contingency — the plan commits to one algorithm, and anchors cover the proof side of that commitment.

> - **[invariant]** If the postcondition happens to require non-negativity of the accumulator, the invariant should be strengthened with an `acc ≥ 0` conjunct; re-check after Phase 4.
> - **[proof_strategy]** The inductive case might need an additional hypothesis if `List.sum` unfolds awkwardly under the chosen rewrite tactic; if so, split the step case into sub-cases.
> - **[aux_lemmas]** A generalized form of `List.sum_cons` is expected to exist in Mathlib; if not, inline a local helper.

If no uncertainty: `- None anticipated.`

## Worked example

File `SumList.lean` containing:

```lean
def sumList : List Int → Int := fun xs => sorry

theorem sumList_correct (xs : List Int) : sumList xs = xs.sum := by sorry
```

The corresponding `SumList.plan.md`:

```markdown
## Target

- Definition `sumList` — takes a list of integers and returns their sum.
- Theorem `sumList_correct` — states that `sumList xs` equals the mathematical sum of the elements of `xs`.

## Restated contract

- Inputs: a list of integers `xs`.
- Precondition: none (total function).
- Postcondition: the result equals the mathematical sum of the elements of `xs`.
- Locked algorithm: none (no instruction.md, no Instruction: comment).

## Library support

- `List.sum` — Mathlib's list sum; appears in the postcondition as `xs.sum`.
- `List.sum_cons` — states `(x :: xs).sum = x + xs.sum`; used for the algebraic rewriting in the inductive step.
- No single lemma reduces the full task to a library call — a derivation with accumulator invariant is still needed.

## Algorithmic idea

Fold the input list left-to-right with a running accumulator that tracks the partial sum. A tail-recursive shape keeps the correctness proof clean because the induction step corresponds exactly to consuming one element from the input.

## Recursion scheme

Recurses on the input list. Termination is by structural recursion on that list.

The base case is an empty list; in that case the function returns the current accumulator.

The inductive case is a nonempty list — split into a head element and a tail. We recurse on the tail with the accumulator updated by adding the head.

There is one accumulator, named `acc`, initialized to zero. It holds the running partial sum of all elements already consumed.

## Invariant

**Invariant**: the accumulator plus the sum of the remaining list equals the total sum of the original input list.

- **Base holds**: at the initial call, `acc = 0` and `remaining` equals the original list, so `0 + original.sum = original.sum` trivially.
- **Preserved**: when consuming head `x`, update `acc` to `acc + x` and `remaining` to the tail. The new obligation `(acc + x) + tail.sum = original.sum` follows from associativity and the definition of list sum: `(acc + x) + tail.sum = acc + (x + tail.sum) = acc + remaining.sum`, equal to `original.sum` by the prior invariant.
- **Implies postcondition at termination**: when `remaining` is empty, `remaining.sum = 0`, so invariant gives `acc = original.sum`. The function returns `acc`, so result equals the original sum, matching the postcondition.

## Proof strategy

**Main induction**: on the input list, generalizing the accumulator (because the accumulator varies across recursive calls and the induction hypothesis must range over all starting accumulator values).

**Cases**:

- Base (empty list): reduce the function to its base case and close by direct computation plus the invariant at the base point. *Expected closer*: `simp [sumList]`.
- Inductive (head + tail): reduce by one step, apply IH with the updated accumulator, close residual by algebraic rewriting of the preservation identity. *Expected closer*: `simp [sumList, List.sum_cons]; linarith [ih (acc + x)]`.

## Auxiliary lemmas

**`[library]` List.sum_cons** — unfolds the sum of a cons into head plus tail sum.

- *Used by*: the preservation argument and the inductive case of the main theorem.

**`[derived]` sumList_invariant_generalized** — for any starting accumulator value and any remaining-list suffix satisfying the invariant, the function applied to them produces the total sum.

- *Needed because*: the main theorem's induction cannot range over different accumulator values unless the invariant is stated generically.
- *Proof idea*: induction on the remaining list, generalizing over the accumulator; both cases reduce by unfolding and algebraic rewriting.

## Revision anchors

- **[invariant]** If `List.sum` unfolds awkwardly under the chosen simplification tactic, consider rephrasing the invariant as `acc = original.sum - remaining.sum` — equivalent, sometimes more tractable.
- **[aux_lemmas]** `List.sum_cons` is expected in Mathlib with this name; if lookup fails, inline a local helper.
```

## How each phase consumes the plan

- **Phase 2** — produces or updates the plan file (pure prose).
- **Phase 3** — a review subagent reads the plan and checks: the complexity stated in `## Algorithmic idea` matches any Complexity bound in `## Restated contract`, and `## Invariant`'s termination justification implies the postcondition. Fail → revise the named field, re-run.
- **Phase 4** — subagents **interpret** the plan into Lean:
  - *Code subagent* reads `## Algorithmic idea` + `## Recursion scheme`, writes the formal `def` body.
  - *Proof-sketch subagent* reads `## Invariant` + `## Proof strategy` + `## Auxiliary lemmas`, writes formal `private lemma ... := by sorry` stubs and the main theorem's `induction` skeleton. It **translates prose into Lean**; it does not copy Lean verbatim from the plan (because there is none).
- **Phase 5** — subagents receive the plan plus specific sorry locations; the plan's `## Proof strategy` per-case hints seed their tactic search.
- **When stuck** — identify the plan field (or revision anchor) implicated, revise *only that field in prose*, re-enter from the earliest affected phase (re-running Phase 3 review after any Contract/Invariant edit).

## Anti-patterns

- **Lean syntax leaking into the plan.** If you find yourself typing `:`, `→`, ```lean, or `by`, you are writing formal Lean, not a plan. Rewrite as prose.
- **Vague prose.** "The invariant is roughly that the accumulator tracks partial progress" is a label, not a plan. Precise prose names variables and states relationships exactly.
- **Plan duplicating a proof sketch.** If the plan reads like a sequence of `have` statements or lemma signatures, you have collapsed the informal/formal boundary. Plan describes *what* and *why*; sketch is *how* (formally).
- **Omitting revision anchors.** A plan without anchors claims perfect confidence, which is rarely warranted. Empty anchors (`- None anticipated.`) is fine; a missing section is not.
- **Revising the whole plan on every stuck event.** Target the specific field. If every stuck triggers a full rewrite, you have reverted to propose-then-verify.
- **Empty `## Library support` without thinking.** The section must appear; its content should be populated from prior knowledge with best guesses at useful fragments. Empty content is acceptable only after genuine consideration. The section is not "optional" — missing section ≠ missing content.
- **Ignoring a library hit.** If `## Library support` names a lemma or definition that directly matches the postcondition, `## Algorithmic idea` must reduce to it. Writing a roll-your-own recursion while a library call exists is a co-derivation failure, not a stylistic choice.
