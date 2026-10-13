from dataclasses import dataclass

from stowage.domain._validation import as_int, as_number, as_text
from stowage.domain.slot import Slot


_NUMERIC_FIELDS = (
    "length_m",
    "beam_m",
    "depth_m",
    "first_bay_offset_m",
    "bay_spacing_m",
    "first_row_center_y_m",
    "row_spacing_m",
    "base_height_m",
    "container_height_m",
    "tier_spacing_m",
    "lightship_mass_kg",
    "lightship_cg_x_m",
    "lightship_cg_y_m",
    "lightship_cg_z_m",
    "water_density_kg_m3",
    "max_bay_load_t",
    "max_column_load_t",
)

_POSITIVE_FIELDS = (
    "length_m",
    "beam_m",
    "depth_m",
    "bay_spacing_m",
    "row_spacing_m",
    "container_height_m",
    "tier_spacing_m",
    "lightship_mass_kg",
    "water_density_kg_m3",
    "max_bay_load_t",
    "max_column_load_t",
)

_NON_NEGATIVE_FIELDS = (
    "first_bay_offset_m",
    "base_height_m",
)


@dataclass(frozen=True)
class Vessel:
    """Параметры судна и его контейнерной грузовой сетки."""

    vessel_id: str
    name: str
    synthetic: bool
    hull_model: str

    length_m: float
    beam_m: float
    depth_m: float

    bays: int
    rows: int
    tiers: int

    first_bay_offset_m: float
    bay_spacing_m: float
    first_row_center_y_m: float
    row_spacing_m: float

    base_height_m: float
    container_height_m: float
    tier_spacing_m: float

    lightship_mass_kg: float
    lightship_cg_x_m: float
    lightship_cg_y_m: float
    lightship_cg_z_m: float

    water_density_kg_m3: float

    max_bay_load_t: float
    max_column_load_t: float

    def __post_init__(self) -> None:
        for field_name in ("vessel_id", "name", "hull_model"):
            object.__setattr__(
                self,
                field_name,
                as_text(getattr(self, field_name), f"Vessel {field_name}"),
            )

        if type(self.synthetic) is not bool:
            raise TypeError("Vessel synthetic flag must be a boolean")

        for field_name in ("bays", "rows", "tiers"):
            value = as_int(
                getattr(self, field_name),
                f"Vessel {field_name}",
            )
            object.__setattr__(self, field_name, value)

            if value <= 0:
                raise ValueError(
                    f"Vessel {field_name} must be positive"
                )

        for field_name in _NUMERIC_FIELDS:
            value = as_number(
                getattr(self, field_name),
                f"Vessel {field_name}",
            )
            object.__setattr__(self, field_name, value)

        for field_name in _POSITIVE_FIELDS:
            if getattr(self, field_name) <= 0:
                raise ValueError(
                    f"Vessel {field_name} must be positive"
                )

        for field_name in _NON_NEGATIVE_FIELDS:
            if getattr(self, field_name) < 0:
                raise ValueError(
                    f"Vessel {field_name} must be non-negative"
                )

        last_bay_x = (
            self.first_bay_offset_m
            + (self.bays - 1) * self.bay_spacing_m
        )

        if last_bay_x > self.length_m:
            raise ValueError(
                "Bay positions must fit within vessel length"
            )

        last_row_y = (
            self.first_row_center_y_m
            + (self.rows - 1) * self.row_spacing_m
        )

        if (
            min(self.first_row_center_y_m, last_row_y)
            < -self.beam_m / 2
            or max(self.first_row_center_y_m, last_row_y)
            > self.beam_m / 2
        ):
            raise ValueError(
                "Row positions must fit within vessel beam"
            )

        if self.tier_spacing_m < self.container_height_m:
            raise ValueError(
                "Tier spacing must not be smaller than container height"
            )

        highest_container_top = (
            self.base_height_m
            + (self.tiers - 1) * self.tier_spacing_m
            + self.container_height_m
        )

        if highest_container_top > self.depth_m:
            raise ValueError(
                "Container tiers must fit within vessel depth"
            )

        if not 0 <= self.lightship_cg_x_m <= self.length_m:
            raise ValueError(
                "Lightship CG X must fit within vessel length"
            )

        if abs(self.lightship_cg_y_m) > self.beam_m / 2:
            raise ValueError(
                "Lightship CG Y must fit within vessel beam"
            )

        if not 0 <= self.lightship_cg_z_m <= self.depth_m:
            raise ValueError(
                "Lightship CG Z must fit within vessel depth"
            )

    def coordinates_for(self, slot: Slot) -> tuple[float, float, float]:
        """Возвращает координаты центра контейнера: X, Y, Z в метрах."""

        if not isinstance(slot, Slot):
            raise TypeError("Expected a Slot instance")

        if slot.bay >= self.bays:
            raise ValueError("Slot bay index is outside vessel grid")

        if slot.row >= self.rows:
            raise ValueError("Slot row index is outside vessel grid")

        if slot.tier >= self.tiers:
            raise ValueError("Slot tier index is outside vessel grid")

        x = self.first_bay_offset_m + slot.bay * self.bay_spacing_m
        y = self.first_row_center_y_m + slot.row * self.row_spacing_m
        z = (
            self.base_height_m
            + slot.tier * self.tier_spacing_m
            + self.container_height_m / 2
        )

        return float(x), float(y), float(z)