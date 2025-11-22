"""
Plotting helpers for scenario comparisons. Generates PNG files for key metrics.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Any

import matplotlib

# Use non-GUI backend to work in headless environments
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

import config

COLORS = ["#1f77b4", "#d62728", "#2ca02c", "#ff7f0e", "#9467bd", "#8c564b"]
LINESTYLES = ["-", "--", "-.", ":", (0, (3, 1, 1, 1)), (0, (5, 2))]
MARKERS = ["o", "s", "^", "D", "P", "X"]

# Custom style mapping for known scenarios to ensure consistency and visibility
STYLE_MAP = {
    "baseline": {"color": "#444444", "ls": "--", "marker": "o", "lw": 2.0, "zorder": 10},
    "tariff_only": {"color": "#e41a1c", "ls": "-", "marker": "s", "lw": 2.0, "zorder": 5},
    "subsidy_only": {"color": "#377eb8", "ls": "-", "marker": "^", "lw": 2.0, "zorder": 5},
    "tariff_plus_subsidy": {"color": "#984ea3", "ls": "-.", "marker": "D", "lw": 2.5, "zorder": 6},
    "diff_by_chip": {"color": "#4daf4a", "ls": ":", "marker": "X", "lw": 2.5, "zorder": 6},
}

def _get_style(name: str, idx: int) -> Dict[str, Any]:
    if name in STYLE_MAP:
        return STYLE_MAP[name]
    # Fallback for unknown scenarios
    return {
        "color": COLORS[idx % len(COLORS)],
        "ls": LINESTYLES[idx % len(LINESTYLES)],
        "marker": MARKERS[idx % len(MARKERS)],
        "lw": 2.0,
        "zorder": 3
    }

def _plot_metric(results_all: Dict[str, Any], metric: str, title: str, ylabel: str, out_path: Path) -> None:
    plt.figure(figsize=(10, 6))  # Increased figure size
    
    # Set a nice style manually
    plt.rcParams['axes.grid'] = True
    plt.rcParams['grid.alpha'] = 0.3
    plt.rcParams['grid.linestyle'] = '--'
    
    for idx, (name, res) in enumerate(results_all.items()):
        style = _get_style(name, idx)
        plt.plot(
            res["year"],
            res[metric],
            marker=style["marker"],
            linewidth=style["lw"],
            markersize=6,
            linestyle=style["ls"],
            color=style["color"],
            label=name,
            alpha=0.85, # Slight transparency
            zorder=style["zorder"]
        )
    
    plt.title(title, fontsize=14, pad=15)
    plt.xlabel("Year", fontsize=12)
    plt.ylabel(ylabel, fontsize=12)
    
    # Improve legend: place at bottom
    plt.legend(loc="upper center", bbox_to_anchor=(0.5, -0.15), ncol=3, frameon=False, fontsize=10)
    
    plt.tight_layout()
    plt.savefig(out_path, dpi=300) # Higher DPI
    plt.close()


def _plot_import_share(results_all: Dict[str, Any], chip_type: str, out_path: Path) -> None:
    plt.figure(figsize=(10, 6))
    
    plt.rcParams['axes.grid'] = True
    plt.rcParams['grid.alpha'] = 0.3
    plt.rcParams['grid.linestyle'] = '--'

    for idx, (name, res) in enumerate(results_all.items()):
        shares = [row.get(chip_type, 0.0) for row in res["us_import_cn_share"]]
        style = _get_style(name, idx)
        plt.plot(
            res["year"],
            shares,
            marker=style["marker"],
            linewidth=style["lw"],
            markersize=6,
            linestyle=style["ls"],
            color=style["color"],
            label=name,
            alpha=0.85,
            zorder=style["zorder"]
        )
    
    plt.title(f"US import share from CN ({chip_type})", fontsize=14, pad=15)
    plt.xlabel("Year", fontsize=12)
    plt.ylabel("Share of US consumption", fontsize=12)
    
    plt.legend(loc="upper center", bbox_to_anchor=(0.5, -0.15), ncol=3, frameon=False, fontsize=10)
    
    plt.tight_layout()
    plt.savefig(out_path, dpi=300)
    plt.close()


def save_all_plots(results_all: Dict[str, Any], out_dir: Path) -> None:
    """
    Save line charts for NSI, Welfare, Gap_H, and US import dependency by chip type.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    _plot_metric(results_all, "NSI", "National Security Index", "Index", out_dir / "nsi.png")
    _plot_metric(results_all, "Welfare", "Welfare", "Value", out_dir / "welfare.png")
    _plot_metric(results_all, "gap_H", "Technology Gap (ln T_US/T_CN, High-end)", "Gap_H", out_dir / "gap_H.png")

    for s in config.CHIP_TYPES:
        _plot_import_share(results_all, s, out_dir / f"us_import_share_CN_{s}.png")


__all__ = ["save_all_plots"]
