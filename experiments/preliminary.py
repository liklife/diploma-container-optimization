"""Предварительное сравнение методов на первых 10 и всех 50 эталонных записях."""

import argparse
import csv
import hashlib
import json
import math
import platform
from dataclasses import asdict
from importlib.metadata import version
from pathlib import Path
from time import perf_counter

import pandas as pd
from matplotlib.backends.backend_agg import FigureCanvasAgg

from stowage.algorithms.decoder import decode_permutation
from stowage.algorithms.solver import solve
from stowage.config import load_project_config
from stowage.domain.container import Container
from stowage.domain.plan import Plan
from stowage.model.constraints import check_plan
from stowage.model.evaluation import evaluate_plan
from stowage.viz.loading_2d import plot_loading_plan
from stowage.viz.pareto import plot_pareto, plot_run_comparison


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/samples/containers_legacy.csv"
SIZES = (10, 50)
SEEDS = (42, 43, 44, 45, 46)
POP_SIZE = 40
GENERATIONS = 25
OBJECTIVES = ["r", "abs_heel_rad", "abs_trim_m"]


def dominates(a, b) -> bool:
    """Объект a не хуже по каждой минимизируемой цели и строго лучше по одной."""
    pairs = tuple(zip(a, b, strict=True))
    return all(x <= y for x, y in pairs) and any(x < y for x, y in pairs)


def observed_front(solutions: pd.DataFrame) -> pd.DataFrame:
    """По одному представителю точного вектора на сценарий, только из допустимых."""
    valid = solutions.loc[solutions["is_valid"]]
    unique = valid.drop_duplicates(subset=["scenario", *OBJECTIVES])
    indices = []
    for _, group in unique.groupby("scenario", sort=False):
        vectors = list(group[OBJECTIVES].itertuples(index=False, name=None))
        indices.extend(
            index for index, vector in zip(group.index, vectors, strict=True)
            if not any(dominates(other, vector) for other in vectors)
        )
    return unique.loc[indices].copy()


def min_transverse_gm(cargo, config) -> float:
    """Минимум GM_T среди перестановок на фиксированных слотах этого декодера."""
    vessel = config.vessel
    reference = decode_permutation(vessel, cargo, range(len(cargo)))
    if reference.unplaced_containers:
        raise ValueError("GM bound requires fixed mass and complete placement")
    slots = sorted(
        (slot for _, slot in reference.placements),
        key=lambda slot: vessel.coordinates_for(slot)[2],
    )
    # При фиксированной массе осадка, KB и BM неизменны. Назначение самых
    # тяжёлых контейнеров самым высоким слотам максимизирует Z_G.
    light_to_heavy = sorted(cargo, key=lambda container: container.mass_kg)
    highest_cg = Plan(vessel, cargo, [
        (container.id, slot) for container, slot in zip(light_to_heavy, slots, strict=True)
    ])
    evaluation = evaluate_plan(highest_cg, config.ports.rotation, config.limits)
    return evaluation.hydrostatics[4]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _save(figure, path: Path) -> None:
    FigureCanvasAgg(figure)
    figure.savefig(path, dpi=160)


def _collect_runs(cargo, config, verify_reproducibility):
    runs, solutions, placements = [], [], []
    plans = {}
    for size in SIZES:
        for seed in (None, *SEEDS):
            method = "heuristic" if seed is None else "nsga2"
            run_id = f"{size}-{method}" + (f"-{seed}" if seed is not None else "")
            scenario = (config.vessel, cargo[:size], config.ports.rotation, config.limits)
            settings = {} if seed is None else dict(seed=seed, pop_size=POP_SIZE, generations=GENERATIONS)
            start = perf_counter()
            result = solve(*scenario, method=method, **settings)
            elapsed = perf_counter() - start
            repeat_elapsed = None
            if verify_reproducibility:
                start = perf_counter()
                repeated = solve(*scenario, method=method, **settings)
                repeat_elapsed = perf_counter() - start
                if repeated != result:
                    raise RuntimeError(f"Result did not repeat for {run_id}")
            run = dict(
                scenario=size, run_id=run_id, method=method, seed=seed,
                pop_size=result.pop_size, generations=result.generations,
                budget_evaluations=1 if seed is None else POP_SIZE * GENERATIONS,
                n_evaluations=result.n_evaluations, elapsed_s=elapsed,
                repeat_elapsed_s=repeat_elapsed, reproducibility_checked=verify_reproducibility,
                n_valid=len(result.solutions), status=result.status, reason=result.reason,
            )
            run_solutions = []
            for i, (plan, evaluation) in enumerate(result.solutions, start=1):
                is_valid, violations = check_plan(plan, config.limits)
                if not is_valid or not evaluation.is_valid:
                    raise RuntimeError(f"Unexpected invalid solver output for {run_id}: {violations}")
                plan_id = f"{run_id}-{i:03d}"
                r, heel, trim = evaluation.objectives
                row = dict(
                    **run, plan_id=plan_id, is_valid=is_valid, r=r,
                    abs_heel_rad=heel, abs_heel_deg=math.degrees(heel), abs_trim_m=trim,
                    gm_t_m=evaluation.hydrostatics[4], gm_l_m=evaluation.hydrostatics[5],
                )
                run_solutions.append(row)
                plans[plan_id] = plan
                placements.extend(
                    dict(plan_id=plan_id, container_id=container_id, bay=slot.bay,
                         row=slot.row, tier=slot.tier)
                    for container_id, slot in plan.placements
                )
            solutions.extend(run_solutions)
            runs.append(dict(
                **run,
                min_r=min((row["r"] for row in run_solutions), default=None),
                min_abs_heel_deg=min((row["abs_heel_deg"] for row in run_solutions), default=None),
                min_abs_trim_m=min((row["abs_trim_m"] for row in run_solutions), default=None),
            ))
            print(f"{run_id}: {result.n_evaluations} evals, {len(result.solutions)} valid, {elapsed:.3f} s",
                  flush=True)
    return pd.DataFrame(runs), pd.DataFrame(solutions), pd.DataFrame(placements), plans


def _representatives(solutions, front):
    """Выбор для показа без сведения целей к одному числу."""
    selected = {}
    for size in SIZES:
        baseline = solutions[(solutions["scenario"] == size) & (solutions["method"] == "heuristic")]
        front_vectors = set(front.loc[front["scenario"] == size, OBJECTIVES]
                            .itertuples(index=False, name=None))
        candidates = observed_front(solutions[
            (solutions["scenario"] == size) & (solutions["method"] == "nsga2")
        ])
        if not baseline.empty:
            selected[(size, "heuristic")] = baseline.iloc[0].to_dict()
        for target in OBJECTIVES:
            if not candidates.empty:
                order = [target, *(metric for metric in OBJECTIVES if metric != target), "seed", "plan_id"]
                selected[(size, f"min_{target}")] = candidates.sort_values(order).iloc[0].to_dict()
        for (scenario, _), row in selected.items():
            if scenario == size:
                row["on_observed_front"] = tuple(row[metric] for metric in OBJECTIVES) in front_vectors
    return selected


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "results/preliminary_2026-11-25")
    parser.add_argument("--verify-reproducibility", action="store_true")
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT / "results") or output.exists():
        parser.error("--output must be a new directory inside results/")

    input_hash = _sha256(SOURCE)
    config = load_project_config(ROOT / "configs")
    with SOURCE.open(encoding="utf-8-sig", newline="") as stream:
        cargo = tuple(
            Container(int(row["id"]), float(row["weight"]),
                      config.ports.normalize_port(row["port"]), row["type"])
            for row in csv.DictReader(stream)
        )
    if len(cargo) != 50:
        raise ValueError(f"Expected 50 reference containers, found {len(cargo)}")
    runs, solutions, placements, plans = _collect_runs(cargo, config, args.verify_reproducibility)
    if _sha256(SOURCE) != input_hash:
        raise RuntimeError("Reference CSV changed during the run")
    if solutions.empty:
        # Состояния отказа полезны даже без таблиц решений и графиков.
        output.mkdir(parents=True)
        runs.to_csv(output / "runs.csv", index=False, encoding="utf-8-sig")
        print("No feasible solutions. Saved runs.csv.")
        return
    front = observed_front(solutions)
    representatives = _representatives(solutions, front)
    gm_rows = []
    for size in SIZES:
        minimum = min_transverse_gm(cargo[:size], config)
        gm_rows.append(dict(
            scenario=size, min_gm_t_over_slot_permutations_m=minimum,
            limit_gm_t_m=config.limits.min_gm_m,
            margin_m=minimum - config.limits.min_gm_m,
        ))
    source_paths = [Path(__file__)]
    for layer in ("algorithms", "config", "domain", "model", "viz"):
        source_paths.extend(sorted((ROOT / "src/stowage" / layer).glob("*.py")))
    manifest = dict(
        input_path=SOURCE.relative_to(ROOT).as_posix(), input_sha256=input_hash,
        scenario_sizes=SIZES, containers_in_input_order=[asdict(container) for container in cargo],
        vessel=asdict(config.vessel), limits=asdict(config.limits), route=config.ports.rotation.ports,
        plan_encoding="placements.csv: plan_id, container_id and zero-based (bay, row, tier); select scenario from solutions.csv",
        seeds=SEEDS, pop_size=POP_SIZE, generations=GENERATIONS,
        python=platform.python_version(), platform=platform.platform(),
        packages={name: version(name) for name in ("numpy", "pandas", "matplotlib", "pymoo")},
        source_sha256={path.relative_to(ROOT).as_posix(): _sha256(path) for path in source_paths},
        verified_repeats=args.verify_reproducibility,
    )
    output.mkdir(parents=True)
    for name, table in (
        ("runs", runs), ("solutions", solutions), ("placements", placements), ("pareto_front", front),
        ("representative", pd.DataFrame([dict(role=role, **row) for (_, role), row in representatives.items()])),
        ("gm_bounds", pd.DataFrame(gm_rows)),
    ):
        table.to_csv(output / f"{name}.csv", index=False, encoding="utf-8-sig")
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    _save(plot_pareto(solutions, front), output / "pareto.png")
    _save(plot_run_comparison(runs), output / "run_comparison.png")
    for role, name, label in (
        ("heuristic", "loading_50_heuristic", "Эвристика"),
        ("min_r", "loading_50_nsga2", "NSGA-II · минимум R, затем меньший крен"),
    ):
        if (50, role) not in representatives:
            print(f"No feasible plan for {name}")
            continue
        row = representatives[(50, role)]
        title = (
            f"{label} · 50 контейнеров · {row['plan_id']}\n"
            f"R = {row['r']}  |  |крен| = {row['abs_heel_deg']:.6f}°  |  "
            f"|дифферент| = {row['abs_trim_m']:.6f} м  |  GMₜ = {row['gm_t_m']:.4f} м"
        )
        figure = plot_loading_plan(plans[row["plan_id"]], config.ports.rotation, title=title)
        _save(figure, output / f"{name}.png")
    print(f"Saved {output}")


if __name__ == "__main__":
    main()
