"""Draw a cartoon-style 3D semantic constraint space.

The figure illustrates three geometric objects:
1. translucent blue planes: linear semantic facets;
2. a purple ellipsoid: a joint-risk / second-order budget boundary;
3. a green solid: their dynamic feasible intersection.

Run:
    MPLCONFIGDIR=/tmp/matplotlib python draw_cartoon_constraint_space.py
"""

from pathlib import Path

import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from scipy.spatial import ConvexHull


OUTPUT_DIR = Path(__file__).resolve().parent / "outputs"
PNG_PATH = OUTPUT_DIR / "cartoon_constraint_space.png"
SVG_PATH = OUTPUT_DIR / "cartoon_constraint_space.svg"


COLORS = {
    "ink": "#263238",
    "blue": "#5B9BD5",
    "blue_fill": "#CFE8FA",
    "purple": "#8A67C7",
    "purple_fill": "#C9B7EA",
    "green": "#53A567",
    "green_fill": "#8FD19E",
    "orange": "#F2A65A",
    "red": "#E85D5D",
    "cream": "#FFFDF6",
}


def linear_feasible(points: np.ndarray) -> np.ndarray:
    """Return the mask for the linear semantic half-spaces."""
    x, y, z = points.T
    return (
        (x >= 0.12)
        & (y >= 0.12)
        & (z >= 0.12)
        & (x + 0.55 * z <= 1.06)
        & (y + 0.50 * z <= 1.04)
        & (x + y + 0.45 * z <= 1.43)
    )


def in_risk_budget(points: np.ndarray) -> np.ndarray:
    """Ellipsoidal proxy for a joint second-order risk budget."""
    center = np.array([0.49, 0.47, 0.43])
    radii = np.array([0.47, 0.40, 0.45])
    normalized = (points - center) / radii
    return np.sum(normalized**2, axis=1) <= 1.0


def sample_feasible_intersection(seed: int = 12) -> np.ndarray:
    """Sample the convex intersection and retain points for its hull."""
    rng = np.random.default_rng(seed)
    points = rng.uniform(0.02, 0.98, size=(90_000, 3))
    mask = linear_feasible(points) & in_risk_budget(points)
    feasible = points[mask]

    # Keep computation light while retaining a smooth convex-hull approximation.
    if len(feasible) > 3_500:
        feasible = feasible[rng.choice(len(feasible), 3_500, replace=False)]
    return feasible


def add_plane_z(ax, z_value: float, label: str) -> None:
    grid = np.linspace(0.03, 0.97, 5)
    x, y = np.meshgrid(grid, grid)
    z = np.full_like(x, z_value)
    ax.plot_surface(
        x,
        y,
        z,
        color=COLORS["blue_fill"],
        edgecolor=COLORS["blue"],
        linewidth=0.45,
        alpha=0.22,
        shade=False,
    )
    ax.text(0.94, 0.90, z_value + 0.015, label, color=COLORS["blue"], fontsize=12, weight="bold")


def add_plane_xz(ax, label: str) -> None:
    """Draw x + 0.55z = 1.06 as a translucent facet."""
    y, z = np.meshgrid(np.linspace(0.03, 0.97, 5), np.linspace(0.04, 0.97, 5))
    x = 1.06 - 0.55 * z
    ax.plot_surface(
        x,
        y,
        z,
        color=COLORS["blue_fill"],
        edgecolor=COLORS["blue"],
        linewidth=0.45,
        alpha=0.20,
        shade=False,
    )
    ax.text(0.73, 0.93, 0.62, label, color=COLORS["blue"], fontsize=12, weight="bold")


def add_plane_diagonal(ax, label: str) -> None:
    """Draw x + y + 0.45z = 1.43 as a translucent facet."""
    x, z = np.meshgrid(np.linspace(0.04, 0.96, 6), np.linspace(0.04, 0.96, 6))
    y = 1.43 - x - 0.45 * z
    y[(y < 0.03) | (y > 0.97)] = np.nan
    ax.plot_surface(
        x,
        y,
        z,
        color=COLORS["blue_fill"],
        edgecolor=COLORS["blue"],
        linewidth=0.45,
        alpha=0.20,
        shade=False,
    )
    ax.text(0.81, 0.28, 0.73, label, color=COLORS["blue"], fontsize=12, weight="bold")


def add_risk_ellipsoid(ax) -> None:
    center = np.array([0.49, 0.47, 0.43])
    radii = np.array([0.47, 0.40, 0.45])
    u = np.linspace(0, 2 * np.pi, 46)
    v = np.linspace(0, np.pi, 24)
    x = center[0] + radii[0] * np.outer(np.cos(u), np.sin(v))
    y = center[1] + radii[1] * np.outer(np.sin(u), np.sin(v))
    z = center[2] + radii[2] * np.outer(np.ones_like(u), np.cos(v))

    ax.plot_wireframe(
        x,
        y,
        z,
        rstride=6,
        cstride=6,
        color=COLORS["purple"],
        linewidth=0.75,
        alpha=0.32,
    )


def add_feasible_hull(ax, points: np.ndarray) -> None:
    hull = ConvexHull(points)
    triangles = points[hull.simplices]
    surface = Poly3DCollection(
        triangles,
        facecolor=COLORS["green_fill"],
        edgecolor="none",
        linewidth=0.0,
        alpha=0.37,
    )
    surface.set_zsort("average")
    ax.add_collection3d(surface)


def add_candidate(ax, xyz, color, marker, label, offset, size=95) -> None:
    x, y, z = xyz
    # Soft confidence halo.
    ax.scatter([x], [y], [z], s=size * 3.0, c=color, alpha=0.14, edgecolors="none", depthshade=False)
    ax.scatter(
        [x],
        [y],
        [z],
        s=size,
        c=color,
        marker=marker,
        edgecolors="white",
        linewidths=1.8,
        depthshade=False,
        zorder=20,
    )
    tx, ty, tz = np.array(xyz) + np.array(offset)
    text = ax.text(
        tx,
        ty,
        tz,
        label,
        color=color,
        fontsize=10.5,
        weight="bold",
        bbox=dict(boxstyle="round,pad=0.28", fc="white", ec=color, lw=1.2, alpha=0.94),
        zorder=30,
    )
    text.set_path_effects([pe.withStroke(linewidth=1.0, foreground="white")])


def draw_figure() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "axes.titleweight": "bold",
            "figure.facecolor": COLORS["cream"],
            "savefig.facecolor": COLORS["cream"],
        }
    )

    fig = plt.figure(figsize=(12.8, 8.5), dpi=140)
    ax = fig.add_subplot(111, projection="3d", computed_zorder=False)
    ax.set_proj_type("ortho")
    ax.view_init(elev=23, azim=-52)

    # Core geometry: planes, risk boundary, and their green intersection.
    add_plane_z(ax, 0.12, r"$h_1$")
    add_plane_xz(ax, r"$h_2$")
    add_plane_diagonal(ax, r"$h_3$")
    add_risk_ellipsoid(ax)
    feasible = sample_feasible_intersection()
    add_feasible_hull(ax, feasible)

    # Candidate action embeddings.
    add_candidate(
        ax,
        (0.42, 0.40, 0.40),
        COLORS["green"],
        "*",
        "Selected  $z^{(3)}$",
        (-0.18, -0.15, 0.18),
        size=170,
    )
    add_candidate(
        ax,
        (0.14, 0.84, 0.35),
        COLORS["orange"],
        "o",
        "Clarify  $z^{(2)}$",
        (-0.04, 0.00, 0.15),
        size=82,
    )
    add_candidate(
        ax,
        (0.84, 0.73, 0.58),
        COLORS["red"],
        "X",
        "Blocked  $z^{(1)}$",
        (-0.18, 0.04, 0.10),
        size=105,
    )

    # Labels and cartoon callouts.
    ax.text(
        0.46,
        0.28,
        0.18,
        r"Dynamic feasible region  $\mathcal{F}_t$",
        color="#247A39",
        fontsize=12,
        weight="bold",
        bbox=dict(boxstyle="round,pad=0.36", fc="#EAF7EC", ec=COLORS["green"], lw=1.4, alpha=0.96),
    )
    ax.text(
        0.15,
        0.73,
        0.76,
        r"Joint-risk budget  $\mathcal{K}_t$",
        color="#6946A5",
        fontsize=11,
        weight="bold",
        bbox=dict(boxstyle="round,pad=0.34", fc="#F0EAFB", ec=COLORS["purple"], lw=1.3, alpha=0.95),
    )

    # Cube, axes, and clean paper-style framing.
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_zlim(0, 1)
    ax.set_box_aspect((1.05, 1.0, 0.88))
    ax.set_xlabel(r"$z_1$  Goal alignment", labelpad=11, color=COLORS["ink"], fontsize=10)
    ax.set_ylabel(r"$z_2$  Authorization", labelpad=11, color=COLORS["ink"], fontsize=10)
    ax.set_zlabel(r"$z_3$  Effect safety", labelpad=8, color=COLORS["ink"], fontsize=10)
    ax.set_xticks([0, 0.5, 1.0])
    ax.set_yticks([0, 0.5, 1.0])
    ax.set_zticks([0, 0.5, 1.0])
    ax.tick_params(colors="#78909C", labelsize=8, pad=1)
    for axis in (ax.xaxis, ax.yaxis, ax.zaxis):
        axis.pane.set_facecolor((1, 1, 1, 0.0))
        axis.pane.set_edgecolor((0.52, 0.60, 0.63, 0.38))
        axis._axinfo["grid"]["color"] = (0.65, 0.72, 0.75, 0.18)
        axis._axinfo["grid"]["linewidth"] = 0.55

    title = fig.suptitle(
        "Dynamic Geometric Constraint Space",
        fontsize=22,
        weight="bold",
        color=COLORS["ink"],
        y=0.955,
    )
    title.set_path_effects([pe.withStroke(linewidth=3.5, foreground="white")])
    fig.text(
        0.5,
        0.91,
        "candidate actions â†’ vector points   Â·   semantic rules â†’ facets   Â·   joint risk â†’ curved budget",
        ha="center",
        va="center",
        fontsize=11.2,
        color="#607D8B",
    )

    legend_handles = [
        Line2D([0], [0], color=COLORS["blue"], lw=7, alpha=0.35, label="Linear semantic facets"),
        Line2D([0], [0], color=COLORS["purple"], lw=2.2, ls="--", label="Joint-risk boundary"),
        Line2D([0], [0], color=COLORS["green"], lw=8, alpha=0.55, label="Feasible intersection"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#5163C5", markersize=8, label="Candidate embedding"),
    ]
    legend = fig.legend(
        handles=legend_handles,
        loc="lower center",
        bbox_to_anchor=(0.5, 0.038),
        ncol=4,
        frameon=True,
        fancybox=True,
        framealpha=0.96,
        borderpad=0.8,
        fontsize=10,
    )
    legend.get_frame().set_facecolor("white")
    legend.get_frame().set_edgecolor("#C7D3D8")

    fig.text(
        0.08,
        0.82,
        "Trusted evidence â†‘\nexpands the region",
        ha="left",
        va="center",
        fontsize=10.5,
        weight="bold",
        color="#2F7F43",
        bbox=dict(boxstyle="round,pad=0.45", fc="#EAF7EC", ec=COLORS["green"], lw=1.2),
    )
    fig.text(
        0.80,
        0.20,
        "Risk / uncertainty â†‘\ncontracts the region",
        ha="left",
        va="center",
        fontsize=10.5,
        weight="bold",
        color="#6946A5",
        bbox=dict(boxstyle="round,pad=0.45", fc="#F2ECFB", ec=COLORS["purple"], lw=1.2),
    )

    plt.subplots_adjust(left=0.02, right=0.98, top=0.90, bottom=0.12)
    fig.savefig(
        PNG_PATH,
        dpi=170,
        bbox_inches="tight",
        pad_inches=0.22,
        pil_kwargs={"optimize": True},
    )
    fig.savefig(SVG_PATH, bbox_inches="tight", pad_inches=0.22)
    plt.close(fig)
    print(PNG_PATH)
    print(SVG_PATH)


if __name__ == "__main__":
    draw_figure()