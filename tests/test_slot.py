
import pytest

from stowage.domain.slot import Slot


def test_create_slot():
    slot = Slot(bay=2, row=1, tier=0)

    assert slot.bay == 2
    assert slot.row == 1
    assert slot.tier == 0


def test_zero_indices_are_allowed():
    slot = Slot(bay=0, row=0, tier=0)

    assert (slot.bay, slot.row, slot.tier) == (0, 0, 0)


@pytest.mark.parametrize("field_name", ["bay", "row", "tier"])
def test_negative_index_is_rejected(field_name):
    values = {"bay": 0, "row": 0, "tier": 0}
    values[field_name] = -1

    with pytest.raises(ValueError):
        Slot(**values)


@pytest.mark.parametrize("field_name", ["bay", "row", "tier"])
@pytest.mark.parametrize("invalid_value", [True, False, 1.5, "0", None])
def test_non_integer_index_is_rejected(field_name, invalid_value):
    values = {"bay": 0, "row": 0, "tier": 0}
    values[field_name] = invalid_value

    with pytest.raises(TypeError):
        Slot(**values)


def test_slot_indices_cannot_be_changed():
    slot = Slot(bay=0, row=1, tier=2)

    with pytest.raises(AttributeError):
        slot.bay = 3

def test_slot_normalizes_numpy_integer_indices():
    import numpy as np

    slot = Slot(
        bay=np.int64(3),
        row=np.int64(1),
        tier=np.int64(0),
    )

    assert (slot.bay, slot.row, slot.tier) == (3, 1, 0)
    assert type(slot.bay) is int
    assert type(slot.row) is int
    assert type(slot.tier) is int


def test_slot_rejects_numpy_boolean_index():
    import numpy as np

    with pytest.raises(TypeError):
        Slot(bay=np.bool_(True), row=0, tier=0)