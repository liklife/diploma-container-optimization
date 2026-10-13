from dataclasses import dataclass

from stowage.domain._validation import as_text


@dataclass(frozen=True)
class PortRotation:
    """Последовательность портов захода судна."""

    ports: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.ports, (tuple, list)):
            raise TypeError("Port rotation must be a tuple or list of ports")

        if not self.ports:
            raise ValueError("Port rotation must contain at least one port")

        normalized: list[str] = []

        for port in self.ports:
            normalized.append(
                as_text(
                    port,
                    "Port name",
                    reject_surrounding_whitespace=True,
                )
            )

        object.__setattr__(self, "ports", tuple(normalized))