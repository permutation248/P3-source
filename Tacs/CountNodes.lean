import Lean

open Lean Meta
open Lean.Elab.Tactic
set_option maxHeartbeats 0

/-- Maximum recursion unfolding depth -/
def maxUnfoldDepth : Nat := 30

/-- Use StateT to share visited set, avoiding duplicate unfolding -/
abbrev CollectM := StateT NameSet MetaM

/-- Recursively unfold definitions and collect all constants in the expression -/
partial def collectAllConsts (e : Expr) (depth : Nat := 0) : CollectM NameSet := do
  -- Stop unfolding if depth limit exceeded
  if depth > maxUnfoldDepth then
    return NameSet.empty

  match e with
  | .const name _ =>
    let visited ← get
    -- Avoid infinite recursion
    if visited.contains name then
      return NameSet.empty
    -- Mark as visited
    modify (·.insert name)
    -- Try to unfold the definition of this constant
    if let some info := (← getEnv).find? name then
      match info with
      | .defnInfo val =>
        -- Recursively unfold the definition body with increased depth
        let innerOps ← collectAllConsts val.value (depth + 1)
        return innerOps.insert name
      | _ =>
        return NameSet.empty.insert name
    else
      return NameSet.empty.insert name
  | .app f a =>
    let r1 ← collectAllConsts f depth
    let r2 ← collectAllConsts a depth
    return r1.insertMany r2
  | .lam _ d b _ =>
    let r1 ← collectAllConsts d depth
    let r2 ← collectAllConsts b depth
    return r1.insertMany r2
  | .forallE _ d b _ =>
    let r1 ← collectAllConsts d depth
    let r2 ← collectAllConsts b depth
    return r1.insertMany r2
  | .letE _ t v b _ =>
    let r1 ← collectAllConsts t depth
    let r2 ← collectAllConsts v depth
    let r3 ← collectAllConsts b depth
    return r1.insertMany r2 |>.insertMany r3
  | .mdata _ e => collectAllConsts e depth
  | .proj typeName _ e =>
    let eOps ← collectAllConsts e depth
    return eOps.insert typeName
  | _ => return NameSet.empty

/-- Run collectAllConsts and return the result -/
def runCollectAllConsts (e : Expr) : MetaM NameSet := do
  let (result, _) ← collectAllConsts e |>.run NameSet.empty
  return result

/-- Format constants as JSON array for easy extraction -/
private def formatConstsJson (consts : NameSet) : String :=
  let names := consts.toList.map (fun n => s!"\"{n}\"")
  "[" ++ String.intercalate ", " names ++ "]"

/-- Tactic to count all constants in the current goal's type -/
syntax (name := countNodes) "countNodes" : tactic
elab_rules : tactic
  | `(tactic| countNodes) => do
    let goal ← getMainGoal
    goal.withContext do
      let goalType ← goal.getType
      let ops ← runCollectAllConsts goalType
      logInfo m!"CONSTS_COUNT: {ops.size}"
      logInfo m!"CONSTS_JSON: {formatConstsJson ops}"

/-- Tactic to count all constants in goal + all hypotheses -/
syntax (name := countNodesAll) "countNodesAll" : tactic
elab_rules : tactic
  | `(tactic| countNodesAll) => do
    let goal ← getMainGoal
    goal.withContext do
      let goalType ← goal.getType
      -- Use shared state to collect all constants
      let (goalOps, visited) ← collectAllConsts goalType |>.run NameSet.empty
      let mut allOps := goalOps
      let mut sharedVisited := visited
      -- Collect constants from all hypotheses
      let lctx ← getLCtx
      for ldecl in lctx do
        unless ldecl.isAuxDecl do
          let (hypOps, newVisited) ← collectAllConsts ldecl.type |>.run sharedVisited
          allOps := allOps.insertMany hypOps
          sharedVisited := newVisited
      logInfo m!"CONSTS_COUNT: {allOps.size}"
      logInfo m!"CONSTS_JSON: {formatConstsJson allOps}"
