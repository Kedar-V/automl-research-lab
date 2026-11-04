"""Simple research loop — one self-contained LangGraph file.

Flow:
  START → data_scientist → hypothesis → ml_engineer → judge
            ↑__________________________________|
            |   (revise: memory → context → hypothesis again)
            └── accept/stop → holdout_eval → END

No helper modules. No subprocess nodes. All logic is in the node functions below.
"""

from __future__ import annotations

import json
import operator
from pathlib import Path
from typing import Annotated, TypedDict

import pandas as pd
from langgraph.graph import END, START, StateGraph
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score
from sklearn.model_selection import train_test_split

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent


# ---------------------------------------------------------------------------
# STATE
# LangGraph keeps one shared dict ("state") that every node reads/writes.
# Each node returns a *patch* — only the keys it wants to update.
# Annotated[list, operator.add] means "append to steps" instead of replace.
# ---------------------------------------------------------------------------
class SimpleLoopState(TypedDict, total=False):
    dataset_path: str
    target_column: str
    target_score: float
    max_cycles: int
    cycle: int
    seed: int
    holdout_frac: float
    model: str  # optional OpenRouter id (unused in this heuristic demo)
    profile: dict
    brief: dict
    experiment_spec: dict
    execution_result: dict
    verdict: dict
    memory: dict
    best_spec: dict
    best_val_f1: float
    holdout_metrics: dict
    stop_reason: str
    steps: Annotated[list, operator.add]


# ---------------------------------------------------------------------------
# NODES
# A node is a plain function: state in → dict patch out.
# LangGraph calls it, merges the patch into state, then follows an edge.
# ---------------------------------------------------------------------------


def node_data_scientist(state: SimpleLoopState) -> dict:
    """Read the CSV once and describe columns (no LLM)."""
    df = pd.read_csv(state["dataset_path"])
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
    }


def node_hypothesis(state: SimpleLoopState) -> dict:
    """Propose one tiny experiment (vary C each cycle)."""
    profile = state.get("profile") or {}
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
    }


def node_ml_engineer(state: SimpleLoopState) -> dict:
    """Train on train/val only. Holdout rows are split away and NOT scored here."""
    df = pd.read_csv(state["dataset_path"])
    target = state["target_column"]
    spec = dict(state.get("experiment_spec") or {})
    drops = [c for c in (spec.get("drop_columns") or []) if c in df.columns and c != target]
    seed = int(state.get("seed") or 42)
    holdout_frac = float(state.get("holdout_frac") or 0.2)

    y = df[target]
    X = df.drop(columns=[target, *drops], errors="ignore").select_dtypes("number").fillna(0)
    strat = y if y.nunique() > 1 else None
    # First cut seals the holdout (unused until holdout_eval)
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
    return patch


def node_judge(state: SimpleLoopState) -> dict:
    """Decide accept (good enough) vs revise (try again)."""
    result = state.get("execution_result") or {}
    f1 = float((result.get("validation_metrics") or {}).get("f1") or 0)
    target = float(state.get("target_score") or 0.8)
    action = "accept" if f1 >= target else "revise"
    verdict = {"action": action, "observation": f"val f1={f1:.3f} vs target {target}"}
    return {
        "verdict": verdict,
        "steps": [{"node": "judge", "note": action, "verdict": verdict}],
    }


def node_memory_writer(state: SimpleLoopState) -> dict:
    """Append this cycle's lesson so the next hypothesis can see history."""
    mem = dict(state.get("memory") or {"history": [], "findings": [], "lessons": []})
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
    return {"memory": mem, "steps": [{"node": "memory_writer", "note": "filed lesson"}]}


def node_context_builder(state: SimpleLoopState) -> dict:
    """Build a short brief for the next hypothesis from recent memory."""
    mem = state.get("memory") or {}
    brief = {
        "history": mem.get("history") or [],
        "lessons": (mem.get("lessons") or [])[-3:],
    }
    return {"brief": brief, "steps": [{"node": "context_builder", "note": "next brief"}]}


def node_holdout(state: SimpleLoopState) -> dict:
    """Score the best spec ONCE on the sealed holdout (same seed as ml_engineer)."""
    df = pd.read_csv(state["dataset_path"])
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
    }


def route_after_judge(state: SimpleLoopState) -> str:
    """Router = plain code (not an LLM). Return a key from conditional_edges.

    accept              → holdout
    revise + budget left → memory (loop)
    otherwise           → holdout
    """
    action = str((state.get("verdict") or {}).get("action") or "stop")
    cycle = int(state.get("cycle") or 0)
    max_cycles = int(state.get("max_cycles") or 3)
    if action == "accept":
        return "holdout"
    if action == "revise" and cycle < max_cycles:
        return "memory"
    return "holdout"


# ---------------------------------------------------------------------------
# GRAPH WIRING
# StateGraph = the canvas.
# add_node(name, fn) = put a box on the canvas.
# add_edge(a, b)     = always go a → b after a finishes.
# add_conditional_edges = ask a router function which named edge to take.
# compile()          = freeze the graph into a runnable app (invoke / stream).
# ---------------------------------------------------------------------------
def build_graph():
    g = StateGraph(SimpleLoopState)

    g.add_node("data_scientist", node_data_scientist)
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
    return g.compile()



REQUIRED_NODES = frozenset(
    {
        "data_scientist",
        "hypothesis_generator",
        "ml_engineer",
        "judge",
        "memory_writer",
        "context_builder",
        "holdout_eval",
    }
)


def assess_graph_ready(app) -> dict:
    """Return readiness dict from a compiled LangGraph app."""
    raw = app.get_graph().nodes
    present = {n for n in raw if n not in {START, END, "__start__", "__end__"}}
    missing = sorted(REQUIRED_NODES - present)
    return {
        "ready": not missing,
        "nodes": sorted(present),
        "missing_nodes": missing,
        "error": None if not missing else f"missing nodes: {', '.join(missing)}",
    }


def get_status() -> dict:
    """Import-safe status for the gateway / UI."""
    try:
        app = build_graph()
    except NotImplementedError as exc:
        return {
            "ready": False,
            "nodes": [],
            "missing_nodes": sorted(REQUIRED_NODES),
            "error": str(exc) or "build_graph not implemented",
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "ready": False,
            "nodes": [],
            "missing_nodes": sorted(REQUIRED_NODES),
            "error": str(exc),
        }
    return assess_graph_ready(app)


def _initial_state(
    *,
    dataset_path: str,
    target_column: str,
    target_score: float,
    max_cycles: int,
    seed: int,
    holdout_frac: float,
    model: str | None = None,
) -> SimpleLoopState:
    state: SimpleLoopState = {
        "dataset_path": str(Path(dataset_path).resolve()),
        "target_column": target_column,
        "target_score": target_score,
        "max_cycles": max_cycles,
        "cycle": 0,
        "seed": seed,
        "holdout_frac": holdout_frac,
        "best_val_f1": -1.0,
        "steps": [],
        "memory": {"history": [], "findings": [], "lessons": []},
        "brief": {},
    }
    if model and str(model).strip():
        state["model"] = str(model).strip()
    return state


def _finalize_payload(final: dict) -> dict:
    return {
        "dataset_path": final.get("dataset_path"),
        "target_column": final.get("target_column"),
        "cycles": final.get("cycle"),
        "best_val_f1": final.get("best_val_f1"),
        "best_spec": final.get("best_spec"),
        "holdout_metrics": final.get("holdout_metrics"),
        "verdict": final.get("verdict"),
        "stop_reason": final.get("stop_reason"),
        "profile": final.get("profile"),
        "memory": final.get("memory"),
        "steps": final.get("steps") or [],
    }


def run_simple_loop(
    *,
    dataset_path: str,
    target_column: str = "Survived",
    target_score: float = 0.8,
    max_cycles: int = 3,
    seed: int = 42,
    holdout_frac: float = 0.2,
    model: str | None = None,
) -> dict:
    """Run the whole graph to completion; return a summary dict."""
    app = build_graph()
    initial = _initial_state(
        dataset_path=dataset_path,
        target_column=target_column,
        target_score=target_score,
        max_cycles=max_cycles,
        seed=seed,
        holdout_frac=holdout_frac,
        model=model,
    )
    final = app.invoke(initial, config={"recursion_limit": 8 + max_cycles * 6})
    return _finalize_payload(final)


def stream_simple_loop(
    *,
    dataset_path: str,
    target_column: str = "Survived",
    target_score: float = 0.8,
    max_cycles: int = 3,
    seed: int = 42,
    holdout_frac: float = 0.2,
    model: str | None = None,
):
    """Yield UI events as each node starts/finishes (used by the gateway SSE)."""
    app = build_graph()
    initial = _initial_state(
        dataset_path=dataset_path,
        target_column=target_column,
        target_score=target_score,
        max_cycles=max_cycles,
        seed=seed,
        holdout_frac=holdout_frac,
        model=model,
    )
    yield {
        "type": "run_started",
        "dataset_path": str(Path(dataset_path).resolve()),
        "target_column": target_column,
        "model": initial.get("model"),
    }

    merged: dict = dict(initial)
    last_node: str | None = None
    try:
        for update in app.stream(
            initial, stream_mode="updates", config={"recursion_limit": 8 + max_cycles * 6}
        ):
            if not isinstance(update, dict):
                continue
            for node_name, patch in update.items():
                if last_node == "judge" and node_name in {"memory_writer", "holdout_eval"}:
                    action = str((merged.get("verdict") or {}).get("action") or "stop")
                    yield {
                        "type": "router",
                        "node": "router",
                        "status": "completed",
                        "action": action,
                        "route": "memory" if node_name == "memory_writer" else "holdout",
                    }
                    if node_name == "memory_writer":
                        yield {
                            "type": "node_completed",
                            "node": "research_memory",
                            "status": "completed",
                            "note": "history + lessons filed",
                        }

                yield {"type": "node_started", "node": node_name, "status": "running"}
                if isinstance(patch, dict):
                    merged.update({k: v for k, v in patch.items() if k != "steps"})
                    steps = patch.get("steps") or []
                    note = steps[-1].get("note") if steps else None
                    yield {
                        "type": "node_completed",
                        "node": node_name,
                        "status": "completed",
                        "note": note,
                        "step": steps[-1] if steps else None,
                        "cycle": merged.get("cycle"),
                        "best_val_f1": merged.get("best_val_f1"),
                        "verdict": merged.get("verdict"),
                    }
                else:
                    yield {"type": "node_completed", "node": node_name, "status": "completed"}
                last_node = node_name
    except Exception as exc:  # noqa: BLE001
        yield {"type": "error", "message": str(exc)}
        return

    yield {"type": "run_completed", "result": _finalize_payload(merged)}


if __name__ == "__main__":
    ds = REPO / "datasets" / "Titanic-Dataset.csv"
    result = run_simple_loop(dataset_path=str(ds), target_column="Survived", max_cycles=3)
    print(json.dumps(result, indent=2, default=str))
