"""Draw a text-free 3D action-evidence constraint space.

Blue semantic half-space facets and a purple joint-risk budget jointly carve
out the green feasible intersection. Candidate action states are shown only
through shape and color; the rendered figure contains no text.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib as mpl

mpl.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from scipy.spatial import ConvexHull


OUTPUT_DIR = Path(__file__).resolve().parent / "outputs"
OUTPUT_STEM = OUTPUT_DIR / "geometric_halfspace_constraints"

COLORS = {
    "ink": "#263238",
    "blue": "#5B9BD5",
    "blue_fill": "#CFE8FA",
    "purple": "#8A67C7",
    "green": "#53A567",
    "green_fill": "#8FD19E",
    "orange": "#F2A65A",
    "red": "#E85D5D",
    "cream": "#FFFDF6",
}


def linear_feasible(points: np.ndarray) -> np.ndarray:
    """Mask points satisfying the active linear semantic half-spaces."""
    x, y, z = points.T
    return (
        (x >= 0.12)
        & (y >= 0.12)
        & (z >= 0.12)
        & (x + 0.55 * z <= 1.06)
        & (y + 0.50 * z <= 1.04)
        & (x + y + 0.45 * z <= 1.43)
    )


def in_joint_risk_budget(points: np.ndarray) -> np.ndarray:
    """Ellipsoidal 3D projection of a convex joint risk-support budget."""
    center = np.array([0.49, 0.47, 0.43])
    radii = np.array([0.47, 0.40, 0.45])
    normalized = (points - center) / radii
    return np.sum(normalized**2, axis=1) <= 1.0


def sample_feasible_intersection(seed: int = 12) -> np.ndarray:
    """Sample the half-space/risk-budget intersection for a smooth hull."""
    rng = np.random.default_rng(seed)
    points = rng.uniform(0.02, 0.98, size=(110_000, 3))
    feasible = points[linear_feasible(points) & in_joint_risk_budget(points)]
    if len(feasible) > 4_200:
        feasible = feasible[rng.choice(len(feasible), 4_200, replace=False)]
    if len(feasible) < 4:
        raise RuntimeError("The configured feasible intersection is empty.")
    return feasible


def add_plane_z(ax: plt.Axes, z_value: float = 0.12) -> None:
    grid = np.linspace(0.03, 0.97, 4)
    x, y = np.meshgrid(grid, grid)
    z = np.full_like(x, z_value)
    ax.plot_surface(
        x, y, z,
        color=COLORS["blue_fill"],
        edgecolor=COLORS["blue"],
        linewidth=0.45,
        alpha=0.22,
        shade=False,
        zorder=1,
    )


def add_plane_xz(ax: plt.Axes) -> None:
    """Draw x + 0.55 z = 1.06."""
    y, z = np.meshgrid(np.linspace(0.03, 0.97, 4), np.linspace(0.04, 0.97, 5))
    x = 1.06 - 0.55 * z
    x[(x < 0.03) | (x > 0.97)] = np.nan
    ax.plot_surface(
        x, y, z,
        color=COLORS["blue_fill"],
        edgecolor=COLORS["blue"],
        linewidth=0.45,
        alpha=0.20,
        shade=False,
        zorder=1,
    )


def add_plane_yz(ax: plt.Axes) -> None:
    """Draw y + 0.50 z = 1.04."""
    x, z = np.meshgrid(np.linspace(0.03, 0.97, 5), np.linspace(0.04, 0.97, 6))
    y = 1.04 - 0.50 * z
    y[(y < 0.03) | (y > 0.97)] = np.nan
    ax.plot_surface(
        x, y, z,
        color=COLORS["blue_fill"],
        edgecolor=COLORS["blue"],
        linewidth=0.45,
        alpha=0.15,
        shade=False,
        zorder=1,
    )


def add_plane_diagonal(ax: plt.Axes) -> None:
    """Draw x + y + 0.45 z = 1.43."""
    x, z = np.meshgrid(np.linspace(0.04, 0.96, 5), np.linspace(0.04, 0.96, 5))
    y = 1.43 - x - 0.45 * z
    y[(y < 0.03) | (y > 0.97)] = np.nan
    ax.plot_surface(
        x, y, z,
        color=COLORS["blue_fill"],
        edgecolor=COLORS["blue"],
        linewidth=0.45,
        alpha=0.19,
        shade=False,
        zorder=1,
    )


def add_joint_risk_budget(ax: plt.Axes) -> None:
    """Draw the curved risk-support budget as a purple wireframe."""
    center = np.array([0.49, 0.47, 0.43])
    radii = np.array([0.47, 0.40, 0.45])
    u = np.linspace(0, 2 * np.pi, 52)
    v = np.linspace(0, np.pi, 28)
    x = center[0] + radii[0] * np.outer(np.cos(u), np.sin(v))
    y = center[1] + radii[1] * np.outer(np.sin(u), np.sin(v))
    z = center[2] + radii[2] * np.outer(np.ones_like(u), np.cos(v))
    ax.plot_wireframe(
        x, y, z,
        rstride=6,
        cstride=6,
        color=COLORS["purple"],
        linewidth=0.96,
        alpha=0.46,
        zorder=7,
    )


def add_feasible_hull(ax: plt.Axes, points: np.ndarray) -> None:
    hull = ConvexHull(points)
    surface = Poly3DCollection(
        points[hull.simplices],
        facecolor=COLORS["green_fill"],
        edgecolor="none",
        linewidth=0.0,
        alpha=0.37,
        zorder=5,
    )
    surface.set_zsort("average")
    ax.add_collection3d(surface)


def add_candidate(
    ax: plt.Axes,
    point: tuple[float, float, float],
    *,
    color: str,
    marker: str,
    size: float,
) -> None:
    x, y, z = point
    ax.scatter(
        [x], [y], [z],
        s=size * 3.0,
        c=color,
        alpha=0.14,
        edgecolors="none",
        depthshade=False,
        zorder=18,
    )
    ax.scatter(
        [x], [y], [z],
        s=size,
        c=color,
        marker=marker,
        edgecolors="white",
        linewidths=1.15,
        depthshade=False,
        zorder=20,
    )


def draw_figure() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    mpl.rcParams.update(
        {
            "figure.facecolor": COLORS["cream"],
            "savefig.facecolor": COLORS["cream"],
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
        }
    )

    figure = plt.figure(figsize=(12.8, 8.5), dpi=140)
    ax = figure.add_subplot(111, projection="3d", computed_zorder=False)
    ax.set_proj_type("ortho")
    ax.view_init(elev=23, azim=-52)

    add_plane_z(ax)
    add_plane_xz(ax)
    add_plane_diagonal(ax)
    add_joint_risk_budget(ax)
    add_feasible_hull(ax, sample_feasible_intersection())

    add_candidate(ax, (0.42, 0.40, 0.40), color=COLORS["green"], marker="*", size=230)
    add_candidate(ax, (0.21, 0.22, 0.70), color=COLORS["orange"], marker="o", size=118)
    add_candidate(ax, (0.84, 0.73, 0.58), color=COLORS["red"], marker="X", size=145)

    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_zlim(0, 1)
    ax.set_box_aspect((1.05, 1.0, 0.88))
    ax.set_xticks([0, 0.5, 1.0])
    ax.set_yticks([0, 0.5, 1.0])
    ax.set_zticks([0, 0.5, 1.0])
    ax.set_xticklabels([])
    ax.set_yticklabels([])
    ax.set_zticklabels([])
    ax.set_xlabel("")
    ax.set_ylabel("")
    ax.set_zlabel("")
    ax.tick_params(colors="#78909C", labelsize=0, pad=1)
    for axis in (ax.xaxis, ax.yaxis, ax.zaxis):
        axis.pane.set_facecolor((1, 1, 1, 0.0))
        axis.pane.set_edgecolor((0.52, 0.60, 0.63, 0.38))
        axis._axinfo["grid"]["color"] = (0.65, 0.72, 0.75, 0.18)
        axis._axinfo["grid"]["linewidth"] = 0.55

    figure.subplots_adjust(left=-0.01, right=1.01, top=1.01, bottom=-0.01)
    save_options = dict(
        bbox_inches="tight",
        pad_inches=0.18,
        facecolor=COLORS["cream"],
    )
    figure.savefig(
        OUTPUT_STEM.with_suffix(".png"),
        dpi=240,
        pil_kwargs={"optimize": True},
        **save_options,
    )
    figure.savefig(OUTPUT_STEM.with_suffix(".svg"), **save_options)
    figure.savefig(OUTPUT_STEM.with_suffix(".pdf"), **save_options)
    figure.savefig(
        OUTPUT_STEM.with_suffix(".tiff"),
        dpi=600,
        pil_kwargs={"compression": "tiff_lzw"},
        **save_options,
    )
    plt.close(figure)

    for suffix in ((".png"), (".svg"), (".pdf"), (".tiff")):
        print(OUTPUT_STEM.with_suffix(suffix))


if __name__ == "__main__":
    draw_figure()
