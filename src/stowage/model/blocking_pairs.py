"""Подсчёт потенциальных блокирующих пар при последовательной выгрузке."""

from itertools import combinations

from stowage.domain.plan import Plan
from stowage.domain.port_rotation import PortRotation


def count_blocking_pairs(plan: Plan, rotation: PortRotation) -> int:
    """Считает пары занятых ярусов одной колонны с поздним портом сверху.

    Неразмещённые контейнеры не участвуют. Неизвестный порт размещённого
    контейнера вызывает ValueError через PortRotation.index_of().
    """
    if not isinstance(plan, Plan):
        raise TypeError("Expected a Plan instance")
    if not isinstance(rotation, PortRotation):
        raise TypeError("Expected a PortRotation instance")

    ports_by_id = {container.id: container.port for container in plan.containers}
    columns: dict[tuple[int, int], list[tuple[int, int]]] = {}
    for container_id, slot in plan.placements:
        port_index = rotation.index_of(ports_by_id[container_id])
        columns.setdefault((slot.bay, slot.row), []).append((slot.tier, port_index))

    return sum(
        upper_port > lower_port
        for column in columns.values()
        for (_, lower_port), (_, upper_port) in combinations(sorted(column), 2)
    )
