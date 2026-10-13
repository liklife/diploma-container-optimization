
from collections.abc import Mapping
from dataclasses import dataclass, field
from math import isfinite
from types import MappingProxyType

from stowage.domain._validation import as_text


@dataclass(frozen=True)
class ContainerType:
    """Тип контейнера с настраиваемыми неизменяемыми характеристиками."""

    code: str
    name: str
    attributes: Mapping[str, str | int | float | bool] = field(
        default_factory=dict,
        hash=False,
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "code", as_text(self.code, "Container type code")
        )
        object.__setattr__(
            self, "name", as_text(self.name, "Container type name")
        )

        if not isinstance(self.attributes, Mapping):
            raise TypeError(
                "Container type attributes must be a mapping"
            )

        # Создаём собственную копию до проверки и замораживания.
        attributes = dict(self.attributes)

        for key, value in attributes.items():
            if not isinstance(key, str):
                raise TypeError("Attribute names must be strings")

            if not key.strip():
                raise ValueError("Attribute names must be non-empty strings")

            if type(value) not in (str, int, float, bool):
                raise TypeError(
                    "Attribute values must be simple scalar values"
                )

            if isinstance(value, float) and not isfinite(value):
                raise ValueError("Attribute values must be finite")

        object.__setattr__(
            self,
            "attributes",
            MappingProxyType(attributes),
        )
