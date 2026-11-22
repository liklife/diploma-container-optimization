import sys
from dataclasses import replace

import pandas as pd
import pytest

from experiments import demo_for_advisor as demo
from stowage.config import load_project_config


def test_comparison_prefers_dominance_then_uses_objective_order():
    rows = pd.DataFrame([
        (8, 0.09, 0.05),
        (0, 0.01, 0.10),
        (3, 0.05, 0.03),
        (2, 0.07, 0.04),
    ], columns=demo.OBJECTIVES)
    baseline, zero_r, first_dominating, second_dominating = (rows.iloc[i] for i in range(4))

    assert demo.select_comparison(
        [zero_r, first_dominating, second_dominating], baseline
    ).equals(second_dominating)
    assert demo.select_comparison([zero_r], baseline).equals(zero_r)


def test_saved_mode_rechecks_published_plans_and_reuses_appropriate_figures(
    tmp_path, monkeypatch, capsys
):
    def unexpected_search(*args, **kwargs):
        pytest.fail("Saved mode must not call solve()")

    monkeypatch.setattr(demo, "solve", unexpected_search)
    monkeypatch.setattr(demo, "OUTPUT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["demo_for_advisor", "--saved"])
    demo.main()

    output = capsys.readouterr().out
    assert "ВОСПРОИЗВЕДЕНИЕ СОХРАНЁННЫХ РЕЗУЛЬТАТОВ" in output
    assert "NSGA-II: оценок 1000, допустимых планов 21" in output
    assert "Отрицательный контроль B" in output and "Проверка: отклонён" in output
    assert "Перестановок 24, допустимых 12, отклонено по минимальной GMₜ 4" in output
    assert str(demo.PUBLISHED / "loading_50_heuristic.png") in output
    assert str(demo.gm_active.DEFAULT_OUTPUT / "gm_by_permutation.png") in output
    assert {path.name for path in tmp_path.iterdir()} == {
        "pareto_50_seed42.png", "loading_50_nsga2_seed42.png",
    }


def test_saved_mode_rejects_changed_vessel():
    config = load_project_config()
    cargo = demo.load_cargo(config)
    different = replace(config, vessel=replace(config.vessel, lightship_mass_kg=7_990_000))
    with pytest.raises(ValueError, match="не совпали"):
        demo.restore_runs(different, cargo)
