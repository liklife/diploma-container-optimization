"""Одна детерминированная расстановка для сравнения с оптимизацией."""

from stowage.algorithms.decoder import decode_permutation
from stowage.config.loader import LimitsConfig
from stowage.domain.container import Container
from stowage.domain.plan import Plan
from stowage.domain.port_rotation import PortRotation
from stowage.domain.vessel import Vessel
from stowage.model.evaluation import PlanEvaluation, evaluate_plan


def run_heuristic(
    vessel: Vessel,
    containers: tuple[Container, ...] | list[Container],
    rotation: PortRotation,
    limits: LimitsConfig,
) -> tuple[Plan, PlanEvaluation]:
    """Передаёт декодеру индексы по убыванию массы. При равенстве порядок входной."""
    order = sorted(range(len(containers)), key=lambda index: -containers[index].mass_kg)
    plan = decode_permutation(vessel, containers, order)
    return plan, evaluate_plan(plan, rotation, limits)
