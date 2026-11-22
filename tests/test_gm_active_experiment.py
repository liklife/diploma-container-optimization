import json

import pandas as pd
import pytest

from experiments.gm_active import (
    CONTROL_PERMUTATIONS,
    build_scenario,
    enumerate_candidates,
    summarize,
)
from stowage.config import load_project_config


@pytest.fixture(scope="module")
def experiment():
    scenario = build_scenario()
    candidates = enumerate_candidates(scenario)
    return scenario, candidates


def control(candidates: pd.DataFrame, name: str) -> pd.Series:
    rows = candidates.loc[candidates["control_plan"] == name]
    assert len(rows) == 1
    return rows.iloc[0]


def violation_codes(row: pd.Series) -> list[str]:
    return [message.split(":", 1)[0] for message in json.loads(row["violations"])]


def test_heavy_below_control_is_valid_and_has_zero_gm_excess(experiment):
    _, candidates = experiment
    row = control(candidates, "A_heavy_below")

    assert row["gm_t_m"] == pytest.approx(0.5749, abs=0.001)
    assert row["is_valid"]
    assert violation_codes(row) == []
    assert row["g_min_gm_t"] == 0
    assert row["pymoo_feasible"]


def test_heavy_above_control_is_rejected_only_by_minimum_gm(experiment):
    scenario, candidates = experiment
    row = control(candidates, "B_heavy_above")

    assert 0 < row["gm_t_m"] < scenario.limits.min_gm_m
    assert row["gm_t_m"] == pytest.approx(0.1076, abs=0.001)
    assert not row["is_valid"]
    assert violation_codes(row) == ["gm"]
    assert row["g_min_gm_t"] > 0
    assert not row["pymoo_feasible"]
    assert row["draft_m"] < scenario.vessel.max_draft_m
    assert row["gm_l_m"] > 0
    assert row["abs_heel_deg"] == pytest.approx(0)
    assert row["abs_trim_m"] == pytest.approx(0)


def test_all_permutations_are_distinguished_and_contracts_agree(experiment):
    _, candidates = experiment
    summary = summarize(candidates)

    assert len(candidates) == 24
    assert set(candidates["permutation_indices"]) == {
        json.dumps(order, separators=(",", ":"))
        for order in __import__("itertools").permutations(range(4))
    }
    assert summary["unique_cargo_plans"] == 24
    assert 1 < summary["unique_physical_results"] < 24
    assert summary["valid"] + summary["invalid"] == 24
    assert summary["valid"] > 0 and summary["invalid"] > 0
    assert summary["invalid_with_active_min_gm"] == 4
    assert summary["invalid_without_min_gm"] == 8
    assert candidates["gm_sign_consistent"].all()
    assert candidates["overall_contract_consistent"].all()


def test_enumeration_is_reproducible(experiment):
    scenario, first = experiment
    second = enumerate_candidates(scenario)
    pd.testing.assert_frame_equal(first, second)


def test_scenario_does_not_change_production_configuration_or_published_results(experiment):
    scenario, _ = experiment
    project = load_project_config()

    assert (project.vessel.length_m, project.vessel.beam_m) == (120, 14)
    assert (project.vessel.bays, project.vessel.rows, project.vessel.tiers) == (8, 4, 3)
    assert project.limits.min_gm_m == scenario.limits.min_gm_m == 0.15
    assert scenario.vessel.vessel_id != project.vessel.vessel_id
    assert CONTROL_PERMUTATIONS == {
        "A_heavy_below": (0, 1, 2, 3),
        "B_heavy_above": (2, 3, 0, 1),
    }
