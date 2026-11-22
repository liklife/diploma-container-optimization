import pytest

from stowage.algorithms.heuristic import run_heuristic
from stowage.algorithms.solver import solve
from stowage.config import load_project_config
from stowage.domain.container import Container
from stowage.model.evaluation import evaluate_plan


@pytest.fixture
def scenario():
    config = load_project_config()
    early, middle, late = config.ports.rotation.ports
    cargo = (
        Container(9001, 10_000, early, "dry"),
        Container(0, 20_000, middle, "dry"),
        Container(42, 20_000, late, "dry"),
    )
    return config.vessel, cargo, config.ports.rotation, config.limits


def test_heuristic_sorts_by_mass_and_preserves_input_order_for_ties(scenario):
    vessel, cargo, rotation, limits = scenario
    plan, evaluation = run_heuristic(*scenario)

    assert tuple(container_id for container_id, _ in plan.placements) == (0, 42, 9001)
    assert plan.containers == cargo
    assert evaluation == evaluate_plan(plan, rotation, limits)
    assert evaluation.is_valid
    result = solve(*scenario, method="heuristic")
    assert result.status == "ok"
    assert result.solutions == ((plan, evaluation),)
    assert result.n_evaluations == 1
    assert result.seed is None and result.reason is None


def test_heuristic_exposes_rejected_plan_but_solver_keeps_no_solution(scenario):
    vessel, cargo, rotation, limits = scenario
    scenario = vessel, (*cargo, Container(77, 40_000, cargo[0].port, "dry")), rotation, limits
    plan, evaluation = run_heuristic(*scenario)
    assert len(plan.placements) == 4
    assert evaluation.is_valid is False
    assert any(message.startswith("container_mass:") for message in evaluation.violations)

    result = solve(*scenario, method="heuristic")
    assert result.status == "no_feasible_solution"
    assert result.solutions == ()
    assert "container_mass:" in result.reason
