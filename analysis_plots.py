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


def _plot_metric(results_all: Dict[str, Any], metric: str, title: str, ylabel: str, out_path: Path) -> None:
    plt.figure(figsize=(7, 4))
    for name, res in results_all.items():
        plt.plot(res["year"], res[metric], marker="o", label=name)
    plt.title(title)
    plt.xlabel("Year")
    plt.ylabel(ylabel)
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.legend(loc="upper left", bbox_to_anchor=(1.02, 1))
    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()


def _plot_import_share(results_all: Dict[str, Any], chip_type: str, out_path: Path) -> None:
    plt.figure(figsize=(7, 4))
    for name, res in results_all.items():
        shares = [row.get(chip_type, 0.0) for row in res["us_import_cn_share"]]
        plt.plot(res["year"], shares, marker="o", label=name)
    plt.title(f"US import share from CN ({chip_type})")
    plt.xlabel("Year")
    plt.ylabel("Share of US consumption")
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.legend(loc="upper left", bbox_to_anchor=(1.02, 1))
    plt.tight_layout()
    plt.savefig(out_path)
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
