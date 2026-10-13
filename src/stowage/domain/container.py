from dataclasses import dataclass
import math


@dataclass
class Container:
    """Контейнер в модели размещения на судне."""

    id: int
    mass_kg: float
    port: str
    container_type: str

    def __post_init__(self) -> None:
        if type(self.id) is not int:
            raise TypeError("Container ID must be an integer")

        if self.id < 0:
            raise ValueError("Container ID must be non-negative")

        if isinstance(self.mass_kg, bool) or not isinstance(
            self.mass_kg, (int, float)
        ):
            raise TypeError("Container mass must be a number")

        if not math.isfinite(self.mass_kg) or self.mass_kg <= 0:
            raise ValueError("Container mass must be positive and finite")

        if not isinstance(self.port, str) or not self.port.strip():
            raise ValueError("Container port must be a non-empty string")

        if not isinstance(self.container_type, str) or not self.container_type.strip():
            raise ValueError("Container type must be a non-empty string")