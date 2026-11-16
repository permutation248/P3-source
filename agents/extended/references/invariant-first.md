# Invariant-First Design

When a function involves recursion or accumulation, derive the loop invariant from the postcondition *before* writing the implementation. The invariant determines the code structure — not the other way around.

This approach avoids the common failure mode: generating plausible-looking code, then discovering during proof that the recursion structure doesn't match what induction needs, forcing a costly rollback.

## When to Use

Apply invariant-first design when the function to implement involves:
- Recursive traversal of a list/array with an accumulator
- Dynamic programming (filling a table iteratively)
- Any loop that maintains state across iterations

For simple non-recursive functions (pure mapping, direct arithmetic), skip this — just write the code.

## The Three-Step Derivation

### Step 1: From Postcondition to Invariant

Read the postcondition and ask: *what property, if maintained at every step of the recursion, would imply the postcondition when the recursion terminates?*

**Example**: Postcondition is `result = xs.sum`.

- The function will process `xs` element by element with an accumulator `acc`.
- At any point, some prefix has been processed and the rest remains.
- Invariant: `acc + remaining.sum = xs.sum`
- When `remaining = []`: `acc + 0 = xs.sum`, so `acc = xs.sum = result`. Done.

**Example**: Postcondition is `sorted result ∧ perm result xs`.

- Invariant for insertion sort: `sorted acc ∧ perm (acc ++ remaining) xs`
- When `remaining = []`: `sorted acc ∧ perm acc xs`. Done.

### Step 2: From Invariant to Recursion Structure

The invariant dictates:
- **What to recurse on**: the `remaining` part that shrinks each step
- **What the accumulator carries**: the state mentioned in the invariant
- **How each step transforms state**: must preserve the invariant

From the invariant `acc + remaining.sum = xs.sum`:
- Recurse on `remaining` (a List)
- Each step: `acc' = acc + head`, `remaining' = tail`
- Preservation: `(acc + head) + tail.sum = acc + (head + tail.sum) = acc + remaining.sum = xs.sum` ✓

This directly translates to:
```lean
def sumList (xs : List Int) : Int :=
  xs.foldl (· + ·) 0
```

Or equivalently:
```lean
def sumList : List Int → Int → Int
  | [], acc => acc
  | x :: rest, acc => sumList rest (acc + x)
```

### Step 3: From Invariant to Proof Structure

The invariant becomes a `private lemma` proved by induction on the same structure as the code:

```lean
private lemma sumList_invariant (remaining : List Int) (acc : Int)
    (h_inv : acc + remaining.sum = total) :
    sumList remaining acc = total := by
  induction remaining generalizing acc with
  | nil => simp [sumList, List.sum_nil] at *; omega
  | cons x rest ih =>
    simp [sumList]
    apply ih
    simp [List.sum_cons] at h_inv ⊢
    omega
```

Because the code was designed to match this induction, each case aligns directly.

## Invariant Quality Checklist

A good invariant satisfies all of:

1. **Base case holds** — The invariant is true for the initial state (empty accumulator, full input).
2. **Preserved by each step** — If the invariant holds before processing one element, it holds after.
3. **Implies postcondition at termination** — Invariant ∧ (remaining = []) → postcondition.
4. **Tractable** — The invariant should use concepts that Mathlib has lemmas for. An invariant about `List.sum` is better than one about a custom recursive sum, because `List.sum_cons`, `List.sum_nil` etc. already exist.

If your invariant fails criterion 4, consider weakening it to something more Mathlib-friendly. For example:
- Instead of `acc ++ remaining ~ original` (multiset permutation), try `acc.length + remaining.length = original.length` if that suffices for the postcondition.
- Instead of tracking exact contents, track a numeric summary (length, sum, count) if the postcondition only needs that.

## Compound Postconditions

When the postcondition is a conjunction `P₁ ∧ P₂ ∧ ... ∧ Pₙ`, design a compound invariant `I₁ ∧ I₂ ∧ ... ∧ Iₙ` where each `Iₖ` implies `Pₖ` at termination. Then prove each component as a separate `private lemma` — this keeps individual proofs manageable.

## Worked Example: Count Occurrences

**Spec:**
```lean
def count_postcond (xs : List Nat) (target : Nat) (result : Nat) : Prop :=
  result = (xs.filter (· == target)).length
```

**Step 1 — Invariant:**
`acc + (remaining.filter (· == target)).length = (xs.filter (· == target)).length`

**Step 2 — Code** (follows from invariant):
```lean
def countOcc (xs : List Nat) (target : Nat) : Nat :=
  xs.foldl (fun acc x => if x == target then acc + 1 else acc) 0
```

**Step 3 — Proof skeleton:**
```lean
private lemma countOcc_inv (remaining : List Nat) (target : Nat) (acc : Nat)
    (h : acc + (remaining.filter (· == target)).length = total) :
    remaining.foldl (fun acc x => if x == target then acc + 1 else acc) acc = total := by
  induction remaining generalizing acc with
  | nil => simp [List.foldl, List.filter] at *; omega
  | cons x rest ih =>
    simp only [List.foldl, List.filter]
    split
    · apply ih; simp_all; omega
    · apply ih; simp_all
```

## Common Pitfalls

- **Writing code first, then "discovering" the invariant** — This often leads to invariants that are technically correct but hard to prove, because the code wasn't structured to make preservation obvious.
- **Invariant too strong** — If preservation is hard to prove, the invariant might include unnecessary detail. Weaken it to what the postcondition actually needs.
- **Invariant too weak** — If it doesn't imply the postcondition at termination, strengthen it. The fix is usually to add a conjunct, not to start over.
- **Mismatched recursion** — If the code recurses on `Array` indices but the invariant talks about `List` membership, the proof will require constant bridging. Align them.
