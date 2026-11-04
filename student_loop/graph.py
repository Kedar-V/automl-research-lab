"""STUDENT LAB — identical to mini_loop/graph.py; fill the empty bodies.

Copy each function body from mini_loop/graph.py (or the Guide). When build_graph
is wired, this file should match the reference line-for-line except these stubs.

Simple research loop — one self-contained LangGraph file.

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
    raise NotImplementedError("data_scientist")


def node_hypothesis(state: SimpleLoopState) -> dict:
    """Propose one tiny experiment (vary C each cycle)."""
    raise NotImplementedError("hypothesis_generator")


def node_ml_engineer(state: SimpleLoopState) -> dict:
    """Train on train/val only. Holdout rows are split away and NOT scored here."""
    raise NotImplementedError("ml_engineer")


def node_judge(state: SimpleLoopState) -> dict:
    """Decide accept (good enough) vs revise (try again)."""
    raise NotImplementedError("judge")


def node_memory_writer(state: SimpleLoopState) -> dict:
    """Append this cycle's lesson so the next hypothesis can see history."""
    raise NotImplementedError("memory_writer")


def node_context_builder(state: SimpleLoopState) -> dict:
    """Build a short brief for the next hypothesis from recent memory."""
    raise NotImplementedError("context_builder")


def node_holdout(state: SimpleLoopState) -> dict:
    """Score the best spec ONCE on the sealed holdout (same seed as ml_engineer)."""
    raise NotImplementedError("holdout_eval")


def route_after_judge(state: SimpleLoopState) -> str:
    """Router = plain code (not an LLM). Return a key from conditional_edges.

    accept              → holdout
    revise + budget left → memory (loop)
    otherwise           → holdout
    """
    raise NotImplementedError("router")

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

    # TODO: paste add_node / add_edge / add_conditional_edges / return g.compile()
    # from mini_loop/graph.py (identical block).
    raise NotImplementedError("wire nodes and edges, then return g.compile()")



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
