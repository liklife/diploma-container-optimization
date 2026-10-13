
import pytest

from stowage.domain.slot import Slot
from stowage.domain.vessel import Vessel


DEFAULTS = {
    "vessel_id": "synthetic_box_barge_8x4x3",
    "name": "Синтетическая баржа",
    "synthetic": True,
    "hull_model": "box_barge",
    "length_m": 120.0,
    "beam_m": 14.0,
    "depth_m": 10.0,
    "bays": 8,
    "rows": 4,
    "tiers": 3,
    "first_bay_offset_m": 7.5,
    "bay_spacing_m": 15.0,
    "first_row_center_y_m": -5.25,
    "row_spacing_m": 3.5,
    "base_height_m": 0.2,
    "container_height_m": 2.591,
    "tier_spacing_m": 2.6,
    "lightship_mass_kg": 8000000,
    "lightship_cg_x_m": 60.0,
    "lightship_cg_y_m": 0.0,
    "lightship_cg_z_m": 4.2,
    "water_density_kg_m3": 1025.0,
    "max_bay_load_t": 220.0,
    "max_column_load_t": 60.0,
}


def make_vessel(**overrides):
    values = DEFAULTS.copy()
    values.update(overrides)
    return Vessel(**values)


def test_create_vessel():
    vessel = make_vessel()

    assert vessel.vessel_id == "synthetic_box_barge_8x4x3"
    assert vessel.synthetic is True
    assert vessel.hull_model == "box_barge"
    assert (vessel.bays, vessel.rows, vessel.tiers) == (8, 4, 3)
    assert vessel.lightship_mass_kg == 8000000


@pytest.mark.parametrize(
    "field_name",
    ["vessel_id", "name", "hull_model"],
)
@pytest.mark.parametrize("invalid_value", [None, 123])
def test_text_fields_require_strings(field_name, invalid_value):
    with pytest.raises(TypeError):
        make_vessel(**{field_name: invalid_value})


@pytest.mark.parametrize(
    "field_name",
    ["vessel_id", "name", "hull_model"],
)
@pytest.mark.parametrize("invalid_value", ["", "   "])
def test_text_fields_cannot_be_empty(field_name, invalid_value):
    with pytest.raises(ValueError):
        make_vessel(**{field_name: invalid_value})


@pytest.mark.parametrize("invalid_value", [0, 1, "true", None])
def test_synthetic_flag_must_be_boolean(invalid_value):
    with pytest.raises(TypeError):
        make_vessel(synthetic=invalid_value)


def test_real_vessel_flag_is_a_valid_boolean():
    vessel = make_vessel(synthetic=False)

    assert vessel.synthetic is False


@pytest.mark.parametrize("field_name", ["bays", "rows", "tiers"])
@pytest.mark.parametrize("invalid_value", [True, 1.5, "3", None])
def test_grid_dimensions_must_be_integers(field_name, invalid_value):
    with pytest.raises(TypeError):
        make_vessel(**{field_name: invalid_value})


@pytest.mark.parametrize("field_name", ["bays", "rows", "tiers"])
@pytest.mark.parametrize("invalid_value", [0, -1])
def test_grid_dimensions_must_be_positive(field_name, invalid_value):
    with pytest.raises(ValueError):
        make_vessel(**{field_name: invalid_value})


NUMERIC_FIELDS = [
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
]


@pytest.mark.parametrize("field_name", NUMERIC_FIELDS)
def test_numeric_fields_reject_boolean_values(field_name):
    with pytest.raises(TypeError):
        make_vessel(**{field_name: True})


@pytest.mark.parametrize("field_name", NUMERIC_FIELDS)
def test_numeric_fields_reject_non_finite_values(field_name):
    with pytest.raises(ValueError):
        make_vessel(**{field_name: float("nan")})


POSITIVE_FIELDS = [
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
]


@pytest.mark.parametrize("field_name", POSITIVE_FIELDS)
@pytest.mark.parametrize("invalid_value", [0, -1])
def test_positive_fields_reject_zero_and_negative_values(
    field_name, invalid_value
):
    with pytest.raises(ValueError):
        make_vessel(**{field_name: invalid_value})


@pytest.mark.parametrize(
    "field_name",
    ["first_bay_offset_m", "base_height_m"],
)
def test_non_negative_fields_reject_negative_values(field_name):
    with pytest.raises(ValueError):
        make_vessel(**{field_name: -1})


def test_bay_positions_must_fit_vessel_length():
    with pytest.raises(ValueError, match="vessel length"):
        make_vessel(bay_spacing_m=20.0)


def test_row_positions_must_fit_vessel_beam():
    with pytest.raises(ValueError, match="vessel beam"):
        make_vessel(first_row_center_y_m=-7.1)


def test_tier_spacing_cannot_be_smaller_than_container_height():
    with pytest.raises(ValueError, match="container height"):
        make_vessel(tier_spacing_m=2.0)


def test_all_tiers_must_fit_vessel_depth():
    with pytest.raises(ValueError, match="vessel depth"):
        make_vessel(tiers=4)


def test_lightship_cg_x_must_fit_vessel_length():
    with pytest.raises(ValueError, match="CG X"):
        make_vessel(lightship_cg_x_m=121.0)


def test_lightship_cg_y_must_fit_vessel_beam():
    with pytest.raises(ValueError, match="CG Y"):
        make_vessel(lightship_cg_y_m=7.1)


def test_lightship_cg_z_must_fit_vessel_depth():
    with pytest.raises(ValueError, match="CG Z"):
        make_vessel(lightship_cg_z_m=10.1)


def test_coordinates_for_slot():
    vessel = make_vessel()

    coordinates = vessel.coordinates_for(
        Slot(bay=2, row=3, tier=2)
    )

    assert coordinates == pytest.approx((37.5, 5.25, 6.6955))


@pytest.mark.parametrize(
    "slot",
    [
        Slot(bay=8, row=0, tier=0),
        Slot(bay=0, row=4, tier=0),
        Slot(bay=0, row=0, tier=3),
    ],
)
def test_coordinates_reject_slot_outside_grid(slot):
    vessel = make_vessel()

    with pytest.raises(ValueError, match="outside vessel grid"):
        vessel.coordinates_for(slot)


def test_coordinates_require_slot_instance():
    vessel = make_vessel()

    with pytest.raises(TypeError, match="Slot"):
        vessel.coordinates_for((0, 0, 0))


def test_vessel_is_immutable():
    vessel = make_vessel()

    with pytest.raises(AttributeError):
        vessel.length_m = 150.0
