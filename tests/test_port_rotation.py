import pytest

from stowage.domain.port_rotation import PortRotation


def test_create_port_rotation():
    rotation = PortRotation(
        ports=(
            "Калининград",
            "Санкт-Петербург",
            "Мурманск",
        )
    )

    assert rotation.ports == (
        "Калининград",
        "Санкт-Петербург",
        "Мурманск",
    )


def test_custom_route_is_allowed():
    rotation = PortRotation(
        ports=("Port A", "Port B")
    )

    assert rotation.ports == ("Port A", "Port B")


def test_list_is_converted_to_tuple():
    source = ["Калининград", "Мурманск"]
    rotation = PortRotation(ports=source)

    source.append("Другой порт")

    assert rotation.ports == ("Калининград", "Мурманск")
    assert isinstance(rotation.ports, tuple)


def test_empty_rotation_is_rejected():
    with pytest.raises(ValueError):
        PortRotation(ports=())


@pytest.mark.parametrize(
    "invalid_ports",
    [None, "Калининград", 123, {}],
)
def test_invalid_rotation_container_is_rejected(invalid_ports):
    with pytest.raises(TypeError):
        PortRotation(ports=invalid_ports)


@pytest.mark.parametrize(
    "invalid_port",
    ["", "   "],
)
def test_empty_port_name_is_rejected(invalid_port):
    with pytest.raises(ValueError):
        PortRotation(ports=("Калининград", invalid_port))


@pytest.mark.parametrize(
    "invalid_port",
    [None, 123, True],
)
def test_non_string_port_is_rejected(invalid_port):
    with pytest.raises(TypeError):
        PortRotation(ports=("Калининград", invalid_port))


@pytest.mark.parametrize(
    "invalid_port",
    [" Санкт-Петербург", "Санкт-Петербург "],
)
def test_surrounding_whitespace_is_rejected(invalid_port):
    with pytest.raises(ValueError):
        PortRotation(ports=("Калининград", invalid_port))