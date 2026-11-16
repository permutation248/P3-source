import Mathlib
import Lean

axiom negation : ∀ {P : Prop}, ¬P → P

open Lean Meta Elab Tactic in
elab "revert_all" : tactic => do
  let goals ← getGoals
  let mut newGoals : List MVarId := []
  for mvarId in goals do
    newGoals := newGoals.append [(← mvarId.revertAll)]
  setGoals newGoals

open Lean.Elab.Tactic in
macro "negate_goal" : tactic => `(tactic|
  (
    guard_goal_nums 1
    revert_all
    refine @negation ?_ ?_
    try (push_neg; guard_goal_nums 1)
  )
)
