
from dataclasses import dataclass

from stowage.domain._validation import as_text


@dataclass(frozen=True)
class PortRotation:
    """Упорядоченная последовательность уникальных портов захода."""

    ports: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.ports, (tuple, list)):
            raise TypeError(
                "Port rotation must be a tuple or list of ports"
            )

        if not self.ports:
            raise ValueError(
                "Port rotation must contain at least one port"
            )

        normalized: list[str] = []

        for port in self.ports:
            normalized.append(
                as_text(
                    port,
                    "Port name",
                    reject_surrounding_whitespace=True,
                )
            )

        if len(set(normalized)) != len(normalized):
            raise ValueError(
                "Port rotation must not contain duplicate ports"
            )

        object.__setattr__(self, "ports", tuple(normalized))

    def index_of(self, port: str) -> int:
        """Возвращает позицию порта в маршруте, начиная с нуля."""

        port = as_text(
            port,
            "Port name",
            reject_surrounding_whitespace=True,
        )

        try:
            return self.ports.index(port)
        except ValueError:
            known_ports = ", ".join(self.ports)
            raise ValueError(
                f"Unknown port '{port}'. Known ports: {known_ports}"
            ) from None
