"""Student LangGraph skeleton readiness + Airflow student DAG smoke checks."""

from __future__ import annotations

from pathlib import Path

from langgraph.graph import END, START, StateGraph

from student_loop.graph import (
    REQUIRED_NODES,
    SimpleLoopState,
    assess_graph_ready,
    get_status,
)

REPO = Path(__file__).resolve().parents[2]


def test_skeleton_status_not_ready() -> None:
    status = get_status()
    assert status["ready"] is False
    assert set(status["missing_nodes"]) == set(REQUIRED_NODES)
    assert status["error"]


def test_assess_ready_when_required_nodes_present() -> None:
    def _noop(state: SimpleLoopState) -> dict:
        return {}

    g = StateGraph(SimpleLoopState)
    for name in REQUIRED_NODES:
        g.add_node(name, _noop)
    g.add_edge(START, "data_scientist")
    g.add_edge("data_scientist", "hypothesis_generator")
    g.add_edge("hypothesis_generator", "ml_engineer")
    g.add_edge("ml_engineer", "judge")
    g.add_edge("judge", "memory_writer")
    g.add_edge("memory_writer", "context_builder")
    g.add_edge("context_builder", "holdout_eval")
    g.add_edge("holdout_eval", END)
    app = g.compile()

    status = assess_graph_ready(app)
    assert status["ready"] is True
    assert status["missing_nodes"] == []
    assert set(REQUIRED_NODES).issubset(set(status["nodes"]))


def test_student_airflow_dag_is_unwired_skeleton() -> None:
    path = REPO / "airflow" / "dags" / "student_baseline_prep.py"
    text = path.read_text()
    assert 'dag_id="student_baseline_prep"' in text
    assert "# left = validate_customers()" in text
    assert "raise NotImplementedError" in text
    # Wiring must stay commented so Airflow Graph stays empty for students.
    assert "\n    left = validate_customers()\n" not in text
