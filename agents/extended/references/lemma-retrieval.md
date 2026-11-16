# Lemma Retrieval

**Before writing any proof, search for the lemmas you will need.** Never guess lemma names with `#check` — use search tools first.

## Search Tool Selection

| Situation | Tool | Example |
|-----------|------|---------|
| Know type signature | `lean_loogle` | `"List.Sublist _ (_ ++ _)"` |
| Know concept in words | `lean_leansearch` | `"sublist cancellation on append"` |
| Know partial name | `lean_local_search` | `"Pairwise append"` |
| Inside a proof, need to close goal | `exact?` / `apply?` / `rw?` | `by exact?` |
| Verify a name returned by search | `#check` | `#check @List.pairwise_append` |

## Workflow

```
1. From the proof plan, list ALL Mathlib/stdlib facts needed by each helper lemma
2. For each needed fact, search using the table above (loogle → leansearch → local_search)
3. Collect found lemma names with confirmed signatures
4. GATE: Are ALL needed facts confirmed?
   - YES → start proving
   - NO (search returned empty) → adjust the proof plan to avoid the missing fact, then repeat from step 1
```

**The gate at step 4 is mandatory.** Do not write any proof code (Write or Edit) until every needed Mathlib fact has a confirmed name. A single missing lemma causes compilation failure → full rewrite cycle.

## Anti-Pattern: Guessing Names (STRICTLY PROHIBITED)

```
❌  #check @List.Sublist.of_append_right     → Unknown constant (wasted call)
❌  #check @List.Pairwise.head               → Unknown constant (wasted call)
❌  #check @List.getLast_cons_ne_nil          → Unknown constant (wasted call)
    ... repeat 20 times → $5 wasted, zero progress
```

**The correct approach:**
```
✅  lean_loogle("List.Sublist _ (_ ++ _)")
    → returns List.append_sublist_append_right    (1 call, correct answer)
✅  #check @List.append_sublist_append_right       (verify signature)
```

`#check` is ONLY for verifying names that came from a search tool or the Common Useful Lemmas list in [code-verification](code-verification.md). Never use it to explore whether a lemma exists.

## Anti-Pattern: Partial Search (STRICTLY PROHIBITED)

```
❌  Search 3-4 lemmas → immediately Write 10K chars of full proof
    → compile error (missing lemma) → search 1 more → Write 10K again
    → compile error → search 1 more → Write 10K again × 3
    = 50K output tokens wasted on near-identical full rewrites

✅  Search ALL needed lemmas → confirm ALL → Write once → small Edit fixes
    = ~12K output tokens
```

**Symptom:** If you find yourself searching for a Mathlib lemma *after* writing proof code, you skipped the gate. Stop, go back to the workflow, and complete the search phase before writing more code.
