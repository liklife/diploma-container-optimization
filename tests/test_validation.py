import math

import numpy as np
import pytest

from stowage.domain._validation import as_int, as_number, as_text


def test_as_int_accepts_numpy_integer_and_returns_builtin_int():
    result = as_int(np.int64(3), "test value")

    assert result == 3
    assert type(result) is int


@pytest.mark.parametrize(
    "value",
    [True, False, np.bool_(True), 3.0, "3", None],
)
def test_as_int_rejects_non_integer_values(value):
    with pytest.raises(TypeError):
        as_int(value, "test value")


def test_as_number_accepts_numpy_float():
    result = as_number(np.float64(1.5), "test value")

    assert result == 1.5
    assert type(result) is float


@pytest.mark.parametrize(
    "value",
    [True, np.bool_(True), "1.5", None],
)
def test_as_number_rejects_invalid_types(value):
    with pytest.raises(TypeError):
        as_number(value, "test value")


@pytest.mark.parametrize(
    "value",
    [math.nan, math.inf, -math.inf],
)
def test_as_number_rejects_non_finite_values(value):
    with pytest.raises(ValueError):
        as_number(value, "test value")


@pytest.mark.parametrize("value", ["", "   "])
def test_as_text_rejects_empty_strings(value):
    with pytest.raises(ValueError):
        as_text(value, "test value")


@pytest.mark.parametrize("value", [None, 123, True])
def test_as_text_rejects_non_strings(value):
    with pytest.raises(TypeError):
        as_text(value, "test value")


def test_as_text_does_not_normalize_values():
    value = " test "

    assert as_text(value, "test value") == value


def test_as_text_can_reject_surrounding_whitespace():
    with pytest.raises(ValueError, match="surrounding whitespace"):
        as_text(
            " test ",
            "test value",
            reject_surrounding_whitespace=True,
        )