from dataclasses import dataclass, field
import math


@dataclass
class ContainerType:
    """Тип контейнера с настраиваемыми характеристиками."""

    code: str
    name: str
    attributes: dict[str, str | int | float | bool] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        if not isinstance(self.code, str) or not self.code.strip():
            raise ValueError("Container type code must be a non-empty string")

        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("Container type name must be a non-empty string")

        if not isinstance(self.attributes, dict):
            raise TypeError("Container type attributes must be a dictionary")

        for key, value in self.attributes.items():
            if not isinstance(key, str) or not key.strip():
                raise ValueError("Attribute names must be non-empty strings")

            if type(value) not in (str, int, float, bool):
                raise TypeError("Attribute values must be simple scalar values")

            if isinstance(value, float) and not math.isfinite(value):
                raise ValueError("Attribute values must be finite")