from dataclasses import dataclass


@dataclass(frozen=True)
class PortRotation:
    """Последовательность портов захода судна."""

    ports: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.ports, (tuple, list)):
            raise TypeError("Port rotation must be a tuple or list of ports")

        if not self.ports:
            raise ValueError("Port rotation must contain at least one port")

        for port in self.ports:
            if not isinstance(port, str):
                raise TypeError("Every port name must be a string")

            if not port.strip():
                raise ValueError("Port names must not be empty")

            if port != port.strip():
                raise ValueError(
                    "Port names must not have surrounding whitespace"
                )

        # Храним последовательность неизменяемой.
        object.__setattr__(self, "ports", tuple(self.ports))