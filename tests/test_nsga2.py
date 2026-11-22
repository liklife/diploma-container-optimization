from dataclasses import replace

import numpy as np
import pytest
from pymoo.algorithms.moo.nsga2 import NSGA2
from pymoo.operators.crossover.ox import OrderCrossover
from pymoo.operators.mutation.inversion import InversionMutation
from pymoo.operators.sampling.rnd import PermutationRandomSampling

from stowage.algorithms import nsga2
from stowage.algorithms.pymoo_problem import StowageProblem
from stowage.algorithms.solver import solve
from stowage.config import load_project_config
from stowage.domain.container import Container
from stowage.model.constraints import check_plan


@pytest.fixture
def scenario():
    config = load_project_config()
    ports = config.ports.rotation.ports
    cargo = tuple(
        Container(7 * i, 8000 + 500 * i, ports[i % len(ports)], "dry")
        for i in range(10)
    )
    return config.vessel, cargo, config.ports.rotation, config.limits


def test_real_nsga2_evaluates_permutations_and_repeats_with_same_seed(scenario, monkeypatch):
    original_minimize = nsga2.minimize
    original_evaluate = StowageProblem._evaluate
    candidates = []

    def verify_operators(problem, algorithm, termination, **kwargs):
        assert isinstance(algorithm, NSGA2)
        assert isinstance(algorithm.initialization.sampling, PermutationRandomSampling)
        assert isinstance(algorithm.mating.crossover, OrderCrossover)
        assert isinstance(algorithm.mating.mutation, InversionMutation)
        return original_minimize(problem, algorithm, termination, **kwargs)

    def verify_candidate(problem, order, out, *args, **kwargs):
        assert np.issubdtype(order.dtype, np.integer)
        assert sorted(order) == list(range(len(scenario[1])))
        candidates.append(tuple(order))
        return original_evaluate(problem, order, out, *args, **kwargs)

    monkeypatch.setattr(nsga2, "minimize", verify_operators)
    monkeypatch.setattr(StowageProblem, "_evaluate", verify_candidate)
    options = dict(method="nsga2", seed=42, pop_size=16, generations=6)
    first = solve(*scenario, **options)
    assert len(candidates) == first.n_evaluations == 16 * 6
    assert len(set(candidates)) > 16
    assert first == solve(*scenario, **options)
    assert first.status == "ok"
    assert first.reason is None
    assert len(first.solutions) > 1
    assert len({plan.placements for plan, _ in first.solutions}) == len(first.solutions)
    assert (first.seed, first.pop_size, first.generations) == (42, 16, 6)
    for plan, evaluation in first.solutions:
        assert check_plan(plan, scenario[3]) == (True, ())
        assert evaluation.objectives[0] == 0


def test_stacked_scenario_can_generate_nonzero_r(scenario):
    vessel, cargo, rotation, limits = scenario
    vessel = replace(vessel, bays=1, rows=4, first_bay_offset_m=60)
    problem = StowageProblem(vessel, cargo, rotation, limits)
    plan, evaluation = problem.evaluate_permutation(range(len(cargo)))
    assert max(slot.tier for _, slot in plan.placements) == 2
    # В каждой колонне ранги портов сравниваются между всеми занятыми ярусами.
    assert evaluation.blocking_pairs == 5

    result = solve(
        vessel, cargo, rotation, limits, method="nsga2", seed=42,
        pop_size=16, generations=6,
    )
    assert result.status == "ok"
    assert all(check_plan(plan, limits)[0] for plan, _ in result.solutions)


def test_nsga2_reports_no_feasible_solution_for_insufficient_slots(scenario):
    vessel, cargo, rotation, limits = scenario
    vessel = replace(vessel, bays=1, rows=1, tiers=1)
    result = solve(
        vessel, cargo, rotation, limits, method="nsga2", seed=42,
        pop_size=6, generations=3,
    )

    assert result.status == "no_feasible_solution"
    assert result.reason
    assert result.solutions == ()
    assert result.n_evaluations == 18


@pytest.mark.parametrize("count", [0, 1])
def test_single_possible_permutation_is_evaluated_directly(scenario, count):
    vessel, cargo, rotation, limits = scenario
    result = solve(
        vessel, cargo[:count], rotation, limits, method="nsga2", seed=42,
        pop_size=6, generations=3,
    )
    assert result.status == "ok"
    assert result.n_evaluations == 1
    assert len(result.solutions[0][0].placements) == count


@pytest.mark.parametrize("invalid", [{"seed": None}, {"seed": -1}, {"pop_size": 0}, {"generations": 0}])
def test_nsga2_requires_explicit_valid_search_parameters(scenario, invalid):
    options = dict(seed=42, pop_size=16, generations=6) | invalid
    with pytest.raises(ValueError):
        solve(*scenario, method="nsga2", **options)
