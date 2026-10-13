"""Общие проверки и нормализация значений доменной модели."""

import math
from numbers import Integral, Real


def as_int(value: object, field_name: str) -> int:
    """Принимает целое число и возвращает обычный Python int."""

    if isinstance(value, bool) or not isinstance(value, Integral):
        raise TypeError(f"{field_name} must be an integer")

    return int(value)


def as_number(value: object, field_name: str) -> float:
    """Проверяет конечное вещественное число и возвращает float."""

    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{field_name} must be a number")

    try:
        result = float(value)
    except (OverflowError, ValueError) as exc:
        raise ValueError(f"{field_name} must be finite") from exc

    if not math.isfinite(result):
        raise ValueError(f"{field_name} must be finite")

    return result


def as_text(
    value: object,
    field_name: str,
    *,
    reject_surrounding_whitespace: bool = False,
) -> str:
    """Проверяет непустую строку, не изменяя её содержимое."""

    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")

    if not value.strip():
        raise ValueError(f"{field_name} must not be empty")

    if (
        reject_surrounding_whitespace
        and value != value.strip()
    ):
        raise ValueError(
            f"{field_name} must not have surrounding whitespace"
        )

    return value