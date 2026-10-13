
import math

import pytest

from stowage.domain.container_type import ContainerType


def test_create_container_type():
    container_type = ContainerType(
        code="dry",
        name="Сухой контейнер",
    )

    assert container_type.code == "dry"
    assert container_type.name == "Сухой контейнер"
    assert container_type.attributes == {}


def test_container_type_accepts_custom_attributes():
    container_type = ContainerType(
        code="reefer",
        name="Рефрижераторный контейнер",
        attributes={
            "requires_power": True,
            "description": "Дополнительная характеристика",
            "priority": 2,
            "capacity_factor": 1.5,
        },
    )

    assert container_type.attributes["requires_power"] is True
    assert container_type.attributes["priority"] == 2



def test_default_attributes_are_independent():
    first_source = {}
    second_source = {}

    first = ContainerType(
        code="dry",
        name="Dry",
        attributes=first_source,
    )
    second = ContainerType(
        code="tank",
        name="Tank",
        attributes=second_source,
    )

    first_source["custom"] = True

    assert first.attributes == {}
    assert second.attributes == {}


def test_attributes_are_read_only():
    container_type = ContainerType(
        code="dry",
        name="Dry",
        attributes={"priority": 1},
    )

    with pytest.raises(TypeError):
        container_type.attributes["priority"] = 2


def test_input_mapping_is_copied():
    source = {"priority": 1}
    container_type = ContainerType(
        code="dry",
        name="Dry",
        attributes=source,
    )

    source["priority"] = 99
    source["new"] = True

    assert container_type.attributes["priority"] == 1
    assert "new" not in container_type.attributes


def test_container_type_fields_are_immutable():
    container_type = ContainerType(
        code="dry",
        name="Dry",
        attributes={"priority": 1},
    )

    with pytest.raises(AttributeError):
        container_type.code = "tank"

    with pytest.raises(AttributeError):
        container_type.name = "Tank"

    with pytest.raises(AttributeError):
        container_type.attributes = {}


def test_container_type_remains_hashable():
    container_type = ContainerType(
        code="dry",
        name="Dry",
        attributes={"priority": 1},
    )

    assert isinstance(hash(container_type), int)



@pytest.mark.parametrize("invalid_code", ["", "   ", None, 123])
def test_invalid_code_raises_error(invalid_code):
    with pytest.raises((TypeError, ValueError)):
        ContainerType(code=invalid_code, name="Test")


@pytest.mark.parametrize("invalid_name", ["", "   ", None, 123])
def test_invalid_name_raises_error(invalid_name):
    with pytest.raises((TypeError, ValueError)):
        ContainerType(code="dry", name=invalid_name)


@pytest.mark.parametrize("invalid_attributes", [None, [], "attributes", 123])
def test_invalid_attributes_container_raises_error(invalid_attributes):
    with pytest.raises(TypeError):
        ContainerType(
            code="dry",
            name="Dry",
            attributes=invalid_attributes,
        )


def test_empty_attribute_name_is_rejected():
    with pytest.raises(ValueError):
        ContainerType(
            code="dry",
            name="Dry",
            attributes={" ": "value"},
        )


@pytest.mark.parametrize("invalid_value", [None, [], {}, object()])
def test_invalid_attribute_value_is_rejected(invalid_value):
    with pytest.raises(TypeError):
        ContainerType(
            code="dry",
            name="Dry",
            attributes={"custom": invalid_value},
        )


@pytest.mark.parametrize("invalid_value", [math.nan, math.inf, -math.inf])
def test_non_finite_float_attribute_is_rejected(invalid_value):
    with pytest.raises(ValueError):
        ContainerType(
            code="dry",
            name="Dry",
            attributes={"coefficient": invalid_value},
        )
