"""Единая оценка размещения для алгоритмов и приложения."""

from dataclasses import dataclass

from stowage.config.loader import LimitsConfig
from stowage.domain.plan import Plan
from stowage.domain.port_rotation import PortRotation
from stowage.model.blocking_pairs import count_blocking_pairs
from stowage.model.center_of_gravity import calculate_mass_and_cg
from stowage.model.constraints import check_plan
from stowage.model.heel_and_trim import calculate_heel_and_trim
from stowage.model.hydrostatics import calculate_hydrostatics


@dataclass(frozen=True)
class PlanEvaluation:
    """Сохраняет результаты расчётов в порядке, принятом в T06 и T07.

    mass_and_cg: (M, X_G, Y_G, Z_G) в кг и м.
    hydrostatics: (T, KB, BM_T, BM_L, GM_T, GM_L) в метрах.
    heel_and_trim: (крен, угол дифферента, линейный дифферент) в рад, рад, м.
    None означает, что соответствующая группа показателей недоступна.
    """

    blocking_pairs: int
    is_valid: bool
    violations: tuple[str, ...]
    mass_and_cg: tuple[float, float, float, float] | None
    hydrostatics: tuple[float, float, float, float, float, float] | None
    heel_and_trim: tuple[float, float, float] | None

    @property
    def objectives(self) -> tuple[int, float | None, float | None]:
        """Возвращает (R, |крен| в рад, |дифферент| в м) отдельно."""
        if self.heel_and_trim is None:
            return self.blocking_pairs, None, None
        heel_rad, _, trim_m = self.heel_and_trim
        return self.blocking_pairs, abs(heel_rad), abs(trim_m)


def evaluate_plan(
    plan: Plan, rotation: PortRotation, limits: LimitsConfig
) -> PlanEvaluation:
    """Оценивает даже частичный план. Неизвестный порт вызывает ValueError."""
    blocking_pairs = count_blocking_pairs(plan, rotation)
    is_valid, violations = check_plan(plan, limits)

    mass_and_cg = hydrostatics = heel_and_trim = None
    try:
        mass_and_cg = calculate_mass_and_cg(plan)
        mass, cg_x, cg_y, cg_z = mass_and_cg
        hydrostatics = calculate_hydrostatics(plan.vessel, mass, cg_z)
        _, _, _, _, gm_t, gm_l = hydrostatics
        heel_and_trim = calculate_heel_and_trim(plan.vessel, cg_x, cg_y, gm_t, gm_l)
    except ValueError:
        # check_plan() уже сохранил причину, а успешные этапы доступны в результате.
        pass

    return PlanEvaluation(
        blocking_pairs, is_valid, violations, mass_and_cg, hydrostatics, heel_and_trim
    )
