import json
import shutil
from pathlib import Path

import pytest

from stowage.config import load_project_config


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIGS_SOURCE = PROJECT_ROOT / "configs"


def copy_configs(tmp_path: Path) -> Path:
    """Создаёт отдельную копию конфигураций для теста."""

    destination = tmp_path / "configs"
    shutil.copytree(CONFIGS_SOURCE, destination)
    return destination


def read_config(directory: Path, filename: str) -> dict:
    path = directory / filename
    return json.loads(path.read_text(encoding="utf-8"))


def write_config(
    directory: Path,
    filename: str,
    data: dict,
) -> None:
    path = directory / filename
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def test_load_project_config():
    config = load_project_config()

    assert config.vessel.vessel_id == "synthetic_box_barge_8x4x3"
    assert config.vessel.synthetic is True
    assert (config.vessel.bays, config.vessel.rows, config.vessel.tiers) == (
        8, 4, 3
    )
    assert config.vessel.max_draft_m == 8.0
    assert config.limits.max_container_mass_kg == 30480
    assert config.limits.min_gm_m == 0.15
    assert config.limits.target_gm_m == 0.5

    assert config.ports.rotation.ports == (
        "Калининград",
        "Санкт-Петербург",
        "Мурманск",
    )

def test_real_vessel_configuration_is_rejected(tmp_path):
    directory = copy_configs(tmp_path)
    data = read_config(directory, "vessel.json")
    data["synthetic"] = False
    write_config(directory, "vessel.json", data)

    with pytest.raises(ValueError, match="synthetic must be true"):
        load_project_config(directory)


def test_unsupported_hull_model_is_rejected(tmp_path):
    directory = copy_configs(tmp_path)
    data = read_config(directory, "vessel.json")
    data["hull_model"] = "real_hull"
    write_config(directory, "vessel.json", data)

    with pytest.raises(ValueError, match="hull_model"):
        load_project_config(directory)


def test_normalize_canonical_port():
    config = load_project_config()

    assert config.ports.normalize_port("Мурманск") == "Мурманск"


def test_normalize_alias_and_surrounding_whitespace():
    config = load_project_config()

    assert (
        config.ports.normalize_port(" СПб ")
        == "Санкт-Петербург"
    )


def test_unknown_destination_is_rejected():
    config = load_project_config()

    with pytest.raises(ValueError, match="Unknown port"):
        config.ports.normalize_port("Архангельск")


@pytest.mark.parametrize("invalid_value", [None, 123, True])
def test_port_name_must_be_a_string(invalid_value):
    config = load_project_config()

    with pytest.raises(TypeError, match="Port name"):
        config.ports.normalize_port(invalid_value)


def test_blank_port_name_is_rejected():
    config = load_project_config()

    with pytest.raises(ValueError, match="empty"):
        config.ports.normalize_port("   ")


@pytest.mark.parametrize(
    "filename",
    ["vessel.json", "limits.json", "ports.json"],
)
@pytest.mark.parametrize(
    "invalid_version",
    [True, "1", 2, 1.0, None],
)
def test_invalid_schema_version_is_rejected(
    tmp_path,
    filename,
    invalid_version,
):
    directory = copy_configs(tmp_path)
    data = read_config(directory, filename)
    data["schema_version"] = invalid_version
    write_config(directory, filename, data)

    with pytest.raises(ValueError, match="schema_version"):
        load_project_config(directory)


def test_missing_required_vessel_field_is_rejected(tmp_path):
    directory = copy_configs(tmp_path)
    data = read_config(directory, "vessel.json")
    del data["synthetic"]
    write_config(directory, "vessel.json", data)

    with pytest.raises(ValueError, match="synthetic"):
        load_project_config(directory)


def test_unknown_vessel_field_is_rejected(tmp_path):
    directory = copy_configs(tmp_path)
    data = read_config(directory, "vessel.json")
    data["lenght_m"] = 120.0
    write_config(directory, "vessel.json", data)

    with pytest.raises(ValueError, match="unknown fields"):
        load_project_config(directory)


def test_malformed_json_is_rejected(tmp_path):
    directory = copy_configs(tmp_path)
    path = directory / "vessel.json"
    path.write_text("{broken json", encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid JSON"):
        load_project_config(directory)


def test_json_root_must_be_an_object(tmp_path):
    directory = copy_configs(tmp_path)
    path = directory / "vessel.json"
    path.write_text("[]", encoding="utf-8")

    with pytest.raises(ValueError, match="JSON object"):
        load_project_config(directory)


def test_missing_config_file_is_reported(tmp_path):
    directory = copy_configs(tmp_path)
    (directory / "limits.json").unlink()

    with pytest.raises(FileNotFoundError, match="limits.json"):
        load_project_config(directory)


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("length_m", -1),
        ("length_m", True),
        ("bays", 2.5),
        ("synthetic", "true"),
        ("max_draft_m", 0),
        ("max_draft_m", 10.1),
    ],
)
def test_invalid_vessel_values_are_rejected(
    tmp_path,
    field_name,
    invalid_value,
):
    directory = copy_configs(tmp_path)
    data = read_config(directory, "vessel.json")
    data[field_name] = invalid_value
    write_config(directory, "vessel.json", data)

    with pytest.raises(ValueError, match="Invalid vessel configuration"):
        load_project_config(directory)


@pytest.mark.parametrize(
    ("field_name", "invalid_value", "message"),
    [
        ("max_container_mass_kg", 0, "must be positive"),
        ("min_gm_m", -1, "must be non-negative"),
        ("target_gm_m", 0, "at least min_gm_m"),
        ("max_abs_heel_deg", 6, "must not exceed"),
        ("max_abs_trim_percent_of_length", 0, "must be positive"),
        (
            "small_angle_model_max_abs_heel_deg",
            5.1,
            "must be in",
        ),
        ("max_container_mass_kg", True, "must be a number"),
        ("max_container_mass_kg", float("nan"), "must be finite"),
    ],
)
def test_invalid_limits_are_rejected(
    tmp_path,
    field_name,
    invalid_value,
    message,
):
    directory = copy_configs(tmp_path)
    data = read_config(directory, "limits.json")
    data[field_name] = invalid_value
    write_config(directory, "limits.json", data)

    with pytest.raises((TypeError, ValueError), match=message):
        load_project_config(directory)


def test_duplicate_canonical_ports_are_rejected(tmp_path):
    directory = copy_configs(tmp_path)
    data = read_config(directory, "ports.json")
    data["canonical_ports"].append("Мурманск")
    write_config(directory, "ports.json", data)

    with pytest.raises(ValueError, match="duplicates"):
        load_project_config(directory)


def test_rotation_must_contain_all_canonical_ports(tmp_path):
    directory = copy_configs(tmp_path)
    data = read_config(directory, "ports.json")
    data["rotation"] = ["Калининград", "Мурманск"]
    write_config(directory, "ports.json", data)

    with pytest.raises(ValueError, match="every canonical port"):
        load_project_config(directory)


def test_alias_target_must_be_canonical(tmp_path):
    directory = copy_configs(tmp_path)
    data = read_config(directory, "ports.json")
    data["aliases"] = {"Несуществующий порт": ["Порт X"]}
    write_config(directory, "ports.json", data)

    with pytest.raises(ValueError, match="not a canonical port"):
        load_project_config(directory)


def test_alias_cannot_conflict_with_canonical_port(tmp_path):
    directory = copy_configs(tmp_path)
    data = read_config(directory, "ports.json")
    data["aliases"] = {"Санкт-Петербург": ["Мурманск"]}
    write_config(directory, "ports.json", data)

    with pytest.raises(ValueError, match="conflicts"):
        load_project_config(directory)


def test_alias_cannot_be_assigned_twice(tmp_path):
    directory = copy_configs(tmp_path)
    data = read_config(directory, "ports.json")
    data["aliases"] = {
        "Калининград": ["Общий псевдоним"],
        "Мурманск": ["Общий псевдоним"],
    }
    write_config(directory, "ports.json", data)

    with pytest.raises(ValueError, match="assigned more than once"):
        load_project_config(directory)


def test_aliases_are_read_only():
    config = load_project_config()

    with pytest.raises(TypeError):
        config.ports.aliases["Санкт-Петербург"] = ("Питер",)


def test_project_config_is_immutable():
    config = load_project_config()

    with pytest.raises(AttributeError):
        config.vessel = config.vessel
