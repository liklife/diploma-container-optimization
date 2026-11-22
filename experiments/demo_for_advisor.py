"""Демонстрация исходной загрузки и отдельного теста порога GM."""

import argparse
import csv
import hashlib
import json
import math
import os
from dataclasses import asdict
from time import perf_counter

import pandas as pd

from experiments import gm_active
from experiments.preliminary import OBJECTIVES, ROOT, SOURCE, dominates, observed_front
from stowage.algorithms.solver import SolveResult, solve
from stowage.config import load_project_config
from stowage.domain.container import Container
from stowage.domain.plan import Plan
from stowage.domain.slot import Slot
from stowage.model.constraints import check_plan
from stowage.model.evaluation import evaluate_plan
from stowage.viz.loading_2d import plot_loading_plan
from stowage.viz.pareto import plot_pareto


SETTINGS = dict(seed=42, pop_size=40, generations=25)
PUBLISHED = ROOT / "results/preliminary_2026-11-25"
OUTPUT = ROOT / "results/demo_for_advisor"


def load_cargo(config):
    with SOURCE.open(encoding="utf-8-sig", newline="") as stream:
        cargo = tuple(
            Container(int(row["id"]), float(row["weight"]),
                      config.ports.normalize_port(row["port"]), row["type"])
            for row in csv.DictReader(stream)
        )
    if len(cargo) != 50:
        raise ValueError(f"Ожидалось 50 контейнеров, получено {len(cargo)}.")
    return cargo


def restore_runs(config, cargo, methods=("heuristic", "nsga2")):
    """Восстанавливает планы и заново проверяет показатели опубликованной выдачи."""
    manifest = json.loads((PUBLISHED / "manifest.json").read_text(encoding="utf-8"))
    if (manifest["input_sha256"] != hashlib.sha256(SOURCE.read_bytes()).hexdigest()
            or manifest["vessel"] != asdict(config.vessel)
            or manifest["limits"] != asdict(config.limits)
            or tuple(manifest["route"]) != config.ports.rotation.ports
            or manifest["containers_in_input_order"] != [asdict(c) for c in cargo]):
        raise ValueError("Входные данные не совпали с опубликованным экспериментом.")
    runs, solutions, placements = [
        pd.read_csv(PUBLISHED / f"{name}.csv", float_precision="round_trip")
        for name in ("runs", "solutions", "placements")
    ]
    restored = []
    for method in methods:
        run_id = "50-heuristic" if method == "heuristic" else f"50-nsga2-{SETTINGS['seed']}"
        matching = runs.loc[runs.run_id == run_id]
        if len(matching) != 1:
            raise ValueError(f"Не найден однозначный сохранённый запуск {run_id}.")
        run = matching.iloc[0]
        settings = {} if method == "heuristic" else SETTINGS
        if (run.scenario != 50 or run.method != method or run.status != "ok"
                or any(run[key] != value for key, value in settings.items())):
            raise ValueError(f"Не совпали настройки или статус {run_id}.")
        pairs = []
        for record in solutions.loc[solutions.run_id == run_id].itertuples():
            assigned = placements.loc[placements.plan_id == record.plan_id]
            slots = tuple(
                (row.container_id, Slot(row.bay, row.row, row.tier))
                for row in assigned.itertuples()
            )
            plan = Plan(config.vessel, cargo, slots)
            evaluation = evaluate_plan(plan, config.ports.rotation, config.limits)
            if (not evaluation.is_valid or not record.is_valid
                    or evaluation.objectives != (record.r, record.abs_heel_rad, record.abs_trim_m)
                    or evaluation.hydrostatics[4] != record.gm_t_m):
                raise ValueError(f"Повторная оценка не совпала для {record.plan_id}.")
            pairs.append((plan, evaluation))
        if not pairs or len(pairs) != run.n_valid:
            raise ValueError(f"Неполная выдача сохранённого запуска {run_id}.")
        restored.append((SolveResult(method, tuple(pairs), int(run.n_evaluations), **settings),
                         float(run.elapsed_s)))
    return restored


def select_comparison(candidates, baseline):
    """Предпочитает планы, доминирующие эвристику, затем сравнивает R, крен и дифферент."""
    improving = [row for row in candidates if dominates(row[OBJECTIVES], baseline[OBJECTIVES])]
    return min(improving or candidates, key=lambda row: tuple(row[OBJECTIVES]))


def describe(label, row):
    print(f"{label:<25} R={row.r:2d} · |крен|={row.abs_heel_deg:.6f}° "
          f"· |дифферент|={row.abs_trim_m:.6f} м · GMₜ={row.gm_t_m:.6f} м · допустим")


def show_main_scenario(config, cargo, saved):
    vessel = config.vessel
    print(f"=== 1. Основной сценарий: {len(cargo)} контейнеров, "
          f"сетка {vessel.bays}×{vessel.rows}×{vessel.tiers} ===", flush=True)
    print("Показатель R — блокирующие пары. Проверяется исходная загрузка синтетической баржи.")
    print("Настройки NSGA-II · " + ", ".join(f"{key}={value}" for key, value in SETTINGS.items()),
          flush=True)
    if saved:
        runs = restore_runs(config, cargo)
    else:
        runs = []
        for method in ("heuristic", "nsga2"):
            start = perf_counter()
            result = solve(vessel, cargo, config.ports.rotation, config.limits, method=method,
                           **(SETTINGS if method == "nsga2" else {}))
            runs.append((result, perf_counter() - start))

    records, plans = [], {}
    for result, elapsed in runs:
        method_name = "Эвристика" if result.method == "heuristic" else "NSGA-II"
        print(f"{method_name}: оценок {result.n_evaluations}, допустимых планов "
              f"{len(result.solutions)}, время {elapsed:.3f} с"
              + (" (ранее измерено)" if saved else ""))
        if not result.solutions:
            raise ValueError(result.reason or f"Нет допустимых планов у {method_name}.")
        for i, (plan, evaluation) in enumerate(result.solutions, start=1):
            if not evaluation.is_valid or check_plan(plan, config.limits) != (True, ()):
                raise ValueError(f"{method_name}: план {i} не прошёл повторную проверку.")
            r, heel, trim = evaluation.objectives
            plan_id = f"{method_name} #{i:02d}"
            records.append(dict(scenario=len(cargo), method=result.method, plan_id=plan_id,
                                is_valid=True, r=r, abs_heel_rad=heel, abs_heel_deg=math.degrees(heel),
                                abs_trim_m=trim, gm_t_m=evaluation.hydrostatics[4]))
            plans[plan_id] = plan

    solutions = pd.DataFrame(records)
    front = observed_front(solutions)
    baseline = solutions[solutions.method == "heuristic"].iloc[0]
    nsga = observed_front(solutions[solutions.method == "nsga2"])
    candidates = [row for _, row in nsga.iterrows()]
    selected = select_comparison(candidates, baseline)

    print("\n=== 2. Сравнение и компромиссы ===")
    describe("Эвристика", baseline)
    describe(f"Выбранный {selected.plan_id}", selected)
    print("Выбор для показа: среди планов, доминирующих эвристику, берём минимум R, "
          "затем крена и дифферента. При их отсутствии используем тот же порядок для всей выдачи.")
    shown = {selected.plan_id}
    # Несколько различных компромиссов, если их вернул текущий запуск.
    for objective in ("abs_heel_rad", "abs_trim_m", "r"):
        alternatives = [row for row in candidates if row.plan_id not in shown]
        if len(shown) == 3 or not alternatives:
            break
        row = min(alternatives, key=lambda row: (row[objective], *row[OBJECTIVES]))
        describe(row.plan_id, row)
        shown.add(row.plan_id)
    print(f"Наблюдаемый фронт: {len(front)} уникальных недоминируемых векторов среди показанного запуска и эвристики.")

    OUTPUT.mkdir(parents=True, exist_ok=True)
    pareto_path = OUTPUT / "pareto_50_seed42.png"
    plot_pareto(solutions, front).savefig(pareto_path, dpi=160)
    baseline_path = PUBLISHED / "loading_50_heuristic.png"
    try:
        [(reference, _)] = restore_runs(config, cargo, methods=("heuristic",))
        same_baseline = plans[baseline.plan_id] == reference.solutions[0][0]
    except (OSError, ValueError):
        same_baseline = False
    if not same_baseline or not baseline_path.is_file():
        baseline_path = OUTPUT / "loading_50_heuristic.png"
        save_loading(plans[baseline.plan_id], baseline, config, baseline_path)
    nsga_path = OUTPUT / "loading_50_nsga2_seed42.png"
    save_loading(plans[selected.plan_id], selected, config, nsga_path)
    return pareto_path, baseline_path, nsga_path


def save_loading(plan, row, config, path):
    title = (f"{row.plan_id} · 50 контейнеров\n"
             f"R = {row.r}  |  |крен| = {row.abs_heel_deg:.6f}°  |  "
             f"|дифферент| = {row.abs_trim_m:.6f} м  |  GMₜ = {row.gm_t_m:.6f} м")
    plot_loading_plan(plan, config.ports.rotation, title=title).savefig(path, dpi=160)


def show_gm_scenario():
    scenario = gm_active.build_scenario()
    candidates = gm_active.enumerate_candidates(scenario)
    summary = gm_active.summarize(candidates)
    if (summary["permutations"] != math.factorial(len(scenario.containers))
            or not summary["all_gm_signs_consistent"] or not summary["all_overall_contracts_consistent"]):
        raise ValueError("Проверки перебора GM не согласованы с ядром.")

    vessel = scenario.vessel
    limit = scenario.limits.min_gm_m
    controls = candidates.set_index("control_plan")
    a = controls.loc["A_heavy_below"]
    b = controls.loc["B_heavy_above"]
    b_violations = json.loads(b.violations)
    if (not a.is_valid or a.gm_t_m < limit or b.is_valid or b.gm_t_m >= limit
            or len(b_violations) != 1 or not b_violations[0].startswith("gm:")):
        raise ValueError("Контрольные планы A и B не изолируют порог GMₜ.")
    print(f"\n=== 3. Проверка GM: {vessel.length_m:g}×{vessel.beam_m:g} м, "
          f"{len(scenario.containers)} контейнера, полный перебор ===")
    print(f"Минимальная поперечная GMₜ: {limit:.2f} м.")
    describe("A, тяжёлые снизу", a)
    print(f"Отрицательный контроль B, тяжёлые сверху: GMₜ={b.gm_t_m:.6f} м. "
          f"Проверка: {'допустим' if b.is_valid else 'отклонён'}.")
    for reason in b_violations:
        print(f"  {reason}")
    print(f"Перестановок {summary['permutations']}, допустимых {summary['valid']}, "
          f"отклонено по минимальной GMₜ {summary['invalid_with_active_min_gm']}, "
          f"по другим ограничениям {summary['invalid_without_min_gm']}.")
    plot = gm_active.DEFAULT_OUTPUT / "gm_by_permutation.png"
    keys = ["permutation_id", "gm_t_m", "g_min_gm_t", "is_valid"]
    published = pd.read_csv(gm_active.DEFAULT_OUTPUT / "permutations.csv", float_precision="round_trip")
    if not plot.is_file() or not candidates[keys].equals(published[keys]):
        OUTPUT.mkdir(parents=True, exist_ok=True)
        plot = OUTPUT / "gm_by_permutation.png"
        gm_active._save_plot(candidates, plot, limit)
    return plot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--saved", action="store_true",
                        help="восстановить ранее вычисленные планы эвристики и seed 42")
    parser.add_argument("--open-plots", action="store_true", help="открыть PNG в приложении Windows")
    args = parser.parse_args()
    config = load_project_config(ROOT / "configs")
    print("Режим: ВОСПРОИЗВЕДЕНИЕ СОХРАНЁННЫХ РЕЗУЛЬТАТОВ. Поиск на 50 контейнерах не запускался."
          if args.saved else "Режим: живой запуск эвристики, NSGA-II и проверки GM.", flush=True)
    try:
        images = (*show_main_scenario(config, load_cargo(config), args.saved), show_gm_scenario())
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Демонстрация остановлена: {exc}\n")
    print("\n=== PNG для показа ===")
    for path in images:
        print(path)
        if args.open_plots:
            try:
                os.startfile(path)
            except OSError as exc:
                print(f"Откройте PNG вручную. Windows сообщила об ошибке {exc}.")
    print("Фронт относится к найденным решениям. Остойчивость после выгрузок остаётся открытым вопросом.")


if __name__ == "__main__":
    main()
