"""Детерминированный эксперимент с активным ограничением поперечной GM."""

import argparse
import hashlib
import json
import math
import platform
from dataclasses import asdict, dataclass
from importlib.metadata import version
from itertools import permutations
from pathlib import Path

import pandas as pd
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

from stowage.algorithms.pymoo_problem import CONSTRAINT_NAMES, StowageProblem, constraint_violations
from stowage.config import load_project_config
from stowage.config.loader import LimitsConfig
from stowage.domain.container import Container
from stowage.domain.port_rotation import PortRotation
from stowage.domain.vessel import Vessel
from stowage.model.constraints import check_plan


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "results/gm_active_2026-11-25"
CONTROL_PERMUTATIONS = {
    "A_heavy_below": (0, 1, 2, 3),
    "B_heavy_above": (2, 3, 0, 1),
}


@dataclass(frozen=True)
class ExperimentScenario:
    vessel: Vessel
    containers: tuple[Container, ...]
    rotation: PortRotation
    limits: LimitsConfig


def build_scenario(config_dir: Path = ROOT / "configs") -> ExperimentScenario:
    """Создаёт изолированный сценарий, сохраняя рабочие пределы модели."""
    project = load_project_config(config_dir)
    vessel = Vessel(
        vessel_id="gm_active_small_box_barge_1x2x2",
        name="Малая синтетическая баржа для проверки GM",
        synthetic=True,
        hull_model="box_barge",
        length_m=12.0,
        beam_m=6.0,
        depth_m=8.0,
        max_draft_m=4.0,
        bays=1,
        rows=2,
        tiers=2,
        first_bay_offset_m=6.0,
        bay_spacing_m=6.0,
        first_row_center_y_m=-1.25,
        row_spacing_m=2.5,
        base_height_m=1.5,
        container_height_m=2.0,
        tier_spacing_m=2.0,
        lightship_mass_kg=144_000.0,
        lightship_cg_x_m=6.0,
        lightship_cg_y_m=0.0,
        lightship_cg_z_m=1.5,
        water_density_kg_m3=1000.0,
        max_bay_load_t=220.0,
        max_column_load_t=60.0,
    )
    port = project.ports.rotation.ports[0]
    containers = tuple(
        Container(index, mass, port, "dry")
        for index, mass in enumerate((30_000.0, 30_000.0, 5_000.0, 5_000.0))
    )
    return ExperimentScenario(vessel, containers, project.ports.rotation, project.limits)


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _signature(values) -> str:
    return "|".join(f"{value:.12g}" if isinstance(value, float) else str(value) for value in values)


def enumerate_candidates(scenario: ExperimentScenario) -> pd.DataFrame:
    """Оценивает все 4! перестановки единым ядром и адаптером pymoo."""
    problem = StowageProblem(
        scenario.vessel, scenario.containers, scenario.rotation, scenario.limits
    )
    rows = []
    min_gm_index = CONSTRAINT_NAMES.index("min_gm_t")
    for number, order in enumerate(permutations(range(len(scenario.containers))), start=1):
        plan, evaluation = problem.evaluate_permutation(order)
        is_valid, violations = check_plan(plan, scenario.limits)
        if (is_valid, violations) != (evaluation.is_valid, evaluation.violations):
            raise RuntimeError("evaluate_plan() disagrees with check_plan()")

        g = constraint_violations(plan, scenario.limits, evaluation)
        gm_t = evaluation.hydrostatics[4]
        gm_l = evaluation.hydrostatics[5]
        draft = evaluation.hydrostatics[0]
        heel, _, trim = evaluation.heel_and_trim
        gm_violation = any(message.startswith("gm:") for message in violations)
        numerical_feasible = all(value <= 0.0 for value in g)
        assignments = [
            {
                "container_id": container_id,
                "bay": slot.bay,
                "row": slot.row,
                "tier": slot.tier,
            }
            for container_id, slot in plan.placements
        ]
        plan_signature = _json(sorted(
            (item["container_id"], item["bay"], item["row"], item["tier"])
            for item in assignments
        ))
        physical_signature = _signature((
            draft, gm_t, gm_l, abs(heel), abs(trim), evaluation.blocking_pairs, is_valid
        ))
        control = next(
            (name for name, control_order in CONTROL_PERMUTATIONS.items() if order == control_order),
            "",
        )
        rows.append({
            "permutation_id": number,
            "control_plan": control,
            "permutation_indices": _json(order),
            "slot_assignments": _json(assignments),
            "plan_signature": plan_signature,
            "physical_signature": physical_signature,
            "draft_m": draft,
            "gm_t_m": gm_t,
            "gm_l_m": gm_l,
            "abs_heel_rad": abs(heel),
            "abs_heel_deg": math.degrees(abs(heel)),
            "abs_trim_m": abs(trim),
            "r": evaluation.blocking_pairs,
            "is_valid": is_valid,
            "violations": _json(violations),
            "g_min_gm_t": g[min_gm_index],
            "gm_sign_consistent": (g[min_gm_index] > 0.0) == gm_violation,
            "pymoo_feasible": numerical_feasible,
            "overall_contract_consistent": numerical_feasible == is_valid,
        })
    return pd.DataFrame(rows)


def summarize(candidates: pd.DataFrame) -> dict[str, int | bool]:
    invalid_gm = (~candidates["is_valid"]) & (candidates["g_min_gm_t"] > 0)
    return {
        "permutations": len(candidates),
        "unique_cargo_plans": candidates["plan_signature"].nunique(),
        "unique_physical_results": candidates["physical_signature"].nunique(),
        "valid": int(candidates["is_valid"].sum()),
        "invalid": int((~candidates["is_valid"]).sum()),
        "invalid_with_active_min_gm": int(invalid_gm.sum()),
        "invalid_without_min_gm": int(((~candidates["is_valid"]) & ~invalid_gm).sum()),
        "all_gm_signs_consistent": bool(candidates["gm_sign_consistent"].all()),
        "all_overall_contracts_consistent": bool(
            candidates["overall_contract_consistent"].all()
        ),
    }


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _save_plot(candidates: pd.DataFrame, path: Path, limit: float) -> None:
    figure = Figure(figsize=(9, 5), constrained_layout=True)
    FigureCanvasAgg(figure)
    axis = figure.subplots()
    active_gm = candidates["g_min_gm_t"] > 0
    groups = (
        (candidates["is_valid"], "#2e7d32", "допустим"),
        (active_gm, "#c62828", "отклонён по минимальной GMₜ"),
        ((~candidates["is_valid"]) & ~active_gm, "#ef6c00", "отклонён по другому пределу"),
    )
    for mask, color, label in groups:
        subset = candidates.loc[mask]
        axis.scatter(subset["permutation_id"], subset["gm_t_m"], c=color, s=42, label=label)
    axis.axhline(limit, color="#1565c0", linestyle="--", label=f"предел GMₜ = {limit:.2f} м")
    axis.set(
        xlabel="Номер перестановки",
        ylabel="GMₜ, м",
        title="Поперечная GM для полного перебора 4! перестановок",
        xticks=range(1, len(candidates) + 1),
    )
    axis.grid(alpha=0.25)
    axis.legend()
    figure.savefig(path, dpi=160)


def _report_note(candidates: pd.DataFrame, summary: dict, limit: float) -> str:
    controls = candidates.set_index("control_plan")
    lower = controls.loc["A_heavy_below"]
    upper = controls.loc["B_heavy_above"]
    return f"""# Эксперимент с активным ограничением GMₜ

Эксперимент использует отдельную синтетическую прямоугольную баржу длиной 12 м и
шириной 6 м с сеткой 1 × 2 × 2. Масса порожнего судна — 144 т, его центр тяжести
расположен в диаметральной плоскости на высоте 1,5 м. Осадка ограничена 4 м.
Нижний и верхний центры контейнеров находятся на высотах 2,5 и 4,5 м. Эти круглые
исходные значения задают понятный чувствительный сценарий, а действующий порог
GMₜ = {limit:.2f} м взят без изменения из `configs/limits.json`.

В плане A два контейнера по 30 т стоят снизу, а два по 5 т — сверху. Получено
GMₜ = {lower['gm_t_m']:.6f} м; план допустим. В плане B тяжёлые контейнеры стоят
сверху: GMₜ = {upper['gm_t_m']:.6f} м. План отклонён только из-за нарушения
минимальной GMₜ; опора, массы, нагрузки, осадка, крен, дифферент и положительность
обеих GM соблюдены.

В обоих контрольных планах каждый контейнер легче предела 30,48 т, каждая колонна
несёт 35 т при пределе 60 т, а единственный bay — 70 т при пределе 220 т. Верхние
контейнеры имеют непосредственную опору. Расчётная осадка равна
{lower['draft_m']:.6f} м при эксплуатационном пределе 4 м; крен и дифферент равны
нулю. Продольная GM равна {lower['gm_l_m']:.6f} м в плане A и
{upper['gm_l_m']:.6f} м в плане B.

Полный детерминированный перебор содержит {summary['permutations']} перестановки,
{summary['unique_cargo_plans']} уникальных грузовых планов и
{summary['unique_physical_results']} уникальных физических результатов. Допустимы
{summary['valid']} вариантов, недопустимы {summary['invalid']}. Минимальная GMₜ
активна и отсекает {summary['invalid_with_active_min_gm']} варианта; ещё
{summary['invalid_without_min_gm']} вариантов отклонены по крену при несимметричном
распределении разных масс между левым и правым рядами.
Для всех вариантов знак `G[min_gm_t]` согласован с `check_plan()`, а общая
допустимость числового вектора ограничений pymoo совпадает с результатом ядра.

Интерпретация: подъём тяжёлого груза повышает вертикальный центр тяжести Z_G и
уменьшает GMₜ. Эксперимент демонстрирует работу уже принятой модели, а не
обосновывает инженерную применимость порога для реального судна.
"""


def write_results(output: Path, scenario: ExperimentScenario, candidates: pd.DataFrame) -> None:
    summary = summarize(candidates)
    controls = candidates.loc[candidates["control_plan"] != ""].copy()
    output.mkdir(parents=True, exist_ok=True)
    candidates.to_csv(output / "permutations.csv", index=False, encoding="utf-8-sig")
    controls.to_csv(output / "control_plans.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame([summary]).to_csv(output / "summary.csv", index=False, encoding="utf-8-sig")

    source_paths = (
        Path(__file__),
        ROOT / "src/stowage/algorithms/decoder.py",
        ROOT / "src/stowage/algorithms/pymoo_problem.py",
        ROOT / "src/stowage/model/constraints.py",
        ROOT / "src/stowage/model/evaluation.py",
        ROOT / "configs/limits.json",
    )
    manifest = {
        "experiment": "active_initial_transverse_gm",
        "report_date": "2026-11-25",
        "enumeration": "all 4! permutations in itertools.permutations order",
        "control_permutations": CONTROL_PERMUTATIONS,
        "physical_signature_fields": [
            "draft_m", "gm_t_m", "gm_l_m", "abs_heel_rad", "abs_trim_m", "r", "is_valid"
        ],
        "vessel": asdict(scenario.vessel),
        "containers": [asdict(container) for container in scenario.containers],
        "route": scenario.rotation.ports,
        "limits_from_production_config": asdict(scenario.limits),
        "parameter_rationale": {
            "12_by_6_m_hull": "round dimensions of a small synthetic rectangular barge",
            "one_bay_two_rows_two_tiers": "smallest grid with symmetric lower and upper pairs",
            "lightship_144_t_and_cg_z_1_5_m": "round fixed inputs, independent of optimizer output",
            "slot_centres_z_m": [2.5, 4.5],
            "cargo_masses_t": [30, 30, 5, 5],
            "unchanged_min_gm_m": scenario.limits.min_gm_m,
        },
        "summary": summary,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "packages": {name: version(name) for name in ("stowage-optimization", "pymoo", "pandas", "matplotlib")},
        "source_sha256": {
            path.relative_to(ROOT).as_posix(): _sha256(path) for path in source_paths
        },
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (output / "report_note.md").write_text(
        _report_note(candidates, summary, scenario.limits.min_gm_m), encoding="utf-8"
    )
    _save_plot(candidates, output / "gm_by_permutation.png", scenario.limits.min_gm_m)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output.resolve()
    results_root = (ROOT / "results").resolve()
    if not output.is_relative_to(results_root) or output.exists():
        parser.error("--output must be a new directory inside results/")

    scenario = build_scenario()
    candidates = enumerate_candidates(scenario)
    summary = summarize(candidates)
    if summary["permutations"] != math.factorial(len(scenario.containers)):
        raise RuntimeError("Incomplete permutation enumeration")
    if not summary["all_gm_signs_consistent"] or not summary["all_overall_contracts_consistent"]:
        raise RuntimeError("pymoo numerical constraints disagree with check_plan()")
    write_results(output, scenario, candidates)
    print(json.dumps(summary, ensure_ascii=False))
    print(f"Saved {output}")


if __name__ == "__main__":
    main()
