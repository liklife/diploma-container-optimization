"""Масса и центр тяжести системы «судно — размещённый груз»."""

import math

from stowage.domain.plan import Plan


def calculate_mass_and_cg(
    plan: Plan,
) -> tuple[float, float, float, float]:
    """Возвращает (общая масса в кг, X_G, Y_G, Z_G в метрах).

    M = M_0 + sum(m), координаты ЦТ равны sum(m * coordinate) / M
    с учётом массы и моментов порожнего судна.
    Масса контейнера включает тару и содержимое, его ЦТ совпадает
    с центром назначенного слота. Неразмещённый груз не учитывается.
    Расчёт частичного плана не подтверждает его допустимость.

    TypeError означает неверный тип plan, ValueError — переполнение
    или неконечный результат расчёта.
    """
    if not isinstance(plan, Plan):
        raise TypeError("Expected a Plan instance")

    vessel = plan.vessel
    if not plan.placements:
        return (
            vessel.lightship_mass_kg,
            vessel.lightship_cg_x_m,
            vessel.lightship_cg_y_m,
            vessel.lightship_cg_z_m,
        )

    container_by_id = {container.id: container for container in plan.containers}
    masses = [vessel.lightship_mass_kg]
    moments_x = [vessel.lightship_mass_kg * vessel.lightship_cg_x_m]
    moments_y = [vessel.lightship_mass_kg * vessel.lightship_cg_y_m]
    moments_z = [vessel.lightship_mass_kg * vessel.lightship_cg_z_m]

    for container_id, slot in plan.placements:
        mass = container_by_id[container_id].mass_kg
        x, y, z = vessel.coordinates_for(slot)
        masses.append(mass)
        moments_x.append(mass * x)
        moments_y.append(mass * y)
        moments_z.append(mass * z)

    # fsum уменьшает погрешность при изменении порядка слагаемых.
    try:
        total_mass = math.fsum(masses)
        moment_x = math.fsum(moments_x)
        moment_y = math.fsum(moments_y)
        moment_z = math.fsum(moments_z)
    except (OverflowError, ValueError) as exc:
        raise ValueError(
            "Mass and center of gravity calculation must remain finite"
        ) from exc

    # Конечные входы могут дать бесконечность при умножении или сложении.
    if not all(math.isfinite(value) for value in (
        total_mass, moment_x, moment_y, moment_z
    )):
        raise ValueError(
            "Mass and center of gravity calculation must remain finite"
        )

    result = (
        total_mass,
        moment_x / total_mass,
        moment_y / total_mass,
        moment_z / total_mass,
    )
    if not all(math.isfinite(value) for value in result):
        raise ValueError(
            "Mass and center of gravity calculation must remain finite"
        )

    return result
