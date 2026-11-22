from dataclasses import replace
from itertools import permutations

import numpy as np
import pandas as pd
import pytest

from experiments.preliminary import OBJECTIVES, min_transverse_gm, observed_front
from stowage.algorithms.decoder import decode_permutation
from stowage.config import load_project_config
from stowage.domain.container import Container
from stowage.model.evaluation import evaluate_plan
from stowage.viz.pareto import plot_pareto, plot_run_comparison


def test_observed_front_excludes_dominated_duplicate_and_invalid_points():
    rows = [
        (10, 0, 0.1, 0.3, True),
        (10, 0, 0.1, 0.3, True),   # тот же вектор с другого seed
        (10, 0, 0.2, 0.2, True),   # компромисс по дифференту
        (10, 1, 0.2, 0.3, True),   # доминируется первой точкой
        (10, 0, 0.0, 0.0, False),  # не участвует в сравнении
        (50, 1, 0.4, 0.4, True),   # другой сценарий
    ]
    solutions = pd.DataFrame(rows, columns=["scenario", *OBJECTIVES, "is_valid"])

    assert observed_front(solutions).index.tolist() == [0, 2, 5]


def test_gm_lower_bound_matches_enumeration_when_cargo_uses_two_tiers():
    config = load_project_config()
    vessel = replace(config.vessel, bays=1, rows=2)
    config = replace(config, vessel=vessel)
    cargo = tuple(Container(i, mass, config.ports.rotation.ports[0], "dry")
                  for i, mass in enumerate((5000, 10000, 20000)))
    evaluated = [
        evaluate_plan(decode_permutation(vessel, cargo, order), config.ports.rotation, config.limits)
        .hydrostatics[4]
        for order in permutations(range(len(cargo)))
    ]
    assert min(evaluated) < max(evaluated)
    assert min_transverse_gm(cargo, config) == pytest.approx(min(evaluated))


def test_pareto_uses_observed_r_heel_and_trim_values():
    solutions = pd.DataFrame([
        dict(scenario=50, method="heuristic", r=8, abs_heel_deg=0.09, abs_trim_m=0.05),
        dict(scenario=50, method="nsga2", r=2, abs_heel_deg=0.04, abs_trim_m=0.02),
        dict(scenario=50, method="nsga2", r=0, abs_heel_deg=0.06, abs_trim_m=0.03),
    ])
    figure = plot_pareto(solutions, solutions.iloc[1:])
    front, baseline = figure.axes[0].collections

    np.testing.assert_allclose(front.get_offsets(), [(2, 0.04), (0, 0.06)])
    np.testing.assert_allclose(front.get_array(), [0.02, 0.03])
    np.testing.assert_allclose(baseline.get_offsets(), [(8, 0.09)])
    np.testing.assert_allclose(baseline.get_array(), [0.05])


def test_comparison_plot_keeps_seed_runs_and_their_baseline_separate():
    runs = pd.DataFrame([
        dict(scenario=50, method="heuristic", seed=None, n_valid=1,
             min_r=8, min_abs_heel_deg=0.09, min_abs_trim_m=0.05),
        dict(scenario=50, method="nsga2", seed=42, n_valid=3,
             min_r=0, min_abs_heel_deg=0.03, min_abs_trim_m=0.02),
        dict(scenario=50, method="nsga2", seed=43, n_valid=2,
             min_r=1, min_abs_heel_deg=0.02, min_abs_trim_m=0.04),
    ])
    figure = plot_run_comparison(runs)
    for ax, y, baseline in zip(figure.axes, ([0, 1], [0.03, 0.02], [0.02, 0.04]),
                              (8, 0.09, 0.05), strict=True):
        np.testing.assert_allclose(ax.collections[0].get_offsets(), list(zip([42, 43], y)))
        np.testing.assert_allclose(ax.lines[0].get_ydata(), [baseline, baseline])
