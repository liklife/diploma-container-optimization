import math
from dataclasses import replace

import numpy as np
import pytest

from stowage.algorithms.pymoo_problem import (
    CONSTRAINT_NAMES, StowageProblem, constraint_violations,
)
from stowage.config import load_project_config
from stowage.domain.container import Container
from stowage.domain.plan import Plan
from stowage.domain.slot import Slot
from stowage.model.constraints import check_plan
from stowage.model.evaluation import evaluate_plan


@pytest.fixture
def scenario():
    config = load_project_config()
    vessel = replace(
        config.vessel, length_m=12, beam_m=6, depth_m=8, max_draft_m=4,
        bays=1, rows=2, tiers=2, first_bay_offset_m=6,
        first_row_center_y_m=-0.5, row_spacing_m=1,
        base_height_m=1.5, container_height_m=2, tier_spacing_m=2,
        lightship_mass_kg=144_000, lightship_cg_x_m=6, lightship_cg_z_m=2,
        water_density_kg_m3=1000,
    )
    return vessel, config.ports.rotation, config.limits


def measured_constraints(plan, rotation, limits):
    evaluation = evaluate_plan(plan, rotation, limits)
    g = constraint_violations(plan, limits, evaluation)
    assert np.isfinite(g).all()
    assert (all(value <= 0 for value in g)) == check_plan(plan, limits)[0]
    return dict(zip(CONSTRAINT_NAMES, g, strict=True))


def test_pymoo_objective_order_and_zero_constraints_on_known_permutation(scenario):
    vessel, rotation, limits = scenario
    cargo = tuple(
        Container(i, mass, port, "dry")
        for i, mass, port in zip((42, 0, 9001), (1000, 2000, 3000), rotation.ports)
    )
    problem = StowageProblem(vessel, cargo, rotation, limits)
    order = np.array([0, 1, 2])
    f, g = problem.evaluate(order, return_values_of=["F", "G"])
    plan, evaluation = problem.evaluate_permutation(order)

    assert f == pytest.approx((1, 0.01580895954, 0))
    assert f == pytest.approx(evaluate_plan(plan, rotation, limits).objectives)
    assert evaluation.is_valid
    assert g.tolist() == [0] * len(CONSTRAINT_NAMES)


def test_partial_unsupported_overweight_cargo_and_overloaded_groups(scenario):
    vessel, rotation, limits = scenario
    vessel = replace(vessel, max_column_load_t=1, max_bay_load_t=2)
    cargo = (
        Container(42, 3000, rotation.ports[0], "dry"),
        Container(0, 40_000, rotation.ports[1], "dry"),
    )
    plan = Plan(vessel, cargo, {42: Slot(0, 0, 1)})
    values = measured_constraints(plan, rotation, limits)

    assert values["unplaced"] == 0.5
    assert values["unsupported"] == 0.5
    assert values["container_mass"] == pytest.approx((40000 - 30480) / 40000)
    assert values["column_load"] == pytest.approx(2 / 3)
    assert values["bay_load"] == pytest.approx(1 / 3)
    assert values["check_plan"] == 0


def test_operational_draft_and_gm_limits_in_metres(scenario):
    vessel, rotation, limits = scenario
    vessel = replace(vessel, max_draft_m=1, lightship_cg_z_m=2.4)
    values = measured_constraints(Plan(vessel, ()), rotation, limits)

    # Осадка 2 м, GM_T = 0.1 м. Гидростатика и углы остаются доступными.
    assert values["draft"] == pytest.approx(0.5)
    assert values["min_gm_t"] == pytest.approx(1 / 3)
    assert values["positive_gm_t"] == values["positive_gm_l"] == 0
    assert values["heel"] == values["trim"] == 0


def test_angle_and_trim_limits_are_separate_from_model_domain(scenario):
    vessel, rotation, limits = scenario
    vessel = replace(vessel, lightship_cg_x_m=9, lightship_cg_y_m=1)
    values = measured_constraints(Plan(vessel, ()), rotation, limits)
    heel = math.atan2(1, 0.5)
    trim_angle = math.atan2(3, 5)
    trim_m = 12 * 3 / 5

    assert values["heel"] == pytest.approx(1 - math.radians(1) / heel)
    assert values["trim"] == pytest.approx(1 - 0.12 / trim_m)
    assert values["small_heel"] == pytest.approx(1 - math.radians(5) / heel)
    assert values["small_trim"] == pytest.approx(1 - math.radians(5) / trim_angle)


def test_strict_gm_positivity_even_when_minimum_is_zero(scenario):
    vessel, rotation, limits = scenario
    limits = replace(limits, min_gm_m=0)
    vessel = replace(vessel, lightship_cg_z_m=2.5)
    transverse = measured_constraints(Plan(vessel, ()), rotation, limits)
    assert transverse["min_gm_t"] == 0
    assert transverse["positive_gm_t"] == 1
    assert transverse["positive_gm_l"] == 0

    vessel = replace(
        vessel, length_m=6, beam_m=12, first_bay_offset_m=3,
        lightship_cg_x_m=3, lightship_cg_z_m=2.5,
    )
    longitudinal = measured_constraints(Plan(vessel, ()), rotation, limits)
    assert longitudinal["positive_gm_t"] == 0
    assert longitudinal["positive_gm_l"] == 1
    assert longitudinal["trim"] > 0


def test_unavailable_hydrostatics_are_finite_and_penalized(scenario):
    vessel, rotation, limits = scenario
    vessel = replace(vessel, lightship_mass_kg=1_000_000)
    cargo = (Container(42, 1000, rotation.ports[0], "dry"),)
    problem = StowageProblem(vessel, cargo, rotation, limits)
    f, g = problem.evaluate(np.array([0]), return_values_of=["F", "G"])
    plan, evaluation = problem.evaluate_permutation([0])
    values = measured_constraints(plan, rotation, limits)

    assert evaluation.hydrostatics is None
    assert evaluation.objectives == (0, None, None)
    assert np.isfinite(f).all() and np.isfinite(g).all()
    assert f[0] == 0 and f[1] > math.pi / 2 and f[2] > vessel.length_m
    assert values["draft"] == values["min_gm_t"] == values["trim"] == 2
