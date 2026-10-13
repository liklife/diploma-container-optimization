
from collections.abc import Mapping
from dataclasses import dataclass, field

from stowage.domain.container import Container
from stowage.domain.slot import Slot
from stowage.domain.vessel import Vessel


@dataclass(frozen=True)
class Plan:
    """План размещения контейнеров на грузовых позициях судна."""

    vessel: Vessel
    containers: tuple[Container, ...]
    placements: (
        tuple[tuple[int, Slot], ...]
        | Mapping[int, Slot]
        | list[tuple[int, Slot]]
    ) = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not isinstance(self.vessel, Vessel):
            raise TypeError("Plan vessel must be a Vessel instance")

        if not isinstance(self.containers, (tuple, list)):
            raise TypeError("Plan containers must be a tuple or list")

        containers = tuple(self.containers)

        container_ids: set[int] = set()

        for container in containers:
            if not isinstance(container, Container):
                raise TypeError(
                    "Every plan container must be a Container instance"
                )

            if container.id in container_ids:
                raise ValueError(
                    f"Duplicate container ID: {container.id}"
                )

            container_ids.add(container.id)

        if isinstance(self.placements, Mapping):
            items = tuple(self.placements.items())
        elif isinstance(self.placements, (tuple, list)):
            items = tuple(self.placements)
        else:
            raise TypeError(
                "Plan placements must be a mapping, tuple or list"
            )

        normalized_placements: list[tuple[int, Slot]] = []
        assigned_container_ids: set[int] = set()
        occupied_slots: set[tuple[int, int, int]] = set()

        for item in items:
            if not isinstance(item, (tuple, list)) or len(item) != 2:
                raise ValueError(
                    "Every placement must contain a container ID and a Slot"
                )

            container_id, slot = item

            if type(container_id) is not int:
                raise TypeError("Placement container ID must be an integer")

            if container_id < 0:
                raise ValueError(
                    "Placement container ID must be non-negative"
                )

            if container_id not in container_ids:
                raise ValueError(
                    f"Unknown container ID in placement: {container_id}"
                )

            if container_id in assigned_container_ids:
                raise ValueError(
                    f"Container {container_id} is placed more than once"
                )

            if not isinstance(slot, Slot):
                raise TypeError(
                    "Every placement must reference a Slot instance"
                )

            # Проверяем границы сетки средствами модели Vessel.
            self.vessel.coordinates_for(slot)

            slot_key = (slot.bay, slot.row, slot.tier)

            if slot_key in occupied_slots:
                raise ValueError(
                    f"Slot {slot_key} is assigned more than once"
                )

            assigned_container_ids.add(container_id)
            occupied_slots.add(slot_key)
            normalized_placements.append((container_id, slot))

        # Сохраняем независимые неизменяемые коллекции.
        object.__setattr__(self, "containers", containers)
        object.__setattr__(
            self, "placements", tuple(normalized_placements)
        )

    @property
    def unplaced_containers(self) -> tuple[Container, ...]:
        """Возвращает контейнеры, которым пока не назначен слот."""

        assigned_ids = {
            container_id
            for container_id, _ in self.placements
        }

        return tuple(
            container
            for container in self.containers
            if container.id not in assigned_ids
        )
