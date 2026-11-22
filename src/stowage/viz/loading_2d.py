"""Планы грузовой сетки по ярусам в координатах судна."""

from textwrap import wrap

from matplotlib import colormaps
from matplotlib.figure import Figure
from matplotlib.patches import Patch, Rectangle

from stowage.domain.plan import Plan
from stowage.domain.port_rotation import PortRotation
from stowage.domain.slot import Slot


def plot_loading_plan(plan: Plan, rotation: PortRotation, *, title: str = "") -> Figure:
    """Возвращает схему с осью X к носу и положительной осью Y вправо по борту."""
    vessel = plan.vessel
    containers = {container.id: container for container in plan.containers}
    occupied = {slot: containers[container_id] for container_id, slot in plan.placements}
    ports = tuple(dict.fromkeys((*rotation.ports, *(c.port for c in plan.containers))))
    palette = colormaps["tab20"] if len(ports) <= 20 else colormaps["hsv"].resampled(len(ports))
    colors = {port: palette(i) for i, port in enumerate(ports)}
    width = 0.87 * min(vessel.bay_spacing_m, vessel.length_m / vessel.bays)
    height = 0.81 * min(vessel.row_spacing_m, vessel.beam_m / vessel.rows)
    xs = [vessel.coordinates_for(Slot(bay, 0, 0))[0] for bay in range(vessel.bays)]
    ys = [vessel.coordinates_for(Slot(0, row, 0))[1] for row in range(vessel.rows)]

    missing = ", ".join(str(c.id) for c in plan.unplaced_containers)
    notes = wrap("Неразмещённые ID: " + (missing or "нет"), width=100)
    footer_height = 0.65 + 0.22 * len(notes) + 0.26 * ((len(ports) - 1) // 4)
    figure = Figure(figsize=(12, 2.3 * vessel.tiers + footer_height + 0.8), layout="constrained")
    grid = figure.add_gridspec(vessel.tiers + 1, 1, height_ratios=[2.3] * vessel.tiers + [footer_height])
    figure.suptitle(title or vessel.name, x=0.06, ha="left", fontweight="bold")

    for panel, tier in enumerate(reversed(range(vessel.tiers))):
        ax = figure.add_subplot(grid[panel])
        ax.set_title(f"Ярус {tier}", loc="left", fontweight="bold")
        for bay in range(vessel.bays):
            for row in range(vessel.rows):
                slot = Slot(bay, row, tier)
                x, y, _ = vessel.coordinates_for(slot)
                container = occupied.get(slot)
                ax.add_patch(Rectangle(
                    (x - width / 2, y - height / 2), width, height,
                    facecolor=colors[container.port] if container else "#f1f5f9",
                    edgecolor="#64748b" if container else "#cbd5e1", linewidth=0.8,
                ))
                if container:
                    ax.text(x, y, str(container.id), ha="center", va="center",
                            fontsize=9, color="#0f172a",
                            bbox=dict(facecolor="white", alpha=0.82, edgecolor="none", pad=1))
        ax.set_xlim(min(0, min(xs) - width / 2), max(vessel.length_m, max(xs) + width / 2))
        ax.set_ylim(min(-vessel.beam_m / 2, min(ys) - height / 2),
                    max(vessel.beam_m / 2, max(ys) + height / 2))
        ax.set_xticks(xs, [str(bay) for bay in range(vessel.bays)])
        ax.set_yticks(ys, [str(row) for row in range(vessel.rows)])
        ax.set_xlabel("Bay · от кормы к носу")
        ax.set_ylabel("Row · к правому борту")
        ax.tick_params(length=0)
        ax.axhline(0, color="#94a3b8", linewidth=0.7, linestyle="--", zorder=0)

    footer = figure.add_subplot(grid[-1])
    footer.set_axis_off()
    footer.legend(
        handles=[Patch(facecolor=colors[port], label=port) for port in ports]
        + [Patch(facecolor="#f1f5f9", edgecolor="#cbd5e1", label="Свободный слот")],
        loc="upper left", ncols=min(4, len(ports) + 1), frameon=False,
    )
    footer.text(0.01, 0.04, "\n".join(notes), va="bottom", transform=footer.transAxes)
    return figure
