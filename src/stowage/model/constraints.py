"""Проверки размещения и физических ограничений исходной загрузки."""

import math

from stowage.config.loader import LimitsConfig
from stowage.domain.plan import Plan
from stowage.model.center_of_gravity import calculate_mass_and_cg
from stowage.model.heel_and_trim import calculate_heel_and_trim
from stowage.model.hydrostatics import calculate_hydrostatics


# Согласованная граница продольного угла, не настройка поперечного крена.
LONGITUDINAL_SMALL_ANGLE_LIMIT_DEG = 5.0


def check_plan(plan: Plan, limits: LimitsConfig) -> tuple[bool, tuple[str, ...]]:
    """Возвращает допустимость и конкретные нарушения с кодами.

    Структурные инварианты обеспечены конструкторами доменных объектов.
    limits предполагается проверенной конфигурацией из загрузчика.
    Масса проверяется для всего входного набора; нагрузки и физика —
    только для размещённого груза. Недоступность обязательного расчёта
    также означает False, но не подменяет его результат нулём.
    """
    if not isinstance(plan, Plan):
        raise TypeError("Expected a Plan instance")
    if not isinstance(limits, LimitsConfig):
        raise TypeError("Expected a LimitsConfig instance")

    violations: list[str] = []
    for container in plan.unplaced_containers:
        violations.append(f"unplaced_container: контейнер {container.id} не размещён")
    for container in plan.containers:
        if container.mass_kg > limits.max_container_mass_kg:
            violations.append(
                f"container_mass: контейнер {container.id}: {container.mass_kg} кг "
                f"> {limits.max_container_mass_kg} кг"
            )

    container_by_id = {container.id: container for container in plan.containers}
    occupied = {(slot.bay, slot.row, slot.tier) for _, slot in plan.placements}
    columns: dict[tuple[int, int], list[float]] = {}
    bays: dict[int, list[float]] = {}
    for container_id, slot in plan.placements:
        if slot.tier > 0 and (slot.bay, slot.row, slot.tier - 1) not in occupied:
            violations.append(
                f"unsupported_container: контейнер {container_id}, "
                f"слот ({slot.bay}, {slot.row}, {slot.tier}): нет опоры"
            )
        mass = container_by_id[container_id].mass_kg
        columns.setdefault((slot.bay, slot.row), []).append(mass)
        bays.setdefault(slot.bay, []).append(mass)

    # Одинаковое суммирование для колонн и bay; масса порожнего судна не входит.
    for code, groups, limit_t in (
        ("column_load", columns, plan.vessel.max_column_load_t),
        ("bay_load", bays, plan.vessel.max_bay_load_t),
    ):
        limit_kg = limit_t * 1000
        if not math.isfinite(limit_kg):
            violations.append(f"calculation_error: {code}: перевод предела в кг переполнен")
            continue
        for position, masses in groups.items():
            try:
                load = math.fsum(masses)
            except (OverflowError, ValueError) as exc:
                violations.append(f"calculation_error: {code} {position}: {exc}")
                continue
            if not math.isfinite(load):
                violations.append(f"calculation_error: {code} {position}: нагрузка неконечна")
            elif load > limit_kg:
                violations.append(
                    f"{code}: {position}: {load} кг > {limit_kg} кг"
                )

    violations.extend(_check_physical_constraints(plan, limits))
    return not violations, tuple(violations)


def _check_physical_constraints(plan: Plan, limits: LimitsConfig) -> list[str]:
    """Сравнивает готовые расчёты T06/T07 с пределами, сохраняя причины отказа."""
    violations: list[str] = []
    vessel = plan.vessel
    try:
        mass, cg_x, cg_y, cg_z = calculate_mass_and_cg(plan)
    except ValueError as exc:
        return [f"calculation_error: масса/ЦТ: {exc}; физические проверки не выполнены"]

    try:
        draft, _, _, _, gm_t, gm_l = calculate_hydrostatics(vessel, mass, cg_z)
    except ValueError as exc:
        return [f"hydrostatics: {exc}; проверки осадки, GM и углов не выполнены"]

    try:
        vessel.validate_draft(draft)
    except ValueError as exc:
        violations.append(f"draft: {draft} м, предел {vessel.max_draft_m} м: {exc}")

    if gm_t <= 0:
        violations.append(f"gm: GM_T={gm_t} м; для расчёта углов требуется GM_T > 0")
    elif gm_t < limits.min_gm_m:
        violations.append(f"gm: GM_T={gm_t} м < {limits.min_gm_m} м")
    if gm_l <= 0:
        violations.append(f"gm: GM_L={gm_l} м; для расчёта углов требуется GM_L > 0")
    if gm_t <= 0 or gm_l <= 0:
        violations.append("calculation_error: неположительная GM; проверки углов не выполнены")
        return violations

    try:
        heel, trim_angle, trim_m = calculate_heel_and_trim(vessel, cg_x, cg_y, gm_t, gm_l)
    except ValueError as exc:
        violations.append(f"calculation_error: углы: {exc}; проверки углов не выполнены")
        return violations

    heel_limit = math.radians(limits.max_abs_heel_deg)
    if abs(heel) > heel_limit:
        violations.append(
            f"heel: {math.degrees(heel)}°; предел ±{limits.max_abs_heel_deg}°"
        )

    trim_limit_m = vessel.length_m * limits.max_abs_trim_percent_of_length / 100
    if not math.isfinite(trim_limit_m):
        violations.append("calculation_error: предел дифферента неконечен; проверка не выполнена")
    elif abs(trim_m) > trim_limit_m:
        violations.append(f"trim: {trim_m} м; предел ±{trim_limit_m} м")

    small_heel_limit = math.radians(limits.small_angle_model_max_abs_heel_deg)
    if abs(heel) > small_heel_limit:
        violations.append(
            f"small_angle: крен {math.degrees(heel)}° вне "
            f"±{limits.small_angle_model_max_abs_heel_deg}°; результат диагностический"
        )
    if abs(trim_angle) > math.radians(LONGITUDINAL_SMALL_ANGLE_LIMIT_DEG):
        violations.append(
            f"small_angle: продольный угол {math.degrees(trim_angle)}° вне "
            f"±{LONGITUDINAL_SMALL_ANGLE_LIMIT_DEG}°; результат диагностический"
        )
    return violations
