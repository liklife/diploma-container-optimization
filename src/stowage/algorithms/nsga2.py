"""Поиск допустимых размещений библиотечным NSGA-II."""

import numpy as np
from pymoo.algorithms.moo.nsga2 import NSGA2
from pymoo.operators.crossover.ox import OrderCrossover
from pymoo.operators.mutation.inversion import InversionMutation
from pymoo.operators.sampling.rnd import PermutationRandomSampling
from pymoo.optimize import minimize

from stowage.algorithms.pymoo_problem import StowageProblem
from stowage.domain.plan import Plan
from stowage.model.constraints import check_plan
from stowage.model.evaluation import PlanEvaluation


def run_nsga2(
    problem: StowageProblem, *, seed: int, pop_size: int, generations: int,
) -> tuple[tuple[tuple[Plan, PlanEvaluation], ...], int]:
    """Возвращает проверенные решения и число оценок в поиске."""
    if problem.n_var < 2:
        # Пустая перестановка и перестановка из одного элемента единственны.
        # OX и инверсия требуют двух различных позиций.
        candidates = [range(problem.n_var)]
        evaluations = 1
    else:
        algorithm = NSGA2(
            pop_size=pop_size,
            sampling=PermutationRandomSampling(),
            crossover=OrderCrossover(prob=0.9),
            mutation=InversionMutation(prob=0.2),
            # В малых пространствах число уникальных перестановок может
            # быть меньше популяции. Повторы убираются при выдаче результата.
            eliminate_duplicates=False,
        )
        result = minimize(problem, algorithm, ("n_gen", generations), seed=seed)
        candidates = [] if result.X is None else np.atleast_2d(result.X)
        evaluations = result.algorithm.evaluator.n_eval

    solutions: list[tuple[Plan, PlanEvaluation]] = []
    seen: set[tuple[int, ...]] = set()
    for candidate in candidates:
        order = tuple(candidate)
        if order in seen:
            continue
        seen.add(order)
        plan, evaluation = problem.evaluate_permutation(order)
        if evaluation.is_valid and check_plan(plan, problem.limits)[0]:
            solutions.append((plan, evaluation))

    solutions.sort(key=lambda pair: pair[1].objectives)
    return tuple(solutions), evaluations
