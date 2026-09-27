#!/usr/bin/env python3
"""Generate the AgentDojo multi-LLM grouped bar chart."""

from __future__ import annotations

import csv
import shutil
import subprocess
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.offsetbox import (
    AnchoredOffsetbox,
    AnnotationBbox,
    DrawingArea,
    HPacker,
    OffsetImage,
    TextArea,
    VPacker,
)


HERE = Path(__file__).resolve().parent
DATA_PATH = HERE / "agentdojo_multillm_plot_data.csv"
OUTPUT_STEM = HERE / "fig_agentdojo_multillm"
ICON_PATHS = {
    "DeepSeek V4 Flash": HERE / "logos" / "deepseek.png",
    "GPT-5.4-mini": HERE / "logos" / "openai.png",
    "Claude Haiku 4.5": HERE / "logos" / "claude.png",
}

METHODS = [
    "No Defense",
    "Prompt",
    "PIGuard",
    "Progent",
    "DRIFT",
    "DAFR",
]
MODELS = ["DeepSeek V4 Flash", "GPT-5.4-mini", "Claude Haiku 4.5"]
MODEL_STYLE = {
    "DeepSeek V4 Flash": {
        "color": "#4D6BFE",
        "bottom_icon_zoom": 0.060,
        "legend_icon_zoom": 0.053,
    },
    "GPT-5.4-mini": {
        "color": "#111111",
        "bottom_icon_zoom": 0.068,
        "legend_icon_zoom": 0.059,
    },
    "Claude Haiku 4.5": {
        "color": "#D97757",
        "bottom_icon_zoom": 0.052,
        "legend_icon_zoom": 0.047,
    },
}
METRICS = [
    ("clean_utility", r"(a) Clean Utility ($\uparrow$)", (0, 100), [0, 25, 50, 75, 100]),
    ("attack_utility", r"(b) Attack Utility ($\uparrow$)", (0, 100), [0, 25, 50, 75, 100]),
    ("attack_success_rate", r"(c) Attack Success Rate ($\downarrow$)", (0, 20), [0, 5, 10, 15, 20]),
]


def crop_icon(image: np.ndarray) -> np.ndarray:
    """Remove transparent margins so brand marks align by visible bounds."""
    if image.ndim != 3 or image.shape[2] < 4:
        return image
    visible = np.argwhere(image[:, :, 3] > 0.01)
    if visible.size == 0:
        return image
    (y_min, x_min), (y_max, x_max) = visible.min(0), visible.max(0)
    return image[y_min : y_max + 1, x_min : x_max + 1]



def load_data() -> dict[tuple[str, str], dict[str, float | bool]]:
    records: dict[tuple[str, str], dict[str, float | bool]] = {}
    with DATA_PATH.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            records[(row["method"], row["model"])] = {
                "clean_utility": float(row["clean_utility"]),
                "attack_utility": float(row["attack_utility"]),
                "attack_success_rate": float(row["attack_success_rate"]),
                "is_placeholder": row["is_placeholder"] == "1",
            }
    return records


def save_outlined_pdf(fig: plt.Figure) -> None:
    """Export a vector PDF and convert all text to outlines."""
    raw_pdf = OUTPUT_STEM.with_name(f"{OUTPUT_STEM.name}_with_fonts.pdf")
    outlined_pdf = OUTPUT_STEM.with_name(f"{OUTPUT_STEM.name}_outlined.pdf")
    final_pdf = OUTPUT_STEM.with_suffix(".pdf")
    fig.savefig(raw_pdf)

    ghostscript = next(
        (
            executable
            for name in ("mgs.exe", "gswin64c.exe", "gswin32c.exe", "gs")
            if (executable := shutil.which(name)) is not None
        ),
        None,
    )
    if ghostscript is None:
        raise RuntimeError(
            "Ghostscript is required to convert figure text to vector outlines."
        )

    subprocess.run(
        [
            ghostscript,
            "-dSAFER",
            "-dBATCH",
            "-dNOPAUSE",
            "-sDEVICE=pdfwrite",
            "-dCompatibilityLevel=1.5",
            "-dNoOutputFonts",
            "-dDownsampleColorImages=false",
            "-dDownsampleGrayImages=false",
            "-dDownsampleMonoImages=false",
            f"-sOutputFile={outlined_pdf}",
            str(raw_pdf),
        ],
        check=True,
    )
    outlined_pdf.replace(final_pdf)
    raw_pdf.unlink()


def main() -> None:
    records = load_data()
    icons = {model: crop_icon(plt.imread(path)) for model, path in ICON_PATHS.items()}

    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
            "font.size": 9.0,
            "axes.titlesize": 10.0,
            "axes.labelsize": 9.0,
            "xtick.labelsize": 9.0,
            "ytick.labelsize": 9.0,
            "legend.fontsize": 9.0,
            "figure.dpi": 160,
            "savefig.dpi": 600,
            "savefig.bbox": "tight",
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )

    x = np.arange(len(METHODS))
    bar_width = 0.18
    offsets = [-0.27, 0.0, 0.27]
    fig, axes = plt.subplots(
        3,
        1,
        figsize=(7.0, 4.55),
        sharex=True,
        gridspec_kw={"hspace": 0.28},
    )

    for ax, (metric, title, ylim, ticks) in zip(axes, METRICS):
        dafr_x = len(METHODS) - 1
        ax.axvspan(dafr_x - 0.48, dafr_x + 0.48, color="#EEF1F4", zorder=0)
        ax.set_axisbelow(True)
        ax.grid(axis="y", color="#D9DDE2", linewidth=0.55, alpha=0.85)

        for model, offset in zip(MODELS, offsets):
            style = MODEL_STYLE[model]
            values = [float(records[(method, model)][metric]) for method in METHODS]
            bars = ax.bar(
                x + offset,
                values,
                width=bar_width,
                color=str(style["color"]),
                edgecolor=str(style["color"]),
                linewidth=0.5,
                zorder=3,
            )

            for method_index, (bar, value) in enumerate(zip(bars, values)):
                is_ours = METHODS[method_index] == "DAFR"
                ax.annotate(
                    f"{value:.1f}",
                    (bar.get_x() + bar.get_width() / 2, value),
                    xytext=(0, 2.2),
                    textcoords="offset points",
                    ha="center",
                    va="bottom",
                    fontsize=9.0,
                    color="#202124",
                    fontweight="bold" if is_ours else "normal",
                    clip_on=False,
                    zorder=6,
                )

            zero_indices = [index for index, value in enumerate(values) if value == 0]
            if zero_indices:
                zero_x = [x[index] + offset for index in zero_indices]
                ax.scatter(
                    zero_x,
                    np.zeros(len(zero_indices)),
                    s=60,
                    marker="_",
                    color=str(style["color"]),
                    linewidths=1.5,
                    zorder=5,
                    clip_on=False,
                )

        ax.set_title(title, loc="left", pad=5, fontweight="bold")
        ax.set_ylim(*ylim)
        ax.set_yticks(ticks)
        ax.set_ylabel("Score (%)")
        ax.tick_params(axis="y", length=2.5, color="#80868B")
        ax.tick_params(axis="x", length=0)
        ax.spines["left"].set_color("#B8BDC4")
        ax.spines["bottom"].set_color("#B8BDC4")

    axes[-1].set_xticks(x)
    axes[-1].set_xticklabels(METHODS)
    axes[-1].tick_params(axis="x", pad=23)

    for model, offset in zip(MODELS, offsets):
        for method_x in x:
            icon = AnnotationBbox(
                OffsetImage(
                    icons[model],
                    zoom=float(MODEL_STYLE[model]["bottom_icon_zoom"]),
                ),
                (method_x + offset, -0.095),
                xycoords=axes[-1].get_xaxis_transform(),
                frameon=False,
                pad=0,
                box_alignment=(0.5, 0.5),
                zorder=5,
                annotation_clip=False,
            )
            axes[-1].add_artist(icon)

    for label in axes[-1].get_xticklabels():
        if label.get_text() == "DAFR":
            label.set_fontweight("bold")
            label.set_color("#202124")

    legend_items = [
        ("DeepSeek V4 Flash", "DeepSeek V4 Flash"),
        ("GPT-5.4-mini", "GPT-5.4-mini"),
        ("Claude Haiku 4.5", "Claude Haiku 4.5"),
    ]
    legend_boxes = []
    for model, label in legend_items:
        icon_box = VPacker(
            children=[
                DrawingArea(0, 2.0, 0, 0),
                OffsetImage(
                    icons[model],
                    zoom=float(MODEL_STYLE[model]["legend_icon_zoom"]),
                ),
            ],
            align="center",
            pad=0,
            sep=0,
        )
        text_box = TextArea(
            label,
            textprops={
                "fontsize": 9.0,
                "fontfamily": "serif",
                "verticalalignment": "center",
            },
        )
        legend_boxes.append(
            HPacker(children=[icon_box, text_box], align="center", pad=0, sep=3)
        )

    legend_row = HPacker(children=legend_boxes, align="center", pad=0, sep=14)
    legend = AnchoredOffsetbox(
        loc="upper right",
        child=legend_row,
        pad=0,
        frameon=False,
        bbox_to_anchor=(0.995, 0.995),
        bbox_transform=fig.transFigure,
        borderpad=0,
    )
    fig.add_artist(legend)

    fig.subplots_adjust(left=0.09, right=0.995, top=0.90, bottom=0.13)

    save_outlined_pdf(fig)
    fig.savefig(OUTPUT_STEM.with_suffix(".png"), dpi=600)
    plt.close(fig)


if __name__ == "__main__":
    main()
