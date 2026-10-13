
from dataclasses import dataclass


@dataclass(frozen=True)
class Slot:
    """Место в контейнерной сетке судна с индексами, начинающимися с нуля."""

    bay: int
    row: int
    tier: int

    def __post_init__(self) -> None:
        for field_name, value in (
            ("bay", self.bay),
            ("row", self.row),
            ("tier", self.tier),
        ):
            if type(value) is not int:
                raise TypeError(
                    f"Slot {field_name} index must be an integer"
                )

            if value < 0:
                raise ValueError(
                    f"Slot {field_name} index must be non-negative"
                )
