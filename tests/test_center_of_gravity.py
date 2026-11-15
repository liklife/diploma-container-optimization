from dataclasses import replace

import pytest

from stowage.config import load_project_config
from stowage.domain.container import Container
from stowage.domain.plan import Plan
from stowage.domain.slot import Slot
from stowage.domain.vessel import Vessel
from stowage.model.center_of_gravity import calculate_mass_and_cg


@pytest.fixture
def vessel():
    return Vessel(
        vessel_id="cg_test_vessel",
        name="Тестовая баржа",
        synthetic=True,
        hull_model="box_barge",
        length_m=20,
        beam_m=10,
        depth_m=10,
        max_draft_m=8,
        bays=2,
        rows=2,
        tiers=2,
        first_bay_offset_m=5,
        bay_spacing_m=10,
        first_row_center_y_m=-2,
        row_spacing_m=4,
        base_height_m=1,
        container_height_m=2,
        tier_spacing_m=3,
        lightship_mass_kg=1000,
        lightship_cg_x_m=10,
        lightship_cg_y_m=0,
        lightship_cg_z_m=2,
        water_density_kg_m3=1025,
        max_bay_load_t=220,
        max_column_load_t=60,
    )


def make_container(container_id, mass):
    return Container(
        id=container_id,
        mass_kg=mass,
        port="Мурманск",
        container_type="dry",
    )


def test_empty_plan_returns_lightship_values(vessel):
    plan = Plan(vessel=vessel, containers=[])

    assert calculate_mass_and_cg(plan) == (1000.0, 10.0, 0.0, 2.0)


def test_unplaced_cargo_does_not_change_lightship_values(vessel):
    plan = Plan(vessel=vessel, containers=[make_container(42, 9000)])

    assert calculate_mass_and_cg(plan) == (1000.0, 10.0, 0.0, 2.0)


def test_one_container_matches_hand_calculation(vessel):
    plan = Plan(
        vessel=vessel,
        containers=[make_container(0, 1000)],
        placements={0: Slot(0, 0, 0)},
    )

    # Центр слота: (5, -2, 2). M = 1000 + 1000 = 2000.
    # X_G = (1000*10 + 1000*5)/2000 = 7.5;
    # Y_G = (1000*0 - 1000*2)/2000 = -1; Z_G = 2.
    assert calculate_mass_and_cg(plan) == pytest.approx((2000, 7.5, -1, 2))


def test_partial_plan_ignores_unplaced_container(vessel):
    plan = Plan(
        vessel=vessel,
        containers=[make_container(9001, 9000), make_container(42, 1000)],
        placements={42: Slot(0, 0, 0)},
    )

    assert calculate_mass_and_cg(plan) == pytest.approx((2000, 7.5, -1, 2))


def test_symmetric_cargo_preserves_center(vessel):
    plan = Plan(
        vessel=vessel,
        containers=[make_container(42, 1000), make_container(9001, 1000)],
        placements={42: Slot(0, 0, 0), 9001: Slot(1, 1, 0)},
    )

    assert calculate_mass_and_cg(plan) == pytest.approx((3000, 10, 0, 2))


@pytest.mark.parametrize("reverse_containers", [False, True])
@pytest.mark.parametrize("reverse_placements", [False, True])
def test_different_masses_and_heights_in_any_order(
    vessel, reverse_containers, reverse_placements
):
    containers = [make_container(9001, 2000), make_container(42, 1000)]
    placements = [(42, Slot(0, 0, 0)), (9001, Slot(1, 1, 1))]
    if reverse_containers:
        containers.reverse()
    if reverse_placements:
        placements.reverse()
    plan = Plan(vessel=vessel, containers=containers, placements=placements)

    # Моменты: X=45000, Y=2000, Z=14000 кг·м; масса=4000 кг.
    assert calculate_mass_and_cg(plan) == pytest.approx((4000, 11.25, 0.5, 3.5))


def test_upper_tier_is_calculated_without_support_validation(vessel):
    plan = Plan(
        vessel=vessel,
        containers=[make_container(42, 1000)],
        placements={42: Slot(1, 1, 1)},
    )

    assert calculate_mass_and_cg(plan) == pytest.approx((2000, 12.5, 1, 3.5))


def test_nonzero_lightship_y_is_included(vessel):
    plan = Plan(
        vessel=replace(vessel, lightship_cg_y_m=1),
        containers=[make_container(42, 1000)],
        placements={42: Slot(0, 0, 0)},
    )

    assert calculate_mass_and_cg(plan) == pytest.approx((2000, 7.5, -0.5, 2))


def test_empty_plan_with_project_configuration():
    plan = Plan(vessel=load_project_config().vessel, containers=[])

    assert calculate_mass_and_cg(plan) == (8000000.0, 60.0, 0.0, 4.2)


@pytest.mark.parametrize("placed", [False, True])
def test_result_format_and_input_preservation(vessel, placed):
    plan = Plan(
        vessel=vessel,
        containers=[make_container(42, 1000)],
        placements={42: Slot(0, 0, 0)} if placed else {},
    )
    before = (plan.vessel, plan.containers, plan.placements)

    result = calculate_mass_and_cg(plan)

    assert isinstance(result, tuple)
    assert len(result) == 4
    assert all(type(value) is float for value in result)
    assert (plan.vessel, plan.containers, plan.placements) == before


@pytest.mark.parametrize("invalid_plan", [None, {}, [], "plan", 42])
def test_non_plan_argument_is_rejected(invalid_plan):
    with pytest.raises(TypeError, match="Plan"):
        calculate_mass_and_cg(invalid_plan)


def test_non_finite_moment_is_rejected(vessel):
    plan = Plan(
        vessel=vessel,
        containers=[make_container(42, 1e308)],
        placements={42: Slot(1, 1, 1)},
    )

    with pytest.raises(ValueError, match="finite"):
        calculate_mass_and_cg(plan)


def test_mass_sum_overflow_is_rejected(vessel):
    # Все отдельные моменты конечны, но сумма двух масс переполняется.
    large_vessel = replace(
        vessel,
        lightship_mass_kg=1e308,
        lightship_cg_x_m=0,
        lightship_cg_z_m=0,
        first_bay_offset_m=0,
        first_row_center_y_m=0,
        base_height_m=0,
    )
    plan = Plan(
        vessel=large_vessel,
        containers=[make_container(42, 1e308)],
        placements={42: Slot(0, 0, 0)},
    )

    with pytest.raises(ValueError, match="finite"):
        calculate_mass_and_cg(plan)
