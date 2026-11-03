"""Simple research loop — LangGraph orchestration.

Every node shells out to an isolated script under mini_loop/nodes/.
Router is a plain conditional edge (accept / revise / stop).
Does not touch services/orchestrator/app/graph.py.
"""

from __future__ import annotations

import json
import operator
import subprocess
import sys
from pathlib import Path
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph

ROOT = Path(__file__).resolve().parent
NODES = ROOT / "nodes"
REPO = ROOT.parent


class SimpleLoopState(TypedDict, total=False):
    dataset_path: str
    target_column: str
    target_score: float
    max_cycles: int
    cycle: int
    seed: int
    holdout_frac: float
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


def _run_node(script: str, payload: dict, timeout: int = 180) -> dict:
    path = NODES / script
    proc = subprocess.run(
        [sys.executable, str(path)],
        input=json.dumps(payload, default=str),
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(ROOT),
    )
    raw = (proc.stdout or "").strip()
    if not raw:
        raise RuntimeError(
            f"{script} produced no stdout (code={proc.returncode}): {(proc.stderr or '')[:500]}"
        )
    # Last JSON object line
    data = None
    for line in reversed(raw.splitlines()):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            data = json.loads(line)
            break
    if data is None:
        data = json.loads(raw)
    data["_returncode"] = proc.returncode
    data["_stderr"] = (proc.stderr or "")[:500] or None
    return data


def node_data_scientist(state: SimpleLoopState) -> dict:
    out = _run_node(
        "data_scientist.py",
        {
            "dataset_path": state["dataset_path"],
            "target_column": state["target_column"],
        },
    )
    return {
        "profile": out.get("profile") or {},
        "steps": [
            {
                "node": "data_scientist",
                "used_llm": out.get("used_llm"),
                "note": out.get("note"),
            }
        ],
    }


def node_hypothesis(state: SimpleLoopState) -> dict:
    out = _run_node(
        "hypothesis_generator.py",
        {
            "profile": state.get("profile") or {},
            "brief": state.get("brief") or {},
            "history": (state.get("memory") or {}).get("history")
            or (state.get("brief") or {}).get("history")
            or [],
        },
    )
    return {
        "experiment_spec": out.get("experiment_spec") or {},
        "steps": [
            {
                "node": "hypothesis_generator",
                "used_llm": out.get("used_llm"),
                "note": out.get("note"),
                "spec": out.get("experiment_spec"),
            }
        ],
    }


def node_ml_engineer(state: SimpleLoopState) -> dict:
    out = _run_node(
        "ml_engineer.py",
        {
            "dataset_path": state["dataset_path"],
            "target_column": state["target_column"],
            "experiment_spec": state.get("experiment_spec") or {},
            "seed": state.get("seed", 42),
            "holdout_frac": state.get("holdout_frac", 0.2),
            "repair_budget": 1,
        },
        timeout=240,
    )
    result = out.get("execution_result") or {}
    spec = out.get("experiment_spec") or state.get("experiment_spec") or {}
    f1 = float((result.get("validation_metrics") or {}).get("f1") or -1)
    best_f1 = float(state.get("best_val_f1") or -1)
    patch: dict = {
        "execution_result": result,
        "experiment_spec": spec,
        "cycle": int(state.get("cycle") or 0) + 1,
        "steps": [
            {
                "node": "ml_engineer",
                "repaired": out.get("repaired"),
                "used_llm_repair": out.get("used_llm_repair"),
                "note": out.get("note"),
                "f1": (result.get("validation_metrics") or {}).get("f1"),
                "experiment_id": result.get("experiment_id") or spec.get("experiment_id"),
                "model_family": result.get("model_family") or spec.get("model_family"),
                "validation_metrics": result.get("validation_metrics") or {},
                "duration_seconds": result.get("duration_sec"),
                "status": result.get("status") or "succeeded",
            }
        ],
    }
    if f1 > best_f1:
        patch["best_val_f1"] = f1
        patch["best_spec"] = spec
    return patch


def node_judge(state: SimpleLoopState) -> dict:
    out = _run_node(
        "judge.py",
        {
            "execution_result": state.get("execution_result") or {},
            "experiment_spec": state.get("experiment_spec") or {},
            "target_score": state.get("target_score", 0.8),
            "brief": state.get("brief") or {},
        },
    )
    return {
        "verdict": out.get("verdict") or {},
        "steps": [
            {
                "node": "judge",
                "used_llm": out.get("used_llm"),
                "note": out.get("note"),
                "verdict": out.get("verdict"),
            }
        ],
    }


def node_memory_writer(state: SimpleLoopState) -> dict:
    out = _run_node(
        "memory_writer.py",
        {
            "experiment_spec": state.get("experiment_spec") or {},
            "execution_result": state.get("execution_result") or {},
            "verdict": state.get("verdict") or {},
        },
    )
    return {
        "memory": out.get("memory") or {},
        "steps": [{"node": "memory_writer", "note": out.get("note")}],
    }


def node_context_builder(state: SimpleLoopState) -> dict:
    out = _run_node(
        "context_builder.py",
        {
            "profile": state.get("profile") or {},
            "memory": state.get("memory") or {},
        },
    )
    return {
        "brief": out.get("brief") or {},
        "steps": [{"node": "context_builder", "note": out.get("note")}],
    }


def node_holdout(state: SimpleLoopState) -> dict:
    best = state.get("best_spec") or state.get("experiment_spec") or {}
    out = _run_node(
        "holdout_eval.py",
        {
            "dataset_path": state["dataset_path"],
            "target_column": state["target_column"],
            "best_spec": best,
            "seed": state.get("seed", 42),
            "holdout_frac": state.get("holdout_frac", 0.2),
        },
        timeout=240,
    )
    return {
        "holdout_metrics": out.get("holdout_metrics") or {},
        "stop_reason": state.get("stop_reason") or "finalize",
        "steps": [{"node": "holdout_eval", "note": out.get("note"), "metrics": out.get("holdout_metrics")}],
    }


def route_after_judge(state: SimpleLoopState) -> str:
    """Router (plain code): accept → holdout; revise/reject → memory; else holdout."""
    action = str((state.get("verdict") or {}).get("action") or "stop")
    cycle = int(state.get("cycle") or 0)
    max_cycles = int(state.get("max_cycles") or 3)
    if action == "accept":
        return "holdout"
    if action in {"revise", "reject"} and cycle < max_cycles:
        return "memory"
    return "holdout"


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
    g.add_edge("context_builder", "hypothesis_generator")
    g.add_edge("holdout_eval", END)
    return g.compile()


def _initial_state(
    *,
    dataset_path: str,
    target_column: str,
    target_score: float,
    max_cycles: int,
    seed: int,
    holdout_frac: float,
) -> SimpleLoopState:
    mem_path = ROOT / "memory" / "research_memory.json"
    mem_path.parent.mkdir(parents=True, exist_ok=True)
    mem_path.write_text(json.dumps({"history": [], "findings": [], "lessons": []}, indent=2))
    return {
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
) -> dict:
    app = build_graph()
    initial = _initial_state(
        dataset_path=dataset_path,
        target_column=target_column,
        target_score=target_score,
        max_cycles=max_cycles,
        seed=seed,
        holdout_frac=holdout_frac,
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
):
    """Yield live graph events for the Control Center-style UI.

    Event shapes:
      {type: node_started|node_completed|router|run_completed|error, ...}
    """
    app = build_graph()
    initial = _initial_state(
        dataset_path=dataset_path,
        target_column=target_column,
        target_score=target_score,
        max_cycles=max_cycles,
        seed=seed,
        holdout_frac=holdout_frac,
    )
    yield {"type": "run_started", "dataset_path": str(Path(dataset_path).resolve()), "target_column": target_column}

    merged: dict = dict(initial)
    last_node: str | None = None
    try:
        for update in app.stream(initial, stream_mode="updates", config={"recursion_limit": 8 + max_cycles * 6}):
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
