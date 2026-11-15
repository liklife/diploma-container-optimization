import math
from dataclasses import replace

import pytest

from stowage.domain.container import Container
from stowage.domain.plan import Plan
from stowage.domain.slot import Slot
from stowage.domain.vessel import Vessel
from stowage.model.center_of_gravity import calculate_mass_and_cg
from stowage.model.hydrostatics import calculate_hydrostatics


@pytest.fixture
def vessel():
    return Vessel(
        vessel_id="hydrostatics_test",
        name="Тестовая баржа",
        synthetic=True,
        hull_model="box_barge",
        length_m=12,
        beam_m=6,
        depth_m=8,
        max_draft_m=4,
        bays=3,
        rows=1,
        tiers=1,
        first_bay_offset_m=2,
        bay_spacing_m=4,
        first_row_center_y_m=0,
        row_spacing_m=2,
        base_height_m=1.5,
        container_height_m=2,
        tier_spacing_m=2,
        lightship_mass_kg=72000,
        lightship_cg_x_m=6,
        lightship_cg_y_m=0,
        lightship_cg_z_m=1.5,
        water_density_kg_m3=1000,
        max_bay_load_t=220,
        max_column_load_t=60,
    )


@pytest.mark.parametrize(
    "mass, cg_z, expected",
    [
        (144000, 2, (2, 1, 1.5, 6, 0.5, 5)),
        (216000, 2, (3, 1.5, 1, 4, 0.5, 3.5)),
        (144000, 2.5, (2, 1, 1.5, 6, 0, 4.5)),
        (144000, 3, (2, 1, 1.5, 6, -0.5, 4)),
        (144000, 7, (2, 1, 1.5, 6, -4.5, 0)),
        (144000, 9, (2, 1, 1.5, 6, -6.5, -2)),
        (144000, 0, (2, 1, 1.5, 6, 2.5, 7)),
        (288000, 2, (4, 2, 0.75, 3, 0.75, 3)),
    ],
)
def test_independent_numeric_results(vessel, mass, cg_z, expected):
    # Для M=144000: объём=144 м³, площадь=72 м², T=2 м.
    # KB=1, BM_T=36/24=1.5, BM_L=144/24=6; при Z_G=2 GM=(0.5, 5).
    assert calculate_hydrostatics(vessel, mass, cg_z) == pytest.approx(expected)


def test_water_density_is_used(vessel):
    denser_water = replace(vessel, water_density_kg_m3=1200)

    assert calculate_hydrostatics(denser_water, 144000, 2) == pytest.approx(
        (5 / 3, 5 / 6, 1.8, 7.2, 19 / 30, 181 / 30)
    )


def test_operational_draft_limit_is_separate(vessel):
    result = calculate_hydrostatics(vessel, 360000, 2)

    # T=5 превышает max_draft=4, но остаётся меньше depth=8.
    assert result == pytest.approx((5, 2.5, 0.6, 2.4, 1.1, 2.9))
    with pytest.raises(ValueError, match="max_draft_m"):
        vessel.validate_draft(result[0])


def test_operational_limit_equality_is_allowed(vessel):
    draft = calculate_hydrostatics(vessel, 288000, 2)[0]

    assert draft == 4
    vessel.validate_draft(draft)


@pytest.mark.parametrize("mass", [576000, 648000])
def test_draft_at_or_above_depth_is_rejected(vessel, mass):
    # Эти массы соответствуют осадке 8 и 9 м.
    with pytest.raises(ValueError, match="less than vessel depth_m"):
        calculate_hydrostatics(vessel, mass, 2)


def test_draft_just_below_depth_is_calculated(vessel):
    result = calculate_hydrostatics(vessel, 575928, 2)

    assert result[0] == pytest.approx(7.999)
    assert all(math.isfinite(value) for value in result)


def make_container(container_id):
    return Container(
        id=container_id,
        mass_kg=24000,
        port="Мурманск",
        container_type="dry",
    )


@pytest.mark.parametrize("include_unplaced", [False, True])
def test_t06_to_hydrostatics_with_three_containers(vessel, include_unplaced):
    containers = [make_container(42), make_container(0), make_container(9001)]
    if include_unplaced:
        containers.append(make_container(77))
    plan = Plan(
        vessel=vessel,
        containers=containers,
        placements={42: Slot(0, 0, 0), 0: Slot(1, 0, 0), 9001: Slot(2, 0, 0)},
    )

    mass, _, _, cg_z = calculate_mass_and_cg(plan)

    # Все три центра находятся на Z=1.5+2/2=2.5 м.
    # M=72000+3*24000=144000; Z_G=(72000*1.5+72000*2.5)/144000=2.
    assert (mass, cg_z) == pytest.approx((144000, 2))
    assert calculate_hydrostatics(vessel, mass, cg_z) == pytest.approx(
        (2, 1, 1.5, 6, 0.5, 5)
    )


def test_empty_plan_t06_to_hydrostatics(vessel):
    plan = Plan(vessel=vessel, containers=[])
    mass, _, _, cg_z = calculate_mass_and_cg(plan)

    assert calculate_hydrostatics(vessel, mass, cg_z) == pytest.approx(
        (1, 0.5, 3, 12, 2, 11)
    )


def test_result_format_and_vessel_preservation(vessel):
    before = replace(vessel)

    result = calculate_hydrostatics(vessel, 144000, 2)

    assert isinstance(result, tuple)
    assert len(result) == 6
    assert all(type(value) is float for value in result)
    assert vessel == before


@pytest.mark.parametrize("invalid_vessel", [None, {}, "vessel", 42])
def test_invalid_vessel_type_is_rejected(invalid_vessel):
    with pytest.raises(TypeError, match="Vessel"):
        calculate_hydrostatics(invalid_vessel, 144000, 2)


@pytest.mark.parametrize("overrides", [{"synthetic": False}, {"hull_model": "other"}])
def test_unsupported_model_is_rejected(vessel, overrides):
    with pytest.raises(ValueError, match="synthetic box_barge"):
        calculate_hydrostatics(replace(vessel, **overrides), 144000, 2)


@pytest.mark.parametrize("field", ["total_mass_kg", "cg_z_m"])
@pytest.mark.parametrize("invalid_value", [True, "2", None])
def test_non_numeric_inputs_are_rejected(vessel, field, invalid_value):
    values = {"total_mass_kg": 144000, "cg_z_m": 2}
    values[field] = invalid_value

    with pytest.raises(TypeError, match="must be a number"):
        calculate_hydrostatics(vessel, **values)


@pytest.mark.parametrize("field", ["total_mass_kg", "cg_z_m"])
@pytest.mark.parametrize("invalid_value", [math.nan, math.inf, -math.inf])
def test_non_finite_inputs_are_rejected(vessel, field, invalid_value):
    values = {"total_mass_kg": 144000, "cg_z_m": 2}
    values[field] = invalid_value

    with pytest.raises(ValueError, match="must be finite"):
        calculate_hydrostatics(vessel, **values)


@pytest.mark.parametrize("mass", [0, -1])
def test_non_positive_mass_is_rejected(vessel, mass):
    with pytest.raises(ValueError, match="Total mass must be positive"):
        calculate_hydrostatics(vessel, mass, 2)


def test_negative_cg_z_is_rejected(vessel):
    with pytest.raises(ValueError, match="CG Z must be non-negative"):
        calculate_hydrostatics(vessel, 144000, -1)


@pytest.mark.parametrize(
    "overrides, mass",
    [
        ({"water_density_kg_m3": 5e-324}, 144000),  # Переполнение объёма.
        ({"length_m": 1e308}, 144000),  # Переполнение площади.
        ({"length_m": 1e155}, 1.2e159),  # Переполнение квадрата длины.
        ({}, 5e-324),  # Обнуление объёма.
        ({}, 1e-319),  # Обнуление осадки.
        ({}, 1e-304),  # Переполнение BM при очень малой осадке.
    ],
)
def test_numerical_range_errors_are_rejected(vessel, overrides, mass):
    with pytest.raises(ValueError, match="finite|positive"):
        calculate_hydrostatics(replace(vessel, **overrides), mass, 2)
