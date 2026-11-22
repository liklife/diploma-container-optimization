"""Общий функциональный вход для эвристики и NSGA-II."""

from dataclasses import dataclass
from typing import Literal

from stowage.algorithms.heuristic import run_heuristic
from stowage.config.loader import LimitsConfig
from stowage.domain._validation import as_int
from stowage.domain.container import Container
from stowage.domain.plan import Plan
from stowage.domain.port_rotation import PortRotation
from stowage.domain.vessel import Vessel
from stowage.model.evaluation import PlanEvaluation


@dataclass(frozen=True)
class SolveResult:
    """Настройки запуска и найденные допустимые пары (план, оценка)."""

    method: str
    solutions: tuple[tuple[Plan, PlanEvaluation], ...]
    n_evaluations: int
    reason: str | None = None
    seed: int | None = None
    pop_size: int | None = None
    generations: int | None = None

    @property
    def status(self) -> Literal["ok", "no_feasible_solution"]:
        return "ok" if self.solutions else "no_feasible_solution"


def solve(
    vessel: Vessel,
    containers: tuple[Container, ...] | list[Container],
    rotation: PortRotation,
    limits: LimitsConfig,
    *,
    method: Literal["heuristic", "nsga2"],
    seed: int | None = None,
    pop_size: int | None = None,
    generations: int | None = None,
) -> SolveResult:
    """Запускает выбранный метод. Бюджет NSGA-II задаётся в поколениях."""
    if method not in ("heuristic", "nsga2"):
        raise ValueError(f"Unknown solver method: {method}")
    scenario = Plan(vessel, containers)
    for container in scenario.containers:
        rotation.index_of(container.port)

    if method == "heuristic":
        if any(value is not None for value in (seed, pop_size, generations)):
            raise ValueError("Seed and search budget are only used by NSGA-II")
        plan, evaluation = run_heuristic(vessel, scenario.containers, rotation, limits)
        if not evaluation.is_valid:
            return SolveResult(
                method, (), 1,
                reason="Эвристика не нашла допустимый план. " + ". ".join(evaluation.violations),
            )
        return SolveResult(method, ((plan, evaluation),), 1)

    if seed is None or pop_size is None or generations is None:
        raise ValueError("NSGA-II requires seed, pop_size and generations")
    seed = as_int(seed, "Seed")
    pop_size = as_int(pop_size, "Population size")
    generations = as_int(generations, "Generations")
    if seed < 0 or pop_size <= 0 or generations <= 0:
        raise ValueError("Seed must be nonnegative and the search budget positive")

    # Для базовой эвристики не требуется импортировать pymoo.
    from stowage.algorithms.nsga2 import run_nsga2
    from stowage.algorithms.pymoo_problem import StowageProblem

    problem = StowageProblem(vessel, scenario.containers, rotation, limits)
    solutions, evaluations = run_nsga2(
        problem, seed=seed, pop_size=pop_size, generations=generations,
    )
    reason = None if solutions else "NSGA-II не нашёл допустимый план за заданный бюджет."
    return SolveResult(method, solutions, evaluations, reason, seed, pop_size, generations)
