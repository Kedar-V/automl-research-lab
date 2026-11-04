// Keep in sync with mini_loop/graph.py (filled) and student_loop/graph.py (skeleton)

export interface Snippet {
  id: string
  title: string
  hint: string
  code: string
}

export const STACK_CMD = `make up
cd frontend && npm install && npm run dev`

export const STATUS_CMD = 'python -m student_loop.run_cli --status'

export const NODE_SNIPPETS: Snippet[] = [
  {
    id: 'data_scientist',
    title: 'node_data_scientist',
    hint: 'Replace the raise. All logic stays in this function — no helpers module.',
    code: `df = pd.read_csv(state["dataset_path"])
target = state["target_column"]
drops = [
    c
    for c in df.columns
    if c != target
    and (
        c.lower().endswith("_id")
        or c.lower() in {"passengerid", "name", "ticket", "cabin", "timestamp", "fraud_probability"}
    )
]
nums = [
    c
    for c in df.columns
    if c != target and c not in drops and pd.api.types.is_numeric_dtype(df[c])
]
profile = {
    "n_rows": len(df),
    "n_columns": len(df.columns),
    "target": target,
    "target_rate": float(df[target].mean()) if pd.api.types.is_numeric_dtype(df[target]) else None,
    "numeric_features": nums,
    "recommended_drops": drops,
}
return {
    "profile": profile,
    "steps": [{"node": "data_scientist", "note": f"profiled {len(df)} rows"}],
}`,
  },
  {
    id: 'hypothesis',
    title: 'node_hypothesis',
    hint: 'One experiment per cycle — vary LogisticRegression C.',
    code: `profile = state.get("profile") or {}
cycle = int(state.get("cycle") or 0)
c_values = [0.25, 1.0, 4.0]
spec = {
    "experiment_id": f"exp-{cycle + 1}",
    "model_family": "logistic_regression",
    "hyperparameters": {"C": c_values[cycle % len(c_values)], "max_iter": 500},
    "drop_columns": list(profile.get("recommended_drops") or []),
    "rationale": f"try C={c_values[cycle % len(c_values)]}",
}
return {
    "experiment_spec": spec,
    "steps": [{"node": "hypothesis_generator", "note": spec["rationale"], "spec": spec}],
}`,
  },
  {
    id: 'ml_engineer',
    title: 'node_ml_engineer',
    hint: 'Seal holdout first, train/val only, bump cycle, track best F1.',
    code: `df = pd.read_csv(state["dataset_path"])
target = state["target_column"]
spec = dict(state.get("experiment_spec") or {})
drops = [c for c in (spec.get("drop_columns") or []) if c in df.columns and c != target]
seed = int(state.get("seed") or 42)
holdout_frac = float(state.get("holdout_frac") or 0.2)

y = df[target]
X = df.drop(columns=[target, *drops], errors="ignore").select_dtypes("number").fillna(0)
strat = y if y.nunique() > 1 else None
X_tmp, _X_hold, y_tmp, _y_hold = train_test_split(
    X, y, test_size=holdout_frac, random_state=seed, stratify=strat
)
X_train, X_val, y_train, y_val = train_test_split(
    X_tmp, y_tmp, test_size=0.25, random_state=seed, stratify=y_tmp if y_tmp.nunique() > 1 else None
)

hp = dict(spec.get("hyperparameters") or {})
clf = LogisticRegression(
    C=float(hp.get("C", 1.0)),
    max_iter=int(hp.get("max_iter", 500)),
    class_weight="balanced",
)
clf.fit(X_train, y_train)
f1 = float(f1_score(y_val, clf.predict(X_val), zero_division=0))

result = {
    "status": "succeeded",
    "experiment_id": spec.get("experiment_id"),
    "model_family": spec.get("model_family"),
    "validation_metrics": {"f1": f1},
    "n_train": len(X_train),
    "n_val": len(X_val),
    "n_holdout": len(_X_hold),
}
cycle = int(state.get("cycle") or 0) + 1
patch: dict = {
    "execution_result": result,
    "cycle": cycle,
    "steps": [{"node": "ml_engineer", "note": f"f1={f1:.3f}", "f1": f1}],
}
if f1 > float(state.get("best_val_f1") or -1):
    patch["best_val_f1"] = f1
    patch["best_spec"] = spec
return patch`,
  },
  {
    id: 'judge',
    title: 'node_judge',
    hint: 'Compare val F1 to target_score → accept / revise.',
    code: `result = state.get("execution_result") or {}
f1 = float((result.get("validation_metrics") or {}).get("f1") or 0)
target = float(state.get("target_score") or 0.8)
action = "accept" if f1 >= target else "revise"
verdict = {"action": action, "observation": f"val f1={f1:.3f} vs target {target}"}
return {
    "verdict": verdict,
    "steps": [{"node": "judge", "note": action, "verdict": verdict}],
}`,
  },
  {
    id: 'memory_writer',
    title: 'node_memory_writer',
    hint: 'Append this cycle into memory history + lessons.',
    code: `mem = dict(state.get("memory") or {"history": [], "findings": [], "lessons": []})
hist = list(mem.get("history") or [])
hist.append(
    {
        "cycle": state.get("cycle"),
        "spec": state.get("experiment_spec"),
        "f1": (state.get("execution_result") or {}).get("validation_metrics", {}).get("f1"),
        "verdict": state.get("verdict"),
    }
)
mem["history"] = hist
lessons = list(mem.get("lessons") or [])
lessons.append(str((state.get("verdict") or {}).get("observation") or ""))
mem["lessons"] = lessons
return {"memory": mem, "steps": [{"node": "memory_writer", "note": "filed lesson"}]}`,
  },
  {
    id: 'context_builder',
    title: 'node_context_builder',
    hint: 'Short brief for the next hypothesis from recent memory.',
    code: `mem = state.get("memory") or {}
brief = {
    "history": mem.get("history") or [],
    "lessons": (mem.get("lessons") or [])[-3:],
}
return {"brief": brief, "steps": [{"node": "context_builder", "note": "next brief"}]}`,
  },
  {
    id: 'holdout',
    title: 'node_holdout',
    hint: 'Same seed split as ml_engineer — score holdout once with best_spec.',
    code: `df = pd.read_csv(state["dataset_path"])
target = state["target_column"]
spec = state.get("best_spec") or state.get("experiment_spec") or {}
drops = [c for c in (spec.get("drop_columns") or []) if c in df.columns and c != target]
seed = int(state.get("seed") or 42)
holdout_frac = float(state.get("holdout_frac") or 0.2)

y = df[target]
X = df.drop(columns=[target, *drops], errors="ignore").select_dtypes("number").fillna(0)
strat = y if y.nunique() > 1 else None
X_tmp, X_hold, y_tmp, y_hold = train_test_split(
    X, y, test_size=holdout_frac, random_state=seed, stratify=strat
)
hp = dict(spec.get("hyperparameters") or {})
clf = LogisticRegression(
    C=float(hp.get("C", 1.0)),
    max_iter=int(hp.get("max_iter", 500)),
    class_weight="balanced",
)
clf.fit(X_tmp, y_tmp)
f1 = float(f1_score(y_hold, clf.predict(X_hold), zero_division=0))
metrics = {"f1": f1, "n_holdout": len(X_hold)}
return {
    "holdout_metrics": metrics,
    "stop_reason": "finalize",
    "steps": [{"node": "holdout_eval", "note": "sealed holdout", "metrics": metrics}],
}`,
  },
  {
    id: 'router',
    title: 'route_after_judge',
    hint: 'Must return "holdout" or "memory" (keys in conditional_edges).',
    code: `action = str((state.get("verdict") or {}).get("action") or "stop")
cycle = int(state.get("cycle") or 0)
max_cycles = int(state.get("max_cycles") or 3)
if action == "accept":
    return "holdout"
if action == "revise" and cycle < max_cycles:
    return "memory"
return "holdout"`,
  },
]

export const BUILD_GRAPH_SNIPPET = `g.add_node("data_scientist", node_data_scientist)
g.add_node("hypothesis_generator", node_hypothesis)
g.add_node("ml_engineer", node_ml_engineer)
g.add_node("judge", node_judge)
g.add_node("memory_writer", node_memory_writer)
g.add_node("context_builder", node_context_builder)
g.add_node("holdout_eval", node_holdout)

g.add_edge(START, "data_scientist")
g.add_edge("data_scientist", "hypothesis_generator")
g.add_edge("hypothesis_generator", "ml_engineer")
g.add_edge("ml_engineer", "judge")
g.add_conditional_edges(
    "judge",
    route_after_judge,
    {
        "memory": "memory_writer",
        "holdout": "holdout_eval",
    },
)
g.add_edge("memory_writer", "context_builder")
g.add_edge("context_builder", "hypothesis_generator")  # loop back
g.add_edge("holdout_eval", END)
return g.compile()`
