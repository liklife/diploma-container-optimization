from dataclasses import replace

import numpy as np
import pytest

from stowage.algorithms.decoder import decode_permutation
from stowage.config import load_project_config
from stowage.domain.container import Container
from stowage.domain.slot import Slot
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
    containers = tuple(
        Container(container_id, mass, port, "dry")
        for container_id, mass, port in zip(
            (42, 0, 9001), (1000, 2000, 3000), config.ports.rotation.ports
        )
    )
    return vessel, containers, config


def test_permutations_change_assignments_and_objectives_reproducibly(scenario):
    vessel, containers, config = scenario
    first = decode_permutation(vessel, containers, np.array([0, 1, 2]))
    second = decode_permutation(vessel, containers, [2, 1, 0])

    assert first == decode_permutation(vessel, containers, [0, 1, 2])
    assert first.containers == second.containers == containers
    assert first.placements == (
        (42, Slot(0, 0, 0)), (0, Slot(0, 1, 0)), (9001, Slot(0, 0, 1)),
    )
    assert second.placements == (
        (9001, Slot(0, 0, 0)), (0, Slot(0, 1, 0)), (42, Slot(0, 0, 1)),
    )
    first_evaluation = evaluate_plan(first, config.ports.rotation, config.limits)
    second_evaluation = evaluate_plan(second, config.ports.rotation, config.limits)

    # Y_G = -1/150 м, осадка = 25/12 м, GM_T = 0.421666... и 0.448333... м.
    # Верхний контейнер блокирует нижний только в первом варианте.
    assert first_evaluation.is_valid and second_evaluation.is_valid
    assert first_evaluation.objectives == pytest.approx((1, 0.01580895954, 0))
    assert second_evaluation.objectives == pytest.approx((0, 0.01486879264, 0))


def test_midship_and_centerline_have_priority_within_bottom_tier(scenario):
    vessel, containers, _ = scenario
    vessel = replace(
        vessel, bays=3, first_bay_offset_m=2, bay_spacing_m=4,
        first_row_center_y_m=-1.5,
    )
    plan = decode_permutation(vessel, containers, [0, 1, 2])

    assert plan.placements == (
        (42, Slot(1, 1, 0)), (0, Slot(1, 0, 0)), (9001, Slot(0, 1, 0)),
    )


def test_capacity_shortage_retains_the_unplaced_container(scenario):
    vessel, containers, config = scenario
    vessel = replace(vessel, rows=1, first_row_center_y_m=0)
    plan = decode_permutation(vessel, list(containers), [2, 0, 1])

    assert plan.placements == ((9001, Slot(0, 0, 0)), (42, Slot(0, 0, 1)))
    assert plan.unplaced_containers == (containers[1],)
    evaluation = evaluate_plan(plan, config.ports.rotation, config.limits)
    assert evaluation.is_valid is False
    assert any(reason.startswith("unplaced_container:") for reason in evaluation.violations)


@pytest.mark.parametrize("bad", [[0, 0, 2], [0, 2], [0, 1, 3], [0, 1, -1]])
def test_invalid_permutation_indices_raise(scenario, bad):
    vessel, containers, _ = scenario
    with pytest.raises(ValueError, match="exactly once"):
        decode_permutation(vessel, containers, bad)


@pytest.mark.parametrize("bad", [[False, 1, 2], [0.0, 1, 2], {0, 1, 2}])
def test_permutation_requires_ordered_integer_indices(scenario, bad):
    vessel, containers, _ = scenario
    with pytest.raises(TypeError, match="Permutation"):
        decode_permutation(vessel, containers, bad)


def test_empty_permutation_produces_empty_plan(scenario):
    vessel, _, _ = scenario
    plan = decode_permutation(vessel, (), ())
    assert plan.containers == plan.placements == ()
