from dataclasses import replace

import pytest

from stowage.config import load_project_config
from stowage.domain.container import Container
from stowage.domain.plan import Plan
from stowage.domain.port_rotation import PortRotation
from stowage.domain.slot import Slot
from stowage.model.blocking_pairs import count_blocking_pairs


@pytest.fixture
def vessel():
    return replace(load_project_config().vessel, tiers=4, depth_m=11)


def test_documented_example_with_shuffled_placements_and_sparse_ids(vessel):
    containers = [
        Container(container_id, 1000, port, "dry")
        for container_id, port in [(90, "А"), (0, "Б"), (41, "В"), (13, "А")]
    ]
    plan = Plan(vessel, containers, [
        (41, Slot(0, 0, 2)), (90, Slot(0, 0, 0)),
        (13, Slot(0, 0, 3)), (0, Slot(0, 0, 1)),
    ])

    # Три пары: Б над А, В над А (несоседние ярусы) и В над Б.
    assert count_blocking_pairs(plan, PortRotation(("А", "Б", "В"))) == 3


@pytest.mark.parametrize("upper_slot", [Slot(1, 0, 1), Slot(0, 1, 1)])
def test_different_columns_do_not_block(vessel, upper_slot):
    plan = Plan(vessel, [
        Container(0, 1000, "А", "dry"), Container(99, 1000, "Б", "dry"),
    ], [(0, Slot(0, 0, 0)), (99, upper_slot)])

    assert count_blocking_pairs(plan, PortRotation(("А", "Б"))) == 0


@pytest.mark.parametrize(
    ("upper_port", "rotation", "expected"),
    [
        ("А", ("А", "Б"), 0),
        ("Б", ("Б", "А"), 0),
        ("Б", ("А", "Б"), 1),
    ],
)
def test_port_order_applies_even_to_occupied_tiers_separated_by_a_gap(
    vessel, upper_port, rotation, expected
):
    plan = Plan(vessel, [
        Container(0, 1000, "А", "dry"), Container(99, 1000, upper_port, "dry"),
    ], [(0, Slot(0, 0, 0)), (99, Slot(0, 0, 2))])

    assert count_blocking_pairs(plan, PortRotation(rotation)) == expected


def test_empty_and_unplaced_cargo_do_not_contribute(vessel):
    rotation = PortRotation(("А",))
    assert count_blocking_pairs(Plan(vessel, ()), rotation) == 0
    assert count_blocking_pairs(
        Plan(vessel, [Container(99, 1000, "X", "dry")]), rotation
    ) == 0


def test_unknown_port_of_placed_container_raises(vessel):
    plan = Plan(vessel, [Container(99, 1000, "X", "dry")], {99: Slot(0, 0, 0)})

    with pytest.raises(ValueError, match="Unknown port 'X'"):
        count_blocking_pairs(plan, PortRotation(("А",)))
