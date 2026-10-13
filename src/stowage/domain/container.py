from dataclasses import dataclass

from stowage.domain._validation import as_int, as_number, as_text


@dataclass
class Container:
    """Контейнер в модели размещения на судне."""

    id: int
    mass_kg: float
    port: str
    container_type: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", as_int(self.id, "Container ID"))

        if self.id < 0:
            raise ValueError("Container ID must be non-negative")

        mass = as_number(self.mass_kg, "Container mass")

        if mass <= 0:
            raise ValueError("Container mass must be positive and finite")

        object.__setattr__(self, "mass_kg", mass)
        object.__setattr__(
            self, "port", as_text(self.port, "Container port")
        )
        object.__setattr__(
            self,
            "container_type",
            as_text(self.container_type, "Container type"),
        )