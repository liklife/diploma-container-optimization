"""Начальная гидростатика синтетического прямоугольного корпуса."""

import math

from stowage.domain._validation import as_number
from stowage.domain.vessel import Vessel


def calculate_hydrostatics(
    vessel: Vessel,
    total_mass_kg: float,
    cg_z_m: float,
) -> tuple[float, float, float, float, float, float]:
    """Возвращает (T, KB, BM_T, BM_L, GM_T, GM_L), всё в метрах.

    Для box_barge: T = M/(rho*L*B), KB = T/2,
    BM_T = B²/(12*T), BM_L = L²/(12*T), GM = KB + BM - Z_G.
    Формулы относятся к исходному положению при 0 < T < depth_m.
    Эксплуатационный предел max_draft_m проверяется отдельно.
    Нулевая и отрицательная GM возвращаются без проверки допустимости.

    TypeError означает неверный тип входа; ValueError — неподдерживаемую
    модель, недопустимое значение или численный выход за область расчёта.
    """
    if not isinstance(vessel, Vessel):
        raise TypeError("Expected a Vessel instance")
    if not vessel.synthetic or vessel.hull_model != "box_barge":
        raise ValueError("Only synthetic box_barge vessels are supported")

    mass = as_number(total_mass_kg, "Total mass")
    cg_z = as_number(cg_z_m, "CG Z")
    if mass <= 0:
        raise ValueError("Total mass must be positive")
    if cg_z < 0:
        raise ValueError("CG Z must be non-negative")

    # Масса вытесненной воды равна общей массе судна с грузом.
    volume = mass / vessel.water_density_kg_m3
    waterplane_area = vessel.length_m * vessel.beam_m
    if not all(
        math.isfinite(value) and value > 0
        for value in (volume, waterplane_area)
    ):
        raise ValueError("Displaced volume and waterplane area must remain finite and positive")

    draft = volume / waterplane_area
    if not math.isfinite(draft) or draft <= 0:
        raise ValueError("Calculated draft must remain finite and positive")
    if draft >= vessel.depth_m:
        raise ValueError("Calculated draft must be less than vessel depth_m")

    beam_squared = vessel.beam_m * vessel.beam_m
    length_squared = vessel.length_m * vessel.length_m
    denominator = 12 * draft
    if not all(
        math.isfinite(value) and value > 0
        for value in (beam_squared, length_squared, denominator)
    ):
        raise ValueError("Hydrostatic intermediate values must remain finite and positive")

    kb = draft / 2
    bm_transverse = beam_squared / denominator
    bm_longitudinal = length_squared / denominator
    gm_transverse = kb + bm_transverse - cg_z
    gm_longitudinal = kb + bm_longitudinal - cg_z
    result = (draft, kb, bm_transverse, bm_longitudinal, gm_transverse, gm_longitudinal)

    if not all(math.isfinite(value) for value in result):
        raise ValueError("Hydrostatic results must remain finite")
    if kb <= 0 or bm_transverse <= 0 or bm_longitudinal <= 0:
        raise ValueError("KB and BM must remain positive")

    return result
