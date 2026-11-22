"""Детерминированное размещение контейнеров в порядке перестановки."""

from collections.abc import Iterable, Mapping, Set

from stowage.domain._validation import as_int
from stowage.domain.container import Container
from stowage.domain.plan import Plan
from stowage.domain.slot import Slot
from stowage.domain.vessel import Vessel


def decode_permutation(
    vessel: Vessel,
    containers: tuple[Container, ...] | list[Container],
    permutation: Iterable[int],
) -> Plan:
    """Размещает контейнеры по индексам, заполняя ярусы снизу вверх.

    В пределах яруса приоритет имеют позиции у середины длины корпуса,
    затем у диаметральной плоскости. Равенство разрешается по bay и row.
    Для данного числа контейнеров набор занятых слотов фиксирован.
    При нехватке мест остаток доступен через Plan.unplaced_containers.
    Полноту и физическую допустимость проверяет check_plan().
    """
    if not isinstance(vessel, Vessel):
        raise TypeError("Expected a Vessel instance")
    if not isinstance(containers, (tuple, list)):
        raise TypeError("Containers must be a tuple or list")
    if not all(isinstance(container, Container) for container in containers):
        raise TypeError("Every container must be a Container instance")
    if isinstance(permutation, (Mapping, Set, str, bytes)):
        raise TypeError("Permutation must be an ordered iterable of indices")

    indices = tuple(as_int(index, "Permutation index") for index in permutation)
    if len(indices) != len(containers) or set(indices) != set(range(len(containers))):
        raise ValueError("Permutation must contain each container index exactly once")

    def slot_priority(slot: Slot) -> tuple[float, float, int, int]:
        x, y, _ = vessel.coordinates_for(slot)
        return abs(x - vessel.length_m / 2), abs(y), slot.bay, slot.row

    bottom_slots = sorted(
        (Slot(bay, row, 0) for bay in range(vessel.bays) for row in range(vessel.rows)),
        key=slot_priority,
    )
    slots = (
        Slot(bottom.bay, bottom.row, tier)
        for tier in range(vessel.tiers)
        for bottom in bottom_slots
    )
    placements = tuple(
        (containers[index].id, slot) for index, slot in zip(indices, slots)
    )
    return Plan(vessel, containers, placements)
