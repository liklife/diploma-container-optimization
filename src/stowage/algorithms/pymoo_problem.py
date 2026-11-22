"""Адаптер перестановок, целей и ограничений для pymoo."""

import math
from sys import float_info

from pymoo.core.problem import ElementwiseProblem

from stowage.algorithms.decoder import decode_permutation
from stowage.config.loader import LimitsConfig
from stowage.domain.container import Container
from stowage.domain.plan import Plan
from stowage.domain.port_rotation import PortRotation
from stowage.domain.vessel import Vessel
from stowage.model.constraints import LONGITUDINAL_SMALL_ANGLE_LIMIT_DEG
from stowage.model.evaluation import PlanEvaluation, evaluate_plan


CONSTRAINT_NAMES = (
    "unplaced", "unsupported", "container_mass", "column_load", "bay_load",
    "draft", "min_gm_t", "positive_gm_t", "positive_gm_l",
    "heel", "trim", "small_heel", "small_trim", "check_plan",
)
_UNAVAILABLE = 2.0


def _excess(value: float, limit: float) -> float:
    """Положительное превышение, делённое на max(|значение|, |предел|)."""
    if not math.isfinite(value) or not math.isfinite(limit):
        return _UNAVAILABLE
    if value <= limit:
        return 0.0
    scale = max(abs(value), abs(limit))
    difference = value - limit
    if not math.isfinite(difference):
        return value / scale - limit / scale
    return difference / scale


def _load_excess(groups: dict, limit_t: float) -> float:
    limit_kg = limit_t * 1000
    if not math.isfinite(limit_kg):
        return _UNAVAILABLE
    try:
        return max((_excess(math.fsum(masses), limit_kg) for masses in groups.values()),
                   default=0.0)
    except (ValueError, OverflowError):
        return _UNAVAILABLE


def constraint_violations(
    plan: Plan, limits: LimitsConfig, evaluation: PlanEvaluation
) -> tuple[float, ...]:
    """Возвращает безразмерные g в порядке CONSTRAINT_NAMES.

    Полнота и опора выражены долей от числа контейнеров. Масса и нагрузки
    сравниваются в кг, осадка, GM и линейный дифферент в м, углы в рад.
    Для массы и нагрузок берётся максимальное превышение среди объектов.
    Отсутствие гидростатики (включая выход осадки из 0 < T < depth_m)
    или углов отмечается конечным значением 2 в зависимых ограничениях.
    Строгая положительность GM проверяется индикатором 0/1.
    Нарушение из check_plan() сохраняется даже при отсутствии числового
    превышения. Структурную корректность самого Plan проверяет домен.
    """
    vessel = plan.vessel
    container_count = max(1, len(plan.containers))
    unplaced = len(plan.unplaced_containers) / container_count
    max_mass = max((container.mass_kg for container in plan.containers), default=0.0)
    container_mass = _excess(max_mass, limits.max_container_mass_kg)

    masses_by_id = {container.id: container.mass_kg for container in plan.containers}
    occupied = {(slot.bay, slot.row, slot.tier) for _, slot in plan.placements}
    unsupported_count = 0
    columns: dict[tuple[int, int], list[float]] = {}
    bays: dict[int, list[float]] = {}
    for container_id, slot in plan.placements:
        if slot.tier > 0 and (slot.bay, slot.row, slot.tier - 1) not in occupied:
            unsupported_count += 1
        mass = masses_by_id[container_id]
        columns.setdefault((slot.bay, slot.row), []).append(mass)
        bays.setdefault(slot.bay, []).append(mass)

    if evaluation.hydrostatics is None:
        draft = min_gm_t = positive_gm_t = positive_gm_l = _UNAVAILABLE
    else:
        draft_m, _, _, _, gm_t, gm_l = evaluation.hydrostatics
        draft = _excess(draft_m, vessel.max_draft_m)
        min_gm_t = _excess(-gm_t, -limits.min_gm_m)
        positive_gm_t = float(gm_t <= 0)
        positive_gm_l = float(gm_l <= 0)

    if evaluation.heel_and_trim is None:
        heel = trim = small_heel = small_trim = _UNAVAILABLE
    else:
        heel_rad, trim_rad, trim_m = evaluation.heel_and_trim
        heel = _excess(abs(heel_rad), math.radians(limits.max_abs_heel_deg))
        trim = _excess(abs(trim_m), vessel.length_m * limits.max_abs_trim_percent_of_length / 100)
        small_heel = _excess(abs(heel_rad), math.radians(limits.small_angle_model_max_abs_heel_deg))
        small_trim = _excess(abs(trim_rad), math.radians(LONGITUDINAL_SMALL_ANGLE_LIMIT_DEG))

    constraints = (
        unplaced, unsupported_count / container_count, container_mass,
        _load_excess(columns, vessel.max_column_load_t),
        _load_excess(bays, vessel.max_bay_load_t),
        draft, min_gm_t, positive_gm_t, positive_gm_l,
        heel, trim, small_heel, small_trim,
    )
    has_excess = any(value > 0.0 for value in constraints)
    if evaluation.is_valid and has_excess:
        raise ValueError("Numerical constraints disagree with check_plan()")
    return (*constraints, float(not evaluation.is_valid and not has_excess))


class StowageProblem(ElementwiseProblem):
    """Одна особь представляет индексы всех контейнеров сценария."""

    def __init__(
        self,
        vessel: Vessel,
        containers: tuple[Container, ...] | list[Container],
        rotation: PortRotation,
        limits: LimitsConfig,
    ) -> None:
        self.vessel = vessel
        self.containers = tuple(containers)
        self.rotation = rotation
        self.limits = limits
        super().__init__(
            n_var=len(self.containers), n_obj=3,
            n_ieq_constr=len(CONSTRAINT_NAMES), vtype=int,
        )

    def evaluate_permutation(self, permutation) -> tuple[Plan, PlanEvaluation]:
        plan = decode_permutation(self.vessel, self.containers, permutation)
        return plan, evaluate_plan(plan, self.rotation, self.limits)

    def _evaluate(self, x, out, *args, **kwargs):
        plan, evaluation = self.evaluate_permutation(x)
        blocking_pairs, heel, trim = evaluation.objectives
        # Недоступные цели заведомо не лучше вычисленных. G исключает
        # такой план из допустимых, а в PlanEvaluation остаётся None.
        out["F"] = (
            blocking_pairs,
            math.pi if heel is None else heel,
            float_info.max if trim is None else trim,
        )
        out["G"] = constraint_violations(plan, self.limits, evaluation)
