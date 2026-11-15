import math
from dataclasses import replace

import pytest

from stowage.domain.container import Container
from stowage.domain.plan import Plan
from stowage.domain.slot import Slot
from stowage.domain.vessel import Vessel
from stowage.model.center_of_gravity import calculate_mass_and_cg
from stowage.model.heel_and_trim import calculate_heel_and_trim
from stowage.model.hydrostatics import calculate_hydrostatics


@pytest.fixture
def vessel():
    return Vessel(
        vessel_id="heel_trim_test",
        name="Тестовая баржа",
        synthetic=True,
        hull_model="box_barge",
        length_m=120,
        beam_m=14,
        depth_m=10,
        max_draft_m=8,
        bays=3,
        rows=1,
        tiers=1,
        first_bay_offset_m=20,
        bay_spacing_m=40,
        first_row_center_y_m=0,
        row_spacing_m=2,
        base_height_m=1.5,
        container_height_m=2,
        tier_spacing_m=2,
        lightship_mass_kg=72000,
        lightship_cg_x_m=60,
        lightship_cg_y_m=0,
        lightship_cg_z_m=1.5,
        water_density_kg_m3=1000,
        max_bay_load_t=220,
        max_column_load_t=60,
    )


@pytest.mark.parametrize(
    "cg_x, cg_y, expected",
    [
        (60, 0, (0, 0, 0)),
        (60, 0.02, (0.009999666686665238, 0, 0)),
        (60, -0.02, (-0.009999666686665238, 0, 0)),
        (61, 0, (0, 0.009999666686665238, 1.2)),
        (59, 0, (0, -0.009999666686665238, -1.2)),
        (61, -0.02, (-0.009999666686665238, 0.009999666686665238, 1.2)),
        (59, 0.02, (0.009999666686665238, -0.009999666686665238, -1.2)),
    ],
)
def test_signs_and_independent_numeric_results(vessel, cg_x, cg_y, expected):
    # GM_T=2, GM_L=100. Для X_G=61 плечо=61-120/2=1 м.
    # theta=atan(0.01)=0.009999666686665238 рад; t=120*0.01=1.2 м.
    assert calculate_heel_and_trim(vessel, cg_x, cg_y, 2, 100) == pytest.approx(
        expected, abs=1e-14
    )


def test_degrees_and_trim_percent(vessel):
    heel, trim, trim_m = calculate_heel_and_trim(vessel, 61, 0.02, 2, 100)

    assert math.degrees(heel) == pytest.approx(0.572938697683486)
    assert math.degrees(trim) == pytest.approx(0.572938697683486)
    assert 100 * abs(trim_m) / vessel.length_m == pytest.approx(1)


def test_longitudinal_reference_is_midship_not_lightship_cg_or_grid(vessel):
    shifted = replace(vessel, lightship_cg_x_m=50, first_bay_offset_m=7.5)

    assert calculate_heel_and_trim(shifted, 60, 0, 2, 100) == (0, 0, 0)


@pytest.mark.parametrize("direction", ["transverse", "longitudinal"])
@pytest.mark.parametrize("gm", [0, -1])
@pytest.mark.parametrize("zero_arms", [False, True])
def test_non_positive_gm_is_rejected(vessel, direction, gm, zero_arms):
    gm_t, gm_l = (gm, 100) if direction == "transverse" else (2, gm)
    cg_x, cg_y = (60, 0) if zero_arms else (61, 0.02)

    with pytest.raises(ValueError, match="GM must be positive"):
        calculate_heel_and_trim(vessel, cg_x, cg_y, gm_t, gm_l)


@pytest.mark.parametrize("sign", [-1, 1])
@pytest.mark.parametrize(
    "angle_deg, cg_y, longitudinal_arm, expected_trim_m",
    [
        (4.999, 0.17494215333621793, 8.74710766681089, 10.496529200173075),
        (5.0, 0.17497732705184801, 8.7488663525924, 10.498639623110881),
        (5.001, 0.1750125008748963, 8.75062504374482, 10.500750052493778),
    ],
)
def test_small_angle_boundary_is_not_enforced(
    vessel, sign, angle_deg, cg_y, longitudinal_arm, expected_trim_m
):
    # Входные плечи независимо подобраны для 4.999°, 5°, 5.001°.
    heel, trim, trim_m = calculate_heel_and_trim(
        vessel, 60 + sign * longitudinal_arm, sign * cg_y, 2, 100
    )

    assert math.degrees(heel) == pytest.approx(sign * angle_deg, abs=1e-12)
    assert math.degrees(trim) == pytest.approx(sign * angle_deg, abs=1e-12)
    assert trim_m == pytest.approx(sign * expected_trim_m, abs=1e-12)


def test_outside_small_angles_returns_diagnostic_values(vessel):
    result = calculate_heel_and_trim(vessel, 70, 0.2, 2, 100)

    assert result == pytest.approx((0.09966865249116204, 0.09966865249116204, 12))
    assert math.degrees(result[0]) == pytest.approx(5.710593137499643)


def test_extreme_transverse_ratio_does_not_require_division(vessel):
    result = calculate_heel_and_trim(vessel, 60, 1e308, 5e-324, 100)

    assert result == pytest.approx((1.5707963267948966, 0, 0))


@pytest.mark.parametrize(
    "length, cg_x, gm_l, message",
    [
        (1e308, -1.7e308, 100, "arms"),
        (120, 61, 5e-324, "ratio"),
        (120, 1e307, 1, "results"),
    ],
)
def test_intermediate_overflow_is_rejected(vessel, length, cg_x, gm_l, message):
    with pytest.raises(ValueError, match=message):
        calculate_heel_and_trim(replace(vessel, length_m=length), cg_x, 0, 2, gm_l)


@pytest.mark.parametrize("invalid_vessel", [None, {}, "vessel", 42])
def test_invalid_vessel_type_is_rejected(invalid_vessel):
    with pytest.raises(TypeError, match="Vessel"):
        calculate_heel_and_trim(invalid_vessel, 60, 0, 2, 100)


@pytest.mark.parametrize("overrides", [{"synthetic": False}, {"hull_model": "other"}])
def test_unsupported_model_is_rejected(vessel, overrides):
    with pytest.raises(ValueError, match="synthetic box_barge"):
        calculate_heel_and_trim(replace(vessel, **overrides), 60, 0, 2, 100)


@pytest.mark.parametrize(
    "field", ["cg_x_m", "cg_y_m", "gm_transverse_m", "gm_longitudinal_m"]
)
@pytest.mark.parametrize("invalid_value", [True, "2", None, math.nan, math.inf, -math.inf])
def test_invalid_numeric_inputs_are_rejected(vessel, field, invalid_value):
    values = dict(cg_x_m=60, cg_y_m=0, gm_transverse_m=2, gm_longitudinal_m=100)
    values[field] = invalid_value
    error = TypeError if invalid_value is None or isinstance(invalid_value, (bool, str)) else ValueError

    with pytest.raises(error, match="number|finite"):
        calculate_heel_and_trim(vessel, **values)


def test_result_format_and_input_preservation(vessel):
    before = replace(vessel)
    inputs = dict(cg_x_m=61, cg_y_m=0.02, gm_transverse_m=2, gm_longitudinal_m=100)
    original_inputs = inputs.copy()

    result = calculate_heel_and_trim(vessel, **inputs)

    assert isinstance(result, tuple)
    assert len(result) == 3
    assert all(type(value) is float for value in result)
    assert vessel == before
    assert inputs == original_inputs


@pytest.mark.parametrize("shifted", [False, True])
def test_t06_hydrostatics_and_angles_integration(vessel, shifted):
    small_vessel = replace(
        vessel,
        length_m=12,
        beam_m=6,
        depth_m=8,
        max_draft_m=4,
        first_bay_offset_m=2.1 if shifted else 2,
        bay_spacing_m=4,
        first_row_center_y_m=0.01 if shifted else 0,
        lightship_cg_x_m=6,
    )
    containers = [
        Container(id=i, mass_kg=24000, port="Мурманск", container_type="dry")
        for i in (42, 0, 9001)
    ]
    plan = Plan(
        vessel=small_vessel,
        containers=containers,
        placements={42: Slot(0, 0, 0), 0: Slot(1, 0, 0), 9001: Slot(2, 0, 0)},
    )

    mass, cg_x, cg_y, cg_z = calculate_mass_and_cg(plan)
    _, _, _, _, gm_t, gm_l = calculate_hydrostatics(small_vessel, mass, cg_z)
    result = calculate_heel_and_trim(small_vessel, cg_x, cg_y, gm_t, gm_l)

    assert (mass, cg_z, gm_t, gm_l) == pytest.approx((144000, 2, 0.5, 5))
    if shifted:
        # Половина массы находится в слотах: X_G=6.05, Y_G=0.005.
        # Оба отношения плеч к GM равны 0.01, t=12*0.01=0.12 м.
        assert (cg_x, cg_y) == pytest.approx((6.05, 0.005))
        assert result == pytest.approx((0.009999666686665238, 0.009999666686665238, 0.12))
    else:
        assert result == pytest.approx((0, 0, 0), abs=1e-14)
