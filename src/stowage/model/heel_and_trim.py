"""Крен и дифферент в принятой модели малых углов."""

import math

from stowage.domain._validation import as_number
from stowage.domain.vessel import Vessel


def calculate_heel_and_trim(
    vessel: Vessel,
    cg_x_m: float,
    cg_y_m: float,
    gm_transverse_m: float,
    gm_longitudinal_m: float,
) -> tuple[float, float, float]:
    """Возвращает (heel_rad, trim_rad, trim_m): радианы, радианы, метры.

    Положительный крен направлен на правый борт, дифферент — на нос.
    Продольное плечо отсчитывается от середины длины корпуса.
    Масса и гидростатика не пересчитываются; обе GM должны быть > 0,
    в том числе при нулевых плечах.

    За пределами ±5° числа являются только диагностическими показателями,
    а не достоверной оценкой равновесного угла вне области малых углов.
    Функция не проверяет угловые и эксплуатационные пределы и не
    подтверждает допустимость состояния.

    Неверные типы вызывают TypeError, некорректные значения,
    неподдерживаемая модель и численное переполнение — ValueError.
    """
    if not isinstance(vessel, Vessel):
        raise TypeError("Expected a Vessel instance")
    if not vessel.synthetic or vessel.hull_model != "box_barge":
        raise ValueError("Only synthetic box_barge vessels are supported")

    cg_x = as_number(cg_x_m, "CG X")
    cg_y = as_number(cg_y_m, "CG Y")
    gm_transverse = as_number(gm_transverse_m, "Transverse GM")
    gm_longitudinal = as_number(gm_longitudinal_m, "Longitudinal GM")
    if gm_transverse <= 0:
        raise ValueError("Transverse GM must be positive for heel calculation")
    if gm_longitudinal <= 0:
        raise ValueError("Longitudinal GM must be positive for trim calculation")

    transverse_arm = cg_y
    longitudinal_arm = cg_x - vessel.length_m / 2
    if not all(math.isfinite(value) for value in (transverse_arm, longitudinal_arm)):
        raise ValueError("Heel and trim arms must remain finite")

    # При положительных GM atan2 эквивалентен atan(плечо / GM),
    # но не требует потенциально переполняющегося деления для углов.
    heel_rad = math.atan2(transverse_arm, gm_transverse)
    trim_rad = math.atan2(longitudinal_arm, gm_longitudinal)
    trim_ratio = longitudinal_arm / gm_longitudinal
    if not math.isfinite(trim_ratio):
        raise ValueError("Trim arm to GM ratio must remain finite")

    # L * tan(atan(плечо / GM_L)) = L * (плечо / GM_L).
    trim_m = vessel.length_m * trim_ratio
    result = (heel_rad, trim_rad, trim_m)
    if not all(math.isfinite(value) for value in result):
        raise ValueError("Heel and trim results must remain finite")

    return result
