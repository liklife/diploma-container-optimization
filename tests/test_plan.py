
import pytest

from stowage.domain.container import Container
from stowage.domain.plan import Plan
from stowage.domain.slot import Slot
from stowage.domain.vessel import Vessel


VESSEL_DEFAULTS = {
    "vessel_id": "test_vessel",
    "name": "Тестовое судно",
    "synthetic": True,
    "hull_model": "box_barge",
    "length_m": 120.0,
    "beam_m": 14.0,
    "depth_m": 10.0,
    "bays": 8,
    "rows": 4,
    "tiers": 3,
    "first_bay_offset_m": 7.5,
    "bay_spacing_m": 15.0,
    "first_row_center_y_m": -5.25,
    "row_spacing_m": 3.5,
    "base_height_m": 0.2,
    "container_height_m": 2.591,
    "tier_spacing_m": 2.6,
    "lightship_mass_kg": 8000000,
    "lightship_cg_x_m": 60.0,
    "lightship_cg_y_m": 0.0,
    "lightship_cg_z_m": 4.2,
    "water_density_kg_m3": 1025.0,
    "max_bay_load_t": 220.0,
    "max_column_load_t": 60.0,
}


def make_vessel():
    return Vessel(**VESSEL_DEFAULTS)


def make_container(container_id):
    return Container(
        id=container_id,
        mass_kg=10000,
        port="Мурманск",
        container_type="dry",
    )


def test_create_plan_with_placements():
    vessel = make_vessel()
    first = make_container(0)
    second = make_container(1)

    plan = Plan(
        vessel=vessel,
        containers=[first, second],
        placements={
            0: Slot(bay=0, row=0, tier=0),
            1: Slot(bay=1, row=0, tier=0),
        },
    )

    assert plan.vessel is vessel
    assert plan.containers == (first, second)
    assert len(plan.placements) == 2
    assert plan.unplaced_containers == ()


def test_empty_plan_is_allowed():
    plan = Plan(
        vessel=make_vessel(),
        containers=[],
    )

    assert plan.containers == ()
    assert plan.placements == ()
    assert plan.unplaced_containers == ()


def test_plan_can_have_unplaced_containers():
    first = make_container(0)
    second = make_container(1)

    plan = Plan(
        vessel=make_vessel(),
        containers=[first, second],
        placements={0: Slot(bay=0, row=0, tier=0)},
    )

    assert plan.unplaced_containers == (second,)


def test_container_id_zero_is_supported():
    container = make_container(0)

    plan = Plan(
        vessel=make_vessel(),
        containers=[container],
        placements={0: Slot(bay=0, row=0, tier=0)},
    )

    assert plan.placements[0][0] == 0
    assert plan.unplaced_containers == ()


def test_placements_are_converted_to_tuple():
    source = {
        0: Slot(bay=0, row=0, tier=0),
    }

    plan = Plan(
        vessel=make_vessel(),
        containers=[make_container(0)],
        placements=source,
    )

    source.clear()

    assert len(plan.placements) == 1
    assert isinstance(plan.placements, tuple)


def test_container_list_is_copied():
    source = [make_container(0)]

    plan = Plan(
        vessel=make_vessel(),
        containers=source,
    )

    source.append(make_container(1))

    assert len(plan.containers) == 1


def test_invalid_vessel_is_rejected():
    with pytest.raises(TypeError, match="Vessel"):
        Plan(vessel=None, containers=[])


@pytest.mark.parametrize("invalid_containers", [None, "containers", 123])
def test_invalid_container_collection_is_rejected(invalid_containers):
    with pytest.raises(TypeError, match="containers"):
        Plan(vessel=make_vessel(), containers=invalid_containers)


def test_non_container_item_is_rejected():
    with pytest.raises(TypeError, match="Container"):
        Plan(vessel=make_vessel(), containers=["container"])


def test_duplicate_container_ids_are_rejected():
    with pytest.raises(ValueError, match="Duplicate container ID"):
        Plan(
            vessel=make_vessel(),
            containers=[make_container(0), make_container(0)],
        )


@pytest.mark.parametrize(
    "invalid_placements",
    [None, "placements", 123],
)
def test_invalid_placements_collection_is_rejected(invalid_placements):
    with pytest.raises(TypeError, match="placements"):
        Plan(
            vessel=make_vessel(),
            containers=[make_container(0)],
            placements=invalid_placements,
        )


@pytest.mark.parametrize(
    "invalid_placement",
    [(), (0,), (0, Slot(0, 0, 0), "extra"), None],
)
def test_malformed_placement_is_rejected(invalid_placement):
    with pytest.raises(ValueError, match="placement"):
        Plan(
            vessel=make_vessel(),
            containers=[make_container(0)],
            placements=[invalid_placement],
        )


@pytest.mark.parametrize("invalid_id", [True, 1.5, "0", None])
def test_placement_container_id_must_be_integer(invalid_id):
    with pytest.raises(TypeError, match="integer"):
        Plan(
            vessel=make_vessel(),
            containers=[make_container(0)],
            placements=[(invalid_id, Slot(0, 0, 0))],
        )


def test_negative_placement_container_id_is_rejected():
    with pytest.raises(ValueError, match="non-negative"):
        Plan(
            vessel=make_vessel(),
            containers=[make_container(0)],
            placements=[(-1, Slot(0, 0, 0))],
        )


def test_unknown_container_id_is_rejected():
    with pytest.raises(ValueError, match="Unknown container ID"):
        Plan(
            vessel=make_vessel(),
            containers=[make_container(0)],
            placements={5: Slot(0, 0, 0)},
        )


def test_duplicate_placement_for_same_container_is_rejected():
    with pytest.raises(ValueError, match="more than once"):
        Plan(
            vessel=make_vessel(),
            containers=[make_container(0)],
            placements=[
                (0, Slot(0, 0, 0)),
                (0, Slot(1, 0, 0)),
            ],
        )


def test_non_slot_placement_is_rejected():
    with pytest.raises(TypeError, match="Slot"):
        Plan(
            vessel=make_vessel(),
            containers=[make_container(0)],
            placements={0: (0, 0, 0)},
        )


def test_duplicate_slot_is_rejected():
    slot = Slot(0, 0, 0)

    with pytest.raises(ValueError, match="assigned more than once"):
        Plan(
            vessel=make_vessel(),
            containers=[make_container(0), make_container(1)],
            placements={
                0: slot,
                1: slot,
            },
        )


@pytest.mark.parametrize(
    "slot",
    [
        Slot(8, 0, 0),
        Slot(0, 4, 0),
        Slot(0, 0, 3),
    ],
)
def test_slot_outside_vessel_grid_is_rejected(slot):
    with pytest.raises(ValueError, match="outside vessel grid"):
        Plan(
            vessel=make_vessel(),
            containers=[make_container(0)],
            placements={0: slot},
        )


def test_plan_is_immutable():
    plan = Plan(
        vessel=make_vessel(),
        containers=[make_container(0)],
    )

    with pytest.raises(AttributeError):
        plan.vessel = make_vessel()
