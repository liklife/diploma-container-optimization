import math
from dataclasses import replace

import pytest

from stowage.config import load_project_config
from stowage.domain.container import Container
from stowage.domain.plan import Plan
from stowage.domain.slot import Slot
from stowage.model.evaluation import evaluate_plan


@pytest.fixture
def config():
    return load_project_config()


def test_valid_symmetric_plan_returns_separate_objectives_and_physics(config):
    port = config.ports.rotation.ports[0]
    plan = Plan(config.vessel, [
        Container(42, 10000, port, "dry"), Container(0, 10000, port, "dry"),
    ], {42: Slot(0, 1, 0), 0: Slot(7, 2, 0)})

    result = evaluate_plan(plan, config.ports.rotation, config.limits)

    assert result.is_valid is True
    assert result.violations == ()
    assert result.objectives == pytest.approx((0, 0, 0))
    # Слоты симметричны относительно (60, 0) и оба имеют Z = 1.4955 м.
    mass = 8_020_000
    cg_z = (8_000_000 * 4.2 + 20_000 * 1.4955) / mass
    draft = mass / (1025 * 120 * 14)
    assert result.mass_and_cg == pytest.approx((mass, 60, 0, cg_z))
    assert result.hydrostatics[0] == pytest.approx(draft)
    assert result.heel_and_trim == pytest.approx((0, 0, 0))


def test_partial_plan_keeps_valid_physical_calculations_and_reasons(config):
    port = config.ports.rotation.ports[0]
    plan = Plan(config.vessel, [Container(42, 10000, port, "dry")])

    result = evaluate_plan(plan, config.ports.rotation, config.limits)

    assert result.is_valid is False
    assert len(result.violations) == 1
    assert result.violations[0].startswith("unplaced_container:")
    assert result.mass_and_cg == (8_000_000, 60, 0, 4.2)
    assert result.objectives == (0, 0, 0)


def test_unsupported_slot_can_produce_signed_angles_and_blocking_pairs(config):
    early, late = config.ports.rotation.ports[:2]
    plan = Plan(config.vessel, [
        Container(42, 1000, early, "dry"), Container(0, 1000, late, "dry"),
    ], {42: Slot(0, 1, 0), 0: Slot(0, 1, 2)})

    result = evaluate_plan(plan, config.ports.rotation, config.limits)

    assert result.is_valid is False
    assert any(reason.startswith("unsupported_container:") for reason in result.violations)
    heel, trim_angle, trim_m = result.heel_and_trim
    assert heel < 0 and trim_angle < 0 and trim_m < 0
    assert result.objectives == (1, -heel, -trim_m)


def test_unavailable_hydrostatics_keeps_mass_but_not_angle_objectives(config):
    vessel = replace(config.vessel, lightship_mass_kg=20_000_000)
    result = evaluate_plan(Plan(vessel, ()), config.ports.rotation, config.limits)

    assert result.is_valid is False
    assert any(reason.startswith("hydrostatics:") for reason in result.violations)
    assert result.mass_and_cg == (20_000_000, 60, 0, 4.2)
    assert result.hydrostatics is None
    assert result.heel_and_trim is None
    assert result.objectives == (0, None, None)


def test_nonpositive_gm_keeps_hydrostatics_without_angles(config):
    vessel = replace(config.vessel, lightship_cg_z_m=9)
    result = evaluate_plan(Plan(vessel, ()), config.ports.rotation, config.limits)

    assert result.is_valid is False
    assert any(reason.startswith("gm:") for reason in result.violations)
    assert math.isfinite(result.hydrostatics[4]) and result.hydrostatics[4] < 0
    assert result.heel_and_trim is None
    assert result.objectives == (0, None, None)
