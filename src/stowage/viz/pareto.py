"""Графики предварительного сравнения по трём отдельным целям."""

from matplotlib.colors import Normalize
from matplotlib.figure import Figure
from matplotlib.ticker import MaxNLocator


def plot_pareto(solutions, front) -> Figure:
    """Показывает наблюдаемый фронт и исходную точку эвристики."""
    scenarios = solutions["scenario"].drop_duplicates()
    figure = Figure(figsize=(6.3 * len(scenarios), 4.4), layout="constrained")
    axes = figure.subplots(1, len(scenarios), squeeze=False)[0]
    all_trim = solutions["abs_trim_m"]
    norm = Normalize(vmin=all_trim.min(), vmax=all_trim.max())

    for ax, scenario in zip(axes, scenarios, strict=True):
        points = front[front["scenario"] == scenario]
        baseline = solutions[(solutions["scenario"] == scenario) & (solutions["method"] == "heuristic")]
        scatter = ax.scatter(points["r"], points["abs_heel_deg"], c=points["abs_trim_m"],
                             norm=norm, cmap="viridis", s=60, edgecolors="#0f172a",
                             linewidths=0.4, label="Наблюдаемый фронт")
        if not baseline.empty:
            ax.scatter(baseline["r"], baseline["abs_heel_deg"], c=baseline["abs_trim_m"],
                       norm=norm, cmap="viridis", s=180, marker="*", edgecolors="#0f172a",
                       linewidths=1, label="Эвристика", zorder=3)
        ax.set_title(f"{scenario} контейнеров", loc="left", fontweight="bold")
        ax.set_xlabel("R · блокирующие пары")
        ax.set_ylabel("|Крен|, °")
        ax.xaxis.set_major_locator(MaxNLocator(integer=True, min_n_ticks=1))
        ax.set_xlim(-0.5, max(0, points["r"].max() if not points.empty else 0,
                              baseline["r"].max() if not baseline.empty else 0) + 0.5)
        ax.set_ylim(bottom=-0.03 * ax.get_ylim()[1])
        ax.grid(alpha=0.23)
        ax.legend(loc="best", frameon=False)
    figure.colorbar(scatter, ax=axes.tolist(), label="|Линейный дифферент|, м")
    figure.suptitle("Наблюдаемые компромиссы среди допустимых планов", fontweight="bold")
    return figure


def plot_run_comparison(runs) -> Figure:
    """Сопоставляет минимумы каждой цели по seed и один результат эвристики."""
    scenarios = runs["scenario"].drop_duplicates()
    metrics = (("min_r", "R · пары"), ("min_abs_heel_deg", "|Крен|, °"),
               ("min_abs_trim_m", "|Дифферент|, м"))
    figure = Figure(figsize=(4.25 * len(metrics), 3 * len(scenarios) + 0.7), layout="constrained")
    axes = figure.subplots(len(scenarios), len(metrics), squeeze=False)
    for row, scenario in enumerate(scenarios):
        results = runs[runs["scenario"] == scenario]
        ea = results[results["method"] == "nsga2"]
        baseline = results[results["method"] == "heuristic"].iloc[0]
        for ax, (metric, label) in zip(axes[row], metrics, strict=True):
            ax.scatter(ea["seed"], ea[metric], color="#087f8c", s=46, label="NSGA-II", zorder=3)
            if baseline["n_valid"]:
                ax.axhline(baseline[metric], color="#9a3412", linestyle="--", label="Эвристика")
            ax.set_title(f"{scenario} контейнеров · {label}", loc="left", fontweight="bold")
            ax.set_xticks(ea["seed"])
            ax.set_xlabel("Seed NSGA-II")
            ax.grid(axis="y", alpha=0.24)
            if metric == "min_r":
                ax.set_ylim(-0.25, max(0.75, ax.get_ylim()[1]))
                ax.yaxis.set_major_locator(MaxNLocator(integer=True, min_n_ticks=1))
            else:
                ax.set_ylim(bottom=-0.03 * ax.get_ylim()[1])
    axes[0, 0].legend(frameon=True, framealpha=0.9, loc="best")
    figure.suptitle("Минимумы целей по запускам · разные цели могут достигаться разными планами",
                   fontweight="bold")
    return figure
