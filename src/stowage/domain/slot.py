from dataclasses import dataclass

from stowage.domain._validation import as_int


@dataclass(frozen=True)
class Slot:
    """Место в контейнерной сетке судна с индексами, начинающимися с нуля."""

    bay: int
    row: int
    tier: int

    def __post_init__(self) -> None:
        for field_name in ("bay", "row", "tier"):
            value = as_int(
                getattr(self, field_name),
                f"Slot {field_name} index",
            )
            object.__setattr__(self, field_name, value)

            if value < 0:
                raise ValueError(
                    f"Slot {field_name} index must be non-negative"
                )