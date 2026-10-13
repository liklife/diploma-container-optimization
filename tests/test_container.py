
import math

import pytest

from stowage.domain.container import Container


def test_create_container_with_valid_data():
    container = Container(
        id=1,
        mass_kg=12000,
        port="Калининград",
        container_type="dry",
    )

    assert container.id == 1
    assert container.mass_kg == 12000
    assert container.port == "Калининград"
    assert container.container_type == "dry"


def test_container_id_zero_is_allowed():
    container = Container(
        id=0,
        mass_kg=5000,
        port="Мурманск",
        container_type="reefer",
    )

    assert container.id == 0


@pytest.mark.parametrize("invalid_id", [-1, 1.5, "1", True])
def test_invalid_id_raises_error(invalid_id):
    with pytest.raises((TypeError, ValueError)):
        Container(
            id=invalid_id,
            mass_kg=10000,
            port="Мурманск",
            container_type="dry",
        )


@pytest.mark.parametrize("invalid_mass", [0, -1, math.nan, math.inf, -math.inf])
def test_invalid_mass_raises_error(invalid_mass):
    with pytest.raises(ValueError):
        Container(
            id=1,
            mass_kg=invalid_mass,
            port="Мурманск",
            container_type="dry",
        )


@pytest.mark.parametrize("invalid_mass", [True, "10000", None])
def test_non_numeric_mass_raises_error(invalid_mass):
    with pytest.raises(TypeError):
        Container(
            id=1,
            mass_kg=invalid_mass,
            port="Мурманск",
            container_type="dry",
        )


@pytest.mark.parametrize("invalid_port", ["", "   ", None, 123])
def test_invalid_port_raises_error(invalid_port):
    with pytest.raises((TypeError, ValueError)):
        Container(
            id=1,
            mass_kg=10000,
            port=invalid_port,
            container_type="dry",
        )


@pytest.mark.parametrize("invalid_type", ["", "   ", None, 123])
def test_invalid_container_type_raises_error(invalid_type):
    with pytest.raises((TypeError, ValueError)):
        Container(
            id=1,
            mass_kg=10000,
            port="Мурманск",
            container_type=invalid_type,
        )


def test_new_container_type_is_allowed():
    container = Container(
        id=2,
        mass_kg=8000,
        port="Санкт-Петербург",
        container_type="future_type",
    )

    assert container.container_type == "future_type"

def test_container_normalizes_numpy_integer_id():
    import numpy as np

    container = Container(
        id=np.int64(3),
        mass_kg=10000,
        port="Мурманск",
        container_type="dry",
    )

    assert container.id == 3
    assert type(container.id) is int


def test_container_rejects_numpy_boolean_id():
    import numpy as np

    with pytest.raises(TypeError):
        Container(
            id=np.bool_(True),
            mass_kg=10000,
            port="Мурманск",
            container_type="dry",
        )