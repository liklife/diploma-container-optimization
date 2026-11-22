import io
from dataclasses import replace

import pytest
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

from stowage.config import load_project_config
from stowage.domain.container import Container
from stowage.domain.plan import Plan
from stowage.domain.slot import Slot
from stowage.viz.loading_2d import plot_loading_plan


def test_plan_uses_slot_geometry_port_colors_and_marks_unplaced_ids():
    config = load_project_config()
    vessel = replace(config.vessel, bays=2, rows=2)
    ports = config.ports.rotation.ports
    cargo = tuple(Container(id_, 5000, ports[i], "dry") for i, id_ in enumerate((0, 301, 8)))
    slots = (Slot(1, 1, 0), Slot(1, 1, 1))
    plan = Plan(vessel, cargo, {0: slots[0], 301: slots[1]})

    figure = plot_loading_plan(plan, config.ports.rotation)

    assert isinstance(figure, Figure)
    tier_2, tier_1, tier_0, footer = figure.axes
    assert [len(axis.patches) for axis in (tier_2, tier_1, tier_0)] == [4, 4, 4]
    assert not tier_2.texts
    assert tier_1.texts[0].get_text() == "301"
    assert tier_0.texts[0].get_text() == "0"
    for axis, slot in ((tier_0, slots[0]), (tier_1, slots[1])):
        point = vessel.coordinates_for(slot)
        assert axis.texts[0].get_position() == pytest.approx(point[:2])
        patch = axis.patches[3]
        assert (patch.get_x() + patch.get_width() / 2, patch.get_y() + patch.get_height() / 2
                ) == pytest.approx(point[:2])
    assert tier_1.patches[3].get_facecolor() != tier_0.patches[3].get_facecolor()
    assert "Неразмещённые ID: 8" in footer.texts[0].get_text()
    assert [item.get_text() for item in footer.get_legend().get_texts()][:3] == list(ports)

    stream = io.BytesIO()
    FigureCanvasAgg(figure).print_png(stream)
    assert stream.getvalue().startswith(b"\x89PNG\r\n\x1a\n")
