import math
from dataclasses import replace

import pytest

from stowage.config.loader import LimitsConfig
from stowage.domain.container import Container
from stowage.domain.plan import Plan
from stowage.domain.slot import Slot
from stowage.domain.vessel import Vessel
from stowage.model import constraints
from stowage.model.center_of_gravity import calculate_mass_and_cg
from stowage.model.hydrostatics import calculate_hydrostatics


@pytest.fixture
def vessel():
    return Vessel(
        vessel_id="constraints_test", name="Тестовая баржа",
        synthetic=True, hull_model="box_barge",
        length_m=12, beam_m=6, depth_m=8, max_draft_m=4,
        bays=3, rows=1, tiers=3,
        first_bay_offset_m=2, bay_spacing_m=4,
        first_row_center_y_m=0, row_spacing_m=2,
        base_height_m=1.5, container_height_m=2, tier_spacing_m=2,
        lightship_mass_kg=144000,
        lightship_cg_x_m=6, lightship_cg_y_m=0, lightship_cg_z_m=2,
        water_density_kg_m3=1000, max_bay_load_t=220, max_column_load_t=60,
    )


@pytest.fixture
def limits():
    return LimitsConfig(
        max_container_mass_kg=30480, min_gm_m=0.15, target_gm_m=0.5,
        max_abs_heel_deg=1, max_abs_trim_percent_of_length=1,
        small_angle_model_max_abs_heel_deg=5,
    )


def container(container_id, mass=24000):
    return Container(id=container_id, mass_kg=mass, port="Мурманск", container_type="dry")


def empty_plan(vessel):
    return Plan(vessel=vessel, containers=[])


def codes(result):
    return [message.split(":", 1)[0] for message in result[1]]


def test_valid_full_plan_and_independent_physics(vessel, limits):
    ship = replace(vessel, lightship_mass_kg=72000, lightship_cg_z_m=1.5)
    plan = Plan(
        vessel=ship, containers=[container(9001), container(0), container(42)],
        placements={42: Slot(0, 0, 0), 0: Slot(1, 0, 0), 9001: Slot(2, 0, 0)},
    )
    mass, cg_x, cg_y, cg_z = calculate_mass_and_cg(plan)
    # M=72000+3*24000=144000; Z_G=(108000+180000)/144000=2.
    # T=144000/(1000*12*6)=2, GM_T=1+36/24-2=0.5, GM_L=5.
    assert (mass, cg_x, cg_y, cg_z) == pytest.approx((144000, 6, 0, 2))
    assert calculate_hydrostatics(ship, mass, cg_z) == pytest.approx((2, 1, 1.5, 6, 0.5, 5))
    assert constraints.check_plan(plan, limits) == (True, ())


def test_valid_empty_plan(vessel, limits):
    assert constraints.check_plan(empty_plan(vessel), limits) == (True, ())


def test_partial_plan_ignores_unplaced_cargo_in_physics(vessel, limits):
    plan = Plan(vessel=vessel, containers=[container(77)])

    result = constraints.check_plan(plan, limits)

    assert result[0] is False
    assert codes(result) == ["unplaced_container"]
    assert "77" in result[1][0]


@pytest.mark.parametrize("mass", [30480, 30481])
@pytest.mark.parametrize("placed", [False, True])
def test_container_mass_limit_includes_unplaced(vessel, limits, mass, placed):
    plan = Plan(
        vessel=vessel, containers=[container(42, mass)],
        placements={42: Slot(1, 0, 0)} if placed else {},
    )
    result = constraints.check_plan(plan, limits)
    expected = ([] if placed else ["unplaced_container"])
    if mass > 30480:
        expected.append("container_mass")
        assert any("30481" in message and "30480" in message for message in result[1])
    assert codes(result) == expected
    assert result[0] is (not expected)


def test_missing_immediate_support(vessel, limits):
    # Умеренные массы и широкое судно исключают побочное нарушение GM.
    ship = replace(vessel, beam_m=12)
    plan = Plan(
        vessel=ship, containers=[container(42, 1000), container(77, 1000)],
        placements={42: Slot(1, 0, 0), 77: Slot(1, 0, 2)},
    )
    result = constraints.check_plan(plan, limits)

    assert codes(result) == ["unsupported_container"]
    assert "77" in result[1][0] and "(1, 0, 2)" in result[1][0]


@pytest.mark.parametrize("extra", [0, 1])
def test_column_load_boundary(vessel, limits, extra):
    ship = replace(vessel, beam_m=12)
    plan = Plan(
        vessel=ship,
        containers=[container(42, 20000), container(77, 20000), container(99, 20000 + extra)],
        placements={42: Slot(1, 0, 0), 77: Slot(1, 0, 1), 99: Slot(1, 0, 2)},
    )
    result = constraints.check_plan(plan, limits)

    assert codes(result) == (["column_load"] if extra else [])
    assert result[0] is (extra == 0)
    if extra:
        assert "60001" in result[1][0] and "60000" in result[1][0]


@pytest.mark.parametrize("mass", [27500, 28000])
def test_bay_load_boundary_without_column_violation(vessel, limits, mass):
    ship = replace(vessel, beam_m=12, rows=4, first_row_center_y_m=-3)
    containers = [container(i, mass) for i in range(8)]
    placements = {2 * row + tier: Slot(1, row, tier) for row in range(4) for tier in range(2)}
    result = constraints.check_plan(Plan(vessel=ship, containers=containers, placements=placements), limits)

    assert codes(result) == (["bay_load"] if mass == 28000 else [])
    assert result[0] is (mass == 27500)
    if mass == 28000:
        assert "224000" in result[1][0] and "220000" in result[1][0]


@pytest.mark.parametrize("mass", [288000, 360000])
def test_operational_draft_boundary(vessel, limits, mass):
    result = constraints.check_plan(empty_plan(replace(vessel, lightship_mass_kg=mass)), limits)

    assert codes(result) == ([] if mass == 288000 else ["draft"])
    assert result[0] is (mass == 288000)
    if mass == 360000:
        assert "5.0 м" in result[1][0] and "4.0 м" in result[1][0]


@pytest.mark.parametrize("mass", [576000, 648000])
def test_physical_draft_domain_failure(vessel, limits, mass):
    result = constraints.check_plan(empty_plan(replace(vessel, lightship_mass_kg=mass)), limits)

    assert result[0] is False
    assert codes(result) == ["hydrostatics"]
    assert "depth_m" in result[1][0] and "не выполнены" in result[1][0]


def test_gm_equal_to_configured_minimum(vessel, limits):
    assert constraints.check_plan(empty_plan(vessel), replace(limits, min_gm_m=0.5)) == (True, ())


def test_gm_below_minimum(vessel, limits):
    ship = replace(vessel, lightship_cg_z_m=2.4)
    assert calculate_hydrostatics(ship, 144000, 2.4)[4] == pytest.approx(0.1)
    result = constraints.check_plan(empty_plan(ship), limits)
    assert result[0] is False
    assert codes(result) == ["gm"]


@pytest.mark.parametrize("cg_z", [2.5, 3, 7, 7.5])
def test_non_positive_gm_does_not_call_angles(vessel, limits, monkeypatch, cg_z):
    def unexpected_angles(*args):
        pytest.fail("Углы не должны рассчитываться при неположительной GM")

    monkeypatch.setattr(constraints, "calculate_heel_and_trim", unexpected_angles)
    result = constraints.check_plan(empty_plan(replace(vessel, lightship_cg_z_m=cg_z)), limits)

    assert result[0] is False
    assert codes(result).count("gm") == (2 if cg_z >= 7 else 1)
    assert codes(result)[-1] == "calculation_error"
    if cg_z >= 7:
        assert any("GM_L=" in message for message in result[1])


def test_small_positive_longitudinal_gm_has_no_transverse_minimum(vessel, limits):
    ship = replace(
        vessel, length_m=6, beam_m=12, bays=1, first_bay_offset_m=3,
        lightship_cg_x_m=3, lightship_cg_z_m=2.4,
    )
    assert calculate_hydrostatics(ship, 144000, 2.4)[4:] == pytest.approx((4.6, 0.1))
    assert constraints.check_plan(empty_plan(ship), limits) == (True, ())


@pytest.mark.parametrize("sign", [-1, 1])
def test_heel_exceeds_limit_in_both_directions(vessel, limits, sign):
    result = constraints.check_plan(empty_plan(replace(vessel, lightship_cg_y_m=sign * 0.01)), limits)
    # atan(0.01/0.5) = ±1.145762838°.
    assert result[0] is False
    assert codes(result) == ["heel"]


@pytest.mark.parametrize("sign", [-1, 1])
@pytest.mark.parametrize("arm", [0.05, 0.06])
def test_trim_boundary_in_both_directions(vessel, limits, sign, arm):
    result = constraints.check_plan(empty_plan(replace(vessel, lightship_cg_x_m=6 + sign * arm)), limits)
    # GM_L=5: плечо 0.05 даёт 0.12 м (1%); 0.06 даёт 0.144 м (1.2%).
    assert codes(result) == ([] if arm == 0.05 else ["trim"])
    assert result[0] is (arm == 0.05)


@pytest.mark.parametrize("sign", [-1, 1])
@pytest.mark.parametrize("axis", ["heel", "trim"])
def test_outside_small_angle_model(vessel, limits, sign, axis):
    ship = replace(vessel, **{
        "lightship_cg_y_m" if axis == "heel" else "lightship_cg_x_m":
        sign * 0.05 if axis == "heel" else 6 + sign * 0.5,
    })
    result = constraints.check_plan(empty_plan(ship), limits)
    # Оба варианта дают atan(0.1)=±5.7105931375°.
    assert result[0] is False
    assert codes(result) == [axis, "small_angle"]
    assert "диагностический" in result[1][-1]


@pytest.mark.parametrize("sign", [-1, 1])
@pytest.mark.parametrize("offset", [-1e-10, 0, 1e-10])
def test_exact_heel_threshold_comparison(vessel, limits, monkeypatch, sign, offset):
    # Проверяем включительность сравнения без погрешности обратного atan2.
    angle = sign * (0.017453292519943295 + offset)
    monkeypatch.setattr(constraints, "calculate_heel_and_trim", lambda *args: (angle, 0.0, 0.0))
    result = constraints.check_plan(empty_plan(vessel), limits)
    assert codes(result) == (["heel"] if offset > 0 else [])


@pytest.mark.parametrize("axis", ["heel", "trim"])
@pytest.mark.parametrize("sign", [-1, 1])
@pytest.mark.parametrize("offset", [-1e-10, 0, 1e-10])
def test_exact_small_angle_comparison(vessel, limits, monkeypatch, axis, sign, offset):
    angle = sign * (0.08726646259971647 + offset)
    angles = (angle, 0.0, 0.0) if axis == "heel" else (0.0, angle, 12.0)
    monkeypatch.setattr(constraints, "calculate_heel_and_trim", lambda *args: angles)
    result = constraints.check_plan(empty_plan(vessel), limits)
    assert codes(result) == [axis] + (["small_angle"] if offset > 0 else [])


def test_configured_heel_model_limit_is_not_used_for_longitudinal_angle(vessel, limits, monkeypatch):
    monkeypatch.setattr(constraints, "calculate_heel_and_trim", lambda *args: (0.0, 0.05, 0.6))
    result = constraints.check_plan(empty_plan(vessel), replace(limits, small_angle_model_max_abs_heel_deg=2))
    assert codes(result) == ["trim"]  # 2.865° меньше продольной границы 5°.


def test_independent_violations_are_collected(vessel, limits):
    ship = replace(vessel, max_draft_m=1.9, lightship_cg_x_m=6.06, lightship_cg_y_m=0.01)
    plan = Plan(vessel=ship, containers=[container(77, 40000)])
    result = constraints.check_plan(plan, limits)

    assert result[0] is False
    assert codes(result) == ["unplaced_container", "container_mass", "draft", "heel", "trim"]


def test_angles_continue_when_positive_gm_is_below_minimum(vessel, limits):
    ship = replace(vessel, lightship_cg_z_m=2.4, lightship_cg_y_m=0.003)
    result = constraints.check_plan(empty_plan(ship), limits)
    assert codes(result) == ["gm", "heel"]  # atan(0.003/0.1) ≈ 1.718°.


@pytest.mark.parametrize("stage", ["calculate_mass_and_cg", "calculate_hydrostatics", "calculate_heel_and_trim"])
def test_calculation_errors_preserve_messages_and_previous_violations(vessel, limits, monkeypatch, stage):
    def fail(*args):
        raise ValueError("independent diagnostic")

    monkeypatch.setattr(constraints, stage, fail)
    plan = Plan(vessel=vessel, containers=[container(77)])
    result = constraints.check_plan(plan, limits)

    assert result[0] is False
    assert codes(result) == ["unplaced_container", "hydrostatics" if stage == "calculate_hydrostatics" else "calculation_error"]
    assert "independent diagnostic" in result[1][-1]
    assert "не выполнены" in result[1][-1]


@pytest.mark.parametrize("stage", ["calculate_mass_and_cg", "calculate_hydrostatics", "calculate_heel_and_trim"])
@pytest.mark.parametrize("error", [TypeError, KeyError])
def test_programming_errors_propagate(vessel, limits, monkeypatch, stage, error):
    def fail(*args):
        raise error("unexpected")

    monkeypatch.setattr(constraints, stage, fail)
    with pytest.raises(error, match="unexpected"):
        constraints.check_plan(empty_plan(vessel), limits)


def test_load_sum_overflow_is_not_accepted(vessel, limits):
    ship = replace(vessel, rows=2, first_row_center_y_m=-1)
    plan = Plan(
        vessel=ship, containers=[container(0, 1e308), container(42, 1e308)],
        placements={0: Slot(1, 0, 0), 42: Slot(1, 1, 0)},
    )
    result = constraints.check_plan(plan, limits)
    assert result[0] is False
    assert any(message.startswith("calculation_error: bay_load") for message in result[1])
    assert any("масса/ЦТ" in message for message in result[1])


@pytest.mark.parametrize("field", ["max_bay_load_t", "max_column_load_t"])
def test_tonnes_conversion_overflow(vessel, limits, field):
    result = constraints.check_plan(empty_plan(replace(vessel, **{field: 1e308})), limits)
    assert result[0] is False
    assert codes(result) == ["calculation_error"]
    assert "перевод предела" in result[1][0]


def test_trim_limit_product_overflow(vessel, limits):
    result = constraints.check_plan(empty_plan(vessel), replace(limits, max_abs_trim_percent_of_length=1e308))
    assert result[0] is False
    assert codes(result) == ["calculation_error"]


def test_target_gm_is_not_a_constraint(vessel, limits):
    assert constraints.check_plan(empty_plan(vessel), replace(limits, target_gm_m=1000)) == (True, ())


def test_input_preservation_and_result_format(vessel, limits):
    plan = Plan(vessel=vessel, containers=[container(77)])
    before = (plan.vessel, plan.containers, plan.placements, replace(limits))

    result = constraints.check_plan(plan, limits)

    assert type(result[0]) is bool
    assert isinstance(result[1], tuple)
    assert all(isinstance(message, str) for message in result[1])
    assert (plan.vessel, plan.containers, plan.placements, limits) == before


def test_existing_domain_validation_rejects_duplicate_slot(vessel):
    with pytest.raises(ValueError, match="assigned more than once"):
        Plan(
            vessel=vessel, containers=[container(0), container(42)],
            placements={0: Slot(1, 0, 0), 42: Slot(1, 0, 0)},
        )


@pytest.mark.parametrize("bad_plan", [None, {}, "plan"])
def test_invalid_plan_type(vessel, limits, bad_plan):
    with pytest.raises(TypeError, match="Plan"):
        constraints.check_plan(bad_plan, limits)


def test_invalid_limits_type(vessel):
    with pytest.raises(TypeError, match="LimitsConfig"):
        constraints.check_plan(empty_plan(vessel), None)
