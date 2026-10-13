"""Загрузка и валидация JSON-конфигурации проекта."""

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass, fields
from pathlib import Path
from types import MappingProxyType

from stowage.domain.port_rotation import PortRotation
from stowage.domain.vessel import Vessel


SCHEMA_VERSION = 1

# По принятому решению модель малых углов применима
# только при абсолютном значении угла не более 5 градусов.
MODEL_SMALL_ANGLE_LIMIT_DEG = 5.0


@dataclass(frozen=True)
class LimitsConfig:
    """Глобальные ограничения расчётной модели."""

    max_container_mass_kg: float
    min_gm_m: float
    target_gm_m: float
    max_abs_heel_deg: float
    max_abs_trim_percent_of_length: float
    small_angle_model_max_abs_heel_deg: float


@dataclass(frozen=True)
class PortConfiguration:
    """Канонические названия портов, псевдонимы и маршрут."""

    canonical_ports: tuple[str, ...]
    aliases: Mapping[str, tuple[str, ...]]
    rotation: PortRotation

    def normalize_port(self, value: str) -> str:
        """Нормализует название порта и проверяет его наличие в маршруте."""

        if not isinstance(value, str):
            raise TypeError("Port name must be a string")

        name = value.strip()

        if not name:
            raise ValueError("Port name must not be empty")

        for canonical, alias_values in self.aliases.items():
            if name in alias_values:
                name = canonical
                break

        if name not in self.rotation.ports:
            known_ports = ", ".join(self.rotation.ports)
            raise ValueError(
                f"Unknown port '{name}'. Known ports: {known_ports}"
            )

        return name


@dataclass(frozen=True)
class ProjectConfig:
    """Полная проверенная конфигурация проекта."""

    vessel: Vessel
    limits: LimitsConfig
    ports: PortConfiguration


def _read_json(path: Path) -> dict:
    """Читает JSON-файл и проверяет, что в корне находится объект."""

    try:
        content = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise FileNotFoundError(
            f"Configuration file not found: {path}"
        ) from None

    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Invalid JSON in {path}: {exc.msg}, line {exc.lineno}"
        ) from exc

    if not isinstance(data, dict):
        raise ValueError(
            f"Configuration root must be a JSON object: {path}"
        )

    return data


def _validate_keys(
    data: dict,
    expected_keys: set[str],
    label: str,
) -> None:
    """Проверяет обязательные и неизвестные поля объекта."""

    missing = expected_keys - data.keys()
    unknown = data.keys() - expected_keys

    if missing:
        names = ", ".join(sorted(missing))
        raise ValueError(
            f"{label}: missing required fields: {names}"
        )

    if unknown:
        names = ", ".join(sorted(unknown))
        raise ValueError(
            f"{label}: unknown fields: {names}"
        )


def _validate_version(data: dict, label: str) -> None:
    """Проверяет версию схемы без неявного преобразования типов."""

    version = data.get("schema_version")

    if type(version) is not int or version != SCHEMA_VERSION:
        raise ValueError(
            f"{label}: schema_version must be integer "
            f"{SCHEMA_VERSION}"
        )


def _read_name_list(value: object, label: str) -> tuple[str, ...]:
    """Проверяет список непустых уникальных названий без краевых пробелов."""

    if not isinstance(value, list):
        raise TypeError(f"{label} must be a JSON array")

    if not value:
        raise ValueError(f"{label} must not be empty")

    result: list[str] = []

    for name in value:
        if not isinstance(name, str):
            raise TypeError(f"{label} entries must be strings")

        if not name.strip():
            raise ValueError(f"{label} entries must not be empty")

        if name != name.strip():
            raise ValueError(
                f"{label} entries must not have surrounding whitespace"
            )

        if name in result:
            raise ValueError(f"{label} must not contain duplicates")

        result.append(name)

    return tuple(result)


def _read_number(data: dict, field_name: str) -> float:
    """Проверяет конечное число, явно отклоняя bool и строки."""

    value = data[field_name]

    if type(value) not in (int, float):
        raise TypeError(f"{field_name} must be a number")

    try:
        result = float(value)
    except (OverflowError, ValueError) as exc:
        raise ValueError(f"{field_name} must be finite") from exc

    if not math.isfinite(result):
        raise ValueError(f"{field_name} must be finite")

    return result


def _load_vessel(path: Path) -> Vessel:
    data = _read_json(path)

    expected = {
        "schema_version",
        *(item.name for item in fields(Vessel)),
    }
    _validate_keys(data, expected, "vessel.json")
    _validate_version(data, "vessel.json")

    values = {
        key: value
        for key, value in data.items()
        if key != "schema_version"
    }

    try:
        return Vessel(**values)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Invalid vessel configuration: {exc}"
        ) from exc


def _load_limits(path: Path) -> LimitsConfig:
    data = _read_json(path)

    field_names = {
        "max_container_mass_kg",
        "min_gm_m",
        "target_gm_m",
        "max_abs_heel_deg",
        "max_abs_trim_percent_of_length",
        "small_angle_model_max_abs_heel_deg",
    }
    expected = {"schema_version", *field_names}

    _validate_keys(data, expected, "limits.json")
    _validate_version(data, "limits.json")

    values = {
        name: _read_number(data, name)
        for name in field_names
    }

    if values["max_container_mass_kg"] <= 0:
        raise ValueError("max_container_mass_kg must be positive")

    if values["min_gm_m"] < 0:
        raise ValueError("min_gm_m must be non-negative")

    if values["target_gm_m"] < values["min_gm_m"]:
        raise ValueError("target_gm_m must be at least min_gm_m")

    if values["max_abs_heel_deg"] <= 0:
        raise ValueError("max_abs_heel_deg must be positive")

    if values["max_abs_trim_percent_of_length"] <= 0:
        raise ValueError(
            "max_abs_trim_percent_of_length must be positive"
        )

    angle_limit = values["small_angle_model_max_abs_heel_deg"]

    if not 0 < angle_limit <= MODEL_SMALL_ANGLE_LIMIT_DEG:
        raise ValueError(
            "small_angle_model_max_abs_heel_deg must be in (0, 5]"
        )

    if values["max_abs_heel_deg"] > angle_limit:
        raise ValueError(
            "max_abs_heel_deg must not exceed the small-angle model limit"
        )

    return LimitsConfig(**values)


def _load_ports(path: Path) -> PortConfiguration:
    data = _read_json(path)

    expected = {
        "schema_version",
        "canonical_ports",
        "aliases",
        "rotation",
    }
    _validate_keys(data, expected, "ports.json")
    _validate_version(data, "ports.json")

    canonical_ports = _read_name_list(
        data["canonical_ports"],
        "canonical_ports",
    )
    rotation_ports = _read_name_list(
        data["rotation"],
        "rotation",
    )

    canonical_set = set(canonical_ports)

    if set(rotation_ports) != canonical_set:
        raise ValueError(
            "rotation must contain every canonical port exactly once"
        )

    raw_aliases = data["aliases"]

    if not isinstance(raw_aliases, dict):
        raise TypeError("aliases must be a JSON object")

    normalized_aliases: dict[str, tuple[str, ...]] = {}
    all_alias_names: set[str] = set()

    for canonical, raw_values in raw_aliases.items():
        if canonical not in canonical_set:
            raise ValueError(
                f"Alias target '{canonical}' is not a canonical port"
            )

        alias_values = _read_name_list(
            raw_values,
            f"aliases for '{canonical}'",
        )

        for alias in alias_values:
            if alias in canonical_set:
                raise ValueError(
                    f"Alias '{alias}' conflicts with a canonical port"
                )

            if alias in all_alias_names:
                raise ValueError(
                    f"Alias '{alias}' is assigned more than once"
                )

            all_alias_names.add(alias)

        normalized_aliases[canonical] = alias_values

    try:
        rotation = PortRotation(ports=rotation_ports)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid port rotation: {exc}") from exc

    return PortConfiguration(
        canonical_ports=canonical_ports,
        aliases=MappingProxyType(normalized_aliases),
        rotation=rotation,
    )


def load_project_config(
    config_dir: str | Path | None = None,
) -> ProjectConfig:
    """
    Загружает и проверяет vessel.json, limits.json и ports.json.

    По умолчанию использует каталог configs в корне проекта.
    """

    if config_dir is None:
        directory = Path(__file__).resolve().parents[3] / "configs"
    else:
        directory = Path(config_dir)

    vessel = _load_vessel(directory / "vessel.json")
    limits = _load_limits(directory / "limits.json")
    ports = _load_ports(directory / "ports.json")

    return ProjectConfig(
        vessel=vessel,
        limits=limits,
        ports=ports,
    )